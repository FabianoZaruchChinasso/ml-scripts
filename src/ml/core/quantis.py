"""Régua quantílica para latência e jitter: faixa p50–p90 em escala log, por prédio.

Latência e jitter têm caudas longas (p99 de 350 ms e 205 ms) e variam muito na mesma
posição: um número só engana. O modelo prevê a faixa, e a régua mede pinball loss e
cobertura (a fração de valores reais abaixo de cada quantil previsto).
"""

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor

from ml.core.avaliacao import (VERSAO_REGUA, _atende_em, _br, _intervalo, _juntar, _resumo_atende,
                               assert_sem_vazamento, reamostras)
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds

QUANTIS = (0.5, 0.9)
ALVOS_QUANTILICOS = ('latency_ms', 'jitter_ms')
# Faixa aceita para a cobertura pooled do p90 num prédio novo.
FAIXA_COBERTURA = (0.80, 0.95)

_COLUNAS = ['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos']


def coluna(q: float) -> str:
  """Nome da coluna de um quantil nas previsões: 0,5 -> 'q50', 0,9 -> 'q90'."""
  return f'q{int(round(q * 100))}'


def modelo_quantil(q: float) -> HistGradientBoostingRegressor:
  """Gradient boosting com perda quantílica; aceita NaN sem imputer."""
  return HistGradientBoostingRegressor(loss='quantile', quantile=q, learning_rate=0.05, max_iter=300,
                                       min_samples_leaf=20, random_state=42)


def _perda(y, previsto, q: float) -> np.ndarray:
  erro = np.asarray(y, dtype=float) - np.asarray(previsto, dtype=float)
  return np.maximum(q * erro, (q - 1) * erro)


def pinball(y, previsto, q: float) -> float:
  """Perda quantílica média: penaliza q vezes o que ficou abaixo e (1 - q) o que ficou acima."""
  return float(np.mean(_perda(y, previsto, q)))


def cobertura(y, previsto) -> float:
  """Fração dos valores reais menores ou iguais ao quantil previsto (o ideal é o próprio quantil)."""
  return float(np.mean(np.asarray(y, dtype=float) <= np.asarray(previsto, dtype=float)))


def prever_quantis_fora_do_fold(df: pd.DataFrame, colunas, y_col: str, vazadas,
                                estimadores: dict = None) -> pd.DataFrame:
  """p50 e p90 de cada linha pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  Treina em log1p(y) e volta com expm1, cortado em 0. Se o p90 sair abaixo do p50
  (quantis cruzados), o p90 passa a valer o p50 e a linha fica com `cruzado` verdadeiro.
  `estimadores` ({quantil: estimador}) troca os modelos; são clonados a cada fold.
  Devolve _linha, y (em ms), q50, q90, cruzado, _site, _pos, indexados como `df`.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return pd.DataFrame(columns=_COLUNAS)
  sub = df[df[y_col].notna()]
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  y_log = np.log1p(y.clip(lower=0))
  linha = sub['_linha'] if '_linha' in sub.columns else pd.Series(sub.index.astype(str), index=sub.index)
  posicao = sub['_pos'] if '_pos' in sub.columns else sub['_site']
  partes = []
  for fold in outer_logo_folds(X, y_log, sub['_site']):
    previstos = {}
    for q in QUANTIS:
      base = (estimadores or {}).get(q)
      modelo = clone(base) if base is not None else modelo_quantil(q)
      modelo.fit(fold.X_train, fold.y_train)
      previstos[q] = np.clip(np.expm1(np.asarray(modelo.predict(fold.X_test), dtype=float)), 0, None)
    cruzado = previstos[0.9] < previstos[0.5]
    previstos[0.9] = np.maximum(previstos[0.9], previstos[0.5])
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': linha.loc[indice].to_numpy(), 'y': y.loc[indice].to_numpy(),
                                'q50': previstos[0.5], 'q90': previstos[0.9], 'cruzado': cruzado,
                                '_site': fold.test_site, '_pos': posicao.loc[indice].to_numpy()},
                               index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS)
  return pd.concat(partes)


def _metricas(prev: pd.DataFrame) -> dict:
  return {'pinball': {coluna(q): round(pinball(prev['y'], prev[coluna(q)], q), 4) for q in QUANTIS},
          'cobertura': {coluna(q): round(cobertura(prev['y'], prev[coluna(q)]), 4) for q in QUANTIS}}


def resumir_quantis(prev: pd.DataFrame, n: int, amostras=None) -> dict:
  """Pinball e cobertura de cada quantil, pooled e por prédio, com intervalo de 90% pooled.

  `mediana_mae` é o MAE em ms do p50, para comparar com a regressão pontual.
  `cruzados` conta as linhas em que o p90 foi corrigido para o p50.
  """
  resumo = {'n': n, 'versao_regua': VERSAO_REGUA}
  if prev.empty:
    return dict(resumo, pinball={}, cobertura={}, por_local={}, intervalos={}, cruzados=0, mediana_mae=None)
  resumo.update(_metricas(prev))
  resumo['por_local'] = {s: _metricas(g) for s, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0])}
  resumo['cruzados'] = int(prev['cruzado'].astype(bool).sum())
  y = prev['y'].to_numpy(dtype=float)
  resumo['mediana_mae'] = round(float(np.mean(np.abs(y - prev['q50'].to_numpy(dtype=float)))), 4)
  resumo['intervalos'] = {}
  if len(prev) > 1:
    amostras = reamostras(prev['_pos'], prev['_site']) if amostras is None else amostras
    for q in QUANTIS:
      c = coluna(q)
      p = prev[c].to_numpy(dtype=float)
      resumo['intervalos'][f'pinball_{c}'] = _intervalo([pinball(y[i], p[i], q) for i in amostras])
      resumo['intervalos'][f'cobertura_{c}'] = _intervalo([cobertura(y[i], p[i]) for i in amostras])
  return resumo


def delta_pinball(nova: pd.DataFrame, base: pd.DataFrame, q: float = 0.9, amostras=None) -> dict:
  """Pinball do quantil `q` da nova versão menos o da base, nas mesmas linhas e reamostragens."""
  c = coluna(q)
  j = nova.set_index('_linha')[['y', c, '_site', '_pos']].join(
    base.set_index('_linha')[[c]].rename(columns={c: 'base'}), how='inner')
  if j.empty:
    raise ValueError('as duas versões não têm previsões em comum para comparar')
  y = j['y'].to_numpy(dtype=float)
  perda_nova, perda_base = _perda(y, j[c], q), _perda(y, j['base'], q)
  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(float(perda_nova.mean() - perda_base.mean()), 4),
          'intervalo': _intervalo([perda_nova[i].mean() - perda_base[i].mean() for i in amostras]),
          'pinball_base': round(float(perda_base.mean()), 4), 'n': int(len(j))}


def veredito_quantis(delta: dict, cobertura_nova: float) -> dict:
  """Melhor / empate / pior para latência e jitter (nova − base, intervalo de 90%).

  Pior: a cobertura pooled do p90 da nova versão sai de FAIXA_COBERTURA, ou o
  intervalo de Δ pinball fica todo acima de 0. Melhor: o intervalo fica todo abaixo
  de 0 com a cobertura na faixa. Empate: o resto.
  """
  lo_c, hi_c = FAIXA_COBERTURA
  lo, hi = delta['intervalo']
  faixa = f'{_br(lo, 2)} a {_br(hi, 2)}'
  if not lo_c <= cobertura_nova <= hi_c:
    return {'resultado': 'pior', 'motivo': f'A cobertura do p90 é {_br(cobertura_nova, 2)}, fora da faixa de '
                                           f'{_br(lo_c, 2)} a {_br(hi_c, 2)}: a faixa prevista não é confiável.'}
  if lo > 0:
    return {'resultado': 'pior', 'motivo': f'O pinball do p90 subiu {_br(delta["valor"], 2)} (90%: {faixa}).'}
  if hi < 0:
    return {'resultado': 'melhor', 'motivo': f'O pinball do p90 caiu {_br(-delta["valor"], 2)} (90%: {faixa}), '
                                             'com a cobertura na faixa.'}
  return {'resultado': 'empate', 'motivo': 'O intervalo da diferença de pinball inclui 0: com estes locais, '
                                           'não dá para separar as duas versões.'}


def atende_completo(prev_dn: pd.DataFrame, prev_up: pd.DataFrame, quant_lat: pd.DataFrame,
                    quant_jit: pd.DataFrame, aplicacoes: dict, amostras=None) -> dict:
  """Acurácia balanceada de "atende" com os quatro limiares, por aplicação.

  Real: download >= dn, upload >= up, latência <= lat e jitter <= jit. Previsto:
  download e upload pontuais, e o p90 de latência e de jitter. Só nas linhas
  presentes nos quatro alvos.
  """
  j = _juntar(dn=prev_dn, up=prev_up,
              lat=quant_lat.rename(columns={'q90': 'yhat'}), jit=quant_jit.rename(columns={'q90': 'yhat'}))
  if j.empty:
    raise ValueError('nenhuma linha comum aos quatro alvos para medir "atende completo"')
  classes = {}
  for nome, lim in aplicacoes.items():
    real = (_atende_em(j, lim, 'y_dn', 'y_up') & (j['y_lat'] <= lim['lat']).to_numpy()
            & (j['y_jit'] <= lim['jit']).to_numpy())
    previsto = (_atende_em(j, lim, 'p_dn', 'p_up') & (j['p_lat'] <= lim['lat']).to_numpy()
                & (j['p_jit'] <= lim['jit']).to_numpy())
    classes[nome] = (real, previsto)
  return _resumo_atende(j, classes, amostras)

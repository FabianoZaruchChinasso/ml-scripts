"""Régua única do modelo: LOGO por prédio, métricas, intervalos e veredito de promoção.

O QoE Studio, regression_mlflow.py e regression_benchmark.py medem por aqui, para
que uma versão tenha um número só, venha de onde vier.
"""

from statistics import mean

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline

from ml.core.features import matriz
from ml.core.sites import teto_wan
from ml.core.splits import outer_logo_folds

# Muda quando a régua muda: avaliações guardadas com outra versão ficam "desatualizadas".
VERSAO_REGUA = '2026-10-05.2'
ARVORES = 200
ALVOS_COM_TETO = ('speedtest_down_mbps', 'speedtest_up_mbps')
_COLUNAS_PREVISAO = ['_linha', 'y', 'yhat', '_site', '_pos']
N_BOOTSTRAP = 1000
SEMENTE = 42
# Intervalo de 90%.
PERCENTIS = (5, 95)
# Piora tolerada na métrica que não melhorou: 0,02 de acurácia balanceada e 2% do MAE da base.
RUIDO_ATENDE = 0.02
RUIDO_MAE_REL = 0.02


def modelo_regua(arvores: int = None) -> Pipeline:
  """O modelo que compara versões: fixo, para que a diferença venha das features."""
  return Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('reg', RandomForestRegressor(n_estimators=arvores or ARVORES, min_samples_leaf=2,
                                  n_jobs=-1, random_state=42)),
  ])


_modelo = modelo_regua  # nome antigo, usado pelo Studio


def assert_sem_vazamento(colunas, vazadas) -> None:
  proibidas = sorted(set(colunas) & set(vazadas))
  if proibidas:
    raise AssertionError(f'colunas com vazamento chegaram a um ajuste: {proibidas}')


def prever_fora_do_fold(df: pd.DataFrame, colunas, y_col: str, vazadas, arvores: int = None,
                        min_teste: int = 1, min_treino: int = 1, estimador=None,
                        ao_ajustar=None) -> pd.DataFrame:
  """Previsão de cada linha pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  Para download e upload, linhas `_limitado_wan` saem do treino e a previsão é
  cortada no teto de WAN do prédio de teste. `estimador` troca o modelo da régua
  (é clonado a cada fold); `ao_ajustar(fold, modelo)` é chamado depois de cada ajuste.
  Devolve colunas _linha, y, yhat, _site, _pos, indexadas como `df`.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return pd.DataFrame(columns=_COLUNAS_PREVISAO)
  sub = df[df[y_col].notna()]
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  com_teto = y_col in ALVOS_COM_TETO
  limitado = pd.Series(False, index=sub.index)
  if com_teto and '_limitado_wan' in sub.columns:
    limitado = sub['_limitado_wan'].astype(bool)
  linha = sub['_linha'] if '_linha' in sub.columns else pd.Series(sub.index.astype(str), index=sub.index)
  posicao = sub['_pos'] if '_pos' in sub.columns else sub['_site']
  partes = []
  for fold in outer_logo_folds(X, y, sub['_site']):
    treino = ~limitado.loc[fold.X_train.index].to_numpy()
    if len(fold.y_test) < min_teste or int(treino.sum()) < min_treino:
      continue
    modelo = clone(estimador) if estimador is not None else modelo_regua(arvores)
    modelo.fit(fold.X_train[treino], fold.y_train[treino])
    previsto = np.asarray(modelo.predict(fold.X_test), dtype=float)
    teto = teto_wan(fold.test_site, y_col) if com_teto else None
    if teto is not None:
      previsto = np.minimum(previsto, teto)
    if ao_ajustar is not None:
      ao_ajustar(fold, modelo)
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': linha.loc[indice].to_numpy(), 'y': fold.y_test.to_numpy(),
                                'yhat': previsto, '_site': fold.test_site,
                                '_pos': posicao.loc[indice].to_numpy()}, index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS_PREVISAO)
  return pd.concat(partes)


def mae_log(y, yhat) -> float:
  """Média de |log1p(y) - log1p(ŷ)|: erro relativo, para os prédios rápidos não dominarem.

  Previsão negativa é cortada em 0 (throughput e tempo não são negativos).
  """
  y = np.asarray(y, dtype=float)
  yhat = np.clip(np.asarray(yhat, dtype=float), 0, None)
  return float(np.mean(np.abs(np.log1p(y) - np.log1p(yhat))))


def reamostras(pos, site, n: int = None, semente: int = SEMENTE) -> list:
  """Índices posicionais de cada reamostragem bootstrap.

  Sorteia com reposição as posições de medição de cada prédio, levando todas as
  linhas de cada posição sorteada: linhas da mesma posição não são independentes.
  Estratificado por prédio, então todo prédio aparece em toda reamostragem.
  """
  n = N_BOOTSTRAP if n is None else n
  rng = np.random.default_rng(semente)
  blocos = {}
  for i, (s, p) in enumerate(zip(np.asarray(site), np.asarray(pos))):
    blocos.setdefault(str(s), {}).setdefault(str(p), []).append(i)
  por_site = [[np.array(blocos[s][p]) for p in sorted(blocos[s])] for s in sorted(blocos)]
  saida = []
  for _ in range(n):
    partes = []
    for posicoes in por_site:
      partes.extend(posicoes[i] for i in rng.integers(0, len(posicoes), size=len(posicoes)))
    saida.append(np.concatenate(partes))
  return saida


def _r2(y: np.ndarray, p: np.ndarray) -> float:
  soma = float(np.sum((y - y.mean()) ** 2))
  return float('nan') if soma == 0 else 1 - float(np.sum((y - p) ** 2)) / soma


def _intervalo(valores):
  """Percentis PERCENTIS dos valores que não são NaN; None se não sobra nenhum."""
  v = np.asarray(valores, dtype=float)
  v = v[~np.isnan(v)]
  if not len(v):
    return None
  lo, hi = np.percentile(v, PERCENTIS)
  return [round(float(lo), 4), round(float(hi), 4)]


def intervalos(prev: pd.DataFrame, amostras=None) -> dict:
  """Intervalo de 90% de R² pooled, MAE e MAE log sobre as previsões fora do fold (não retreina)."""
  if len(prev) < 2:
    return {}
  amostras = reamostras(prev['_pos'], prev['_site']) if amostras is None else amostras
  y, p = prev['y'].to_numpy(dtype=float), prev['yhat'].to_numpy(dtype=float)
  r2s, maes, logs = [], [], []
  for idx in amostras:
    yy, pp = y[idx], p[idx]
    r2s.append(_r2(yy, pp))
    maes.append(float(np.mean(np.abs(yy - pp))))
    logs.append(mae_log(yy, pp))
  return {'pooled': _intervalo(r2s), 'mae': _intervalo(maes), 'mae_log': _intervalo(logs)}


def _tupla(prev: pd.DataFrame):
  """Previsões no formato antigo do Studio: (R² por local, y real, y previsto, MAE por local)."""
  if prev.empty:
    return {}, [], [], {}
  grupos = prev.groupby('_site', sort=False)
  por_local = {s: float(r2_score(g['y'], g['yhat'])) for s, g in grupos}
  mae_local = {s: float(mean_absolute_error(g['y'], g['yhat'])) for s, g in grupos}
  return por_local, prev['y'].astype(float).tolist(), prev['yhat'].astype(float).tolist(), mae_local


def _logo(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1):
  """LOGO por local de coleta. Devolve (R² por local, y real, y previsto, MAE por local)."""
  return _tupla(prever_fora_do_fold(df, colunas, y_col, vazadas, arvores, min_teste, min_treino))


def r2_por_local(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1) -> dict:
  return _logo(df, colunas, y_col, vazadas, arvores, min_teste, min_treino)[0]


def _resumo(logo, n: int) -> dict:
  """Média por local, mais R² e MAE sobre todas as previsões fora do fold.

  Com poucos locais a média dos R² por fold é dominada pelo local de menor
  variância do alvo; o R² pooled e o MAE não têm esse problema.
  """
  por_local, reais, previstos, mae_local = logo
  return {'n': n, 'media': round(mean(por_local.values()), 4) if por_local else None,
          'pooled': round(float(r2_score(reais, previstos)), 4) if len(reais) > 1 else None,
          'mae': round(float(mean_absolute_error(reais, previstos)), 4) if reais else None,
          'por_local': {s: round(v, 4) for s, v in sorted(por_local.items())},
          'mae_por_local': {s: round(v, 4) for s, v in sorted(mae_local.items())}}


def resumir(prev: pd.DataFrame, n: int) -> dict:
  """Resumo da régua: o do Studio mais MAE log e a versão da régua."""
  resumo = _resumo(_tupla(prev), n)
  vazio = prev.empty
  resumo['mae_log'] = None if vazio else round(mae_log(prev['y'], prev['yhat']), 4)
  resumo['mae_log_por_local'] = {} if vazio else {
    s: round(mae_log(g['y'], g['yhat']), 4) for s, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0])}
  resumo['intervalos'] = intervalos(prev)
  resumo['versao_regua'] = VERSAO_REGUA
  return resumo


def avaliar(conj, features, vazadas, com_previsoes: bool = False):
  """LOGO por local de coleta de uma lista de features, como está.

  Feature ausente do conjunto sai da conta e é listada; feature com vazamento
  levanta (assert_sem_vazamento), nunca é descartada em silêncio. Com
  `com_previsoes`, devolve (resumo, previsões fora do fold).
  """
  presentes = [f for f in features if f in conj.df.columns]
  prev = prever_fora_do_fold(conj.df, presentes, conj.alvo, vazadas)
  resumo = resumir(prev, len(presentes))
  resumo['ausentes'] = [f for f in features if f not in conj.df.columns]
  return (resumo, prev) if com_previsoes else resumo


def avaliar_versao(conj, features, vazadas, com_previsoes: bool = False):
  """Como avaliar, mas uma versão salva que usa coluna hoje marcada como vazamento é
  avaliada sem ela, e a lista sai em `removidas_por_vazamento`. Assim a comparação
  continua de pé quando alguém confirma um vazamento depois de a versão existir."""
  removidas = [f for f in features if f in vazadas]
  saida = avaliar(conj, [f for f in features if f not in vazadas], vazadas, com_previsoes)
  resumo = saida[0] if com_previsoes else saida
  resumo['removidas_por_vazamento'] = removidas
  return saida


def _acuracia_balanceada(real, previsto) -> float:
  """Média de sensibilidade e especificidade; NaN se o real tem uma classe só."""
  real = np.asarray(real, dtype=bool)
  previsto = np.asarray(previsto, dtype=bool)
  if real.all() or not real.any():
    return float('nan')
  return float((np.mean(previsto[real]) + np.mean(~previsto[~real])) / 2)


def _media_sem_nan(valores) -> float:
  v = [x for x in valores if not np.isnan(x)]
  return float(mean(v)) if v else float('nan')


def _juntar(**previsoes) -> pd.DataFrame:
  """Junta previsões fora do fold por `_linha` (só as linhas presentes em todas).

  Cada argumento vira as colunas y_<nome> e p_<nome>; _site e _pos vêm do primeiro.
  """
  nomes = list(previsoes)
  j = previsoes[nomes[0]].set_index('_linha')[['_site', '_pos']]
  for nome in nomes:
    p = previsoes[nome].set_index('_linha')[['y', 'yhat']]
    j = j.join(p.rename(columns={'y': f'y_{nome}', 'yhat': f'p_{nome}'}), how='inner')
  return j


def _atende_em(j: pd.DataFrame, limiares: dict, y_dn: str, y_up: str) -> np.ndarray:
  return ((j[y_dn] >= limiares['dn']) & (j[y_up] >= limiares['up'])).to_numpy()


def _resumo_atende(j: pd.DataFrame, classes: dict, amostras=None) -> dict:
  """Acurácia balanceada por aplicação, média e intervalo de 90%.

  `classes`: nome da aplicação -> (real, previsto), vetores booleanos alinhados com `j`.
  Aplicação em que só uma classe aparece nos dados reais fica fora da média, com aviso.
  """
  pares, por_aplicacao, avisos = {}, {}, []
  for nome, (real, previsto) in classes.items():
    valor = _acuracia_balanceada(real, previsto)
    if np.isnan(valor):
      avisos.append(f'{nome}: só uma classe nos dados reais; fora da média')
      continue
    pares[nome] = (real, previsto)
    por_aplicacao[nome] = round(valor, 4)
  media = round(mean(por_aplicacao.values()), 4) if por_aplicacao else None
  intervalo = None
  if pares and len(j) > 1:
    amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
    intervalo = _intervalo([_media_sem_nan([_acuracia_balanceada(r[i], p[i]) for r, p in pares.values()])
                            for i in amostras])
  return {'por_aplicacao': por_aplicacao, 'media': media, 'intervalo': intervalo,
          'n': int(len(j)), 'avisos': avisos}


def atende(prev_down: pd.DataFrame, prev_up: pd.DataFrame, aplicacoes: dict, amostras=None) -> dict:
  """Acurácia balanceada de "atende em throughput" por aplicação, real contra previsto.

  Atende = download >= limiar dn e upload >= limiar up, nas linhas com os dois alvos.
  """
  j = _juntar(dn=prev_down, up=prev_up)
  classes = {nome: (_atende_em(j, limiares, 'y_dn', 'y_up'), _atende_em(j, limiares, 'p_dn', 'p_up'))
             for nome, limiares in aplicacoes.items()}
  return _resumo_atende(j, classes, amostras)


def delta_mae(nova: pd.DataFrame, base: pd.DataFrame, amostras=None) -> dict:
  """MAE da nova versão menos o da base, nas mesmas linhas e nas mesmas reamostragens."""
  j = _juntar(nova=nova, base=base)
  if j.empty:
    raise ValueError('as duas versões não têm previsões em comum para comparar')
  erro_nova = np.abs(j['y_nova'] - j['p_nova']).to_numpy(dtype=float)
  erro_base = np.abs(j['y_base'] - j['p_base']).to_numpy(dtype=float)
  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(float(erro_nova.mean() - erro_base.mean()), 4),
          'intervalo': _intervalo([erro_nova[i].mean() - erro_base[i].mean() for i in amostras]),
          'mae_base': round(float(erro_base.mean()), 4), 'n': int(len(j))}


def delta_atende(nova_dn, nova_up, base_dn, base_up, aplicacoes: dict, amostras=None):
  """Acurácia balanceada média de "atende" da nova menos a da base.

  None quando nenhuma aplicação tem as duas classes nos dados reais.
  """
  j = _juntar(ndn=nova_dn, nup=nova_up, bdn=base_dn, bup=base_up)
  trios = []
  for limiares in aplicacoes.values():
    real = _atende_em(j, limiares, 'y_ndn', 'y_nup')
    if real.all() or not real.any():
      continue
    trios.append((real, _atende_em(j, limiares, 'p_ndn', 'p_nup'), _atende_em(j, limiares, 'p_bdn', 'p_bup')))
  if not trios:
    return None

  def diferenca(idx):
    nova = _media_sem_nan([_acuracia_balanceada(r[idx], n[idx]) for r, n, _ in trios])
    base = _media_sem_nan([_acuracia_balanceada(r[idx], b[idx]) for r, _, b in trios])
    return nova - base

  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(diferenca(np.arange(len(j))), 4),
          'intervalo': _intervalo([diferenca(i) for i in amostras]), 'n': int(len(j))}


def _br(valor: float, casas: int) -> str:
  return f'{valor:.{casas}f}'.replace('.', ',')


def veredito_promocao(delta_mae: dict, delta_atende: dict = None) -> dict:
  """Melhor / empate / pior pela régua de promoção (nova − base, intervalo de 90%).

  Pior: o intervalo exclui 0 contra a nova em MAE ou em "atende". Melhor: exclui 0
  a favor numa delas e a outra não piora mais que o ruído. Empate: o resto.
  `delta_atende` é None em latência e jitter, que decidem só pelo MAE.
  """
  lo_m, hi_m = delta_mae['intervalo']
  faixa_m = f'{_br(lo_m, 1)} a {_br(hi_m, 1)}'
  if lo_m > 0:
    return {'resultado': 'pior', 'motivo': f'O MAE subiu {_br(delta_mae["valor"], 1)} (90%: {faixa_m}).'}
  if delta_atende is not None and delta_atende['intervalo'][1] < 0:
    lo_a, hi_a = delta_atende['intervalo']
    return {'resultado': 'pior', 'motivo': f'A acurácia de "atende" caiu {_br(-delta_atende["valor"], 3)} '
                                           f'(90%: {_br(lo_a, 3)} a {_br(hi_a, 3)}).'}
  mae_ok = delta_mae['valor'] <= RUIDO_MAE_REL * delta_mae['mae_base']
  atende_ok = delta_atende is None or delta_atende['valor'] >= -RUIDO_ATENDE
  if hi_m < 0 and atende_ok:
    return {'resultado': 'melhor', 'motivo': f'O MAE caiu {_br(-delta_mae["valor"], 1)} (90%: {faixa_m}) '
                                             'sem piorar "atende".'}
  if delta_atende is not None and delta_atende['intervalo'][0] > 0 and mae_ok:
    lo_a, hi_a = delta_atende['intervalo']
    return {'resultado': 'melhor', 'motivo': f'A acurácia de "atende" subiu {_br(delta_atende["valor"], 3)} '
                                             f'(90%: {_br(lo_a, 3)} a {_br(hi_a, 3)}) sem piorar o MAE.'}
  return {'resultado': 'empate', 'motivo': 'Os intervalos das diferenças incluem 0: com estes locais, '
                                           'não dá para separar as duas versões.'}

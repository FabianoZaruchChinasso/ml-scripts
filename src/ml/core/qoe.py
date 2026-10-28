"""QoE por aplicação: classificador direto de "atende", medido prédio a prédio.

O rótulo vem dos limiares do perfil (core/aplicacoes: 'atual' ou 'norma'), com os
quatro critérios. A régua de regressão (core/avaliacao) continua igual e é outro
caminho. Spec: docs/superpowers/specs/2026-10-27-qoe-norma-design.md.
"""

from statistics import mean

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from ml.core import aplicacoes as core_aplicacoes
from ml.core.avaliacao import (_acuracia_balanceada, _br, _intervalo, _media_sem_nan, assert_sem_vazamento,
                               reamostras)
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds

ALVOS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')
# Muda quando o modelo, a monotonia ou a medida mudam: avaliações com outra versão ficam desatualizadas.
VERSAO_QOE = '2026-10-27.1'
# Sentido físico, decidido antes de olhar os dados. Sinal, SNR e ruído ficam livres: o
# router_signal_dbm não é comparável entre roteadores (no villa lê uns 20 dB abaixo do celular).
MONOTONIA = {'router_tx_rate_mbps': 1, 'router_rx_rate_mbps': 1, 'router_expected_throughput_mbps': 1,
             'n_clients': -1, 'concorrentes_mesmo_radio': -1}
# Trava de alarme falso nos prédios em que tudo atende: a nova passa disto e piora mais que o ruído.
ALARME_MAXIMO = 0.05
ALARME_RUIDO = 0.02
# Queda num prédio que o põe na lista "piora em".
RUIDO_PREDIO = 0.02


def conjunto_qoe(conjs: dict) -> pd.DataFrame:
  """Linhas presentes nos quatro conjuntos (um por alvo), com os quatro alvos.

  `conjs`: {alvo: Conjunto}. Features e prédio vêm do conjunto do download; cada alvo,
  do seu conjunto, já com os descartes dele (teste falho, alvo vazio).
  """
  faltam = [a for a in ALVOS if a not in conjs]
  if faltam:
    raise ValueError(f'faltam conjuntos para {faltam}')
  base = conjs[ALVOS[0]].df
  comuns = set(base['_linha'])
  for alvo in ALVOS[1:]:
    comuns &= set(conjs[alvo].df['_linha'])
    if conjs[alvo].df['_linha'].duplicated().any():
      raise ValueError(f'_linha duplicada no conjunto de {alvo}')
  df = base[base['_linha'].isin(comuns)].copy()
  for alvo in ALVOS[1:]:
    df[alvo] = df['_linha'].map(conjs[alvo].df.set_index('_linha')[alvo]).to_numpy()
  if df.empty:
    raise ValueError('nenhuma linha comum aos quatro alvos para medir QoE')
  vazios = [a for a in ALVOS if df[a].isna().any()]
  if vazios:
    raise ValueError(f'alvo com valor vazio (NaN) nas linhas comuns: {vazios}')
  return df.reset_index(drop=True)


def rotulos(df: pd.DataFrame, aplicacoes: dict) -> dict:
  """{aplicação: vetor booleano}: download >= dn, upload >= up, latência <= lat e jitter <= jit."""
  return {nome: ((df['speedtest_down_mbps'] >= lim['dn']) & (df['speedtest_up_mbps'] >= lim['up'])
                 & (df['latency_ms'] <= lim['lat']) & (df['jitter_ms'] <= lim['jit'])).to_numpy()
          for nome, lim in aplicacoes.items()}


def restricoes(colunas) -> tuple:
  """Vetor de monotonia do XGBoost, na ordem das colunas da matriz (one-hot e desconhecidas: 0)."""
  return tuple(int(MONOTONIA.get(c, 0)) for c in colunas)


class Balanceado(BaseEstimator, ClassifierMixin):
  """Ajusta `estimador` com peso balanceado por classe (o XGBoost não tem class_weight)."""

  def __init__(self, estimador=None):
    self.estimador = estimador

  def fit(self, X, y):
    y = np.asarray(y, dtype=int)
    self.modelo_ = clone(self.estimador).fit(X, y, sample_weight=compute_sample_weight('balanced', y))
    self.classes_ = self.modelo_.classes_
    return self

  def predict(self, X):
    return self.modelo_.predict(X)

  def predict_proba(self, X):
    return self.modelo_.predict_proba(X)


def modelo_qoe(colunas) -> Balanceado:
  """O modelo do QoE: fixo, para que a diferença entre versões venha das features e do perfil."""
  return Balanceado(XGBClassifier(n_estimators=600, learning_rate=0.05, max_depth=3, subsample=0.8,
                                  colsample_bytree=0.8, min_child_weight=5, tree_method='hist',
                                  random_state=42, n_jobs=-1, monotone_constraints=restricoes(colunas)))


def modelo_referencia(colunas=None) -> Pipeline:
  """Random Forest de referência (e piso, só com `radio`): confere a escolha do XGBoost.

  `colunas` não é usado: existe só para casar com a assinatura da fábrica (`modelo_qoe`).
  """
  return Pipeline([('imputer', SimpleImputer(strategy='median')),
                   ('clf', RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight='balanced',
                                                  n_jobs=-1, random_state=42))])


def prever_fora_do_fold(df: pd.DataFrame, colunas, rot: dict, fabrica, vazadas=()):
  """Previsão de cada aplicação pelo modelo treinado sem o prédio da linha (LOGO por `_site`).

  `fabrica(colunas_da_matriz)` devolve um estimador novo. Fold cujo treino tem uma classe
  só prevê essa classe para o prédio de teste. Devolve ({aplicação: vetor booleano
  alinhado com `df`}, [(aplicação, prédio) desses folds]). `df` precisa de índice único.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not df.index.is_unique:
    raise ValueError('índice do df precisa ser único')
  X = matriz(df, colunas)
  previstos, uma_classe = {}, []
  for nome, y in rot.items():
    serie = pd.Series(np.asarray(y, dtype=int), index=df.index)
    p = np.zeros(len(df), dtype=bool)
    for fold in outer_logo_folds(X, serie, df['_site']):
      pos = df.index.get_indexer(fold.X_test.index)
      if fold.y_train.nunique() < 2:
        p[pos] = bool(fold.y_train.iloc[0])
        uma_classe.append((nome, fold.test_site))
        continue
      modelo = fabrica(list(X.columns)).fit(fold.X_train, fold.y_train)
      p[pos] = np.asarray(modelo.predict(fold.X_test)).astype(bool)
    previstos[nome] = p
  return previstos, uma_classe


def _erro_uma_classe(real: np.ndarray, previsto: np.ndarray) -> float:
  """Prédio de uma classe só: alarme falso (tudo atende) ou perda (nada atende)."""
  return float(np.mean(~previsto)) if real.all() else float(np.mean(previsto))


def _nota(rot: dict, prev: dict, sites: np.ndarray, idx: np.ndarray) -> float:
  """Média entre prédios da média das aplicações com as duas classes naquele prédio."""
  s = sites[idx]
  notas = []
  for site in sorted(set(s)):
    m = idx[s == site]
    notas.append(_media_sem_nan(_acuracia_balanceada(rot[a][m], prev[a][m]) for a in rot))
  return _media_sem_nan(notas)


def _arredondar(valor):
  return None if valor is None or np.isnan(valor) else round(float(valor), 4)


def resumir(df: pd.DataFrame, rot: dict, prev: dict, amostras=None) -> dict:
  """Nota por prédio (cada prédio pesa igual), erro nos prédios de uma classe, pooled e intervalo."""
  sites = df['_site'].astype(str).to_numpy()
  tudo = np.arange(len(df))
  amostras = reamostras(df['_pos'], df['_site']) if amostras is None else amostras
  por_predio = {}
  for site in sorted(set(sites)):
    m = tudo[sites == site]
    por_predio[site] = {}
    for a in rot:
      real, previsto = rot[a][m], prev[a][m]
      if real.all() or not real.any():
        por_predio[site][a] = {'classes': 1, 'atende': bool(real.all()),
                               'erro': round(_erro_uma_classe(real, previsto), 4)}
      else:
        por_predio[site][a] = {'classes': 2, 'acuracia': round(_acuracia_balanceada(real, previsto), 4)}
  na_nota = sorted(s for s, apps in por_predio.items() if any(v['classes'] == 2 for v in apps.values()))
  por_aplicacao = {a: _arredondar(_acuracia_balanceada(rot[a], prev[a])) for a in rot}
  pooled = [v for v in por_aplicacao.values() if v is not None]
  return {'nota': _arredondar(_nota(rot, prev, sites, tudo)),
          'intervalo': _intervalo([_nota(rot, prev, sites, i) for i in amostras]),
          'pooled': round(mean(pooled), 4) if pooled else None,
          'por_aplicacao': por_aplicacao, 'por_predio': por_predio,
          'predios_na_nota': na_nota, 'predios_fora_da_nota': sorted(set(por_predio) - set(na_nota)),
          'n': int(len(df)), 'n_predios': len(por_predio), 'n_posicoes': int(df['_pos'].nunique())}


def veredito(df: pd.DataFrame, rot: dict, nova: dict, base: dict, amostras=None) -> dict:
  """Melhor / empate / pior da nova contra a base, nas mesmas linhas e reamostras.

  Pior: intervalo da diferença de nota todo abaixo de 0, ou alarme falso da nova acima de
  ALARME_MAXIMO e ALARME_RUIDO acima do da base num prédio em que tudo atende. Melhor:
  intervalo todo acima de 0 sem a trava. Empate: o resto.
  """
  sites = df['_site'].astype(str).to_numpy()
  tudo = np.arange(len(df))
  amostras = reamostras(df['_pos'], df['_site']) if amostras is None else amostras
  delta = _nota(rot, nova, sites, tudo) - _nota(rot, base, sites, tudo)
  intervalo = _intervalo([_nota(rot, nova, sites, i) - _nota(rot, base, sites, i) for i in amostras])
  alarmes, contra = [], []
  for site in sorted(set(sites)):
    m = tudo[sites == site]
    diferencas = []
    for a in rot:
      real = rot[a][m]
      # A trava de alarme só olha prédios em que tudo atende; nos demais, a nota já pesa o erro.
      if real.all():
        e_nova, e_base = _erro_uma_classe(real, nova[a][m]), _erro_uma_classe(real, base[a][m])
        if e_nova > ALARME_MAXIMO and e_nova - e_base > ALARME_RUIDO:
          alarmes.append({'predio': site, 'aplicacao': a, 'nova': round(e_nova, 4), 'base': round(e_base, 4)})
      elif real.any():
        diferencas.append(_acuracia_balanceada(real, nova[a][m]) - _acuracia_balanceada(real, base[a][m]))
    if diferencas and mean(diferencas) < -RUIDO_PREDIO:
      contra.append(site)
  saida = {'delta': _arredondar(delta), 'intervalo': intervalo, 'alarmes': alarmes, 'predios_contra': contra}
  if intervalo is None:
    return dict(saida, resultado='empate', motivo='Sem prédios com as duas classes: não dá para comparar.')
  lo, hi = intervalo
  faixa = f'{_br(lo, 3)} a {_br(hi, 3)}'
  if hi < 0:
    return dict(saida, resultado='pior', motivo=f'A nota de QoE caiu {_br(-delta, 3)} (90%: {faixa}).')
  if alarmes:
    a = alarmes[0]
    return dict(saida, resultado='pior',
                motivo=f'Alarme falso em {a["predio"]} ({a["aplicacao"]}): {_br(a["nova"] * 100, 1)}% das linhas '
                       f'previstas como "não atende", contra {_br(a["base"] * 100, 1)}% da base.')
  if lo > 0:
    return dict(saida, resultado='melhor', motivo=f'A nota de QoE subiu {_br(delta, 3)} (90%: {faixa}).')
  return dict(saida, resultado='empate',
              motivo=f'O intervalo da diferença inclui 0 ({faixa}): com estes prédios, não dá para separar.')


MODELOS = {'modelo': modelo_qoe, 'referencia': modelo_referencia}


def avaliar(conjs: dict, features, vazadas, perfil: str, features_base=None) -> dict:
  """Avaliação de QoE de uma lista de features no perfil pedido; com `features_base`, o veredito contra ela.

  Features com vazamento ou ausentes do conjunto ficam fora da conta (listadas em `ausentes`
  quando não existem). O piso é o RF só com `radio`.
  """
  aplicacoes = core_aplicacoes.carregar_perfil(perfil)
  df = conjunto_qoe(conjs)
  fora = set(vazadas)

  def usaveis(lista):
    return [f for f in lista if f in df.columns and f not in fora]

  usadas = usaveis(features)
  if not usadas:
    raise ValueError('nenhuma feature utilizável para o QoE (todas ausentes ou com vazamento)')
  rot = rotulos(df, aplicacoes)
  amostras = reamostras(df['_pos'], df['_site'])
  prev, uma_classe = {}, {}
  for nome, fabrica in MODELOS.items():
    prev[nome], uma = prever_fora_do_fold(df, usadas, rot, fabrica)
    uma_classe[nome] = [list(par) for par in uma]
  colunas = list(matriz(df, usadas).columns)
  saida = {'perfil': perfil, 'versao_qoe': VERSAO_QOE, 'limiares': aplicacoes,
           'fontes': core_aplicacoes.fontes(perfil), 'features': usadas,
           'descartadas': [f for f in features if f in df.columns and f in fora],
           'ausentes': [f for f in features if f not in df.columns],
           'restricoes': {c: s for c, s in zip(colunas, restricoes(colunas)) if s}}
  for nome in MODELOS:
    saida[nome] = resumir(df, rot, prev[nome], amostras)
  saida['piso'] = None
  saida['supera_piso'] = None
  uma_classe['piso'] = []
  if 'radio' in df.columns:
    if usadas == ['radio']:
      prev_piso = prev['referencia']
      uma_classe['piso'] = uma_classe['referencia']
    else:
      prev_piso, uma = prever_fora_do_fold(df, ['radio'], rot, modelo_referencia)
      uma_classe['piso'] = [list(par) for par in uma]
    saida['piso'] = resumir(df, rot, prev_piso, amostras)
    nota, piso = saida['modelo']['nota'], saida['piso']['nota']
    # Compara estimativas pontuais, sem intervalo: leitura de apoio, não veredito.
    saida['supera_piso'] = None if nota is None or piso is None else bool(nota > piso)
  saida['folds_uma_classe'] = uma_classe
  saida['promocao_qoe'] = None
  if features_base is not None:
    usadas_base = usaveis(features_base)
    if not usadas_base:
      saida['promocao_qoe_motivo'] = 'nenhuma feature da base utilizável'
    else:
      prev_base = prev['modelo'] if usadas_base == usadas else prever_fora_do_fold(df, usadas_base, rot, modelo_qoe)[0]
      saida['promocao_qoe'] = dict(veredito(df, rot, prev['modelo'], prev_base, amostras),
                                   nota_base=resumir(df, rot, prev_base, amostras=[])['nota'])
  return saida

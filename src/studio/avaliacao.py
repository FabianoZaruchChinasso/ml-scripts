"""Avaliação do Studio: LOGO por prédio, MAE/RMSE/R² e "atende" por aplicação.

Própria do Studio, sem relação com a régua de ml/core/avaliacao.py. As regras de
descarte são parâmetros explícitos, e a contagem de linhas que cada uma tirou
volta para ser logada no run.
"""

import re
import unicodedata

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import balanced_accuracy_score, mean_absolute_error, mean_squared_error, r2_score

COLUNA_PREDIO = '_predio'
# Chave do limiar em config/aplicacoes.json e sentido do "atende" de cada alvo.
LIMIAR = {'speedtest_down_mbps': ('dn', 'min'), 'speedtest_up_mbps': ('up', 'min'),
          'latency_ms': ('lat', 'max'), 'jitter_ms': ('jit', 'max')}
REGRAS_PADRAO = {'descartar_alvo_zero': True, 'teto_wan': False}
# Fração do teto de WAN a partir da qual o speedtest pode estar medindo a internet.
FRACAO_TETO = 0.85


def slug(texto: str) -> str:
  """Nome de aplicação como pedaço de nome de métrica: 'Chamada de vídeo' -> 'chamada_de_video'."""
  base = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
  return re.sub(r'[^a-z0-9]+', '_', base.lower()).strip('_')


def aplicar_regras(df: pd.DataFrame, alvo: str, regras: dict, tetos: dict) -> tuple:
  """(df filtrado com índice refeito, {regra: linhas removidas}).

  `tetos` = {prédio: Mbps} para este alvo. Alvo vazio sai sempre.
  """
  removidas = {}
  y = pd.to_numeric(df[alvo], errors='coerce')
  vazio = y.isna()
  removidas['alvo_vazio'] = int(vazio.sum())
  df, y = df[~vazio], y[~vazio]
  if regras.get('descartar_alvo_zero'):
    zero = y == 0
    removidas['descartar_alvo_zero'] = int(zero.sum())
    df, y = df[~zero], y[~zero]
  if regras.get('teto_wan'):
    teto = df[COLUNA_PREDIO].map(tetos).astype(float)
    if 'router_expected_throughput_mbps' in df.columns:
      esperado = pd.to_numeric(df['router_expected_throughput_mbps'], errors='coerce')
    else:
      esperado = pd.Series(np.nan, index=df.index)
    no_teto = (teto.notna() & (y >= FRACAO_TETO * teto) & (esperado > teto)).fillna(False).astype(bool)
    removidas['teto_wan'] = int(no_teto.sum())
    df = df[~no_teto]
  return df.reset_index(drop=True), removidas


def fora_do_fold(modelo, X: pd.DataFrame, y: pd.Series, grupos: pd.Series) -> np.ndarray:
  """Previsão de cada linha pelo modelo treinado sem o prédio dela (LOGO)."""
  pred = np.full(len(y), np.nan)
  grupos = np.asarray(grupos)
  for predio in sorted(set(grupos)):
    teste = grupos == predio
    ajustado = clone(modelo).fit(X[~teste], y[~teste])
    pred[teste] = ajustado.predict(X[teste])
  return pred


def _regressao(y: np.ndarray, pred: np.ndarray) -> dict:
  return {'mae': float(mean_absolute_error(y, pred)),
          'rmse': float(np.sqrt(mean_squared_error(y, pred))),
          'r2': float(r2_score(y, pred)) if len(y) > 1 else float('nan')}


def atende(valores: np.ndarray, alvo: str, limiar: float) -> np.ndarray:
  _, sentido = LIMIAR[alvo]
  return valores >= limiar if sentido == 'min' else valores <= limiar


def metricas(y, pred, grupos, alvo: str, aplicacoes: dict) -> dict:
  y = np.asarray(y, dtype=float)
  pred = np.asarray(pred, dtype=float)
  grupos = np.asarray(grupos)
  saida = dict(_regressao(y, pred))
  for predio in sorted(set(grupos)):
    m = grupos == predio
    for nome, valor in _regressao(y[m], pred[m]).items():
      saida[f'{nome}__{predio}'] = valor
  chave, _ = LIMIAR[alvo]
  for app, limiares in aplicacoes.items():
    real, previsto = atende(y, alvo, limiares[chave]), atende(pred, alvo, limiares[chave])
    if len(set(real.tolist())) < 2:
      continue  # todas as amostras do mesmo lado do limiar: acurácia balanceada indefinida
    saida[f'atende_bacc__{slug(app)}'] = float(balanced_accuracy_score(real, previsto))
  saida['linhas'] = int(len(y))
  saida['predios'] = int(len(set(grupos)))
  return saida


def tabela_por_predio(y, pred, grupos) -> pd.DataFrame:
  y, pred, grupos = np.asarray(y, dtype=float), np.asarray(pred, dtype=float), np.asarray(grupos)
  linhas = []
  for predio in sorted(set(grupos)):
    m = grupos == predio
    linhas.append({'predio': predio, 'linhas': int(m.sum()), **_regressao(y[m], pred[m])})
  return pd.DataFrame(linhas)

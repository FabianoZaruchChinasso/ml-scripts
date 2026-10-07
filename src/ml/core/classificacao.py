"""Classificação direta de "atende" por aplicação, medida na régua única (LOGO por prédio).

Serve para responder se um classificador treinado para "atende" decide melhor que o
caminho da régua: regredir Mbps e comparar a previsão com o limiar da aplicação.
"""

import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone

from ml.core.avaliacao import (_acuracia_balanceada, _atende_em, _intervalo, _juntar, assert_sem_vazamento,
                               reamostras)
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds

_COLUNAS = ['_linha', 'y', 'yhat', '_site', '_pos']


def alvo_atende(conj_dn, conj_up, limiares: dict) -> pd.DataFrame:
  """O df do download, só nas linhas presentes nos dois conjuntos, com `_atende` (download >= dn e upload >= up)."""
  upload = conj_up.df.set_index('_linha')[conj_up.alvo]
  df = conj_dn.df[conj_dn.df['_linha'].isin(upload.index)].copy()
  df['_atende'] = ((df[conj_dn.alvo] >= limiares['dn']).to_numpy()
                   & (df['_linha'].map(upload) >= limiares['up']).to_numpy())
  return df.reset_index(drop=True)


def prever_classe_fora_do_fold(df: pd.DataFrame, colunas, vazadas, estimador, ajustar=None,
                               y_col: str = '_atende') -> pd.DataFrame:
  """Classe de cada linha pelo classificador treinado sem o prédio dela (LOGO por `_site`).

  `estimador` é clonado a cada fold; `ajustar(estimador, fold)` troca o ajuste (por exemplo,
  uma busca de hiperparâmetros) e devolve o modelo ajustado. Fold cujo treino tem uma classe
  só é pulado, com aviso. Devolve _linha, y, yhat (booleanos), _site, _pos.
  """
  assert_sem_vazamento(colunas, vazadas)
  X = matriz(df, colunas)
  y = df[y_col].astype(bool).astype(int)
  partes = []
  for fold in outer_logo_folds(X, y, df['_site']):
    if fold.y_train.nunique() < 2:
      warnings.warn(f'fold de {fold.test_site!r} pulado: o treino tem uma classe só', UserWarning, stacklevel=2)
      continue
    modelo = ajustar(estimador, fold) if ajustar is not None else clone(estimador).fit(fold.X_train, fold.y_train)
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': df.loc[indice, '_linha'].to_numpy(),
                                'y': fold.y_test.astype(bool).to_numpy(),
                                'yhat': np.asarray(modelo.predict(fold.X_test)).astype(bool),
                                '_site': fold.test_site, '_pos': df.loc[indice, '_pos'].to_numpy()},
                               index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS)
  return pd.concat(partes)


def referencia_regua(prev_dn: pd.DataFrame, prev_up: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """O "atende" da régua: previsões de regressão de download e upload comparadas com os limiares."""
  j = _juntar(dn=prev_dn, up=prev_up)
  return pd.DataFrame({'_linha': j.index.to_numpy(), 'y': _atende_em(j, limiares, 'y_dn', 'y_up'),
                       'yhat': _atende_em(j, limiares, 'p_dn', 'p_up'),
                       '_site': j['_site'].to_numpy(), '_pos': j['_pos'].to_numpy()})


def _arredondar(valor):
  return None if np.isnan(valor) else round(float(valor), 4)


def resumir_classe(prev: pd.DataFrame, amostras=None) -> dict:
  """Acurácia balanceada pooled e por prédio, com intervalo de 90% pelo bootstrap de posições."""
  if prev.empty:
    return {'pooled': None, 'por_local': {}, 'intervalo': None, 'n': 0}
  real, previsto = prev['y'].to_numpy(dtype=bool), prev['yhat'].to_numpy(dtype=bool)
  por_local = {}
  for site, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0]):
    valor = _acuracia_balanceada(g['y'].to_numpy(dtype=bool), g['yhat'].to_numpy(dtype=bool))
    if not np.isnan(valor):
      por_local[site] = round(valor, 4)
  intervalo = None
  if len(prev) > 1:
    amostras = reamostras(prev['_pos'], prev['_site']) if amostras is None else amostras
    intervalo = _intervalo([_acuracia_balanceada(real[i], previsto[i]) for i in amostras])
  return {'pooled': _arredondar(_acuracia_balanceada(real, previsto)), 'por_local': por_local,
          'intervalo': intervalo, 'n': int(len(prev))}

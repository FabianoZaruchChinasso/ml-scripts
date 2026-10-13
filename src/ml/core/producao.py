"""Contrato de entrada do modelo em produção: as colunas exatas que o modelo final viu.

O treino monta a matriz com features.matriz, que transforma categóricas em one-hot com as
categorias presentes nos dados. Em produção chega uma linha por vez, com a grafia do ACS
('5GHz' no lugar de '5ghz'): as colunas precisam vir do contrato, não da linha.
"""

import pandas as pd

from ml.core.features import matriz


def _categorica(serie: pd.Series) -> bool:
  return not pd.api.types.is_numeric_dtype(serie)


def contrato(df: pd.DataFrame, features) -> dict:
  """Features, colunas da matriz de treino (na ordem) e categorias vistas de cada categórica."""
  features = list(features)
  categorias = {f: sorted(df[f].dropna().astype(str).unique()) for f in features if _categorica(df[f])}
  return {'features': features, 'colunas': list(matriz(df, features).columns), 'categorias': categorias,
          'uso': 'X = producao.preparar_entrada(linhas, contrato)[0]; modelo.predict(X)'}


def _casar(valor, conhecidas: list):
  """O valor como o treino o viu: igual, ou igual sem diferença de maiúsculas e espaços.

  None quando não há uma correspondência só (categoria que o treino não viu).
  """
  if pd.isna(valor):
    return None
  texto = str(valor).strip()
  if texto in conhecidas:
    return texto
  iguais = [c for c in conhecidas if c.lower() == texto.lower()]
  return iguais[0] if len(iguais) == 1 else None


def preparar_entrada(df: pd.DataFrame, contrato: dict):
  """Matriz de produção com as colunas do contrato, na mesma ordem. Devolve (X, avisos).

  Categoria que o treino não viu vira zero em todas as colunas dela, com aviso. Feature
  numérica que chega como texto é convertida (texto inválido vira NaN, que o imputer trata).
  """
  faltam = [f for f in contrato['features'] if f not in df.columns]
  if faltam:
    raise ValueError(f'features do contrato ausentes na entrada: {faltam}')
  df = df[contrato['features']].copy()
  avisos = []
  for f in contrato['features']:
    if f in contrato['categorias']:
      conhecidas = contrato['categorias'][f]
      casados = df[f].map(lambda v: _casar(v, conhecidas))
      fora = sorted({str(v) for v, c in zip(df[f], casados) if not pd.isna(v) and c is None})
      if fora:
        avisos.append(f'{f}: valores que o treino não viu {fora}; viram zero em todas as colunas de {f}')
      df[f] = casados.astype(object)
    else:
      df[f] = pd.to_numeric(df[f], errors='coerce').astype(float)
  X = matriz(df, contrato['features']).reindex(columns=contrato['colunas'], fill_value=0.0)
  return X, avisos

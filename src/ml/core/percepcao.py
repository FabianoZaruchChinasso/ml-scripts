"""Rótulo de percepção por cômodo: quem estava no local diz se a experiência era boa ou ruim.

O rótulo é por posição (core/percepcao.json), agrupado em três classes. O classificador é
treinado nas linhas e avaliado por posição, deixando um prédio de fora por vez. Spec:
docs/superpowers/specs/2026-10-29-rotulo-percepcao-design.md.
"""

import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from ml.core import sites
from ml.core.avaliacao import _intervalo, assert_sem_vazamento
from ml.core.features import matriz
from ml.core.splits import outer_logo_folds

PERCEPCAO_PATH = os.path.join(os.path.dirname(__file__), 'percepcao.json')
CLASSES = ('excelente', 'media', 'ruim')
# Acaso e "sempre a classe majoritária" dão o mesmo na acurácia balanceada de 3 classes.
ACASO = 1 / len(CLASSES)
# Erros que trocam um extremo pelo outro.
GRAVES = (('excelente', 'ruim'), ('ruim', 'excelente'))


def _posicao_conhecida(chave: str, registro: dict) -> bool:
  """Posição canônica: valor de `posicoes` de algum prédio, ou valor que resolve para si mesmo (prefixo)."""
  if any(chave in p.get('posicoes', {}).values() for p in registro['predios'].values()):
    return True
  try:
    return sites.resolve_site_id(pd.Series([chave]), registro=registro).iloc[0] == chave
  except ValueError:
    return False


def validar(dados, registro: dict = None) -> None:
  if not isinstance(dados, dict) or set(dados) != {'classes', 'posicoes'}:
    raise ValueError("percepcao.json precisa ter exatamente as chaves 'classes' e 'posicoes'")
  fora = sorted(set(dados['classes'].values()) - set(CLASSES))
  if fora:
    raise ValueError(f'classes desconhecidas {fora}; esperado uma de {list(CLASSES)}')
  registro = sites.registro_atual() if registro is None else registro
  for posicao, nivel in dados['posicoes'].items():
    if nivel not in dados['classes']:
      raise ValueError(f'{posicao!r}: nível {nivel!r} fora de {sorted(dados["classes"])}')
    if not _posicao_conhecida(posicao, registro):
      raise ValueError(f'{posicao!r}: posição desconhecida em core/predios.json')


def carregar(path: str = PERCEPCAO_PATH, registro: dict = None) -> dict:
  """{posição: classe} de percepcao.json, validado contra o registro de prédios."""
  with open(path, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar(dados, registro)
  return {posicao: dados['classes'][nivel] for posicao, nivel in dados['posicoes'].items()}


def rotular(df: pd.DataFrame, rotulos: dict) -> tuple:
  """(df só com posições rotuladas, com `_classe` e índice refeito; posições sem rótulo; rotuladas sem linhas)."""
  sem_rotulo = sorted(set(df['_pos']) - set(rotulos))
  sem_linhas = sorted(set(rotulos) - set(df['_pos']))
  saida = df[df['_pos'].isin(list(rotulos))].reset_index(drop=True)
  return saida.assign(_classe=saida['_pos'].map(rotulos)), sem_rotulo, sem_linhas


def pesos(pos, classe) -> np.ndarray:
  """Peso por linha: cada posição soma o mesmo dentro da classe e cada classe soma o mesmo total.

  Sem isso uma posição com 180 linhas valeria nove vezes uma com 20. A soma é o número de posições.
  """
  pos = pd.Series(np.asarray(pos))
  classe = pd.Series(np.asarray(classe))
  w = 1.0 / pos.map(pos.value_counts())
  por_classe = w.groupby(classe).transform('sum')
  return (w / por_classe * (pos.nunique() / classe.nunique())).to_numpy()


def modelo() -> Pipeline:
  """Os hiperparâmetros do RF de referência do QoE, sem class_weight: o balanceamento vem de `pesos`."""
  return Pipeline([('imputer', SimpleImputer(strategy='median')),
                   ('clf', RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=-1,
                                                  random_state=42))])


def prever_fora_do_fold(df: pd.DataFrame, colunas, vazadas, fabrica=modelo) -> pd.DataFrame:
  """Probabilidade de cada classe em cada linha, pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  `fabrica()` devolve um Pipeline com o passo 'clf', que recebe os pesos de `pesos`. Devolve um
  DataFrame alinhado com `df`, colunas CLASSES; classe ausente do treino do fold fica com 0.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not df.index.is_unique:
    raise ValueError('índice do df precisa ser único')
  X = matriz(df, colunas)
  proba = pd.DataFrame(0.0, index=df.index, columns=list(CLASSES))
  for fold in outer_logo_folds(X, df['_classe'], df['_site']):
    w = pesos(df.loc[fold.X_train.index, '_pos'], fold.y_train)
    ajustado = fabrica().fit(fold.X_train, fold.y_train, clf__sample_weight=w)
    p = pd.DataFrame(ajustado.predict_proba(fold.X_test), index=fold.X_test.index, columns=ajustado.classes_)
    proba.loc[fold.X_test.index] = p.reindex(columns=list(CLASSES), fill_value=0.0).to_numpy()
  return proba


def por_posicao(df: pd.DataFrame, proba: pd.DataFrame) -> pd.DataFrame:
  """Uma linha por posição (índice `_pos`): `_site`, `real` e `previsto` (classe de maior probabilidade média)."""
  media = proba.groupby(df['_pos']).mean()
  info = df.groupby('_pos')[['_site', '_classe']].first()
  return pd.DataFrame({'_site': info['_site'], 'real': info['_classe'],
                       'previsto': media.loc[info.index, list(CLASSES)].idxmax(axis=1)})


def acuracia_balanceada(real, previsto) -> float:
  """Média do recall das classes presentes em `real`."""
  real, previsto = np.asarray(real), np.asarray(previsto)
  return float(np.mean([np.mean(previsto[real == c] == c) for c in np.unique(real)]))


def resumir(pos_df: pd.DataFrame, amostras) -> dict:
  """Acurácia balanceada por posição e o intervalo de 90% nas reamostragens (índices posicionais de `pos_df`)."""
  real, prev = pos_df['real'].to_numpy(), pos_df['previsto'].to_numpy()
  return {'nota': round(acuracia_balanceada(real, prev), 4),
          'intervalo': _intervalo([acuracia_balanceada(real[i], prev[i]) for i in amostras])}


def diferenca(nova: pd.DataFrame, base: pd.DataFrame, amostras) -> dict:
  """Diferença pareada de acurácia balanceada (nova - base) nas mesmas reamostragens."""
  if not nova.index.equals(base.index):
    raise ValueError('nova e base precisam das mesmas posições, na mesma ordem')
  real = nova['real'].to_numpy()
  pn, pb = nova['previsto'].to_numpy(), base['previsto'].to_numpy()
  return {'diferenca': round(acuracia_balanceada(real, pn) - acuracia_balanceada(real, pb), 4),
          'intervalo': _intervalo([acuracia_balanceada(real[i], pn[i]) - acuracia_balanceada(real[i], pb[i])
                                   for i in amostras])}


def leitura(piso: dict, nova: dict, dif: dict) -> dict:
  """Regra fixada no spec (seção 3.4) antes de rodar."""
  aprendivel = any(r['intervalo'] is not None and r['intervalo'][0] > ACASO for r in (piso, nova))
  if dif['intervalo'] is None:
    contra_piso = 'empate'
  else:
    lo, hi = dif['intervalo']
    contra_piso = 'melhor' if lo > 0 else 'piora' if hi < 0 else 'empate'
  return {'aprendivel': aprendivel, 'contra_piso': contra_piso}


def confusao(pos_df: pd.DataFrame) -> tuple:
  """(matriz 3x3 em posições, real nas linhas; quantos erros graves excelente <-> ruim)."""
  m = pd.crosstab(pos_df['real'], pos_df['previsto']).reindex(index=list(CLASSES), columns=list(CLASSES),
                                                              fill_value=0)
  return m, int(sum(m.loc[a, b] for a, b in GRAVES))


def por_predio(pos_df: pd.DataFrame) -> dict:
  """{prédio: (acertos, posições)}."""
  certo = pos_df['real'] == pos_df['previsto']
  return {s: (int(certo[g.index].sum()), len(g)) for s, g in pos_df.groupby('_site')}

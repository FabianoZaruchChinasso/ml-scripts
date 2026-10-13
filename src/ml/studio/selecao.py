"""Desenho automático de um modelo: seleção gulosa com folds por local.

O escopo 'tudo' busca o melhor treino com todas as colunas elegíveis; 'implantavel' fica
só com status TR-181 padrão, derivável ou proxy. O resultado traz a cobertura TR-069.

Dois números saem daqui, e a diferença entre eles é o ponto:

- a nota da seleção: o conjunto escolhido olhando os 3 locais, avaliado nos
  mesmos 3 locais. É otimista por construção (a escolha já viu o teste);
- a nota aninhada: para cada local de teste, a seleção roda só com os outros
  locais e o modelo resultante é testado no local que ficou de fora. É a
  estimativa honesta de "rodar este procedimento e levar para um prédio novo".
"""

import time
from statistics import mean

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline

from ml.core import avaliacao as A
from ml.core import features as F
from ml.core.sites import teto_wan
from ml.core.splits import assert_sites_disjoint
from ml.studio import features as SF

# A busca avalia centenas de subconjuntos: floresta menor aqui, e a nota final
# de cada conjunto escolhido usa o mesmo modelo de 200 árvores do resto do Studio.
ARVORES_BUSCA = 60
MAX_FEATURES = 12
TOLERANCIA = 0.005

# Contadores brutos que crescem com o volume de tráfego. O coletor os mede na janela
# do teste (confirmado em 2026-10-02), então carregam o próprio alvo. As razões por
# pacote (retry_por_pacote, fracao_airtime_tx, ...) herdam esse vazamento. A exclusão
# continua aqui porque o estado pode voltar a "não sei" em Limites e pendências.
CONTADORES_VOLUME = F.CONTADORES_JANELA


def _modelo_busca() -> Pipeline:
  return Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('reg', RandomForestRegressor(n_estimators=ARVORES_BUSCA, min_samples_leaf=2, n_jobs=-1,
                                  random_state=42)),
  ])


def _pooled(df: pd.DataFrame, colunas: list, alvo: str) -> float:
  """R² pooled das previsões fora do fold, deixando um local de fora por vez."""
  X = SF.matriz(df, colunas)
  y = df[alvo].astype(float).to_numpy()
  locais = df['_site'].to_numpy()
  previsto = np.empty(len(y))
  for local in np.unique(locais):
    teste = locais == local
    assert_sites_disjoint(np.unique(locais[~teste]), [local])
    previsto[teste] = _modelo_busca().fit(X[~teste], y[~teste]).predict(X[teste])
  return float(r2_score(y, previsto))


def gulosa(df: pd.DataFrame, candidatas: list, alvo: str, progresso=None,
           max_features: int = MAX_FEATURES, tolerancia: float = TOLERANCIA):
  """Soma, a cada passo, a candidata que mais sobe o R² pooled; para quando o ganho < tolerância."""
  escolhidas, passos, melhor = [], [], -np.inf
  restantes = list(candidatas)
  while restantes and len(escolhidas) < max_features:
    notas = {c: _pooled(df, escolhidas + [c], alvo) for c in restantes}
    c, nota = max(notas.items(), key=lambda kv: kv[1])
    if nota - melhor < tolerancia:
      break
    passos.append({'feature': c, 'pooled': round(nota, 4),
                   'ganho': None if melhor == -np.inf else round(nota - melhor, 4)})
    escolhidas.append(c)
    restantes.remove(c)
    melhor = nota
    if progresso:
      progresso(passos[-1])
  return escolhidas, passos


def aninhada(df: pd.DataFrame, candidatas: list, alvo: str, progresso=None) -> dict:
  """Para cada local: seleção só com os outros locais, teste no local que ficou de fora."""
  reais, previstos, por_local, mae_local, escolhas = [], [], {}, {}, {}
  for local in sorted(df['_site'].unique()):
    treino = df[df['_site'] != local].reset_index(drop=True)
    teste = df[df['_site'] == local].reset_index(drop=True)
    assert_sites_disjoint(treino['_site'].unique(), [local])
    if treino['_site'].nunique() < 2:
      raise ValueError('a seleção aninhada precisa de pelo menos 3 locais de coleta')
    if progresso:
      progresso({'fase': f'aninhada: selecionando sem {local}'})
    feats, _ = gulosa(treino, candidatas, alvo)
    escolhas[local] = feats
    # Mesmas regras da régua (prever_fora_do_fold): linha no teto de WAN fora do treino
    # e previsão cortada no teto do prédio de teste. Sem isso, a diferença entre a nota
    # da seleção e a aninhada mistura otimismo de seleção com diferença de protocolo.
    com_teto = alvo in A.ALVOS_COM_TETO
    if com_teto and '_limitado_wan' in treino.columns:
      treino = treino[~treino['_limitado_wan'].astype(bool)]
    X_tr, X_te = SF.matriz(treino, feats), SF.matriz(teste, feats)
    X_te = X_te.reindex(columns=X_tr.columns, fill_value=0.0)
    y_te = teste[alvo].astype(float)
    p = A.modelo_regua().fit(X_tr, treino[alvo].astype(float)).predict(X_te)
    teto = teto_wan(local, alvo) if com_teto else None
    if teto is not None:
      p = np.minimum(p, teto)
    por_local[local] = round(float(r2_score(y_te, p)), 4)
    mae_local[local] = round(float(mean_absolute_error(y_te, p)), 4)
    reais.extend(y_te.tolist())
    previstos.extend(p.tolist())
  return {'media': round(mean(por_local.values()), 4),
          'pooled': round(float(r2_score(reais, previstos)), 4),
          'mae': round(float(mean_absolute_error(reais, previstos)), 4),
          'por_local': por_local, 'mae_por_local': mae_local, 'escolhas_por_local': escolhas}


ESCOPOS = ('tudo', 'implantavel')


def candidatas(inv: dict, escopo: str = 'tudo') -> list:
  """Elegíveis para o desenho; 'implantavel' fica só com status TR-181 padrão, derivável ou proxy."""
  if escopo not in ESCOPOS:
    raise ValueError(f'escopo {escopo!r} inválido; esperado um de {list(ESCOPOS)}')
  por_nome = {c['coluna']: c for c in inv['colunas']}
  return [c for c in SF.elegiveis(inv) if escopo == 'tudo' or por_nome[c]['implantavel']]


def desenhar(conj: SF.Conjunto, inv: dict, progresso=None, sem_volume: bool = False,
             escopo: str = 'tudo') -> dict:
  inicio = time.time()
  SF._checar_locais(conj.df)
  df = conj.df[conj.df[conj.alvo].notna()].reset_index(drop=True)
  # Sem volume: tira os contadores brutos e tudo que ainda está com vazamento não
  # confirmado (as derivadas deles herdam o 'pendente', ex.: fracao_airtime_tx).
  pendentes = {c['coluna'] for c in inv['colunas'] if c.get('pendente')}
  excluidas = sorted(set(CONTADORES_VOLUME) | pendentes) if sem_volume else []
  escolhiveis = [c for c in candidatas(inv, escopo) if c not in excluidas]
  if not escolhiveis:
    raise ValueError(f'nenhuma coluna elegível neste conjunto (escopo {escopo!r})')
  if progresso:
    progresso({'fase': f'seleção com os {df["_site"].nunique()} locais ({len(escolhiveis)} candidatas)'})
  features, passos = gulosa(df, escolhiveis, conj.alvo, progresso)
  vazadas = SF.vazadas_do_conjunto(conj)
  nota_selecao = SF.avaliar(conj, features, vazadas)
  nota_aninhada = aninhada(df, escolhiveis, conj.alvo, progresso)
  return {'alvo': conj.alvo, 'datasets': conj.datasets, 'candidatas': escolhiveis,
          'features': features, 'passos': passos,
          'nota_selecao': nota_selecao, 'nota_aninhada': nota_aninhada,
          'parametros': {'arvores_busca': ARVORES_BUSCA, 'max_features': MAX_FEATURES,
                         'tolerancia': TOLERANCIA, 'criterio': 'R² pooled, folds por local de coleta',
                         'sem_volume': sem_volume,
                         'escopo': escopo,
                         'excluidas': excluidas},
          'cobertura': F.cobertura_tr069(features, conj.tabela, conj.catalogo),
          'segundos': round(time.time() - inicio, 1)}

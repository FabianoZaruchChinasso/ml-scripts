"""Régua por cômodo: a experiência de cada posição em relação ao resto da casa.

Verdade: por posição, só com as linhas em que o cliente está sozinho no rádio, a capacidade
(mediana de download e upload) como fração da melhor posição do prédio (V0 provisório) e a
interatividade (p90 de latência e jitter) contra o perfil de norma, em bom / degradado / ruim.
Previsão: as grandezas físicas fora do fold (régua de regressão e p90 com CQR), classificadas
com a mesma referência. Spec: docs/superpowers/specs/2026-10-29-regua-comodo-design.md.
"""

import numpy as np
import pandas as pd

from ml.core import avaliacao, quantis
from ml.core.percepcao import acuracia_balanceada, diferenca, por_predio, resumir

# Muda quando cortes, referência, filtro de linhas ou regras mudam.
VERSAO_COMODO = '2026-10-29.1'
CLASSES = ('bom', 'degradado', 'ruim')
# Fração da capacidade da casa: abaixo de CORTE_RUIM é ruim, abaixo de CORTE_BOM é degradado.
CORTE_RUIM = 0.25
CORTE_BOM = 0.75
# Posição com menos linhas sozinha no rádio não define a referência da casa.
MIN_LINHAS_REFERENCIA = 10
NAVEGACAO, CHAMADA, JOGO = 'Navegação', 'Chamada de vídeo', 'Jogo em nuvem'
DN, UP, LAT, JIT = 'speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms'
# Erros que trocam um extremo pelo outro.
GRAVES = (('bom', 'ruim'), ('ruim', 'bom'))
# Níveis do rótulo humano (core/percepcao.json) nas classes desta régua.
ROTULO_PARA_CLASSE = {'Excelente': 'bom', 'Bom': 'bom', 'Ok': 'degradado', 'Ruim': 'ruim', 'Ausente': 'ruim'}


def sozinhas(df: pd.DataFrame) -> pd.DataFrame:
  """Linhas com o cliente sozinho no rádio (`concorrentes_mesmo_radio` conta a própria linha)."""
  return df[df['concorrentes_mesmo_radio'] == 1]


def estatisticas(df: pd.DataFrame) -> pd.DataFrame:
  """Uma linha por posição (índice `_pos`): `_site`, `n`, medianas de download e upload, p90 de latência e jitter."""
  g = df.groupby('_pos')
  return pd.DataFrame({'_site': g['_site'].first(), 'n': g.size(), 'dn': g[DN].median(), 'up': g[UP].median(),
                       'lat': g[LAT].quantile(0.9), 'jit': g[JIT].quantile(0.9)})


def referencia(est: pd.DataFrame) -> pd.DataFrame:
  """V0 provisório por prédio: maior mediana de download e de upload entre posições com MIN_LINHAS_REFERENCIA linhas."""
  ref = est[est['n'] >= MIN_LINHAS_REFERENCIA].groupby('_site')[['dn', 'up']].max()
  faltam = sorted(set(est['_site']) - set(ref.index))
  if faltam:
    raise ValueError(f'prédios sem posição com {MIN_LINHAS_REFERENCIA} linhas sozinhas no rádio: {faltam}')
  return ref


def _falha(est: pd.DataFrame, lim: dict) -> pd.Series:
  return (est['lat'] > lim['lat']) | (est['jit'] > lim['jit'])


def classificar(est: pd.DataFrame, ref: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Razão de capacidade, classe e "apto para jogo" de cada posição de `est`, com a referência `ref`.

  `limiares`: {aplicação: {'lat', 'jit', ...}}, como aplicacoes.carregar_perfil devolve. Ruim:
  razão abaixo de CORTE_RUIM ou falha em Navegação. Degradado: razão abaixo de CORTE_BOM ou falha
  em Chamada de vídeo (nunca ruim só por Chamada). Jogo em nuvem não entra na classe.
  """
  faltam = sorted(set(est['_site']) - set(ref.index))
  if faltam:
    raise ValueError(f'sem referência da casa para os prédios {faltam}')
  razao = np.minimum(est['dn'] / est['_site'].map(ref['dn']), est['up'] / est['_site'].map(ref['up']))
  ruim = (razao < CORTE_RUIM) | _falha(est, limiares[NAVEGACAO])
  degradado = (razao < CORTE_BOM) | _falha(est, limiares[CHAMADA])
  classe = np.where(ruim, 'ruim', np.where(degradado, 'degradado', 'bom'))
  return pd.DataFrame({'_site': est['_site'], 'razao': razao, 'classe': classe,
                       'apto_jogo': ~_falha(est, limiares[JOGO])}, index=est.index)


def verdade(df: pd.DataFrame, limiares: dict) -> tuple:
  """(classe de cada posição, referência por prédio), só com as linhas sozinhas no rádio."""
  est = estatisticas(sozinhas(df))
  ref = referencia(est)
  return classificar(est, ref, limiares), ref


def prever(conjs: dict, features, vazadas: dict, denominador: dict = None) -> pd.DataFrame:
  """Previsões fora do fold (LOGO por prédio) dos quatro alvos, casadas por `_linha`.

  `conjs`: {alvo: objeto com `.df`} (o Conjunto da carga); `vazadas`: {alvo: colunas com
  vazamento}; `denominador`: {alvo: valor do registro} para download e upload. Feature
  ausente ou com vazamento num alvo fica fora só dele. Linha sem previsão em algum alvo sai.
  Devolve _linha, _site, _pos, dn, up (previsão pontual), lat, jit (p90 com CQR).
  """
  partes = {}
  for alvo, nome in ((DN, 'dn'), (UP, 'up'), (LAT, 'lat'), (JIT, 'jit')):
    df = conjs[alvo].df
    colunas = [f for f in features if f in df.columns and f not in vazadas[alvo]]
    if not colunas:
      raise ValueError(f'nenhuma feature utilizável para {alvo}')
    if alvo in (LAT, JIT):
      p = quantis.prever_quantis_fora_do_fold(df, colunas, alvo, vazadas[alvo])
      partes[nome] = p.set_index('_linha')['q90']
    else:
      p = avaliacao.prever_fora_do_fold(df, colunas, alvo, vazadas[alvo],
                                        denominador=(denominador or {}).get(alvo))
      partes[nome] = p.set_index('_linha')['yhat']
  saida = pd.concat(partes, axis=1, join='inner')
  base = conjs[DN].df.set_index('_linha')
  saida = saida.assign(_site=base['_site'].reindex(saida.index).to_numpy(),
                       _pos=base['_pos'].reindex(saida.index).to_numpy())
  return saida.rename_axis('_linha').reset_index()


def classe_prevista(prev: pd.DataFrame, ref: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Classe de cada posição pela previsão: medianas de download, upload e dos p90 previstos,
  com a referência da verdade (o V0 é dado conhecido)."""
  g = prev.groupby('_pos')
  est = pd.DataFrame({'_site': g['_site'].first(), 'n': g.size(), 'dn': g['dn'].median(), 'up': g['up'].median(),
                      'lat': g['lat'].median(), 'jit': g['jit'].median()})
  return classificar(est, ref, limiares)


def juntar(real: pd.DataFrame, previsto: pd.DataFrame) -> pd.DataFrame:
  """Posições presentes nas duas tabelas, em ordem: `_site`, `real`, `previsto`, `jogo_real`, `jogo_previsto`."""
  comuns = real.index.intersection(previsto.index).sort_values()
  return pd.DataFrame({'_site': real.loc[comuns, '_site'], 'real': real.loc[comuns, 'classe'],
                       'previsto': previsto.loc[comuns, 'classe'], 'jogo_real': real.loc[comuns, 'apto_jogo'],
                       'jogo_previsto': previsto.loc[comuns, 'apto_jogo']})


def nota(pos_df: pd.DataFrame, amostras) -> dict:
  """Acurácia balanceada das 3 classes sobre as posições de todos os prédios juntas, com o
  intervalo de 90% nas reamostras. Não é média entre prédios: um prédio de uma classe só não prende a nota."""
  return resumir(pos_df, amostras)


def nota_jogo(pos_df: pd.DataFrame) -> float:
  """Acurácia balanceada de "apto para jogo" por posição."""
  return acuracia_balanceada(pos_df['jogo_real'], pos_df['jogo_previsto'])


def comparar(nova: pd.DataFrame, base: pd.DataFrame, amostras) -> dict:
  """Diferença pareada de nota (nova - base) e o resultado: intervalo todo acima de 0 é melhor,
  todo abaixo é pior, o resto é empate."""
  dif = diferenca(nova, base, amostras)
  if dif['intervalo'] is None:
    resultado = 'empate'
  else:
    lo, hi = dif['intervalo']
    resultado = 'melhor' if lo > 0 else 'pior' if hi < 0 else 'empate'
  return dict(dif, resultado=resultado)


def confusao(pos_df: pd.DataFrame) -> tuple:
  """(matriz 3x3 em posições, real nas linhas; quantos erros graves bom <-> ruim)."""
  m = pd.crosstab(pos_df['real'], pos_df['previsto']).reindex(index=list(CLASSES), columns=list(CLASSES),
                                                              fill_value=0)
  return m, int(sum(m.loc[a, b] for a, b in GRAVES))


def contra_rotulo(real: pd.DataFrame, niveis: dict) -> tuple:
  """Verdade contra o rótulo humano (níveis brutos de percepcao.json), nas posições em comum.

  Devolve (acurácia balanceada da verdade contra o rótulo, matriz 3x3 com o rótulo nas linhas).
  """
  comuns = sorted(set(real.index) & set(niveis))
  pos_df = pd.DataFrame({'real': [ROTULO_PARA_CLASSE[niveis[p]] for p in comuns],
                         'previsto': real.loc[comuns, 'classe'].to_numpy()}, index=comuns)
  m, _ = confusao(pos_df)
  return acuracia_balanceada(pos_df['real'], pos_df['previsto']), m

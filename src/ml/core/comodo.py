"""Régua por cômodo: a experiência de cada posição em relação ao resto da casa.

Verdade: por posição, só com as linhas em que o cliente está sozinho no rádio, a capacidade
(mediana de download e upload) como fração da melhor posição do prédio (V0 provisório) e contra os
mínimos absolutos de download e upload do perfil, e a interatividade (p90 de latência e jitter)
contra o perfil de norma, em bom / degradado / ruim.
Previsão: as grandezas físicas fora do fold (régua de regressão e p90 sem a correção conformal), classificadas
com a mesma referência. Spec: docs/superpowers/specs/2026-10-29-regua-comodo-design.md.
"""

import copy

import numpy as np
import pandas as pd

from ml.core import avaliacao, quantis
from ml.core.carga import LIMIAR_TETO
from ml.core.percepcao import acuracia_balanceada, diferenca, por_predio, resumir
from ml.core.sites import teto_wan

# Muda quando cortes, referência, filtro de linhas ou regras mudam.
VERSAO_COMODO = '2026-11-05.1'
CLASSES = ('bom', 'degradado', 'ruim')
# Fração da capacidade da casa: abaixo de CORTE_RUIM é ruim, abaixo de CORTE_BOM é degradado.
CORTE_RUIM = 0.25
CORTE_BOM = 0.75
# Posição com menos linhas sozinha no rádio não define a referência da casa.
MIN_LINHAS_REFERENCIA = 10
# Experimento de 2026-11-05 (features relativas): taxas viram razão, níveis em dB viram diferença,
# contra o maior valor da casa. Fixadas antes de medir; ver docs/superpowers/plans/2026-11-05-features-relativas.md.
RELATIVAS = {'router_tx_rate_mbps': 'razao', 'router_rx_rate_mbps': 'razao',
             'router_signal_dbm': 'diferenca', 'router_snr': 'diferenca'}
# Alvos do modelo de razão: fração da capacidade do melhor cômodo da casa.
RAZAO_DN, RAZAO_UP = '_razao_dn', '_razao_up'
NAVEGACAO, CHAMADA, JOGO = 'Navegação', 'Chamada de vídeo', 'Jogo em nuvem'
DN, UP, LAT, JIT = 'speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms'
# Erros que trocam um extremo pelo outro.
GRAVES = (('bom', 'ruim'), ('ruim', 'bom'))
# Níveis do rótulo humano (core/percepcao.json) nas classes desta régua.
ROTULO_PARA_CLASSE = {'Excelente': 'bom', 'Bom': 'bom', 'Ok': 'degradado', 'Ruim': 'ruim', 'Ausente': 'ruim'}


def sozinhas(df: pd.DataFrame) -> pd.DataFrame:
  """Linhas com o cliente sozinho no rádio (`concorrentes_mesmo_radio` conta a própria linha)."""
  return df[df['concorrentes_mesmo_radio'] == 1]


def conjuntos_sozinhos(conjs: dict) -> dict:
  """Cópia de cada Conjunto com o `.df` só nas linhas sozinhas no rádio (treino "um dispositivo")."""
  saida = {}
  for alvo, conj in conjs.items():
    novo = copy.copy(conj)
    novo.df = sozinhas(conj.df).reset_index(drop=True)
    saida[alvo] = novo
  return saida


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


def _abaixo_do_minimo(est: pd.DataFrame, lim: dict) -> pd.Series:
  """Capacidade abaixo do mínimo absoluto da aplicação (o limite em si atende)."""
  return (est['dn'] < lim['dn']) | (est['up'] < lim['up'])


def classificar(est: pd.DataFrame, ref: pd.DataFrame, limiares: dict, razao: pd.Series = None) -> pd.DataFrame:
  """Razão de capacidade, classe e "apto para jogo" de cada posição de `est`, com a referência `ref`.

  `limiares`: {aplicação: {'dn', 'up', 'lat', 'jit'}}, como aplicacoes.carregar_perfil devolve. Ruim:
  razão abaixo de CORTE_RUIM, ou falha em Navegação (latência, jitter ou capacidade abaixo do mínimo).
  Degradado: razão abaixo de CORTE_BOM, ou falha em Chamada de vídeo pelos mesmos critérios (nunca ruim
  só por Chamada). O mínimo absoluto cobre a casa cujo melhor cômodo já é fraco. Jogo em nuvem não
  entra na classe; "apto para jogo" é só latência e jitter. Com `razao` (por posição), ela substitui
  `dn ÷ ref` e `ref` não é usada; o piso absoluto continua olhando `dn` e `up` de `est`.
  """
  if razao is None:
    faltam = sorted(set(est['_site']) - set(ref.index))
    if faltam:
      raise ValueError(f'sem referência da casa para os prédios {faltam}')
    razao = np.minimum(est['dn'] / est['_site'].map(ref['dn']), est['up'] / est['_site'].map(ref['up']))
  else:
    razao = razao.reindex(est.index)
  ruim = (razao < CORTE_RUIM) | _falha(est, limiares[NAVEGACAO]) | _abaixo_do_minimo(est, limiares[NAVEGACAO])
  degradado = (razao < CORTE_BOM) | _falha(est, limiares[CHAMADA]) | _abaixo_do_minimo(est, limiares[CHAMADA])
  classe = np.where(ruim, 'ruim', np.where(degradado, 'degradado', 'bom'))
  return pd.DataFrame({'_site': est['_site'], 'razao': razao, 'classe': classe,
                       'apto_jogo': ~_falha(est, limiares[JOGO])}, index=est.index)


def verdade(df: pd.DataFrame, limiares: dict) -> tuple:
  """(classe de cada posição, referência por prédio), só com as linhas sozinhas no rádio."""
  est = estatisticas(sozinhas(df))
  ref = referencia(est)
  return classificar(est, ref, limiares), ref


def de_previsoes(base_df: pd.DataFrame, prev_dn: pd.DataFrame, prev_up: pd.DataFrame, q_lat: pd.DataFrame,
                 q_jit: pd.DataFrame) -> pd.DataFrame:
  """Junta por `_linha` as previsões fora do fold: `yhat` de download e upload (régua de regressão)
  e `q90_bruto` de latência e jitter: o p90 sem a correção conformal, porque a CQR é um limite
  conservador por linha e deixava toda posição fora do apto para jogo. Linha sem previsão em algum alvo sai; `_site` e
  `_pos` vêm de `base_df`. Devolve _linha, _site, _pos, dn, up, lat, jit."""
  saida = pd.concat({'dn': prev_dn.set_index('_linha')['yhat'], 'up': prev_up.set_index('_linha')['yhat'],
                     'lat': q_lat.set_index('_linha')['q90_bruto'],
                     'jit': q_jit.set_index('_linha')['q90_bruto']},
                    axis=1, join='inner')
  base = base_df.set_index('_linha')
  saida = saida.assign(_site=base['_site'].reindex(saida.index).to_numpy(),
                       _pos=base['_pos'].reindex(saida.index).to_numpy())
  return saida.rename_axis('_linha').reset_index()


def prever(conjs: dict, features, vazadas: dict, denominador: dict = None) -> pd.DataFrame:
  """Previsões fora do fold (LOGO por prédio) dos quatro alvos, casadas por `_linha`.

  `conjs`: {alvo: objeto com `.df`} (o Conjunto da carga); `vazadas`: {alvo: colunas com
  vazamento}; `denominador`: {alvo: valor do registro} para download e upload. Feature
  ausente ou com vazamento num alvo fica fora só dele. Linha sem previsão em algum alvo sai.
  Devolve _linha, _site, _pos, dn, up (previsão pontual), lat, jit (p90 sem a correção conformal).
  """
  previsto = {}
  for alvo in (DN, UP, LAT, JIT):
    df = conjs[alvo].df
    colunas = [f for f in features if f in df.columns and f not in vazadas[alvo]]
    if not colunas:
      raise ValueError(f'nenhuma feature utilizável para {alvo}')
    if alvo in (LAT, JIT):
      previsto[alvo] = quantis.prever_quantis_fora_do_fold(df, colunas, alvo, vazadas[alvo])
    else:
      previsto[alvo] = avaliacao.prever_fora_do_fold(df, colunas, alvo, vazadas[alvo],
                                                     denominador=(denominador or {}).get(alvo))
  return de_previsoes(conjs[DN].df, previsto[DN], previsto[UP], previsto[LAT], previsto[JIT])


def estatisticas_previstas(prev: pd.DataFrame) -> pd.DataFrame:
  """Uma linha por posição a partir das previsões: `_site`, `n`, medianas previstas de download, upload
  e dos p90 previstos de latência e jitter (mesmo formato de `estatisticas`)."""
  g = prev.groupby('_pos')
  return pd.DataFrame({'_site': g['_site'].first(), 'n': g.size(), 'dn': g['dn'].median(), 'up': g['up'].median(),
                       'lat': g['lat'].median(), 'jit': g['jit'].median()})


def referencia_prevista(prev: pd.DataFrame) -> pd.DataFrame:
  """Referência da casa pelas previsões: o melhor cômodo PREVISTO, com a mesma regra de `referencia`.

  Numa casa nova o melhor cômodo real não é conhecido; o previsto é. Um erro de nível da casa
  inteira (eficiência do prédio que o modelo não vê) aparece no cômodo e na referência e se cancela.
  """
  return referencia(estatisticas_previstas(prev))


def referencia_features(df: pd.DataFrame, colunas, por_banda: bool = False) -> pd.DataFrame:
  """Por prédio (e por `radio`, com `por_banda`), o maior valor entre as medianas por posição de cada
  coluna, com as linhas sozinhas no rádio e grupos com MIN_LINHAS_REFERENCIA linhas (a regra de
  `referencia`). Só usa entradas (taxa PHY, sinal, SNR): numa casa nova ela existe."""
  so = sozinhas(df)
  colunas = [c for c in colunas if c in so.columns]
  chave = ['_pos', 'radio'] if por_banda else ['_pos']
  grupos = [so[k] for k in chave]
  med = so[colunas].apply(pd.to_numeric, errors='coerce').groupby(grupos).median()
  med['_site'] = so.groupby(grupos)['_site'].first()
  med['n'] = so.groupby(grupos).size()
  med = med[med['n'] >= MIN_LINHAS_REFERENCIA].reset_index()
  return med.groupby(['_site', 'radio'] if por_banda else '_site')[colunas].max()


def relativizar(df: pd.DataFrame, ref_feat: pd.DataFrame, modos: dict = None, por_banda: bool = False) -> pd.DataFrame:
  """Acrescenta `<coluna>_rel` para cada coluna de `modos` (padrão RELATIVAS) presente em `df` e em
  `ref_feat`: razão (taxas) ou diferença (dB) contra a referência da casa da linha. Com `por_banda`,
  a referência é a do prédio na mesma `radio` da linha."""
  novas = {}
  for coluna, modo in (modos or RELATIVAS).items():
    if coluna not in df.columns or coluna not in ref_feat.columns:
      continue
    valor = pd.to_numeric(df[coluna], errors='coerce')
    if por_banda:
      chave = pd.MultiIndex.from_arrays([df['_site'], df['radio']])
      ref = pd.Series(ref_feat[coluna].reindex(chave).to_numpy(), index=df.index)
    else:
      ref = df['_site'].map(ref_feat[coluna])
    rel = valor / ref if modo == 'razao' else valor - ref
    novas[f'{coluna}_rel'] = rel.replace([np.inf, -np.inf], np.nan)
  return df.assign(**novas)


def alvos_razao(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
  """Acrescenta RAZAO_DN e RAZAO_UP: download e upload como fração da referência real da casa."""
  return df.assign(**{RAZAO_DN: pd.to_numeric(df[DN], errors='coerce') / df['_site'].map(ref['dn']),
                      RAZAO_UP: pd.to_numeric(df[UP], errors='coerce') / df['_site'].map(ref['up'])})


def prever_razao(conjs: dict, features, vazadas: dict, ref: pd.DataFrame, ref_feat: pd.DataFrame,
                 relativas: bool = True, por_banda: bool = False, excluir_wan: bool = False) -> pd.DataFrame:
  """Previsão fora do fold (LOGO por prédio) da razão de capacidade: RAZAO_DN e RAZAO_UP por `_linha`.

  O alvo de treino é a fração da referência REAL da casa (`alvos_razao`); o prédio de teste nunca entra
  no treino, então a referência dele não vaza. `relativas=True` troca as features de RELATIVAS pela
  versão `_rel` (contra `ref_feat`); `relativas=False` usa as features absolutas (o teste de 2026-10-29).
  Com `excluir_wan`, as linhas limitadas pela WAN saem do treino, como na v5.
  """
  saida = {}
  for alvo, coluna in ((DN, RAZAO_DN), (UP, RAZAO_UP)):
    df = alvos_razao(conjs[alvo].df, ref)
    colunas = list(features)
    if relativas:
      df = relativizar(df, ref_feat, por_banda=por_banda)
      colunas = [f'{f}_rel' if f in RELATIVAS and f'{f}_rel' in df.columns else f for f in colunas]
    colunas = [f for f in colunas if f in df.columns and f not in vazadas[alvo]]
    if not colunas:
      raise ValueError(f'nenhuma feature utilizável para {coluna}')
    saida[coluna] = avaliacao.prever_fora_do_fold(df, colunas, coluna, vazadas[alvo],
                                                 excluir_limitados=excluir_wan).set_index('_linha')['yhat']
  return pd.concat(saida, axis=1, join='inner').rename_axis('_linha').reset_index()


def classe_prevista_razao(prev: pd.DataFrame, prev_razao: pd.DataFrame, limiares: dict,
                          saturar_wan: bool = False) -> pd.DataFrame:
  """Classe de cada posição pela razão prevista direto: o menor entre as medianas da razão de download
  e de upload. Latência, jitter e o piso absoluto vêm de `prev` (Mbps e p90 previstos, `prever`).

  Com `saturar_wan`, a linha cuja previsão absoluta de `prev` (já cortada no teto, como na v5) chega a
  LIMIAR_TETO x teto de WAN do prédio fica com razão pelo menos 1: ela satura a WAN, como o melhor cômodo.
  É a mesma informação do teto que a v5 recebe."""
  prev = prev[prev['_linha'].isin(set(prev_razao['_linha']))]
  r = prev_razao.set_index('_linha').reindex(prev['_linha'])
  razoes = {'dn': r[RAZAO_DN].to_numpy(dtype=float), 'up': r[RAZAO_UP].to_numpy(dtype=float)}
  if saturar_wan:
    for chave, alvo in (('dn', DN), ('up', UP)):
      teto = prev['_site'].map(lambda s, a=alvo: teto_wan(s, a)).astype(float).to_numpy()
      satura = prev[chave].to_numpy(dtype=float) >= LIMIAR_TETO * teto
      razoes[chave] = np.where(satura, np.maximum(razoes[chave], 1.0), razoes[chave])
  por_pos = pd.DataFrame({'_pos': prev['_pos'].to_numpy(), **razoes}).groupby('_pos').median()
  return classificar(estatisticas_previstas(prev), None, limiares,
                     razao=np.minimum(por_pos['dn'], por_pos['up']))


def classe_prevista(prev: pd.DataFrame, ref: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Classe de cada posição pela previsão (medianas de download, upload e dos p90 previstos)
  contra a referência `ref`: a da verdade (`verdade`) ou a prevista (`referencia_prevista`)."""
  return classificar(estatisticas_previstas(prev), ref, limiares)


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


def tabela_posicoes(df: pd.DataFrame, prev: pd.DataFrame, limiares: dict) -> pd.DataFrame:
  """Verdade e classe prevista por posição, só com as linhas sozinhas no rádio (índice `_pos`).

  `prev`: saída de `prever` ou `de_previsoes`. Colunas `_site`, `real`, `previsto`,
  `razao_prevista`, `apto_real`, `apto_previsto`.
  """
  real, ref = verdade(df, limiares)
  linhas = set(sozinhas(df)['_linha'])
  previsto = classe_prevista(prev[prev['_linha'].isin(linhas)], ref, limiares)
  comuns = real.index.intersection(previsto.index).sort_values()
  return pd.DataFrame({'_site': real.loc[comuns, '_site'], 'real': real.loc[comuns, 'classe'],
                       'previsto': previsto.loc[comuns, 'classe'], 'razao_prevista': previsto.loc[comuns, 'razao'],
                       'apto_real': real.loc[comuns, 'apto_jogo'], 'apto_previsto': previsto.loc[comuns, 'apto_jogo']})


def amostras_posicoes(tabela: pd.DataFrame) -> list:
  """Reamostras de posições estratificadas por prédio, com a semente fixa da régua: duas tabelas
  com as mesmas posições dão as mesmas reamostras."""
  return avaliacao.reamostras(tabela.index, tabela['_site'])


def _lista(tabela: pd.DataFrame) -> list:
  """Tabela por posição em tipos nativos do Python (vai para o modelos.json)."""
  return [{'pos': str(p), 'site': str(l['_site']), 'real': str(l['real']), 'previsto': str(l['previsto']),
           'razao_prevista': round(float(l['razao_prevista']), 4), 'apto_real': bool(l['apto_real']),
           'apto_previsto': bool(l['apto_previsto'])} for p, l in tabela.iterrows()]


def _tabela(lista: list) -> pd.DataFrame:
  return pd.DataFrame(lista).set_index('pos').rename(columns={'site': '_site'})


_APTO = {True: 'apto', False: 'nao_apto'}


def bloco(tabela: pd.DataFrame, piso: pd.DataFrame, meta: dict) -> dict:
  """Bloco `comodo` guardado na avaliação de uma versão. `meta`: {'datasets', 'ambiente'}.

  `jogo`: acurácia balanceada de "apto para jogo" por posição (versão e piso), com o intervalo
  de 90% nas mesmas reamostras da nota. É informativa: não entra na ativação.
  """
  if not tabela.index.equals(piso.index):
    raise ValueError('a versão e o piso precisam das mesmas posições, na mesma ordem')
  amostras = amostras_posicoes(tabela)
  r, rp = nota(tabela, amostras), nota(piso, amostras)
  c = comparar(tabela, piso, amostras)
  jogo, jogo_piso = (resumir(pd.DataFrame({'real': t['apto_real'].map(_APTO), 'previsto': t['apto_previsto'].map(_APTO)}),
                             amostras) for t in (tabela, piso))
  m, graves = confusao(tabela)
  return {'versao_comodo': VERSAO_COMODO, 'datasets': list(meta['datasets']), 'ambiente': meta['ambiente'],
          'nota': r['nota'], 'intervalo': r['intervalo'], 'piso': {'nota': rp['nota'], 'intervalo': rp['intervalo']},
          'contra_piso': {'diferenca': c['diferenca'], 'intervalo': c['intervalo'], 'resultado': c['resultado']},
          'jogo': {'nota': jogo['nota'], 'intervalo': jogo['intervalo'],
                   'piso': {'nota': jogo_piso['nota'], 'intervalo': jogo_piso['intervalo']}},
          'por_predio': {s: [a, n] for s, (a, n) in por_predio(tabela).items()},
          'confusao': m.values.tolist(), 'graves': graves,
          'posicoes': _lista(tabela), 'piso_posicoes': _lista(piso)}


def comparar_blocos(nova: dict, base: dict) -> dict:
  """Diferença pareada de nota (nova - base) a partir das tabelas guardadas, e o resultado.

  Levanta ValueError se as duas avaliações não são comparáveis: outra régua, outros datasets,
  outro ambiente, outras posições ou outra verdade.
  """
  for campo in ('versao_comodo', 'datasets', 'ambiente'):
    if nova.get(campo) != base.get(campo):
      raise ValueError(f'{campo} diferente: {nova.get(campo)!r} contra {base.get(campo)!r}')
  tn, tb = _tabela(nova['posicoes']), _tabela(base['posicoes'])
  if not tn.index.equals(tb.index):
    raise ValueError('as duas avaliações não têm as mesmas posições')
  if not (tn['real'] == tb['real']).all():
    raise ValueError('a verdade das duas avaliações difere')
  c = comparar(tn, tb, amostras_posicoes(tn))
  return {'diferenca': c['diferenca'], 'intervalo': c['intervalo'], 'resultado': c['resultado'],
          'nota': nova['nota'], 'nota_base': base['nota']}

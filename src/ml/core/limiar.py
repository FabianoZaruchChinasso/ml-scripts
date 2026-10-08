"""Fator de decisão do "atende" em throughput, escolhido sem olhar o prédio de teste.

A regressão superestima os enlaces quase mortos: comparar a previsão de Mbps direto com o
limiar da aplicação diz "atende" demais. O fator k exige previsão >= k × limiar (download e
upload). Em cada fold da régua, k vem de um LOGO interno nos prédios de treino (a maior
acurácia balanceada do "atende"); em produção, de um LOGO com todos os prédios.
"""

import numpy as np
import pandas as pd

from ml.core.avaliacao import (_acuracia_balanceada, _atende_em, _intervalo, _juntar, _media_sem_nan,
                               _resumo_atende, prever_fora_do_fold, reamostras)

# Grade geométrica de 0,5 a 16, passo 2^(1/8): no protótipo, 8 ainda batia na borda.
FATORES = tuple(float(round(2 ** e, 4)) for e in np.arange(-1, 4.0001, 0.125))
ALVO_DN, ALVO_UP = 'speedtest_down_mbps', 'speedtest_up_mbps'


def _decide(j: pd.DataFrame, limiares: dict, k) -> np.ndarray:
  return (j['p_dn'].to_numpy(dtype=float) >= limiares['dn'] * k) & (j['p_up'].to_numpy(dtype=float) >= limiares['up'] * k)


def escolher_fator(j: pd.DataFrame, limiares: dict, fatores=FATORES) -> float:
  """Fator da grade com a maior acurácia balanceada de "atende"; empate fica com o mais perto de 1.

  `j` é a junção (avaliacao._juntar) das previsões fora do fold de download (dn) e upload (up).
  Com uma classe só no real, devolve 1.
  """
  real = _atende_em(j, limiares, 'y_dn', 'y_up')
  if real.all() or not real.any():
    return 1.0
  melhor, melhor_valor = 1.0, -1.0
  for k in sorted(fatores, key=lambda f: abs(np.log(f))):
    valor = _acuracia_balanceada(real, _decide(j, limiares, k))
    if valor > melhor_valor + 1e-12:
      melhor, melhor_valor = k, valor
  return float(melhor)


def _vazadas(conj) -> list:
  return [c for c, k in conj.classes.items() if k is not None and k.vazamento]


def _prever(conj, features, denominador, df=None) -> pd.DataFrame:
  vazadas = _vazadas(conj)
  presentes = [f for f in features if f in conj.df.columns and f not in vazadas]
  return prever_fora_do_fold(conj.df if df is None else df, presentes, conj.alvo, vazadas,
                             denominador=denominador)


def _previsoes(conj_dn, conj_up, features, den_dn, den_up, sem_predio=None) -> pd.DataFrame:
  """Previsões fora do fold de download e upload, juntas por `_linha`; `sem_predio` tira um prédio antes."""
  df_dn = conj_dn.df if sem_predio is None else conj_dn.df[conj_dn.df['_site'] != sem_predio]
  df_up = conj_up.df if sem_predio is None else conj_up.df[conj_up.df['_site'] != sem_predio]
  return _juntar(dn=_prever(conj_dn, features, den_dn, df_dn), up=_prever(conj_up, features, den_up, df_up))


def decisoes_atende(conj_dn, conj_up, features, aplicacoes: dict, den_dn=None, den_up=None,
                    ajustar: bool = True) -> dict:
  """Decisão "atende" de cada linha e aplicação, com o prédio de teste fora do treino e da escolha do fator.

  Com `ajustar`, o fator de cada prédio de teste vem de escolher_fator sobre previsões fora do
  fold feitas só com os outros prédios (LOGO interno); com menos de 2 prédios de treino, ou sem
  `ajustar`, o fator é 1 (a régua de antes). Devolve
  {aplicação: DataFrame(_linha, _site, _pos, real, previsto, fator)}.
  """
  externo = _previsoes(conj_dn, conj_up, features, den_dn, den_up)
  sites = sorted(externo['_site'].unique())
  fatores = {app: {} for app in aplicacoes}
  for site in sites:
    if not ajustar or len(sites) < 3:
      for app in aplicacoes:
        fatores[app][site] = 1.0
      continue
    interno = _previsoes(conj_dn, conj_up, features, den_dn, den_up, sem_predio=site)
    for app, limiares in aplicacoes.items():
      fatores[app][site] = escolher_fator(interno, limiares)
  saida = {}
  for app, limiares in aplicacoes.items():
    k = externo['_site'].map(fatores[app]).to_numpy(dtype=float)
    saida[app] = pd.DataFrame({'_linha': externo.index.to_numpy(), '_site': externo['_site'].to_numpy(),
                               '_pos': externo['_pos'].to_numpy(),
                               'real': _atende_em(externo, limiares, 'y_dn', 'y_up'),
                               'previsto': _decide(externo, limiares, k), 'fator': k})
  return saida


def resumir_decisoes(decisoes: dict, amostras=None) -> dict:
  """A forma de avaliacao.atende (por aplicação, média, intervalo, n, avisos), mais os fatores por prédio."""
  if not decisoes:
    return {'por_aplicacao': {}, 'media': None, 'intervalo': None, 'n': 0, 'avisos': [], 'fatores': {}}
  primeiro = next(iter(decisoes.values()))
  j = primeiro.set_index('_linha')[['_site', '_pos']]
  classes = {app: (d['real'].to_numpy(dtype=bool), d['previsto'].to_numpy(dtype=bool)) for app, d in decisoes.items()}
  resumo = _resumo_atende(j, classes, amostras)
  resumo['fatores'] = {app: {s: float(g['fator'].iloc[0]) for s, g in sorted(d.groupby('_site'), key=lambda kv: kv[0])}
                       for app, d in decisoes.items()}
  return resumo


def delta_decisoes(nova: dict, base: dict, amostras=None):
  """Acurácia balanceada média do "atende" da nova versão menos a da base, nas mesmas linhas.

  None quando nenhuma aplicação tem as duas classes no real.
  """
  trios, j = [], None
  for app, d in nova.items():
    if app not in base:
      continue
    m = d.set_index('_linha')[['_site', '_pos', 'real', 'previsto']].join(
      base[app].set_index('_linha')[['previsto']].rename(columns={'previsto': 'base'}), how='inner')
    j = m if j is None else j
    real = m['real'].to_numpy(dtype=bool)
    if real.all() or not real.any():
      continue
    trios.append((real, m['previsto'].to_numpy(dtype=bool), m['base'].to_numpy(dtype=bool)))
  if not trios:
    return None

  def diferenca(idx):
    return (_media_sem_nan([_acuracia_balanceada(r[idx], n[idx]) for r, n, _ in trios])
            - _media_sem_nan([_acuracia_balanceada(r[idx], b[idx]) for r, _, b in trios]))

  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(diferenca(np.arange(len(j))), 4), 'intervalo': _intervalo([diferenca(i) for i in amostras]),
          'n': int(len(j)), 'ajustado': True}


def fatores_producao(conj_dn, conj_up, features, aplicacoes: dict, den_dn=None, den_up=None) -> dict:
  """{aplicação: fator} escolhido sobre as previsões fora do fold de todos os prédios (para produção)."""
  externo = _previsoes(conj_dn, conj_up, features, den_dn, den_up)
  return {app: escolher_fator(externo, limiares) for app, limiares in aplicacoes.items()}

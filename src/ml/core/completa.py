"""Avaliação completa de uma versão: os quatro alvos, os três "atende" e a régua por cômodo.

É o que fica guardado junto de cada versão. Mora no core para poder ser chamada sem o servidor do
Studio (por um script que registre no MLflow, por exemplo): quem chama diz como obter o conjunto de
cada alvo, e o Studio passa os datasets e o ambiente escolhidos na tela.
"""

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import comodo as core_comodo
from ml.core import features as core_features
from ml.core import limiar as core_limiar
from ml.core import qoe as core_qoe
from ml.core import quantis as core_quantis
from ml.core.carga import TARGETS

# Rótulo de cada etapa, na ordem em que roda (progresso do salvar e do reavaliar).
ETAPAS = {'speedtest_down_mbps': 'download', 'speedtest_up_mbps': 'upload',
          'latency_ms': 'latência', 'jitter_ms': 'jitter'}
# Depois dos quatro alvos: o "atende" da regressão e a régua por cômodo.
N_ETAPAS = len(ETAPAS) + 2

# Tabela por posição do piso da régua por cômodo (só radio): igual para todas as versões, uma por
# (datasets, ambiente, VERSAO_COMODO). Quem troca os dados no meio do processo precisa esvaziar.
_piso_cache = {}


def _vazadas(conj) -> list:
  return [c for c, k in conj.classes.items() if k is not None and k.vazamento]


def presentes(conj, lista):
  """(features de `lista` que existem no conjunto e não são vazamento, colunas de vazamento)."""
  vazadas = _vazadas(conj)
  return [f for f in lista if f in conj.df.columns and f not in vazadas], vazadas


def prever_quantis(conj, lista):
  usadas, vazadas = presentes(conj, lista)
  return core_quantis.prever_quantis_fora_do_fold(conj.df, usadas, conj.alvo, vazadas)


def bloco_comodo(conjs: dict, prev, ambiente: str = None) -> dict:
  """Bloco `comodo` da avaliação (core/comodo.py), com o piso (só radio) em cache por conjunto.

  `prev`: previsões dos quatro alvos (comodo.prever ou comodo.de_previsoes). A régua usa sempre o
  perfil de norma. `ambiente` vazio ou None quer dizer todos.
  """
  limiares = core_aplicacoes.carregar_perfil('norma')
  df = core_qoe.conjunto_qoe(conjs)
  meta = {'datasets': list(conjs[core_comodo.DN].datasets), 'ambiente': ambiente or 'todos'}
  chave = (tuple(meta['datasets']), meta['ambiente'], core_comodo.VERSAO_COMODO)
  if chave not in _piso_cache:
    vazadas = {alvo: _vazadas(c) for alvo, c in conjs.items()}
    _piso_cache[chave] = core_comodo.tabela_posicoes(df, core_comodo.prever(conjs, ['radio'], vazadas), limiares)
  return core_comodo.bloco(core_comodo.tabela_posicoes(df, prev, limiares), _piso_cache[chave], meta)


def avaliacao_completa(conjunto, ambiente: str, features: list, denominador: dict = None, progresso=None,
                       perfil_qoe: str = 'atual') -> dict:
  """Avaliação dos quatro alvos, de "atende em throughput" e de "atende completo", guardada junto da versão.

  `conjunto(alvo)` devolve o Conjunto daquele alvo; é chamado uma vez por alvo, logo depois do aviso
  de progresso da etapa. `ambiente` vazio ou None quer dizer todos. Latência e jitter levam também o
  resumo quantílico (p50 e p90). Colunas hoje marcadas como vazamento saem da conta e ficam em
  `removidas_por_vazamento` (a versão salva antes da marcação continua avaliável, como no
  benchmark). `progresso(evento)` recebe {'etapa', 'passo', 'passos'} antes de cada uma das seis
  etapas (a última é a régua por cômodo; `perfil_qoe` define os limiares do "atende").
  """
  avisar = progresso or (lambda evento: None)
  saida, previsoes, quantis = {}, {}, {}
  aplicacoes = core_aplicacoes.carregar_perfil(perfil_qoe)
  conjs, removidas = {}, set()
  for passo, alvo in enumerate(TARGETS):
    avisar({'etapa': ETAPAS[alvo], 'passo': passo, 'passos': N_ETAPAS})
    conj = conjunto(alvo)
    conjs[alvo] = conj
    vazadas = _vazadas(conj)
    usadas = [f for f in features if f not in vazadas]
    fora = [f for f in features if f in vazadas]
    removidas.update(fora)
    resumo, previsoes[alvo] = core_avaliacao.avaliar(conj, usadas, vazadas, com_previsoes=True,
                                                     denominador=(denominador or {}).get(alvo))
    saida[alvo] = dict(resumo, datasets=conj.datasets, ambiente=ambiente or 'todos',
                       versao_tabela=core_features.versao_tabela(),
                       versao_catalogo=core_features.CATALOGO_VERSAO,
                       removidas_por_vazamento=fora)
    if alvo in core_quantis.ALVOS_QUANTILICOS:
      quantis[alvo] = prever_quantis(conj, usadas)
      saida[alvo]['quantis'] = core_quantis.resumir_quantis(quantis[alvo], resumo['n'])
  avisar({'etapa': 'atende', 'passo': N_ETAPAS - 2, 'passos': N_ETAPAS})
  usadas = [f for f in features if f not in removidas]
  saida['atende_throughput'] = core_avaliacao.atende(previsoes['speedtest_down_mbps'],
                                                     previsoes['speedtest_up_mbps'], aplicacoes)
  conj_dn, conj_up = conjs['speedtest_down_mbps'], conjs['speedtest_up_mbps']
  den = denominador or {}
  decisoes = core_limiar.decisoes_atende(conj_dn, conj_up, usadas, aplicacoes,
                                         den.get(conj_dn.alvo), den.get(conj_up.alvo))
  saida['atende_ajustado'] = dict(core_limiar.resumir_decisoes(decisoes),
                                  fatores_producao=core_limiar.fatores_producao(
                                    conj_dn, conj_up, usadas, aplicacoes, den.get(conj_dn.alvo),
                                    den.get(conj_up.alvo)))
  saida['atende_completo'] = core_quantis.atende_completo(previsoes['speedtest_down_mbps'],
                                                          previsoes['speedtest_up_mbps'],
                                                          quantis['latency_ms'], quantis['jitter_ms'], aplicacoes)
  avisar({'etapa': 'cômodo', 'passo': N_ETAPAS - 1, 'passos': N_ETAPAS})
  prev = core_comodo.de_previsoes(conjs['speedtest_down_mbps'].df, previsoes['speedtest_down_mbps'],
                                  previsoes['speedtest_up_mbps'], quantis['latency_ms'], quantis['jitter_ms'])
  saida['comodo'] = bloco_comodo(conjs, prev, ambiente)
  saida['perfil'] = perfil_qoe
  saida['removidas_por_vazamento'] = sorted(removidas)
  return saida

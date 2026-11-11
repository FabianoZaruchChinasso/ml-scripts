"""Portão de promoção: decide se uma definição candidata substitui a ativa.

As duas definições são comparadas nas mesmas linhas: previsões fora do fold (LOGO por prédio) recalculadas
nos dados da candidata, com as mesmas funções da avaliação. Download e upload decidem pelo Δ MAE
(core_avaliacao.veredito_promocao, sem o "atende"); latência e jitter, pelo Δ pinball do p90 e pela cobertura
do p90 (core_quantis.veredito_quantis). Não importa o MLflow: src/ml/portao_mlflow.py lê o Registry, grava o
veredito e move o alias.
"""

import pandas as pd

from ml.core import avaliacao as core_avaliacao
from ml.core import completa as core_completa
from ml.core import quantis as core_quantis

ALVOS = tuple(core_avaliacao.ALVOS_COM_TETO) + tuple(core_quantis.ALVOS_QUANTILICOS)


def _prever_pontual(conj, definicao: dict):
  usadas, vazadas = core_completa.presentes(conj, definicao['features'])
  return core_avaliacao.prever_fora_do_fold(conj.df, usadas, conj.alvo, vazadas,
                                            denominador=(definicao.get('denominador') or {}).get(conj.alvo))


def comparar(conjs: dict, candidata: dict, ativa: dict) -> dict:
  """{alvo: bloco} com a diferença candidata − ativa e o veredito de cada alvo.

  `conjs`: {alvo: Conjunto} dos quatro alvos. `candidata` e `ativa`: {'features', 'denominador'}, com o
  denominador no formato de modelos.json ({alvo: coluna} ou {alvo: {'coluna', 'radio'}}) ou None.
  """
  por_alvo = {}
  for alvo in core_avaliacao.ALVOS_COM_TETO:
    delta = core_avaliacao.delta_mae(_prever_pontual(conjs[alvo], candidata), _prever_pontual(conjs[alvo], ativa))
    por_alvo[alvo] = {'delta_mae': delta, 'veredito': core_avaliacao.veredito_promocao(delta)}
  for alvo in core_quantis.ALVOS_QUANTILICOS:
    nova = core_completa.prever_quantis(conjs[alvo], candidata['features'])
    delta = core_quantis.delta_pinball(nova, core_completa.prever_quantis(conjs[alvo], ativa['features']))
    cobertura = round(core_quantis.cobertura(nova['y'], nova['q90']), 4)
    por_alvo[alvo] = {'delta_pinball': delta, 'cobertura': cobertura,
                      'veredito': core_quantis.veredito_quantis(delta, cobertura)}
  return por_alvo


def decidir(por_alvo: dict) -> dict:
  """Promove se nenhum alvo piorar e pelo menos um melhorar; empate mantém a ativa."""
  resultados = {alvo: bloco['veredito']['resultado'] for alvo, bloco in por_alvo.items()}
  piores = [a for a, r in resultados.items() if r == 'pior']
  melhores = [a for a, r in resultados.items() if r == 'melhor']
  if piores:
    return {'promover': False, 'resultado': 'pior', 'motivo': f'a candidata piora em {", ".join(piores)}'}
  if melhores:
    return {'promover': True, 'resultado': 'melhor',
            'motivo': f'a candidata melhora em {", ".join(melhores)} sem piorar nos outros alvos'}
  return {'promover': False, 'resultado': 'empate',
          'motivo': 'empate nos quatro alvos: com estes prédios não dá para separar as duas versões; a ativa fica'}


def situacao_mesma_definicao(fp_candidata, fp_ativa) -> str:
  """Re-treino da mesma definição: 'igual' (mesmos dados), 'dado_novo' (os da ativa e mais algum) ou
  'dados_diferentes' (não contém os da ativa)."""
  candidata, ativa = set(fp_candidata), set(fp_ativa)
  if candidata == ativa:
    return 'igual'
  return 'dado_novo' if candidata > ativa else 'dados_diferentes'


def decidir_sem_comparar(situacao: str) -> dict:
  """Mesma definição em que o portão não compara: mantém a ativa e explica."""
  if situacao == 'igual':
    return {'promover': False, 'resultado': 'igual', 'motivo': 'mesma definição e mesmos dados da ativa: nada a trocar'}
  return {'promover': False, 'resultado': 'dados_diferentes',
          'motivo': 'mesma definição com dados que não contêm os da ativa: o portão não compara; '
                    'se for o caso, troque à mão com src/ml/ativar_mlflow.py'}


def _treino(conj, ids_antigos) -> pd.Series:
  return conj.df['_ds'].isin(list(ids_antigos))


def comparar_dado_novo(conjs: dict, definicao: dict, ids_antigos) -> dict:
  """Mesma receita, dois treinos: só as linhas dos datasets `ids_antigos` ("ativa") contra todas
  ("candidata"). Mesmo formato de `comparar`; as previsões são das mesmas linhas (LOGO por prédio)."""
  por_alvo = {}
  for alvo in core_avaliacao.ALVOS_COM_TETO:
    conj = conjs[alvo]
    usadas, vazadas = core_completa.presentes(conj, definicao['features'])
    den = (definicao.get('denominador') or {}).get(alvo)
    com_tudo = core_avaliacao.prever_fora_do_fold(conj.df, usadas, alvo, vazadas, denominador=den)
    so_antigo = core_avaliacao.prever_fora_do_fold(conj.df, usadas, alvo, vazadas, denominador=den,
                                                   treinar_em=_treino(conj, ids_antigos))
    delta = core_avaliacao.delta_mae(com_tudo, so_antigo)
    por_alvo[alvo] = {'delta_mae': delta, 'veredito': core_avaliacao.veredito_promocao(delta)}
  for alvo in core_quantis.ALVOS_QUANTILICOS:
    conj = conjs[alvo]
    usadas, vazadas = core_completa.presentes(conj, definicao['features'])
    com_tudo = core_quantis.prever_quantis_fora_do_fold(conj.df, usadas, alvo, vazadas)
    so_antigo = core_quantis.prever_quantis_fora_do_fold(conj.df, usadas, alvo, vazadas,
                                                         treinar_em=_treino(conj, ids_antigos))
    delta = core_quantis.delta_pinball(com_tudo, so_antigo)
    cobertura = round(core_quantis.cobertura(com_tudo['y'], com_tudo['q90']), 4)
    por_alvo[alvo] = {'delta_pinball': delta, 'cobertura': cobertura,
                      'veredito': core_quantis.veredito_quantis(delta, cobertura)}
  return por_alvo


def decidir_dado_novo(por_alvo: dict) -> dict:
  """Re-treino com dado novo: promove se nenhum alvo piorar. Mais dado da mesma receita é a expectativa;
  com 6 prédios, exigir "melhor" deixaria a ativa presa no dado velho."""
  piores = [a for a, b in por_alvo.items() if b['veredito']['resultado'] == 'pior']
  if piores:
    return {'promover': False, 'resultado': 'pior', 'motivo': f'o dado novo piora {", ".join(piores)}'}
  return {'promover': True, 'resultado': 'dado_novo',
          'motivo': 'mesma definição com dado novo, sem piorar nenhum alvo'}

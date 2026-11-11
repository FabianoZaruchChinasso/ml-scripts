"""Portão de promoção: decide se uma versão registrada de 'qoe-wifi' substitui a ativa (alias 'ativo').

VERSAO=<n> escolhe a candidata (padrão: a versão registrada mais recente, a que versao_mlflow.py acabou de
gravar). As duas definições são comparadas nos dados da candidata (core/portao.py): download e upload pelo
Δ MAE, latência e jitter pelo Δ pinball e pela cobertura do p90. Promove se nenhum alvo piorar e pelo menos
um melhorar. A mesma definição com dado novo é comparada consigo mesma treinada só com o dado da ativa, e é
promovida se nenhum alvo piorar; sem versão ativa, a candidata é promovida. Quando a candidata traz
datasets que a ativa não viu, mede também a degradação da ativa: o erro do pacote dela nessas linhas contra o
esperado (core/degradacao.py), só informativo. SIMULAR=1 grava o veredito sem mover o alias. O veredito fica no run da candidata (tags portao_*
e portao.json) e na versão registrada (tags portao e portao_contra). O código de saída é 0 tanto para
"promovida" quanto para "mantida".

  venv/bin/python src/ml/portao_mlflow.py
  VERSAO=6 venv/bin/python src/ml/portao_mlflow.py
  SIMULAR=1 VERSAO=4 venv/bin/python src/ml/portao_mlflow.py
"""

import json
import os
import sys
from datetime import date

import mlflow

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import carga as core_carga
from ml.core import degradacao as core_degradacao
from ml.core import modelos as core_modelos
from ml.core import pacote as core_pacote
from ml.core import pacote_mlflow as core_pacote_mlflow
from ml.core import portao as core_portao
from ml.core import registro_mlflow as core_registro_mlflow
from ml.core import registry_mlflow as core_registry

AUXILIARES = ('comodo_nota', 'comodo_lo90', 'comodo_hi90', 'atende_completo')


def _definicao(registro: dict, nome: str) -> dict:
  core_registry.escolher_definicao(nome, registro)   # sai com mensagem se a definição não existir
  versao = registro['versoes'][nome]
  return {'features': list(versao['features']), 'denominador': versao.get('denominador')}


def _ids(fingerprints: list) -> list:
  """Ids em data/ dos datasets da candidata, na ordem dos fingerprints."""
  por_fp = {d['fingerprint']: d['id'] for d in core_carga.descobertos() if d.get('usable')}
  faltam = [f for f in fingerprints if f not in por_fp]
  if faltam:
    raise SystemExit(f'os dados da candidata não estão em data/ (fingerprints {faltam}): '
                     'o portão não tem como reproduzi-los')
  return [por_fp[f] for f in fingerprints]


def _antigos(ids: list, candidata: dict, ativa: dict) -> list:
  """Ids da candidata cujo dataset a ativa já viu (os outros são o dado novo)."""
  vistos = set(ativa['fingerprints'])
  return [i for i, fp in zip(ids, candidata['fingerprints']) if fp in vistos]


def _degradacao(ativa: dict, conjs: dict, antigos: list) -> dict:
  """Erro do pacote da ativa nas linhas que ele nunca viu, contra o esperado gravado no run dela."""
  mlflow.set_tracking_uri(core_registro_mlflow.uri_rastreamento())
  pacote = core_pacote_mlflow.carregar(f"models:/{core_registry.NOME_MODELO}/{ativa['versao']}")
  esperado = core_registro_mlflow.cliente().get_run(ativa['run_id']).data.metrics
  return core_degradacao.medir(pacote, conjs, antigos, esperado)


def _auxiliares(cli, run_id: str) -> dict:
  metricas = cli.get_run(run_id).data.metrics
  return {chave: metricas.get(chave) for chave in AUXILIARES}


def gravar(candidata: dict, ativa, decisao: dict, por_alvo, simular: bool, degradacao=None) -> None:
  """portao.json e tags no run da candidata; tags na versão registrada."""
  cli = core_registro_mlflow.cliente()
  contra = str(ativa['versao']) if ativa else 'nenhuma'
  relatorio = {
    'data': date.today().isoformat(), 'candidata': candidata, 'ativa': ativa, 'decisao': decisao,
    'simulado': simular, 'por_alvo': por_alvo, 'degradacao': degradacao,
    'auxiliares': {'candidata': _auxiliares(cli, candidata['run_id']),
                   'ativa': _auxiliares(cli, ativa['run_id']) if ativa else None,
                   'nota': 'métricas gravadas em cada run, não decidem; podem ser de dados diferentes'}}
  # json com default=float: os blocos do core podem trazer números do numpy.
  cli.log_dict(candidata['run_id'], json.loads(json.dumps(relatorio, default=float)), 'portao.json')
  tags = {'portao': decisao['resultado'], 'portao_promovida': 'sim' if decisao['promover'] and not simular else 'nao',
          'portao_contra': contra, 'portao_simulado': 'sim' if simular else 'nao',
          'portao_degradacao': ('sem_dado_novo' if degradacao is None
                                else 'sim' if core_degradacao.degradou(degradacao) else 'nao')}
  for chave, valor in tags.items():
    cli.set_tag(candidata['run_id'], chave, valor)
  core_registry.marcar_portao(candidata['versao'], {'portao': decisao['resultado'], 'portao_contra': contra})


def _imprimir(candidata: dict, ativa, decisao: dict, por_alvo, simular: bool, degradacao=None) -> None:
  for alvo, bloco in (por_alvo or {}).items():
    print(f"  {alvo}: {bloco['veredito']['resultado']} ({bloco['veredito']['motivo']})")
  for alvo, bloco in (degradacao or {}).items():
    print(f"  degradação da ativa em {alvo}: {bloco['resultado']} ({bloco['motivo']})")
  contra = f"{ativa['versao']} ({ativa['definicao']})" if ativa else 'nenhuma'
  print(f"candidata {candidata['versao']} ({candidata['definicao']}) contra a ativa {contra}: "
        f"{decisao['resultado']}; {decisao['motivo']}")
  if decisao['promover'] and simular:
    print('SIMULAR=1: seria promovida, o alias não mudou')
  elif decisao['promover']:
    print(f"promovida: {core_registry.NOME_MODELO}@{core_registry.ALIAS} -> {candidata['versao']}")
  else:
    print('mantida: o alias não mudou')


def main():
  simular = os.environ.get('SIMULAR') == '1'
  numero = os.environ.get('VERSAO')
  if numero and not numero.isdigit():
    raise SystemExit(f'VERSAO={numero!r}: use o número da versão registrada')
  try:
    candidata = core_registry.info_versao(int(numero) if numero else core_registry.versao_mais_recente())
  except ValueError as erro:
    raise SystemExit(str(erro)) from erro
  try:
    ativa = core_registry.info_versao(core_registry.ativa()['versao'])
  except core_registry.SemVersaoAtiva:
    ativa = None
  if ativa and ativa['versao'] == candidata['versao']:
    print(f"a versão {candidata['versao']} ({candidata['definicao']}) já é a ativa: nada a decidir")
    return
  registro = core_modelos.carregar()
  def_candidata = _definicao(registro, candidata['definicao'])
  por_alvo, degradacao = None, None
  if ativa is None:
    decisao = {'promover': True, 'resultado': 'primeira', 'motivo': 'não há versão ativa'}
  elif candidata['definicao'] == ativa['definicao']:
    situacao = core_portao.situacao_mesma_definicao(candidata['fingerprints'], ativa['fingerprints'])
    if situacao != 'dado_novo':
      decisao = core_portao.decidir_sem_comparar(situacao)
    else:
      ids = _ids(candidata['fingerprints'])
      antigos = _antigos(ids, candidata, ativa)
      print(f"{candidata['definicao']} com dado novo: treino só com {antigos} contra treino com {ids}")
      conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
      por_alvo = core_portao.comparar_dado_novo(conjs, def_candidata, ids_antigos=antigos)
      decisao = core_portao.decidir_dado_novo(por_alvo)
      degradacao = _degradacao(ativa, conjs, antigos)
  else:
    def_ativa = _definicao(registro, ativa['definicao'])
    ids = _ids(candidata['fingerprints'])
    print(f"comparando {candidata['definicao']} (versão {candidata['versao']}) com {ativa['definicao']} "
          f"(versão {ativa['versao']}) nos datasets {ids}")
    conjs = {alvo: core_carga.carregar(alvo, ids=ids) for alvo in core_pacote.PREFIXOS}
    por_alvo = core_portao.comparar(conjs, def_candidata, def_ativa)
    decisao = core_portao.decidir(por_alvo)
    antigos = _antigos(ids, candidata, ativa)
    if len(antigos) < len(ids):
      degradacao = _degradacao(ativa, conjs, antigos)
  gravar(candidata, ativa, decisao, por_alvo, simular, degradacao)
  if decisao['promover'] and not simular:
    core_registry.ativar(candidata['versao'])
  _imprimir(candidata, ativa, decisao, por_alvo, simular, degradacao)


if __name__ == '__main__':
  main()

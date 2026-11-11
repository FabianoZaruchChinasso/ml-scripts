"""Model Registry do MLflow: o modelo registrado 'qoe-wifi' e o alias 'ativo'.

"Definição" é uma entrada de core/modelos.json (v1, ..., v5): features, denominador e perfil.
"Versão registrada" é o número do Registry (1, 2, 3...): o pacote treinado com uma definição sobre um
conjunto de dados. Cada versão registrada leva a tag 'definicao'. O alias 'ativo' é a única fonte da
versão ativa; o campo 'ativo' de modelos.json saiu em 2026-11-11.
"""

import os
from typing import Optional

import mlflow
from mlflow.exceptions import MlflowException

from ml.core import registro_mlflow as core_registro_mlflow

NOME_MODELO = 'qoe-wifi'
ALIAS = 'ativo'
# Modelo inexistente: RESOURCE_DOES_NOT_EXIST; alias ou versão inexistente: INVALID_PARAMETER_VALUE (mlflow 3.15.1).
_AUSENTE = ('RESOURCE_DOES_NOT_EXIST', 'INVALID_PARAMETER_VALUE')
_COMO_RESOLVER = ('Passe a definição (MODELO=<definição> ou --modelo <definição>) '
                  'ou ative uma com src/ml/ativar_mlflow.py')


class SemVersaoAtiva(RuntimeError):
  """Não há banco do MLflow, modelo registrado ou alias 'ativo'."""


def _cliente_de_leitura():
  """Cliente do MLflow que não cria o banco: na máquina de outra pessoa, ler não pode deixar um mlflow.db vazio."""
  uri = core_registro_mlflow.uri_rastreamento()
  if uri.startswith('sqlite:///') and not os.path.exists(uri[len('sqlite:///'):]):
    raise SemVersaoAtiva(f'não há banco do MLflow em {uri}')
  return core_registro_mlflow.cliente()


def registrar(model_uri: str, definicao: str, fingerprints: list, versao_pacote: str) -> int:
  """Cria uma versão de NOME_MODELO a partir do modelo em `model_uri` e devolve o número. Não move o alias."""
  mlflow.set_tracking_uri(core_registro_mlflow.uri_rastreamento())
  versao = mlflow.register_model(model_uri, NOME_MODELO, tags={
    'definicao': definicao, 'fingerprints': ','.join(fingerprints), 'versao_pacote': versao_pacote})
  return int(versao.version)


def versao_da_definicao(definicao: str) -> int:
  """A versão registrada mais recente da definição. ValueError se ela nunca foi registrada."""
  achadas = core_registro_mlflow.cliente().search_model_versions(
    f"name='{NOME_MODELO}' and tag.definicao='{definicao}'")
  if not achadas:
    raise ValueError(f'a definição {definicao!r} não tem versão registrada em {NOME_MODELO!r}; '
                     f'rode MODELO={definicao} venv/bin/python src/ml/versao_mlflow.py')
  return max(int(v.version) for v in achadas)


def versao_mais_recente() -> int:
  """O maior número de versão registrada. ValueError se não houver nenhuma."""
  achadas = core_registro_mlflow.cliente().search_model_versions(f"name='{NOME_MODELO}'")
  if not achadas:
    raise ValueError(f'nenhuma versão registrada de {NOME_MODELO!r}; rode src/ml/versao_mlflow.py')
  return max(int(v.version) for v in achadas)


def info_versao(versao: int) -> dict:
  """{'versao', 'definicao', 'run_id', 'fingerprints'} de uma versão registrada. ValueError se não existir."""
  cli = core_registro_mlflow.cliente()
  try:
    v = cli.get_model_version(NOME_MODELO, str(versao))
  except MlflowException as erro:
    if erro.error_code in _AUSENTE:
      raise ValueError(f'{NOME_MODELO!r} não tem a versão {versao}') from erro
    raise
  return {'versao': int(v.version), 'definicao': v.tags.get('definicao'), 'run_id': v.run_id,
          'fingerprints': [f for f in (v.tags.get('fingerprints') or '').split(',') if f]}


def marcar_portao(versao: int, tags: dict) -> None:
  """Grava as tags do veredito do portão na versão registrada."""
  cli = core_registro_mlflow.cliente()
  for chave, valor in tags.items():
    cli.set_model_version_tag(NOME_MODELO, str(versao), chave, str(valor))


def ativa() -> dict:
  """{'versao', 'definicao', 'run_id'} da versão apontada pelo alias. SemVersaoAtiva se faltar algo."""
  cli = _cliente_de_leitura()
  try:
    v = cli.get_model_version_by_alias(NOME_MODELO, ALIAS)
  except MlflowException as erro:
    if erro.error_code in _AUSENTE:
      raise SemVersaoAtiva(f'o modelo {NOME_MODELO!r} não tem o alias {ALIAS!r} '
                           f'em {core_registro_mlflow.uri_rastreamento()}') from erro
    raise
  return {'versao': int(v.version), 'definicao': v.tags.get('definicao'), 'run_id': v.run_id}


def definicao_ativa() -> Optional[str]:
  """A definição da versão ativa, ou None sem banco, sem modelo ou sem alias."""
  try:
    return ativa()['definicao']
  except SemVersaoAtiva:
    return None


def ativar(versao: int) -> dict:
  """Move o alias para `versao`. ValueError se ela não existir."""
  cli = core_registro_mlflow.cliente()
  try:
    nova = cli.get_model_version(NOME_MODELO, str(versao))
  except MlflowException as erro:
    if erro.error_code in _AUSENTE:
      raise ValueError(f'{NOME_MODELO!r} não tem a versão {versao}') from erro
    raise
  anterior = cli.get_registered_model(NOME_MODELO).aliases.get(ALIAS)
  definicao_anterior = None
  if anterior is not None:
    definicao_anterior = cli.get_model_version(NOME_MODELO, str(anterior)).tags.get('definicao')
  cli.set_registered_model_alias(NOME_MODELO, ALIAS, str(versao))
  return {'anterior': None if anterior is None else int(anterior), 'atual': int(versao),
          'definicao_anterior': definicao_anterior, 'definicao_atual': nova.tags.get('definicao')}


def escolher_definicao(explicita: Optional[str], registro: dict) -> str:
  """A definição que um script deve usar: `explicita` se vier; senão a do alias.

  Sai com SystemExit (mensagem para quem rodou o script) sem alias ou com uma definição que não existe
  em core/modelos.json.
  """
  if explicita:
    nome, origem = explicita, 'pedida'
  else:
    try:
      nome = ativa()['definicao']
    except SemVersaoAtiva as erro:
      raise SystemExit(f'nenhuma versão ativa no Model Registry ({erro}). {_COMO_RESOLVER}') from erro
    origem = f'ativa no Registry ({NOME_MODELO}@{ALIAS})'
  if nome not in registro['versoes']:
    raise SystemExit(f'a definição {origem} {nome!r} não existe em core/modelos.json; '
                     f'definições: {sorted(registro["versoes"])}')
  return nome

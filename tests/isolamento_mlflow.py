"""Aponta o MLflow para um banco que não existe, durante um módulo de testes inteiro.

Os testes que importam o Studio usam no módulo:

  from isolamento_mlflow import isolar as setUpModule, restaurar as tearDownModule

Sem isso, o Studio leria o alias 'ativo' do mlflow.db da raiz, e o resultado dos testes dependeria da
máquina. Com o banco inexistente, registry_mlflow.definicao_ativa() devolve None sem criar o arquivo;
o teste que precisa de uma ativa faz mock de api.core_registry.definicao_ativa.
"""

import os
import tempfile
from unittest import mock

_estado = {}


def isolar():
  pasta = tempfile.TemporaryDirectory()
  patch = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{pasta.name}/nao-existe.db'})
  patch.start()
  _estado.update(pasta=pasta, patch=patch)


def restaurar():
  _estado.pop('patch').stop()
  _estado.pop('pasta').cleanup()


def com_ativa(nome: str):
  """(setUpModule, tearDownModule) que isolam o MLflow e fixam `nome` como a versão ativa (alias 'ativo').

  Uso: `setUpModule, tearDownModule = com_ativa('v1')`. Vale para o módulo inteiro e para quem lê o alias
  pelo módulo ml.core.registry_mlflow, como o Studio. Troca o atributo à mão, e não com mock.patch.start:
  vários testes chamam mock.patch.stopall no cleanup, que desligaria o patch no meio do módulo.
  """
  guardado = {}

  def subir():
    from ml.core import registry_mlflow
    isolar()
    guardado['original'] = registry_mlflow.definicao_ativa
    registry_mlflow.definicao_ativa = lambda: nome

  def descer():
    from ml.core import registry_mlflow
    registry_mlflow.definicao_ativa = guardado.pop('original')
    restaurar()

  return subir, descer

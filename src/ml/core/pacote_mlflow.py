"""Grava e carrega o pacote de uma versão (core/pacote.py) como modelo pyfunc do MLflow.

O código de ml/core vai dentro do modelo gravado, para que ele carregue sem o repositório: quem
serve o pacote só precisa das bibliotecas (mlflow, scikit-learn, skops, pandas).
"""

import json
import os
import shutil
import tempfile
import zipfile

import mlflow
import mlflow.pyfunc
import skops.io

from ml.core import pacote as core_pacote

NOME = 'pacote'
# O imputer do modelo da régua guarda um numpy.dtype, que o skops não confia por padrão.
TIPOS_CONFIAVEIS = ['numpy.dtype']
_CORE = os.path.dirname(os.path.abspath(__file__))


class PacoteQoE(mlflow.pyfunc.PythonModel):
  """Recebe linhas com as colunas de receita['entradas'] e devolve as de pacote.SAIDAS."""

  def load_context(self, context):
    with open(context.artifacts['receita'], encoding='utf-8') as f:
      receita = json.load(f)
    modelos = {nome: skops.io.load(caminho, trusted=TIPOS_CONFIAVEIS)
               for nome, caminho in context.artifacts.items() if nome != 'receita'}
    self.pacote = core_pacote.Pacote(modelos, receita)

  def predict(self, context, model_input, params=None):
    return core_pacote.prever(self.pacote, model_input)[0]


def _copia_do_core(destino: str) -> str:
  """ml/core numa pasta 'ml' só dele: code_paths copia a pasta inteira, e src/ml também tem o Studio e os scripts."""
  raiz = os.path.join(destino, 'ml')
  shutil.copytree(_CORE, os.path.join(raiz, 'core'), ignore=shutil.ignore_patterns('__pycache__'))
  return raiz


def gravar(pacote: core_pacote.Pacote, exemplo):
  """Grava o pacote no run ativo, em NOME, e devolve o ModelInfo. `exemplo`: poucas linhas com as colunas de entradas.

  Sem assinatura do MLflow (signature=False): ela recusa um inteiro ausente em coluna inteira e um
  inteiro em coluna decimal, e os contadores chegam inteiros e às vezes faltam. Quem valida a entrada
  é pacote.prever. O exemplo fica gravado junto do modelo, como documentação.
  """
  with tempfile.TemporaryDirectory() as tmp:
    artefatos = {}
    for nome, modelo in pacote.modelos.items():
      artefatos[nome] = os.path.join(tmp, f'{nome}.skops')
      skops.io.dump(modelo, artefatos[nome], compression=zipfile.ZIP_DEFLATED)
    artefatos['receita'] = os.path.join(tmp, 'receita.json')
    with open(artefatos['receita'], 'w', encoding='utf-8') as f:
      json.dump(pacote.receita, f, ensure_ascii=False, indent=1)
    return mlflow.pyfunc.log_model(name=NOME, python_model=PacoteQoE(), artifacts=artefatos,
                                   code_paths=[_copia_do_core(tmp)], input_example=exemplo, signature=False)


def carregar(uri: str) -> core_pacote.Pacote:
  """O pacote gravado em `uri` (por exemplo 'runs:/<run_id>/pacote')."""
  return mlflow.pyfunc.load_model(uri).unwrap_python_model().pacote

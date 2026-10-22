"""Única porta do Studio para o MLflow: URI, cliente, experimento, nomes e links.

Recusa apontar para o MLflow da raiz do repositório (mlflow.db, mlruns/): é do
Fabiano, e o benchmark e o regression_mlflow.py gravam lá.
"""

import math
import os

import mlflow
from mlflow import MlflowClient

from studio import caminhos

EXPERIMENTO = 'QoE Studio'
ALVOS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')
ALIAS_ATIVO = 'ativo'


def uri() -> str:
  """A URI em uso, se for o servidor local do Studio ou um sqlite fora do mlflow.db da raiz."""
  u = caminhos.MLFLOW_URI or ''
  if u.startswith(('http://127.0.0.1:', 'http://localhost:')):
    return u
  if u.startswith('sqlite:///'):
    path = os.path.abspath(u[len('sqlite:///'):])
    if path != os.path.join(caminhos.REPO, 'mlflow.db'):
      return u
  raise RuntimeError(f'URI do MLflow recusada: {u!r}. O Studio só usa o próprio servidor local '
                     'ou um sqlite fora do mlflow.db da raiz.')


def cliente() -> MlflowClient:
  """Cliente apontado para o MLflow do Studio. Ajusta também a URI global (start_run, load_model)."""
  u = uri()
  mlflow.set_tracking_uri(u)
  mlflow.set_registry_uri(u)
  return MlflowClient(tracking_uri=u, registry_uri=u)


def experimento_id(cli: MlflowClient) -> str:
  exp = cli.get_experiment_by_name(EXPERIMENTO)
  if exp is not None:
    return exp.experiment_id
  return cli.create_experiment(EXPERIMENTO, artifact_location=caminhos.ARTEFATOS_URI)


def nome_modelo(alvo: str) -> str:
  if alvo not in ALVOS:
    raise ValueError(f'alvo {alvo!r} desconhecido; esperado um de {list(ALVOS)}')
  return f'studio-{alvo}'


def link_run(experimento: str, run_id: str) -> str:
  return f'{caminhos.MLFLOW_UI}/#/experiments/{experimento}/runs/{run_id}'


def link_versao(nome: str, versao) -> str:
  return f'{caminhos.MLFLOW_UI}/#/models/{nome}/versions/{versao}'


def registrar_metricas(metricas: dict) -> None:
  """log_metrics só com números finitos: NaN (R² de prédio com 1 linha) fica de fora."""
  mlflow.log_metrics({k: float(v) for k, v in metricas.items()
                      if isinstance(v, (int, float)) and math.isfinite(v)})


def disponivel() -> bool:
  """sqlite (testes) está sempre disponível; o servidor do Studio, quando responde ao /health."""
  u = uri()
  if u.startswith('sqlite:///'):
    return True
  from studio import mlflow_servidor
  return mlflow_servidor.saudavel(u)

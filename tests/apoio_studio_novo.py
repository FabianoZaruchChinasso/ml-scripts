"""Apoio dos testes do Studio novo: CSVs pequenos e pastas temporárias no lugar das reais."""

import contextlib
import json
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from studio import caminhos, catalogo, predios  # noqa: E402

PREDIOS = {'aliases': {}, 'predios': {
  'alfa': {'rotulo': 'Alfa', 'studio': 'alfa', 'ambiente': 'domestico', 'prefixos': ['alfa'],
           'tetos_wan': {'speedtest_down_mbps': 100.0}},
  'beta': {'rotulo': 'Beta', 'studio': 'beta', 'ambiente': 'corporativo', 'prefixos': ['beta']},
  'gama': {'rotulo': 'Gama', 'studio': 'gama', 'ambiente': 'corporativo', 'prefixos': ['gama']},
}}


def frame(locais, n=12, semente=0, deslocamento=0.0) -> pd.DataFrame:
  """n linhas por local, geração atual (combo, n_clients, station_x, house_x0), alvos ligados ao SNR."""
  rng = np.random.default_rng(semente)
  linhas = []
  for local in locais:
    for i in range(n):
      snr = float(rng.uniform(10, 40))
      linhas.append({
        'local': local,
        'router_snr': snr,
        'router_signal_dbm': -90.0 + snr,
        'router_tx_retries': float(rng.integers(0, 50)),
        'speedtest_down_mbps': round(2.0 * snr + deslocamento + float(rng.normal(0, 1)), 6),
        'speedtest_up_mbps': round(snr + float(rng.normal(0, 1)), 6),
        'latency_ms': round(60.0 - snr + float(rng.normal(0, 1)), 6),
        'jitter_ms': round(10.0 - snr / 5.0 + float(rng.uniform(0, 1)), 6),
        'combo': 'c1', 'n_clients': 1,
        'station_x': 100.0 + i, 'station_y': 200.0, 'station_z': 0.0,
        'house_x0': 400.0, 'house_y0': 900.0, 'house_z0': 280.0,
        'router_x': 50.0, 'router_y': 60.0, 'router_z': 100.0,
      })
  return pd.DataFrame(linhas)


def gravar_csv(pasta: str, nome: str, df: pd.DataFrame) -> str:
  os.makedirs(pasta, exist_ok=True)
  path = os.path.join(pasta, nome)
  df.to_csv(path, index=False)
  return path


@contextlib.contextmanager
def pastas_temporarias(registro: dict = None):
  """Aponta data/, .studio/, predios.json e docs/planta/ para uma pasta temporária."""
  raiz = tempfile.mkdtemp(prefix='studio-novo-')
  p = SimpleNamespace(
    raiz=raiz,
    data=os.path.join(raiz, 'data'),
    estado=os.path.join(raiz, 'estado'),
    uploads=os.path.join(raiz, 'estado', 'uploads'),
    planta=os.path.join(raiz, 'planta'),
    predios_path=os.path.join(raiz, 'predios.json'),
  )
  for pasta in (p.data, p.uploads, p.planta):
    os.makedirs(pasta)
  with open(p.predios_path, 'w', encoding='utf-8') as handle:
    json.dump(registro if registro is not None else PREDIOS, handle)
  troca = {'DATA_DIR': p.data, 'ESTADO_DIR': p.estado, 'UPLOADS_DIR': p.uploads,
           'CONJUNTO_PATH': os.path.join(p.estado, 'conjunto.json'),
           'PREDIOS_PATH': p.predios_path, 'PLANTA_DIR': p.planta}
  with mock.patch.multiple(caminhos, **troca):
    catalogo.esquecer()
    predios.esquecer()
    try:
      yield p
    finally:
      catalogo.esquecer()
      predios.esquecer()
      shutil.rmtree(raiz, ignore_errors=True)


@contextlib.contextmanager
def mlflow_temporario():
  """MLflow do Studio num sqlite temporário, sem servidor. Restaura a URI global ao sair."""
  import mlflow
  raiz = tempfile.mkdtemp(prefix='studio-mlflow-')
  anterior = mlflow.get_tracking_uri()
  troca = {'MLFLOW_URI': 'sqlite:///' + os.path.join(raiz, 'mlflow.db'),
           'ARTEFATOS_URI': 'file://' + os.path.join(raiz, 'artefatos'),
           'MLFLOW_UI': 'http://127.0.0.1:5100'}
  with mock.patch.multiple(caminhos, **troca):
    try:
      yield raiz
    finally:
      mlflow.set_tracking_uri(anterior)
      mlflow.set_registry_uri(anterior)
      shutil.rmtree(raiz, ignore_errors=True)


def esperar_job(job_id: str, limite_s: float = 180.0) -> dict:
  from studio import fila
  fim = time.time() + limite_s
  while time.time() < fim:
    job = fila.job(job_id)
    if job['status'] in ('concluído', 'falhou'):
      return job
    time.sleep(0.05)
  raise AssertionError(f'job {job_id} não terminou em {limite_s} s')

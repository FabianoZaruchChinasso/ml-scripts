"""Processo filho `mlflow server` do Studio: backend e artefatos em .studio/, só em 127.0.0.1.

Nunca se conecta a um MLflow que já esteja rodando (pode ser o de outra pessoa):
com a porta ocupada, recusa.
"""

import os
import subprocess
import sys
import time
import urllib.request

from studio import caminhos, portas

ESPERA_S = 90

_estado = {'proc': None, 'log': None}


def comando(porta: int) -> list:
  return [sys.executable, '-m', 'mlflow', 'server',
          '--backend-store-uri', 'sqlite:///' + caminhos.MLFLOW_DB,
          '--artifacts-destination', caminhos.ARTEFATOS_DIR,
          '--host', '127.0.0.1', '--port', str(porta)]


def saudavel(url: str = None, timeout: float = 1.0) -> bool:
  try:
    with urllib.request.urlopen((url or caminhos.MLFLOW_URI) + '/health', timeout=timeout) as resposta:
      return resposta.status == 200
  except OSError:
    return False


def iniciar(porta: int = None) -> subprocess.Popen:
  porta = porta or caminhos.MLFLOW_PORTA
  if not portas.livre(porta):
    raise RuntimeError(f'porta {porta} ocupada: o Studio não se conecta a um MLflow que já está rodando')
  os.makedirs(caminhos.ARTEFATOS_DIR, exist_ok=True)
  log = open(os.path.join(caminhos.ESTADO_DIR, 'mlflow.log'), 'ab')
  # cwd em .studio/: qualquer arquivo solto que o servidor crie fica lá, nunca na raiz.
  proc = subprocess.Popen(comando(porta), stdout=log, stderr=subprocess.STDOUT, cwd=caminhos.ESTADO_DIR)
  _estado.update(proc=proc, log=log)
  limite = time.time() + ESPERA_S
  while time.time() < limite:
    if proc.poll() is not None:
      parar()
      raise RuntimeError(f'mlflow server saiu com código {proc.returncode}; veja .studio/mlflow.log')
    if saudavel(f'http://127.0.0.1:{porta}'):
      return proc
    time.sleep(0.5)
  parar()
  raise RuntimeError(f'mlflow server não respondeu em {ESPERA_S} s; veja .studio/mlflow.log')


def parar() -> None:
  proc, log = _estado['proc'], _estado['log']
  if proc is not None and proc.poll() is None:
    proc.terminate()
    try:
      proc.wait(10)
    except subprocess.TimeoutExpired:
      proc.kill()
  if log is not None:
    log.close()
  _estado.update(proc=None, log=None)


def reiniciar() -> subprocess.Popen:
  parar()
  return iniciar(caminhos.MLFLOW_PORTA)

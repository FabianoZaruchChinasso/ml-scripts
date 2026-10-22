"""Fila de jobs com um worker só: treinos e reavaliações rodam um por vez, fora da requisição."""

import itertools
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

MAX_LISTADOS = 20

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio-job')
_jobs = {}
_lock = threading.Lock()
_ordem = itertools.count()


def enfileirar(tipo: str, descricao: str, tarefa) -> dict:
  """`tarefa(progresso)` roda no worker; `progresso(texto)` atualiza a etapa mostrada na tela."""
  job = {'id': uuid.uuid4().hex[:12], 'tipo': tipo, 'descricao': descricao, 'status': 'na fila',
         'etapa': None, 'resultado': None, 'erro': None, 'criado': time.time(), '_ordem': next(_ordem)}
  with _lock:
    _jobs[job['id']] = job

  def progresso(texto: str) -> None:
    with _lock:
      job['etapa'] = texto

  def rodar() -> None:
    with _lock:
      job['status'] = 'rodando'
    try:
      resultado = tarefa(progresso)
    except Exception as erro:  # o motivo vai para a tela
      with _lock:
        job.update(status='falhou', erro=f'{type(erro).__name__}: {erro}')
      return
    with _lock:
      job.update(status='concluído', resultado=resultado)

  _executor.submit(rodar)
  return _publico(job)


def _publico(job: dict) -> dict:
  return {k: v for k, v in job.items() if not k.startswith('_')}


def job(job_id: str) -> dict:
  with _lock:
    if job_id not in _jobs:
      raise KeyError(f'job {job_id!r} desconhecido')
    return _publico(_jobs[job_id])


def listar() -> list:
  with _lock:
    recentes = sorted(_jobs.values(), key=lambda j: j['_ordem'], reverse=True)[:MAX_LISTADOS]
    return [_publico(j) for j in recentes]

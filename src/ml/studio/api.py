"""Servidor local do QoE Studio.

Um endpoint de dados e os estaticos. O payload sai inteiro numa chamada e o
recalculo de limiares acontece no cliente — nao ha estado de sessao no servidor.
"""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ml.studio.data import build_payload

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)

_cache = {}


@app.get('/api/payload')
def payload():
  """Varre o repositorio e devolve o payload. Cacheado por processo.

  Reiniciar o servidor e o jeito de recarregar apos um `git pull` — deliberado:
  uma varredura por requisicao releria todo o CSV a cada F5.
  """
  if 'payload' not in _cache:
    _cache['payload'] = build_payload()
  return JSONResponse(_cache['payload'])


app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')

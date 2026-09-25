"""Servidor local do QoE Studio.

O payload sai inteiro numa chamada e o recalculo de limiares acontece no cliente.
As unicas escritas sao arquivos versionados do repositorio, aceitas so a partir
da propria maquina; o commit e sempre humano.
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ml.core import features as core_features
from ml.studio import features as studio_features
from ml.studio import plans
from ml.studio.data import BUILDINGS, build_payload, descobertos

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)

_cache = {}
_ajustes = {}


def _payload() -> dict:
  if 'payload' not in _cache:
    _cache['payload'] = build_payload()
  return _cache['payload']


@app.get('/api/payload')
def payload():
  """Varre o repositorio e devolve o payload. Cacheado por processo.

  Reiniciar o servidor e o jeito de recarregar apos um `git pull` — deliberado:
  uma varredura por requisicao releria todo o CSV a cada F5.
  """
  return JSONResponse(_payload())


def _so_local(request: Request) -> None:
  if request.client is None or request.client.host not in LOOPBACK:
    raise HTTPException(403, 'gravação só é aceita a partir da própria máquina')


def _tabela():
  try:
    return core_features.carregar_tabela(), None
  except (OSError, ValueError) as erro:
    return {'prefixos': {}, 'colunas': {}}, f'tabela de classificação ilegível: {erro}'


def _ambiente(ambiente: str) -> Optional[str]:
  return None if ambiente in ('', 'todos') else ambiente


def _conjunto(ds: str, alvo: str, ambiente: str = ''):
  pedidos = [x for x in ds.split(',') if x]
  por_id = {d['id']: d for d in descobertos() if d.get('usable')}
  desconhecidos = [x for x in pedidos if x not in por_id]
  if desconhecidos:
    raise HTTPException(400, f'datasets desconhecidos: {desconhecidos}')
  frames = {x: por_id[x]['_frame'] for x in pedidos if por_id[x]['generation'] == 'current'}
  legacy = [x for x in pedidos if por_id[x]['generation'] != 'current']
  tabela, erro_tabela = _tabela()
  try:
    conj = studio_features.preparar(frames, alvo, tabela, _ambiente(ambiente))
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  if legacy:
    conj.avisos.insert(0, f'datasets legacy ignorados nesta view: {legacy}')
  return conj, erro_tabela


@app.get('/api/features/inventario')
def features_inventario(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, erro_tabela = _conjunto(ds, alvo, ambiente)
  inv = studio_features.inventario(conj)
  inv['tabela_erro'] = erro_tabela
  return inv


@app.get('/api/features/ajuste')
def features_ajuste(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  chave = (tuple(conj.datasets), alvo, _ambiente(ambiente), core_features.versao_tabela(),
           core_features.CATALOGO_VERSAO)
  if chave not in _ajustes:
    try:
      _ajustes[chave] = studio_features.ajuste(conj, studio_features.inventario(conj))
    except ValueError as erro:
      raise HTTPException(422, str(erro))
  return _ajustes[chave]


class NovaClassificacao(BaseModel):
  coluna: str
  classe: str
  vazamento: bool = False
  parametro: Optional[str] = None


@app.post('/api/columns')
def classificar_coluna(corpo: NovaClassificacao, request: Request):
  _so_local(request)
  conhecidas = set()
  for d in descobertos():
    if d.get('usable'):
      conhecidas.update(d['_frame'].columns)
  try:
    core_features.gravar_classificacao(corpo.coluna, corpo.classe, corpo.vazamento,
                                       corpo.parametro, conhecidas)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  _ajustes.clear()
  return {'ok': True}


def _envelope(predio: str) -> dict:
  env = _payload()['envelopes'].get(predio)
  if env is None:
    raise HTTPException(404, f'prédio {predio!r} sem envelope nos dados')
  return env


@app.get('/api/plan/arquivos')
def plan_arquivos():
  return plans.listar_arquivos()


@app.get('/api/plan/arquivo/{nome}')
def plan_arquivo(nome: str):
  try:
    path = plans.caminho(nome)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  if not os.path.exists(path):
    raise HTTPException(404, f'{nome!r} não encontrado em docs/planta/')
  return FileResponse(path)


@app.get('/api/plan/{predio}/paredes')
def plan_paredes(predio: str, arquivo: str, origem: str, eixo_x: str):
  env = _envelope(predio)
  try:
    segmentos = plans.ler_paredes(plans.caminho(arquivo))
    return {'paredes': plans.paredes_em_cm(segmentos, origem, eixo_x, env['w'], env['h']),
            'papel': plans.papel_das_paredes(origem, eixo_x)}
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))


@app.get('/api/plan/{predio}/foto.png')
def plan_foto(predio: str, arquivo: Optional[str] = None, cantos: Optional[str] = None,
              v: Optional[str] = None):
  env = _envelope(predio)
  previa = arquivo is not None
  if previa:
    try:
      numeros = [float(t) for t in (cantos or '').split(',') if t]
    except ValueError:
      raise HTTPException(422, 'cantos inválidos')
    lista = [numeros[i:i + 2] for i in range(0, len(numeros), 2)]
  else:
    calibrada = (_payload()['plantas'].get(predio) or {}).get('calibracao', {}).get('foto') or {}
    arquivo, lista = calibrada.get('arquivo'), calibrada.get('cantos')
    if not arquivo or not lista:
      raise HTTPException(404, 'foto ainda não calibrada')
  try:
    path = plans.caminho(arquivo)
    lista = plans.validar_cantos(lista, *plans.tamanho_imagem(path))
    png = plans.endireitar(path, lista, env['w'], env['h'], cache=not previa)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  return Response(png, media_type='image/png')


class Calibracao(BaseModel):
  paredes: Optional[dict] = None
  foto: Optional[dict] = None


@app.post('/api/plan/{predio}')
def plan_salvar(predio: str, corpo: Calibracao, request: Request):
  _so_local(request)
  if predio not in BUILDINGS:
    raise HTTPException(404, f'prédio {predio!r} desconhecido')
  _envelope(predio)
  try:
    plans.salvar_calibracao(predio, corpo.paredes, corpo.foto)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  dados = _payload()
  dados['plantas'], dados['plantasAvisos'] = plans.montar_plantas(dados['envelopes'])
  return {'plantas': dados['plantas'], 'plantasAvisos': dados['plantasAvisos']}


app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')

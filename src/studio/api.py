"""API do Studio novo. Lê data/ e grava só em .studio/ e em src/studio/config/.

POST só a partir da própria máquina: Host e Origin de loopback (middleware) e
cliente de loopback (_so_local).
"""

import os
from typing import Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from mlflow.exceptions import MlflowException

from studio import (avaliacao, caminhos, catalogo, colunas, conjunto, dados, fila, mlflow_servidor, plantas,
                    predios, rastreio, registro, treino, upload)

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)


def _post_permitido(host: Optional[str], origin: Optional[str]) -> bool:
  """POST só com Host de loopback (contra DNS rebinding) e Origin ausente ou de loopback."""
  if not host or urlsplit('//' + host).hostname not in LOOPBACK:
    return False
  return origin is None or urlsplit(origin).hostname in LOOPBACK


@app.middleware('http')
async def _so_post_local(request: Request, call_next):
  if request.method == 'POST' and not _post_permitido(request.headers.get('host'),
                                                      request.headers.get('origin')):
    return JSONResponse({'detail': 'POST só a partir da própria máquina (Host e Origin de loopback)'},
                        status_code=403)
  return await call_next(request)


def _so_local(request: Request) -> None:
  if request.client is None or request.client.host not in LOOPBACK:
    raise HTTPException(403, 'gravação só é aceita a partir da própria máquina')


_cache = {}


def _payload() -> dict:
  if 'payload' not in _cache:
    _cache['payload'] = dados.montar_payload()
  return _cache['payload']


def dados_mudaram() -> None:
  """Dataset ou prédio novo: catálogo, cadastro e payload são refeitos no próximo pedido."""
  catalogo.esquecer()
  predios.esquecer()
  _cache.clear()


# ---------------- Dados e conjunto ----------------

@app.get('/api/payload')
def payload():
  """Cacheado por processo; o conjunto ativo entra a cada pedido, sem refazer a varredura."""
  return JSONResponse(dados.com_conjunto(_payload(), conjunto.ler()))


class Conjunto(BaseModel):
  datasets: list[str]


@app.get('/api/conjunto')
def conjunto_ler():
  return {'datasets': conjunto.ler()}


@app.post('/api/conjunto')
def conjunto_gravar(corpo: Conjunto, request: Request):
  _so_local(request)
  try:
    return {'datasets': conjunto.gravar(corpo.datasets)}
  except ValueError as erro:
    raise HTTPException(422, str(erro))


# ---------------- Upload ----------------

@app.post('/api/upload/previa')
async def upload_previa(request: Request, nome: str):
  """Corpo cru (application/octet-stream): sem multipart, sem python-multipart."""
  _so_local(request)
  limite = upload.LIMITE_BYTES
  tamanho = request.headers.get('content-length')
  if tamanho and tamanho.isdigit() and int(tamanho) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  conteudo = await request.body()
  if len(conteudo) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  try:
    token = upload.guardar(nome, conteudo)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  previa = await run_in_threadpool(upload.previa, token, nome, (), catalogo.descobertos())
  return {'token': token, 'previa': previa}


class PredioNovo(BaseModel):
  chave: str
  rotulo: str
  ambiente: str
  prefixo: str


class Revisao(BaseModel):
  token: str
  nome: str
  predios_novos: list[PredioNovo] = []


@app.post('/api/upload/revisar')
def upload_revisar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    return upload.previa(corpo.token, corpo.nome, novos, catalogo.descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])


@app.post('/api/upload/confirmar')
def upload_confirmar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    resultado = upload.confirmar(corpo.token, corpo.nome, novos, catalogo.descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  except OSError as erro:
    # O prédio pode ter sido cadastrado antes da falha.
    dados_mudaram()
    raise HTTPException(422, str(erro))
  dados_mudaram()
  return resultado


# ---------------- Planta ----------------

def _envelope(predio: str) -> dict:
  env = _payload()['envelopes'].get(predio)
  if env is None:
    raise HTTPException(404, f'prédio {predio!r} sem envelope nos dados')
  return env


@app.get('/api/plan/arquivos')
def plan_arquivos():
  return plantas.listar_arquivos()


@app.get('/api/plan/arquivo/{nome}')
def plan_arquivo(nome: str):
  try:
    path = plantas.caminho(nome)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  if not os.path.exists(path):
    raise HTTPException(404, f'{nome!r} não encontrado em docs/planta/')
  return FileResponse(path)


@app.get('/api/plan/{predio}/paredes')
def plan_paredes(predio: str, arquivo: str, origem: str, eixo_x: str, formato: str = 'px',
                 dx: float = 0.0, dy: float = 0.0):
  env = _envelope(predio)
  registro = {'arquivo': arquivo, 'origem': origem, 'eixo_x': eixo_x, 'formato': formato, 'dx': dx, 'dy': dy}
  try:
    paredes, papel = plantas.ler_registro(registro, env['w'], env['h'])
    return {'paredes': paredes, 'papel': papel}
  except (OSError, ValueError, KeyError) as erro:
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
    path = plantas.caminho(arquivo)
    lista = plantas.validar_cantos(lista, *plantas.tamanho_imagem(path))
    png = plantas.endireitar(path, lista, env['w'], env['h'], cache=not previa)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  return Response(png, media_type='image/png')


class Calibracao(BaseModel):
  paredes: Optional[dict] = None
  foto: Optional[dict] = None
  andar: Optional[str] = None


@app.post('/api/plan/{predio}')
def plan_salvar(predio: str, corpo: Calibracao, request: Request):
  _so_local(request)
  if predio not in dados.predios_studio(predios.atual()):
    raise HTTPException(404, f'prédio {predio!r} desconhecido')
  _envelope(predio)
  try:
    plantas.salvar_calibracao(predio, corpo.paredes, corpo.foto, andar=corpo.andar)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  atual = _payload()
  atual['plantas'], atual['plantasAvisos'] = plantas.montar_plantas(atual['envelopes'])
  return {'plantas': atual['plantas'], 'plantasAvisos': atual['plantasAvisos']}


# ---------------- Modelo (MLflow do Studio) ----------------

def _alvo(alvo: str) -> None:
  if alvo not in rastreio.ALVOS:
    raise HTTPException(404, f'alvo {alvo!r} desconhecido')


def _com_mlflow(funcao, *args):
  """KeyError -> 404, ValueError -> 422, falha do MLflow -> 503, sempre com o motivo."""
  try:
    return funcao(*args)
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  except MlflowException as erro:
    raise HTTPException(503, f'MLflow: {erro.message}')


def _lista(texto: str) -> list:
  return [x.strip() for x in (texto or '').split(',') if x.strip()]


@app.get('/api/mlflow/status')
def mlflow_status():
  return {'ok': rastreio.disponivel(), 'ui': caminhos.MLFLOW_UI}


@app.post('/api/mlflow/reiniciar')
def mlflow_reiniciar(request: Request):
  _so_local(request)
  try:
    mlflow_servidor.reiniciar()
  except RuntimeError as erro:
    raise HTTPException(503, str(erro))
  return {'ok': True}


@app.get('/api/colunas')
def colunas_disponiveis(ds: str = ''):
  ids = _lista(ds) or conjunto.ler()
  try:
    return {'datasets': ids, 'colunas': colunas.disponiveis(ids)}
  except ValueError as erro:
    raise HTTPException(422, str(erro))


@app.get('/api/modelos/padroes')
def modelos_padroes():
  return {'modelos': {nome: padrao for nome, (_, padrao) in treino.MODELOS.items()},
          'regras': dict(avaliacao.REGRAS_PADRAO), 'alvos': list(rastreio.ALVOS)}


@app.get('/api/modelos/{alvo}')
def modelos_alvo(alvo: str):
  _alvo(alvo)
  return {'nome': rastreio.nome_modelo(alvo), 'ativo': _com_mlflow(registro.ativo, alvo),
          'versoes': _com_mlflow(registro.versoes, alvo)}


@app.get('/api/modelos/{alvo}/promover')
def modelos_promover_comparar(alvo: str, versao: str):
  _alvo(alvo)
  return _com_mlflow(registro.comparar, alvo, versao)


class Promocao(BaseModel):
  versao: str


@app.post('/api/modelos/{alvo}/promover')
def modelos_promover(alvo: str, corpo: Promocao, request: Request):
  _so_local(request)
  _alvo(alvo)
  return {'ativo': _com_mlflow(registro.promover, alvo, corpo.versao)}


class PedidoTreino(BaseModel):
  alvo: str
  datasets: list[str]
  features: list[str]
  modelo: str = 'RandomForest'
  hiper: dict = {}
  regras: dict = {}


@app.post('/api/treinos')
def treinos_iniciar(corpo: PedidoTreino, request: Request):
  """Valida na requisição (422 com o motivo); só um pedido válido entra na fila."""
  _so_local(request)
  pedido = treino.Pedido(alvo=corpo.alvo, datasets=corpo.datasets, features=corpo.features,
                         modelo=corpo.modelo, hiper=dict(corpo.hiper),
                         regras={**avaliacao.REGRAS_PADRAO, **corpo.regras})
  prep = _com_mlflow(treino.preparar, pedido)
  if not rastreio.disponivel():
    raise HTTPException(503, 'MLflow indisponível: reinicie pela aba Modelo')
  descricao = f'treino {corpo.modelo} · {corpo.alvo} · {len(corpo.features)} features'
  return fila.enfileirar('treino', descricao, lambda progresso: treino.executar(prep, progresso))


class PedidoReavaliacao(BaseModel):
  versao: str
  datasets: list[str]


@app.post('/api/modelos/{alvo}/reavaliar')
def modelos_reavaliar(alvo: str, corpo: PedidoReavaliacao, request: Request):
  _so_local(request)
  _alvo(alvo)
  prep = _com_mlflow(registro.preparar_reavaliacao, alvo, corpo.versao, corpo.datasets)
  descricao = f'reavaliação v{corpo.versao} · {alvo} · {len(corpo.datasets)} datasets'
  return fila.enfileirar('reavaliacao', descricao, lambda progresso: registro.executar_reavaliacao(prep, progresso))


@app.get('/api/jobs')
def jobs():
  return {'jobs': fila.listar()}


@app.get('/api/jobs/{job_id}')
def job(job_id: str):
  try:
    return fila.job(job_id)
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])

app.mount('/', StaticFiles(directory=WEB_DIR, html=True), name='static')

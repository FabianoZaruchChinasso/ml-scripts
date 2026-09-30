"""Servidor local do QoE Studio.

O payload sai inteiro numa chamada e o recalculo de limiares acontece no cliente.
As unicas escritas sao arquivos versionados do repositorio, aceitas so a partir
da propria maquina; o commit e sempre humano.
"""

import os
import threading
import uuid
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel

from ml.core import features as core_features
from ml.core import formulas as core_formulas
from ml.core import modelos as core_modelos
from ml.core.sites import BUILDING_ENVIRONMENT, resolve_site_id
from ml.core.splits import COMFORTABLE_SITES
from ml.studio import features as studio_features
from ml.studio import paralelos as studio_paralelos
from ml.studio import plans
from ml.studio import receitas as studio_receitas
from ml.studio import selecao as studio_selecao
from ml.studio.data import BUILDINGS, build_payload, descobertos

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)

_cache = {}
_ajustes = {}
_modelos_cache = {}


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


def _registro():
  """Registro de versões; se estiver ilegível, cai para o MODELO_ATUAL e avisa."""
  try:
    return core_modelos.carregar(), None
  except (OSError, ValueError) as erro:
    reserva = {'ativo': 'v1-legado', 'versoes': {'v1-legado': {
      'features': list(core_features.MODELO_ATUAL), 'descricao': 'reserva: modelos.json ilegível'}}}
    return reserva, f'registro de modelos ilegível: {erro}'


def _versoes_por_nome(registro) -> dict:
  return {nome: v['features'] for nome, v in registro['versoes'].items()}


def _chave_versoes():
  return (core_features.versao_tabela(), core_features.CATALOGO_VERSAO,
          core_features.versao_derivadas(), core_modelos.versao_registro())


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
  registro, erro_registro = _registro()
  inv = studio_features.inventario(conj, core_modelos.ativo(registro))
  inv['tabela_erro'] = erro_tabela
  inv['registro_erro'] = erro_registro
  inv['modelo_ativo'] = registro['ativo']
  return inv


@app.get('/api/features/ajuste')
def features_ajuste(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  chave = (tuple(conj.datasets), alvo, _ambiente(ambiente)) + _chave_versoes()
  if chave not in _ajustes:
    try:
      inv = studio_features.inventario(conj, core_modelos.ativo(registro))
      _ajustes[chave] = studio_features.ajuste(conj, inv, _versoes_por_nome(registro))
    except ValueError as erro:
      raise HTTPException(422, str(erro))
  return _ajustes[chave]


# ---------------- Modelos ----------------

def _colunas_conhecidas() -> set:
  conhecidas = {d.nome for d in core_features.catalogo_completo()}
  for d in descobertos():
    if d.get('usable'):
      conhecidas.update(d['_frame'].columns)
  return conhecidas


@app.get('/api/modelos')
def modelos_listar():
  registro, erro = _registro()
  tabela, _ = _tabela()
  versoes = []
  for nome, v in registro['versoes'].items():
    classes = core_modelos.classificar_features(v['features'], tabela)
    versoes.append(dict(v, nome=nome, ativo=nome == registro['ativo'],
                        fora_do_tr069=core_modelos.fora_do_tr069(v['features'], tabela),
                        pendentes=[f for f, c in classes.items() if c is not None and c.pendente],
                        vazadas=[f for f, c in classes.items() if c is not None and c.vazamento]))
  return {'ativo': registro['ativo'], 'versoes': versoes, 'erro': erro,
          'contadores': core_features.estado_contadores(tabela),
          'versao_tabela': core_features.versao_tabela(),
          'versao_catalogo': core_features.CATALOGO_VERSAO}


@app.get('/api/modelos/comparar')
def modelos_comparar(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  chave = ('comparar', tuple(conj.datasets), alvo, _ambiente(ambiente)) + _chave_versoes()
  if chave not in _modelos_cache:
    try:
      inv = studio_features.inventario(conj, core_modelos.ativo(registro))
      _modelos_cache[chave] = studio_features.comparar(conj, inv, _versoes_por_nome(registro),
                                                       registro['ativo'])
    except ValueError as erro:
      raise HTTPException(422, str(erro))
  return _modelos_cache[chave]


def _lista(texto: str) -> list:
  return [x for x in texto.split(',') if x]


@app.get('/api/modelos/avaliar')
def modelos_avaliar(features: str, ds: str = '', alvo: str = 'speedtest_down_mbps',
                    ambiente: str = '', base: str = ''):
  feats = _lista(features)
  if not feats:
    raise HTTPException(422, 'escolha pelo menos uma feature')
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  if base and base not in registro['versoes']:
    raise HTTPException(404, f'versão {base!r} não existe')
  chave = ('avaliar', tuple(conj.datasets), alvo, _ambiente(ambiente), tuple(feats), base) + _chave_versoes()
  if chave not in _modelos_cache:
    vazadas = studio_features.vazadas_do_conjunto(conj)
    try:
      studio_features.assert_sem_vazamento(feats, vazadas)
      studio_features._checar_locais(conj.df)
      resumo = studio_features.avaliar(conj, feats, vazadas)
      saida = {'alvo': alvo, 'features': feats, 'resumo': resumo,
               'correlacoes': studio_features.correlacoes(conj.df, feats),
               'fora_do_tr069': core_modelos.fora_do_tr069(feats, conj.tabela)}
      if base:
        saida['base'] = base
        saida['resumo_base'] = studio_features.avaliar_versao(conj, registro['versoes'][base]['features'], vazadas)
        saida['delta'] = studio_features.delta_por_local(resumo, saida['resumo_base'])
        pendentes = [f for f in feats if conj.classes.get(f) is not None and conj.classes[f].pendente]
        saida['veredito'] = studio_features.veredito(saida['delta'], int(conj.df['_site'].nunique()),
                                                     pendentes, studio_features.UNIDADES[alvo])
    except (ValueError, AssertionError) as erro:
      raise HTTPException(422, str(erro))
    _modelos_cache[chave] = saida
  return _modelos_cache[chave]


def avaliacao_completa(ds: str, ambiente: str, features: list) -> dict:
  """Avaliação dos quatro alvos, guardada junto da versão como registro da época."""
  saida = {}
  for alvo in studio_features.TARGETS:
    conj, _ = _conjunto(ds, alvo, ambiente)
    resumo = studio_features.avaliar(conj, features, studio_features.vazadas_do_conjunto(conj))
    saida[alvo] = dict(resumo, datasets=conj.datasets, ambiente=_ambiente(ambiente) or 'todos',
                       versao_tabela=core_features.versao_tabela(),
                       versao_catalogo=core_features.CATALOGO_VERSAO)
  return saida


# Desenho automático e paralelos rodam em thread: levam minutos e a página
# acompanha pelo progresso. Mesmo pedido com as mesmas versões reaproveita o job.
_desenhos = {}
_desenhos_lock = threading.Lock()


def _iniciar_job(chave: tuple, tarefa) -> dict:
  """`tarefa(progresso)` devolve o resultado; exceção vira status 'erro' com a mensagem."""
  with _desenhos_lock:
    for job_id, job in _desenhos.items():
      if job['chave'] == chave and job['status'] in ('rodando', 'pronto'):
        return {'id': job_id}
    job_id = uuid.uuid4().hex[:12]
    job = _desenhos[job_id] = {'chave': chave, 'status': 'rodando', 'progresso': [],
                               'resultado': None, 'erro': None}

  def progresso(evento):
    with _desenhos_lock:
      job['progresso'].append(evento)

  def rodar():
    try:
      resultado = tarefa(progresso)
      with _desenhos_lock:
        job['resultado'], job['status'] = resultado, 'pronto'
    except Exception as erro:  # o erro vai para a página, não para o log do servidor
      detalhe = erro.detail if isinstance(erro, HTTPException) else str(erro)
      with _desenhos_lock:
        job['erro'], job['status'] = detalhe, 'erro'
  threading.Thread(target=rodar, daemon=True).start()
  return {'id': job_id}


def _job(job_id: str) -> dict:
  job = _desenhos.get(job_id)
  if job is None:
    raise HTTPException(404, 'tarefa não encontrada; o servidor pode ter reiniciado')
  with _desenhos_lock:
    return {k: v for k, v in job.items() if k != 'chave'}


@app.post('/api/modelos/desenhar')
def modelos_desenhar(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = '',
                     sem_volume: bool = False):
  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    inv = studio_features.inventario(conj, core_modelos.ativo(registro))
    resultado = studio_selecao.desenhar(conj, inv, progresso, sem_volume)
    resultado['ambiente'] = _ambiente(ambiente) or 'todos'
    return resultado
  return _iniciar_job(('desenho', tuple(sorted(_lista(ds))), alvo, _ambiente(ambiente), sem_volume)
                      + _chave_versoes(), tarefa)


@app.get('/api/modelos/desenhar/{job_id}')
def modelos_desenho(job_id: str):
  return _job(job_id)


# ---------------- Limites e pendências dos dados ----------------

@app.get('/api/pendencias')
def pendencias(ds: str = '', ambiente: str = ''):
  """O que limita a leitura dos resultados hoje. A coleta está em andamento: isto muda."""
  tabela, _ = _tabela()
  pedidos = set(_lista(ds))
  locais, ambientes, ambiguos = set(), {}, []
  for d in descobertos():
    if not d.get('usable') or d['id'] not in pedidos or d['generation'] != 'current':
      continue
    frame = d['_frame']
    for valor in frame['local'].dropna().unique():
      try:
        predio = resolve_site_id(pd.Series([valor]), level='building').iloc[0]
      except ValueError:
        continue
      amb = BUILDING_ENVIRONMENT[predio]
      if _ambiente(ambiente) in (None, amb):
        locais.add(predio)
        ambientes.setdefault(amb, set()).add(predio)
    coluna = frame.get('router_opportunity_medium_use')
    # Coletor antigo: nunca grava vazio, e 0 pode ser "sem scan".
    if coluna is not None and coluna.notna().all() and (coluna == 0).any():
      ambiguos.append({'dataset': d['id'], 'zeros': round(float((coluna == 0).mean()), 3)})
  return {'locais': sorted(locais), 'n_locais': len(locais), 'minimo_confortavel': COMFORTABLE_SITES,
          'ambientes': {a: sorted(p) for a, p in ambientes.items()},
          'contadores': {'estado': core_features.estado_contadores(tabela),
                         'colunas': list(core_features.CONTADORES_JANELA)},
          'zeros_ambiguos': ambiguos}


class EstadoContadores(BaseModel):
  estado: str


@app.post('/api/contadores')
def contadores(corpo: EstadoContadores, request: Request):
  _so_local(request)
  try:
    core_features.gravar_estado_contadores(corpo.estado)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  _ajustes.clear()
  _modelos_cache.clear()
  return {'estado': corpo.estado}


# ---------------- Paralelos e derivadas ----------------

def _features_base(base: str) -> list:
  registro, _ = _registro()
  nome = base or registro['ativo']
  if nome not in registro['versoes']:
    raise HTTPException(404, f'versão {nome!r} não existe')
  return list(registro['versoes'][nome]['features'])


@app.post('/api/paralelos')
def paralelos_iniciar(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = '', base: str = ''):
  feats = _features_base(base)

  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    inv = studio_features.inventario(conj, core_modelos.ativo(registro))
    resultado = studio_paralelos.analisar(conj, inv, feats, progresso)
    resultado['versao_base'] = base or registro['ativo']
    return resultado
  return _iniciar_job(('paralelos', tuple(sorted(_lista(ds))), alvo, _ambiente(ambiente), base)
                      + _chave_versoes(), tarefa)


@app.get('/api/paralelos/{job_id}')
def paralelos_status(job_id: str):
  return _job(job_id)


@app.get('/api/derivadas')
def derivadas_listar():
  try:
    derivadas = core_features.carregar_derivadas_usuario()
    erro = None
  except (OSError, ValueError) as e:
    derivadas, erro = [], f'derivadas.json ilegível: {e}'
  return {'erro': erro, 'derivadas': [{'nome': d.nome, 'formula': d.formula, 'descricao': d.descricao,
                                       'status': d.status, 'inspirada_em': d.inspirada_em,
                                       'insumos': list(d.insumos)} for d in derivadas],
          'catalogo': [{'nome': d.nome, 'insumos': list(d.insumos), 'descricao': d.descricao}
                       for d in core_features.CATALOGO],
          'funcoes': sorted(core_formulas.FUNCOES)}


class Formula(BaseModel):
  nome: str
  formula: str
  inspirada_em: Optional[str] = None
  descricao: str = ''
  base: str = ''
  ds: str = ''
  alvo: str = 'speedtest_down_mbps'
  ambiente: str = ''


@app.post('/api/derivadas/previa')
def derivadas_previa(corpo: Formula):
  conj, _ = _conjunto(corpo.ds, corpo.alvo, corpo.ambiente)
  try:
    return studio_paralelos.previa(conj, corpo.nome, corpo.formula, corpo.inspirada_em or None)
  except ValueError as erro:
    raise HTTPException(422, str(erro))


def _testar(corpo: Formula) -> dict:
  conj, _ = _conjunto(corpo.ds, corpo.alvo, corpo.ambiente)
  try:
    return studio_paralelos.testar(conj, corpo.nome, corpo.formula, _features_base(corpo.base),
                                   corpo.inspirada_em or None)
  except (ValueError, AssertionError) as erro:
    raise HTTPException(422, str(erro))


@app.post('/api/derivadas/testar')
def derivadas_testar(corpo: Formula):
  return _testar(corpo)


@app.post('/api/derivadas')
def derivadas_salvar(corpo: Formula, request: Request):
  """O status vem do teste rodado aqui, nunca do que o navegador mandar."""
  _so_local(request)
  teste = _testar(corpo)
  resumo_teste = {'alvo': corpo.alvo, 'datasets': sorted(_lista(corpo.ds)), 'ambiente': _ambiente(corpo.ambiente) or 'todos',
                  'base': corpo.base or _registro()[0]['ativo'], 'criterios': teste['criterios'],
                  'ganho': teste['ganho'], 'reconstrucao': teste['reconstrucao'],
                  'versao_tabela': core_features.versao_tabela()}
  try:
    core_features.gravar_derivada(corpo.nome, corpo.formula, corpo.descricao, teste['status'],
                                  corpo.inspirada_em or None, resumo_teste, _colunas_conhecidas(),
                                  date.today().isoformat())
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  _ajustes.clear()
  _modelos_cache.clear()
  return {'status': teste['status'], 'teste': teste, 'lista': derivadas_listar()}


# ---------------- Assistente ----------------

@app.get('/api/assistente/colunas')
def assistente_colunas(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  inv = studio_features.inventario(conj, core_modelos.ativo(registro))
  return {'colunas': studio_features.lista_assistente(inv, conj.catalogo)}


@app.post('/api/assistente/sugestoes')
def assistente_sugestoes(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = '', base: str = ''):
  """Ganho +1 de cada coluna TR-069 liberada sobre a versão de partida, em thread."""
  feats = _features_base(base)

  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    studio_features._checar_locais(conj.df)
    inv = studio_features.inventario(conj, core_modelos.ativo(registro))
    liberadas = [c['coluna'] for c in studio_features.lista_assistente(inv, conj.catalogo) if c['liberada']]
    candidatas = [c for c in liberadas if c not in feats]
    ganho = studio_features.ganho_mais_um(conj, feats, candidatas, studio_features.vazadas_do_conjunto(conj),
                                          progresso)
    return {'base': base or registro['ativo'], 'alvo': alvo, 'ganho': ganho,
            'ganho_min': studio_paralelos.GANHO_MIN}
  return _iniciar_job(('sugestoes', tuple(sorted(_lista(ds))), alvo, _ambiente(ambiente), base)
                      + _chave_versoes(), tarefa)


@app.get('/api/assistente/sugestoes/{job_id}')
def assistente_sugestoes_status(job_id: str):
  return _job(job_id)


@app.get('/api/receitas')
def receitas_listar():
  return {'receitas': studio_receitas.listar()}


class MontarReceita(BaseModel):
  receita: str
  colunas: list


@app.post('/api/receitas/montar')
def receitas_montar(corpo: MontarReceita):
  try:
    return studio_receitas.montar(corpo.receita, corpo.colunas, _colunas_conhecidas())
  except ValueError as erro:
    raise HTTPException(422, str(erro))


def _metadados_do_desenho(job_id: str, features: list) -> dict:
  job = _desenhos.get(job_id)
  if job is None or job['status'] != 'pronto':
    raise ValueError('o desenho indicado não existe ou não terminou; rode de novo')
  r = job['resultado']
  if list(r['features']) != list(features):
    raise ValueError('as features mudaram depois do desenho: salve sem o vínculo com a seleção')
  campos = ('media', 'pooled', 'mae', 'por_local', 'mae_por_local')
  return {'alvo': r['alvo'], 'datasets': r['datasets'], 'ambiente': r['ambiente'],
          'parametros': r['parametros'], 'passos': r['passos'],
          'nota_selecao': {k: r['nota_selecao'][k] for k in campos},
          'nota_aninhada': {k: r['nota_aninhada'][k] for k in campos + ('escolhas_por_local',)}}


class NovaVersao(BaseModel):
  nome: str
  features: list
  descricao: str
  ds: str = ''
  ambiente: str = ''
  desenho: Optional[str] = None


@app.post('/api/modelos')
def modelos_salvar(corpo: NovaVersao, request: Request):
  _so_local(request)
  tabela, erro_tabela = _tabela()
  if erro_tabela:
    raise HTTPException(422, erro_tabela)
  registro, _ = _registro()
  if corpo.nome in registro['versoes']:
    raise HTTPException(422, f'a versão {corpo.nome!r} já existe e é imutável; escolha outro nome')
  try:
    core_modelos.validar_registro({'ativo': corpo.nome, 'versoes': {corpo.nome: {
      'features': corpo.features, 'descricao': corpo.descricao or '-'}}})
    selecao = _metadados_do_desenho(corpo.desenho, corpo.features) if corpo.desenho else None
    avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, corpo.features)
    core_modelos.salvar_versao(corpo.nome, corpo.features, corpo.descricao, _colunas_conhecidas(),
                               tabela, origem='selecao-gulosa' if selecao else 'studio',
                               avaliacao=avaliacao, selecao=selecao)
  except (ValueError, AssertionError) as erro:
    raise HTTPException(422, str(erro))
  _ajustes.clear()
  _modelos_cache.clear()
  return modelos_listar()


class Ativo(BaseModel):
  nome: str


@app.post('/api/modelos/ativo')
def modelos_ativo(corpo: Ativo, request: Request):
  _so_local(request)
  try:
    core_modelos.definir_ativo(corpo.nome)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  _ajustes.clear()
  _modelos_cache.clear()
  return modelos_listar()


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
  _modelos_cache.clear()
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
def plan_paredes(predio: str, arquivo: str, origem: str, eixo_x: str, formato: str = 'px',
                 dx: float = 0.0, dy: float = 0.0):
  env = _envelope(predio)
  registro = {'arquivo': arquivo, 'origem': origem, 'eixo_x': eixo_x, 'formato': formato, 'dx': dx, 'dy': dy}
  try:
    paredes, papel = plans.ler_registro(registro, env['w'], env['h'])
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
    path = plans.caminho(arquivo)
    lista = plans.validar_cantos(lista, *plans.tamanho_imagem(path))
    png = plans.endireitar(path, lista, env['w'], env['h'], cache=not previa)
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
  if predio not in BUILDINGS:
    raise HTTPException(404, f'prédio {predio!r} desconhecido')
  _envelope(predio)
  try:
    plans.salvar_calibracao(predio, corpo.paredes, corpo.foto, andar=corpo.andar)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  dados = _payload()
  dados['plantas'], dados['plantasAvisos'] = plans.montar_plantas(dados['envelopes'])
  return {'plantas': dados['plantas'], 'plantasAvisos': dados['plantasAvisos']}


app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')

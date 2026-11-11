"""Servidor local do QoE Studio.

O payload sai inteiro numa chamada e o recalculo de limiares acontece no cliente.
As unicas escritas sao arquivos versionados do repositorio, aceitas so a partir
da propria maquina; o commit e sempre humano.
"""

import os
import threading
import time
import uuid
from datetime import date
from typing import Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import comodo as core_comodo
from ml.core import completa as core_completa
from ml.core import features as core_features
from ml.core import limiar as core_limiar
from ml.core import formulas as core_formulas
from ml.core import modelos as core_modelos
from ml.core import qoe as core_qoe
from ml.core import quantis as core_quantis
from ml.core import registro_mlflow as core_registro_mlflow
from ml.core import registry_mlflow as core_registry
from ml.core.sites import BUILDING_ENVIRONMENT, resolve_site_id
from ml.core.splits import COMFORTABLE_SITES
from ml.studio import features as studio_features
from ml.studio import ingestao as studio_ingestao
from ml.studio import paralelos as studio_paralelos
from ml.studio import plans
from ml.studio import receitas as studio_receitas
from ml.studio import selecao as studio_selecao
from ml.studio import data as studio_data
from ml.studio.data import build_payload, descobertos, predios_studio

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)


def _post_permitido(host: Optional[str], origin: Optional[str]) -> bool:
  """POST só com Host de loopback (contra DNS rebinding) e Origin ausente ou de loopback (contra
  uma página de outro site aberta no navegador desta máquina)."""
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

_cache = {}
_ajustes = {}
_modelos_cache = {}
# O cache do piso da régua por cômodo mora em core/completa.py; este é o mesmo dicionário, e é por
# ele que _dados_mudaram esvazia o cache quando chega dataset ou prédio novo.
_piso_comodo_cache = core_completa._piso_cache


def _payload() -> dict:
  if 'payload' not in _cache:
    # Marca antes de ler: um arquivo que chegue durante a leitura conta como mudança.
    _cache['lido_em'] = time.time()
    _cache['payload'] = build_payload()
  return _cache['payload']


def _data_mudou() -> bool:
  """data/ ganhou, perdeu ou renomeou arquivo depois da última leitura: a tela mostra dados velhos.

  O upload pelo próprio Studio relê tudo (_dados_mudaram limpa _cache), então só avisa de
  mudanças feitas fora dele (git pull, arquivo copiado, arquivo apagado).
  """
  lido_em = _cache.get('lido_em')
  if lido_em is None:
    return False
  try:
    return os.path.getmtime(core_carga.DATA_DIR) > lido_em
  except OSError:
    return False


@app.get('/api/payload')
def payload():
  """Varre o repositorio e devolve o payload. Cacheado por processo.

  Reiniciar o servidor e o jeito de recarregar apos um `git pull` — deliberado:
  uma varredura por requisicao releria todo o CSV a cada F5.
  """
  return JSONResponse(dict(_payload(), dataMudou=_data_mudou()))


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
    reserva = {'versoes': {'v1': {
      'features': list(core_features.MODELO_ATUAL), 'descricao': 'reserva: modelos.json ilegível'}}}
    return reserva, f'registro de modelos ilegível: {erro}'


def _ativa(registro) -> Optional[str]:
  """Definição da versão ativa (alias 'ativo' do Model Registry), ou None sem alias ou com alias para
  uma definição que não está em modelos.json."""
  nome = core_registry.definicao_ativa()
  return nome if nome in registro['versoes'] else None


def _base(base, registro) -> str:
  """A versão base pedida; sem ela, a ativa; sem as duas, 409."""
  nome = base or _ativa(registro)
  if not nome:
    raise HTTPException(409, 'sem versão ativa no Model Registry: escolha a versão base '
                             '(ou ative uma com src/ml/ativar_mlflow.py)')
  return nome


def _features_ativa(registro) -> list:
  """Features do ponto de partida do inventário: a ativa; sem alias, a última versão (o inventário é informativo)."""
  nome = _ativa(registro) or list(registro['versoes'])[-1]
  return core_modelos.features_de(registro, nome)


def _versoes_por_nome(registro) -> dict:
  return {nome: v['features'] for nome, v in registro['versoes'].items()}


def _denominadores(registro) -> dict:
  return {nome: v.get('denominador') or {} for nome, v in registro['versoes'].items()}


def _chave_versoes():
  return (core_features.versao_tabela(), core_features.CATALOGO_VERSAO,
          core_features.versao_derivadas(), core_modelos.versao_registro(), core_aplicacoes.versao(),
          core_aplicacoes.versao(core_aplicacoes.APLICACOES_NORMA_PATH), core_registry.definicao_ativa())


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
  inv = studio_features.inventario(conj, _features_ativa(registro))
  inv['tabela_erro'] = erro_tabela
  inv['registro_erro'] = erro_registro
  inv['modelo_ativo'] = _ativa(registro)
  return inv


@app.get('/api/features/ajuste')
def features_ajuste(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  chave = (tuple(conj.datasets), alvo, _ambiente(ambiente)) + _chave_versoes()
  if chave not in _ajustes:
    try:
      inv = studio_features.inventario(conj, _features_ativa(registro))
      _ajustes[chave] = studio_features.ajuste(conj, inv, _versoes_por_nome(registro), _denominadores(registro))
    except ValueError as erro:
      raise HTTPException(422, str(erro))
  return _ajustes[chave]


# ---------------- Modelos ----------------

def _colunas_conhecidas() -> set:
  conhecidas = {d.nome for d in core_features.catalogo_completo()} | set(core_carga.COLUNAS_CALCULADAS)
  for d in descobertos():
    if d.get('usable'):
      conhecidas.update(d['_frame'].columns)
  return conhecidas


@app.get('/api/modelos')
def modelos_listar():
  registro, erro = _registro()
  tabela, _ = _tabela()
  ativa = _ativa(registro)
  versoes = []
  for nome, v in registro['versoes'].items():
    classes = core_modelos.classificar_features(v['features'], tabela)
    versoes.append(dict(v, nome=nome, ativo=nome == ativa,
                        fora_do_tr069=core_modelos.fora_do_tr069(v['features'], tabela),
                        # Recalculada com a tabela de hoje; 'cobertura_salva' é a gravada na versão.
                        cobertura=core_features.cobertura_tr069(v['features'], tabela),
                        cobertura_salva=v.get('cobertura'),
                        perfil_qoe=core_modelos.perfil_de(registro, nome),
                        pendentes=[f for f, c in classes.items() if c is not None and c.pendente],
                        vazadas=[f for f, c in classes.items() if c is not None and c.vazamento]))
  if not erro and not ativa:
    erro = 'sem versão ativa no Model Registry: ative uma com src/ml/ativar_mlflow.py'
  return {'ativo': ativa, 'versoes': versoes, 'erro': erro,
          'contadores': core_features.estado_contadores(tabela),
          'versao_tabela': core_features.versao_tabela(),
          'versao_catalogo': core_features.CATALOGO_VERSAO,
          'versao_regua': core_avaliacao.VERSAO_REGUA}


@app.get('/api/modelos/comparar')
def modelos_comparar(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = ''):
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  chave = ('comparar', tuple(conj.datasets), alvo, _ambiente(ambiente)) + _chave_versoes()
  if chave not in _modelos_cache:
    try:
      inv = studio_features.inventario(conj, _features_ativa(registro))
      _modelos_cache[chave] = studio_features.comparar(conj, inv, _versoes_por_nome(registro),
                                                       _ativa(registro), _denominadores(registro))
    except ValueError as erro:
      raise HTTPException(422, str(erro))
  return _modelos_cache[chave]


def _lista(texto: str) -> list:
  return [x for x in texto.split(',') if x]


def _presentes(c, lista):
  return core_completa.presentes(c, lista)


def _prever_pontual(c, lista, denominador: dict = None):
  presentes, vazadas = _presentes(c, lista)
  return core_avaliacao.prever_fora_do_fold(c.df, presentes, c.alvo, vazadas,
                                            denominador=(denominador or {}).get(c.alvo))


def _prever_quantis(c, lista):
  return core_completa.prever_quantis(c, lista)


def _promocao(ds: str, ambiente: str, alvo: str, feats: list, feats_base: list, conj,
              den_nova: dict = None, den_base: dict = None) -> dict:
  """Veredito de promoção da régua contra a versão base.

  Latência e jitter: Δ pinball do p90 e cobertura da nova versão. Download e upload:
  Δ MAE e Δ "atende em throughput" com o fator de decisão ajustado, cada lado com o seu denominador ({alvo: coluna}).
  """
  if alvo in core_quantis.ALVOS_QUANTILICOS:
    nova = _prever_quantis(conj, feats)
    d_pinball = core_quantis.delta_pinball(nova, _prever_quantis(conj, feats_base))
    cobertura = round(core_quantis.cobertura(nova['y'], nova['q90']), 4)
    return {'delta_pinball': d_pinball, 'cobertura': cobertura,
            'veredito': core_quantis.veredito_quantis(d_pinball, cobertura),
            'versao_regua': core_avaliacao.VERSAO_REGUA}
  d_mae = core_avaliacao.delta_mae(_prever_pontual(conj, feats, den_nova),
                                   _prever_pontual(conj, feats_base, den_base))
  d_atende = None
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
    up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
    aplicacoes = core_aplicacoes.carregar()
    den_nova, den_base = den_nova or {}, den_base or {}
    # "Atende" com o fator de decisão escolhido sem o prédio de teste (core/limiar.py).
    d_atende = core_limiar.delta_decisoes(
      core_limiar.decisoes_atende(dn, up, feats, aplicacoes, den_nova.get(dn.alvo), den_nova.get(up.alvo)),
      core_limiar.decisoes_atende(dn, up, feats_base, aplicacoes, den_base.get(dn.alvo), den_base.get(up.alvo)))
  return {'delta_mae': d_mae, 'delta_atende': d_atende,
          'veredito': core_avaliacao.veredito_promocao(d_mae, d_atende),
          'versao_regua': core_avaliacao.VERSAO_REGUA}


@app.get('/api/modelos/avaliar')
def modelos_avaliar(features: str, ds: str = '', alvo: str = 'speedtest_down_mbps',
                    ambiente: str = '', base: str = '', contra: str = ''):
  feats = _lista(features)
  if not feats:
    raise HTTPException(422, 'escolha pelo menos uma feature')
  conj, _ = _conjunto(ds, alvo, ambiente)
  registro, _ = _registro()
  for nome in (base, contra):
    if nome and nome not in registro['versoes']:
      raise HTTPException(404, f'versão {nome!r} não existe')
  # `base` diz de onde o rascunho partiu, e por isso de quem herda o denominador; `contra`
  # diz com quem comparar. Sem `contra`, compara com a própria base, como antes.
  ref = contra or base
  chave = ('avaliar', tuple(conj.datasets), alvo, _ambiente(ambiente), tuple(feats), base, ref) + _chave_versoes()
  if chave not in _modelos_cache:
    vazadas = studio_features.vazadas_do_conjunto(conj)
    # O rascunho herda o denominador da versão de onde partiu (ou da ativa, sem base).
    den_nova = registro['versoes'][_base(base, registro)].get('denominador') or {}
    den_ref = (registro['versoes'][ref].get('denominador') or {}) if ref else {}
    try:
      studio_features.assert_sem_vazamento(feats, vazadas)
      studio_features._checar_locais(conj.df)
      resumo = studio_features.avaliar(conj, feats, vazadas, denominador=den_nova.get(alvo))
      saida = {'alvo': alvo, 'features': feats, 'resumo': resumo,
               'correlacoes': studio_features.correlacoes(conj.df, feats),
               'fora_do_tr069': core_modelos.fora_do_tr069(feats, conj.tabela),
               'cobertura': core_features.cobertura_tr069(feats, conj.tabela, conj.catalogo)}
      if ref:
        feats_ref = registro['versoes'][ref]['features']
        saida['base'] = base or ref
        if contra:
          saida['contra'] = contra
        saida['resumo_base'] = studio_features.avaliar_versao(conj, feats_ref, vazadas,
                                                              denominador=den_ref.get(alvo))
        saida['delta'] = studio_features.delta_por_local(resumo, saida['resumo_base'])
        pendentes = [f for f in feats if conj.classes.get(f) is not None and conj.classes[f].pendente]
        saida['veredito'] = studio_features.veredito(saida['delta'], int(conj.df['_site'].nunique()),
                                                     pendentes, studio_features.UNIDADES[alvo])
        saida['promocao'] = _promocao(ds, ambiente, alvo, feats, feats_ref, conj, den_nova, den_ref)
    except (ValueError, AssertionError) as erro:
      raise HTTPException(422, str(erro))
    _modelos_cache[chave] = saida
  return _modelos_cache[chave]


@app.get('/api/modelos/avaliar_comodo')
def modelos_avaliar_comodo(features: str, contra: str = '', ds: str = '', ambiente: str = '', base: str = ''):
  """Régua por cômodo do rascunho e o veredito contra a avaliação guardada de `contra` (core/comodo.py).

  Só o rascunho é previsto (quatro alvos, cerca de 1 min sem cache); `contra` entra pela tabela por
  posição guardada na avaliação dele. O denominador é o da `base` (ou da ativa), como no salvar.
  409 quando `contra` não tem o bloco `comodo` ou foi avaliada com outra régua, outros datasets ou
  outro ambiente: é preciso reavaliar `contra` antes.
  """
  feats = _lista(features)
  if not feats:
    raise HTTPException(422, 'escolha pelo menos uma feature')
  registro, _ = _registro()
  for nome in (contra, base):
    if nome and nome not in registro['versoes']:
      raise HTTPException(404, f'versão {nome!r} não existe')
  contra = contra or _base(base, registro)   # sem `contra` (sem ativa), compara com a própria base
  chave = (('avaliar_comodo', tuple(sorted(_lista(ds))), _ambiente(ambiente), tuple(feats), contra, base)
           + _chave_versoes())
  if chave not in _modelos_cache:
    guardado = (registro['versoes'][contra].get('avaliacao') or {}).get('comodo')
    if not guardado:
      raise HTTPException(409, f'{contra} não foi avaliada pela régua por cômodo: reavalie {contra} antes de comparar')
    denominador = registro['versoes'][_base(base, registro)].get('denominador') or None
    conjs = {alvo: _conjunto(ds, alvo, ambiente)[0] for alvo in core_qoe.ALVOS}
    vazadas = {alvo: studio_features.vazadas_do_conjunto(c) for alvo, c in conjs.items()}
    try:
      novo = _bloco_comodo(conjs, core_comodo.prever(conjs, feats, vazadas, denominador), ambiente)
    except (ValueError, AssertionError) as erro:
      raise HTTPException(422, str(erro))
    try:
      comp = core_comodo.comparar_blocos(novo, guardado)
    except ValueError as erro:
      raise HTTPException(409, f'{erro}: reavalie {contra} antes de comparar')
    _modelos_cache[chave] = {'nota': novo['nota'], 'intervalo': novo['intervalo'], 'piso': novo['piso'],
                             'contra_piso': novo['contra_piso'], 'por_predio': novo['por_predio'],
                             'jogo': novo['jogo'], 'jogo_base': guardado.get('jogo'),
                             'nota_base': comp['nota_base'], 'diferenca': comp['diferenca'],
                             'intervalo_diferenca': comp['intervalo'], 'resultado': comp['resultado']}
  return _modelos_cache[chave]


def _bloco_comodo(conjs: dict, prev, ambiente: str) -> dict:
  """Bloco `comodo` da avaliação, com o piso em cache (core/completa.py)."""
  return core_completa.bloco_comodo(conjs, prev, ambiente)


def avaliacao_completa(ds: str, ambiente: str, features: list, denominador: dict = None, progresso=None,
                       perfil_qoe: str = 'atual') -> dict:
  """A avaliação completa (core/completa.py) com os datasets e o ambiente escolhidos no Studio."""
  return core_completa.avaliacao_completa(lambda alvo: _conjunto(ds, alvo, ambiente)[0], ambiente, features,
                                          denominador, progresso=progresso, perfil_qoe=perfil_qoe)


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
                     sem_volume: bool = False, escopo: str = 'tudo'):
  if escopo not in studio_selecao.ESCOPOS:
    raise HTTPException(422, f'escopo {escopo!r} inválido; esperado um de {list(studio_selecao.ESCOPOS)}')

  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    inv = studio_features.inventario(conj, _features_ativa(registro))
    resultado = studio_selecao.desenhar(conj, inv, progresso, sem_volume, escopo)
    resultado['ambiente'] = _ambiente(ambiente) or 'todos'
    return resultado
  return _iniciar_job(('desenho', tuple(sorted(_lista(ds))), alvo, _ambiente(ambiente), sem_volume, escopo)
                      + _chave_versoes(), tarefa)


@app.get('/api/modelos/desenhar/{job_id}')
def modelos_desenho(job_id: str):
  return _job(job_id)


# ---------------- Dados novos pela interface ----------------

def _dados_mudaram() -> None:
  """Dataset ou prédio novo: descoberta, payload e tudo que depende do conjunto é refeito."""
  core_carga.esquecer_descobertos()
  studio_data.limpar_cache_predios()
  _cache.clear()
  _ajustes.clear()
  _modelos_cache.clear()
  _piso_comodo_cache.clear()
  with _desenhos_lock:
    for job_id in [j for j, job in _desenhos.items() if job['status'] != 'rodando']:
      del _desenhos[job_id]


@app.post('/api/datasets/previa')
async def datasets_previa(request: Request, nome: str):
  """Corpo cru (application/octet-stream): sem multipart, sem python-multipart."""
  _so_local(request)
  limite = studio_ingestao.LIMITE_BYTES
  tamanho = request.headers.get('content-length')
  if tamanho and tamanho.isdigit() and int(tamanho) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  conteudo = await request.body()
  if len(conteudo) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  try:
    token = studio_ingestao.guardar(nome, conteudo)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  previa = await run_in_threadpool(studio_ingestao.previa, token, nome, (), None, descobertos())
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


@app.post('/api/datasets/revisar')
def datasets_revisar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    return studio_ingestao.previa(corpo.token, corpo.nome, novos, existentes=descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])


@app.post('/api/datasets/confirmar')
def datasets_confirmar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    resultado = studio_ingestao.confirmar(corpo.token, corpo.nome, novos, existentes=descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  except OSError as erro:
    # O prédio pode ter sido cadastrado antes da falha: o registro em memória já mudou.
    _dados_mudaram()
    raise HTTPException(422, str(erro))
  _dados_mudaram()
  return resultado


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
  nome = _base(base, registro)
  if nome not in registro['versoes']:
    raise HTTPException(404, f'versão {nome!r} não existe')
  return list(registro['versoes'][nome]['features'])


@app.post('/api/paralelos')
def paralelos_iniciar(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = '', base: str = ''):
  feats = _features_base(base)

  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    inv = studio_features.inventario(conj, _features_ativa(registro))
    resultado = studio_paralelos.analisar(conj, inv, feats, progresso)
    resultado['versao_base'] = _base(base, registro)
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
                  'base': _base(corpo.base, _registro()[0]), 'criterios': teste['criterios'],
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
  inv = studio_features.inventario(conj, _features_ativa(registro))
  return {'colunas': studio_features.lista_assistente(inv, conj.catalogo)}


@app.post('/api/assistente/sugestoes')
def assistente_sugestoes(ds: str = '', alvo: str = 'speedtest_down_mbps', ambiente: str = '', base: str = ''):
  """Ganho +1 de cada coluna TR-069 liberada sobre a versão de partida, em thread."""
  feats = _features_base(base)

  def tarefa(progresso):
    conj, _ = _conjunto(ds, alvo, ambiente)
    registro, _ = _registro()
    studio_features._checar_locais(conj.df)
    inv = studio_features.inventario(conj, _features_ativa(registro))
    liberadas = [c['coluna'] for c in studio_features.lista_assistente(inv, conj.catalogo) if c['liberada']]
    candidatas = [c for c in liberadas if c not in feats]
    ganho = studio_features.ganho_mais_um(conj, feats, candidatas, studio_features.vazadas_do_conjunto(conj),
                                          progresso)
    return {'base': _base(base, registro), 'alvo': alvo, 'ganho': ganho,
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


AVISO_MLFLOW_MAX = 200


def _registrar_mlflow(acao) -> Optional[str]:
  """Roda o registro no MLflow; devolve None ou o aviso para a tela.

  O modelos.json é a fonte da verdade: uma falha aqui (MLflow fora do ar, banco travado, pacote
  quebrado) nunca desfaz nem impede a gravação. Recuperação: src/ml/studio_mlflow.py.
  O aviso leva só a primeira linha do erro, cortada: o erro de banco travado do SQLAlchemy traz a
  consulta SQL inteira. Com o banco travado, o aviso só chega depois de 20 s (o MLflow força
  PRAGMA busy_timeout = 20000 em toda sessão).
  """
  try:
    acao()
    return None
  except Exception as erro:
    linhas = str(erro).strip().splitlines()
    motivo = linhas[0] if linhas else type(erro).__name__
    if len(motivo) > AVISO_MLFLOW_MAX:
      motivo = motivo[:AVISO_MLFLOW_MAX] + '...'
    return f'não registrou no MLflow: {motivo}'


class NovaVersao(BaseModel):
  nome: str
  features: list
  descricao: str
  ds: str = ''
  ambiente: str = ''
  desenho: Optional[str] = None
  base: Optional[str] = None
  perfil_qoe: str = 'norma'


@app.post('/api/modelos')
def modelos_salvar(corpo: NovaVersao, request: Request):
  """Valida na hora (422 com o motivo); avaliação e gravação rodam num job.

  A avaliação completa leva de 1 a 2 minutos: na requisição, o botão ficava parado sem
  dizer nada. O front acompanha por GET /api/modelos/salvar/{id}.
  """
  _so_local(request)
  if corpo.perfil_qoe not in core_aplicacoes.PERFIS:
    raise HTTPException(422, f'perfil {corpo.perfil_qoe!r} desconhecido; '
                             f'use um de {list(core_aplicacoes.PERFIS)}')
  tabela, erro_tabela = _tabela()
  if erro_tabela:
    raise HTTPException(422, erro_tabela)
  registro, _ = _registro()
  if corpo.nome in registro['versoes']:
    raise HTTPException(422, f'a versão {corpo.nome!r} já existe e é imutável; escolha outro nome')
  if corpo.base and corpo.base not in registro['versoes']:
    raise HTTPException(422, f'versão base {corpo.base!r} não existe')
  vazadas = [f for f, c in core_modelos.classificar_features(corpo.features, tabela).items()
             if c is not None and c.vazamento]
  if vazadas:
    raise HTTPException(422, f'estas colunas estão marcadas como vazamento e não podem entrar numa versão nova: '
                             f'{vazadas}. Tire-as do rascunho.')
  # Mesma regra da avaliação do rascunho: herda o denominador da base (ou da ativa).
  denominador = registro['versoes'][_base(corpo.base, registro)].get('denominador') or None
  try:
    core_modelos.validar_registro({'versoes': {corpo.nome: {
      'features': corpo.features, 'descricao': corpo.descricao or '-'}}})
    selecao = _metadados_do_desenho(corpo.desenho, corpo.features) if corpo.desenho else None
  except (ValueError, AssertionError) as erro:
    raise HTTPException(422, str(erro))
  conhecidas = _colunas_conhecidas()

  def tarefa(progresso):
    avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, corpo.features, denominador, progresso=progresso,
                                  perfil_qoe=corpo.perfil_qoe)
    try:
      gravado = core_modelos.salvar_versao(corpo.nome, corpo.features, corpo.descricao, conhecidas,
                                           tabela, origem='selecao-gulosa' if selecao else 'studio',
                                           avaliacao=avaliacao, selecao=selecao, denominador=denominador,
                                           perfil_qoe=corpo.perfil_qoe)
    finally:
      _ajustes.clear()
      _modelos_cache.clear()
    aviso = _registrar_mlflow(lambda: core_registro_mlflow.registrar_avaliacao(
      corpo.nome, gravado['versoes'][corpo.nome], 'salvar'))
    return {'nome': corpo.nome, 'aviso_mlflow': aviso}

  return _iniciar_job(('salvar', corpo.nome, tuple(sorted(_lista(corpo.ds))), _ambiente(corpo.ambiente),
                       corpo.perfil_qoe, tuple(corpo.features))
                      + _chave_versoes(), tarefa)


@app.get('/api/modelos/salvar/{job_id}')
def modelos_salvamento(job_id: str):
  return _job(job_id)


class Reavaliacao(BaseModel):
  nomes: list[str]
  ds: str = ''
  ambiente: str = ''


@app.post('/api/modelos/reavaliar')
def modelos_reavaliar(corpo: Reavaliacao, request: Request):
  """Recalcula a avaliação de versões existentes com o conjunto escolhido, uma por vez.

  Cada versão é gravada assim que termina: se o lote parar no meio, o que já foi
  reavaliado fica salvo e o erro diz em qual versão parou.
  """
  _so_local(request)
  registro, erro = _registro()
  if erro:
    raise HTTPException(422, erro)
  if not corpo.nomes:
    raise HTTPException(422, 'nenhuma versão para reavaliar')
  faltam = [n for n in corpo.nomes if n not in registro['versoes']]
  if faltam:
    raise HTTPException(422, f'versões que não existem: {faltam}')
  tabela, _ = _tabela()
  nomes = list(corpo.nomes)

  def tarefa(progresso):
    feitas, avisos = [], []
    for i, nome in enumerate(nomes):
      progresso({'nome': nome, 'i': i, 'total': len(nomes)})
      versao = registro['versoes'][nome]
      try:
        etapa = lambda evento, nome=nome, i=i: progresso({'nome': nome, 'i': i, 'total': len(nomes), **evento})
        avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, versao['features'], versao.get('denominador'),
                                       progresso=etapa, perfil_qoe=core_modelos.perfil_de(registro, nome))
        nota = core_modelos.nota_reavaliacao(versao.get('avaliacao'), avaliacao, date.today().isoformat())
        regravado = core_modelos.reavaliar(nome, avaliacao, core_features.cobertura_tr069(versao['features'], tabela),
                                           nota)
      except Exception as falha:
        detalhe = falha.detail if isinstance(falha, HTTPException) else str(falha)
        # As que terminaram já foram gravadas; se o MLflow ficou para trás nelas, o erro precisa dizer.
        mlflow = '; MLflow: ' + '; '.join(f"{a['nome']}: {a['aviso']}" for a in avisos) if avisos else ''
        raise RuntimeError(f'parou em {nome}: {detalhe}; já reavaliadas: {feitas}{mlflow}') from falha
      finally:
        _ajustes.clear()
        _modelos_cache.clear()
      feitas.append(nome)
      aviso = _registrar_mlflow(lambda nome=nome, regravado=regravado: core_registro_mlflow.registrar_avaliacao(
        nome, regravado['versoes'][nome], 'reavaliar'))
      if aviso:
        avisos.append({'nome': nome, 'aviso': aviso})
    return {'reavaliadas': feitas, 'avisos_mlflow': avisos}
  return _iniciar_job(('reavaliar', tuple(nomes), tuple(sorted(_lista(corpo.ds))), _ambiente(corpo.ambiente))
                      + _chave_versoes(), tarefa)


@app.get('/api/modelos/reavaliar/{job_id}')
def modelos_reavaliacao(job_id: str):
  return _job(job_id)


class NovaClassificacao(BaseModel):
  coluna: str
  classe: str
  vazamento: bool = False
  parametro: Optional[str] = None
  # None preserva o tr181 que a regra já tinha.
  tr181: Optional[dict] = None


@app.post('/api/columns')
def classificar_coluna(corpo: NovaClassificacao, request: Request):
  _so_local(request)
  conhecidas = set()
  for d in descobertos():
    if d.get('usable'):
      conhecidas.update(d['_frame'].columns)
  try:
    core_features.gravar_classificacao(corpo.coluna, corpo.classe, corpo.vazamento,
                                       corpo.parametro, conhecidas, tr181=corpo.tr181)
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
  if predio not in predios_studio():
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

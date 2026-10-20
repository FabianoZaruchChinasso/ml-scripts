"""Entrada de datasets pelo QoE Studio: prévia guardada sob um token e confirmação que grava em data/.

O arquivo enviado fica numa pasta temporária do processo até a confirmação, e nada vai
para data/ antes dela. A confirmação refaz a prévia inteira: a tela nunca é a única a
validar.
"""

import os
import re
import shutil
import tempfile
import threading
import time
import uuid

import pandas as pd

from ml.core import carga as core_carga
from ml.core import sites as core_sites

LIMITE_BYTES = 100 * 1024 * 1024
VALIDADE_S = 3600
# Abaixo disto, uma coluna-chave da geração atual quase não ajuda: avisar na prévia.
LIMIAR_PREENCHIMENTO = 0.5
OBRIGATORIAS = ('local',) + tuple(core_carga.TARGETS)
COLUNAS_CHAVE = OBRIGATORIAS + tuple(core_carga.CURRENT_MARKERS)
NOME_ARQUIVO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.(csv|zip)$')
# A descoberta de datasets pula estes nomes (carga.discover).
IGNORADOS = ('-qoe', 'filllast')

_previas = {}
_lock = threading.Lock()


def _extensao(nome: str) -> str:
  for ext in ('.csv', '.zip'):
    if nome.lower().endswith(ext):
      return ext
  raise ValueError(f'{nome!r}: o arquivo precisa ser .csv ou .zip')


def _limpar_expiradas(agora: float) -> None:
  for token in [t for t, p in _previas.items() if agora - p['criado'] > VALIDADE_S]:
    shutil.rmtree(_previas.pop(token)['pasta'], ignore_errors=True)


def guardar(nome: str, conteudo: bytes, agora: float = None) -> str:
  """Guarda o arquivo enviado numa pasta temporária e devolve o token da prévia."""
  if not conteudo:
    raise ValueError('arquivo vazio')
  if len(conteudo) > LIMITE_BYTES:
    raise ValueError(f'arquivo acima de {LIMITE_BYTES // 2 ** 20} MB')
  ext = _extensao(nome)
  agora = time.time() if agora is None else agora
  pasta = tempfile.mkdtemp(prefix='qoe-upload-')
  path = os.path.join(pasta, 'arquivo' + ext)
  with open(path, 'wb') as handle:
    handle.write(conteudo)
  token = uuid.uuid4().hex
  with _lock:
    _limpar_expiradas(time.time())
    _previas[token] = {'pasta': pasta, 'path': path, 'ext': ext, 'criado': agora}
  return token


def _arquivo(token: str) -> dict:
  with _lock:
    _limpar_expiradas(time.time())
    item = _previas.get(token)
  if item is None:
    raise KeyError('prévia expirada ou desconhecida; envie o arquivo de novo')
  return item


def descartar(token: str) -> None:
  with _lock:
    item = _previas.pop(token, None)
  if item:
    shutil.rmtree(item['pasta'], ignore_errors=True)


def _bloqueios_de_nome(nome: str, ext: str, data_dir: str) -> list:
  saida = []
  if not NOME_ARQUIVO.match(nome) or '..' in nome:
    saida.append(f'nome {nome!r} inválido: letras, dígitos, ponto, hífen e sublinhado, terminando em .csv ou .zip')
  elif not nome.lower().endswith(ext):
    saida.append(f'o nome precisa terminar em {ext}, como o arquivo enviado')
  if any(m in nome for m in IGNORADOS):
    saida.append(f'nomes com {" ou ".join(IGNORADOS)} são ignorados pela descoberta de datasets')
  if os.path.exists(os.path.join(data_dir, nome)):
    saida.append(f'já existe data/{nome}')
  return saida


def _prefixo_candidato(valor) -> str:
  """Texto antes do primeiro separador (hífen, sublinhado, ponto ou espaço): `villa_r1` e `villa-sala` são da `villa`."""
  return re.split(r'[-_.\s]', str(valor).strip().lower(), maxsplit=1)[0]


def _preenchimento(frame: pd.DataFrame) -> dict:
  return {c: (round(float(frame[c].notna().mean()), 4) if c in frame.columns and len(frame) else None)
          for c in COLUNAS_CHAVE}


def _locais(frame: pd.DataFrame, registro: dict, conhecidos: set) -> tuple:
  """(prédios reconhecidos, grupos de valores desconhecidos por prefixo candidato)."""
  predios, desconhecidos = {}, {}
  for valor, linhas in frame['local'].dropna().value_counts().items():
    try:
      predio = core_sites.resolve_site_id(pd.Series([valor]), level='building', registro=registro).iloc[0]
      posicao = core_sites.resolve_site_id(pd.Series([valor]), registro=registro).iloc[0]
    except ValueError:
      grupo = desconhecidos.setdefault(_prefixo_candidato(valor), {'valores': [], 'linhas': 0})
      grupo['valores'].append(str(valor))
      grupo['linhas'] += int(linhas)
      continue
    item = predios.setdefault(predio, {'linhas': 0, 'posicoes': set()})
    item['linhas'] += int(linhas)
    item['posicoes'].add(posicao)
  lista_predios = [{'predio': k, 'rotulo': registro['predios'][k]['rotulo'], 'novo': k not in conhecidos,
                    'linhas': v['linhas'], 'posicoes': sorted(v['posicoes'])} for k, v in sorted(predios.items())]
  lista_desc = [{'prefixo': k, 'valores': sorted(v['valores']), 'linhas': v['linhas']}
                for k, v in sorted(desconhecidos.items())]
  return lista_predios, lista_desc


def _relacoes(frame: pd.DataFrame, existentes: list) -> dict:
  usaveis = [d for d in existentes if d.get('usable')]
  digest = core_carga.fingerprint(frame)
  duplicata = next((d['id'] for d in usaveis if d['fingerprint'] == digest), None)
  chaves = core_carga.chaves_alvos(frame)
  contido, contem = [], []
  for d in usaveis:
    outras = core_carga.chaves_alvos(d['_frame'])
    if chaves and chaves < outras:
      contido.append(d['id'])
    elif outras and outras < chaves:
      contem.append(d['id'])
  return {'fingerprint': digest, 'duplicata_de': duplicata, 'contido_em': contido, 'contem': contem}


def previa(token: str, nome: str, predios_novos=(), data_dir: str = None, existentes: list = None) -> dict:
  """O que entraria em data/ com este nome e estes prédios novos. Não grava nada."""
  data_dir = data_dir or core_carga.DATA_DIR
  existentes = core_carga.descobertos() if existentes is None else existentes
  item = _arquivo(token)
  bloqueios, avisos = _bloqueios_de_nome(nome, item['ext'], data_dir), []
  try:
    frame = core_carga._read_any(item['path'])
  except Exception as erro:  # o motivo vai para a tela
    return {'nome': nome, 'bloqueios': bloqueios + [f'arquivo ilegível: {erro}'], 'avisos': avisos}
  saida = {'nome': nome, 'linhas': int(len(frame)), 'colunas': int(len(frame.columns))}
  faltam = [c for c in OBRIGATORIAS if c not in frame.columns]
  if faltam:
    return dict(saida, bloqueios=bloqueios + [f'faltam colunas obrigatórias: {faltam}'], avisos=avisos)

  saida['geracao'] = core_carga._generation(frame.columns)
  saida['marcadores_ausentes'] = [m for m in core_carga.CURRENT_MARKERS if m not in frame.columns]
  if saida['geracao'] == 'legacy':
    avisos.append(f"geração legada (faltam {saida['marcadores_ausentes']}): entra, mas fica fora do conjunto padrão")
  saida['preenchimento'] = _preenchimento(frame)
  for coluna in core_carga.CURRENT_MARKERS:
    valor = saida['preenchimento'][coluna]
    if valor is not None and valor < LIMIAR_PREENCHIMENTO:
      avisos.append(f'{coluna} preenchido em só {valor:.0%} das linhas')

  atual = core_sites.registro_atual()
  try:
    registro = core_sites.com_novos(atual, predios_novos)
    core_sites.validar_predios(registro)
  except ValueError as erro:
    bloqueios.append(f'cadastro de prédio: {erro}')
    registro = atual
  vazios = int(frame['local'].isna().sum())
  if vazios:
    bloqueios.append(f'{vazios} linhas com local vazio')
  saida['predios'], saida['desconhecidos'] = _locais(frame, registro, set(atual['predios']))
  if saida['desconhecidos']:
    prefixos = [g['prefixo'] for g in saida['desconhecidos']]
    bloqueios.append(f'local desconhecido: cadastre o prédio dos prefixos {prefixos}')

  saida.update(_relacoes(frame, existentes))
  if saida['duplicata_de']:
    bloqueios.append(f"mesmos alvos de {saida['duplicata_de']}: seria descartado como duplicata")
  if saida['contido_em']:
    avisos.append(f"todas as linhas já estão em {saida['contido_em']}: seria marcado como substituído")
  if saida['contem']:
    avisos.append(f"contém todas as linhas de {saida['contem']}: esses passariam a ser marcados como substituídos")
  return dict(saida, bloqueios=bloqueios, avisos=avisos)


def confirmar(token: str, nome: str, predios_novos=(), data_dir: str = None, existentes: list = None) -> dict:
  """Refaz a prévia; sem bloqueio, cadastra os prédios e grava data/<nome>."""
  data_dir = data_dir or core_carga.DATA_DIR
  p = previa(token, nome, predios_novos, data_dir, existentes)
  if p['bloqueios']:
    raise ValueError('; '.join(p['bloqueios']))
  item = _arquivo(token)
  novos = [n['chave'].strip() for n in predios_novos]
  if predios_novos:
    core_sites.cadastrar_predios(predios_novos)
  destino = os.path.join(data_dir, nome)
  # .tmp não termina em .csv nem .zip: a descoberta nunca vê o arquivo pela metade.
  temporario = destino + '.tmp'
  try:
    shutil.copyfile(item['path'], temporario)
    os.replace(temporario, destino)
  except OSError as erro:
    if os.path.exists(temporario):
      os.unlink(temporario)
    extra = f'; os prédios {novos} já ficaram cadastrados em core/predios.json' if novos else ''
    raise OSError(f'não foi possível gravar data/{nome}: {erro}{extra}') from erro
  descartar(token)
  return {'dataset': nome, 'predios': novos, 'linhas': p['linhas']}

"""Catálogo de datasets do Studio: data/ (só leitura) e .studio/uploads/.

Porta de ml/core/carga.py (descoberta, fingerprint, duplicatas e contidos), sem
importar de lá. Nada aqui grava: data/ é a pasta que o benchmark varre inteira.
"""

import hashlib
import io
import os
import threading
import zipfile

import pandas as pd

from studio import caminhos

TARGETS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')
# Geração atual do esquema: só ela tem o eixo de contenção (combo, n_clients) e a geometria.
CURRENT_MARKERS = ['combo', 'n_clients', 'station_x', 'house_x0']
# As versões -fix/-distcalc recalculam os alvos e diferem da original em ~1e-14.
FINGERPRINT_DECIMALS = 6
# Os -qoe.csv carregam qoe_dw_score de fórmula perdida; filllast é intermediário.
IGNORADOS = ('-qoe', 'filllast')
# Entre datasets com os mesmos alvos, fica a versão corrigida.
MARCAS_CORRECAO = ('fix', 'distcalc')

_cache = {'itens': None}
_lock = threading.Lock()


def ler(path: str) -> pd.DataFrame:
  """Lê CSV ou o único CSV dentro de um zip, sem gravar nada em disco."""
  if path.endswith('.zip'):
    with zipfile.ZipFile(path) as arquivo:
      nomes = [n for n in arquivo.namelist() if n.endswith('.csv')]
      if len(nomes) != 1:
        raise ValueError(f'{os.path.basename(path)}: esperado exatamente 1 CSV no zip, achei {len(nomes)}')
      with arquivo.open(nomes[0]) as handle:
        return pd.read_csv(io.BytesIO(handle.read()), low_memory=False)
  return pd.read_csv(path, low_memory=False)


def geracao(colunas) -> str:
  return 'current' if all(m in colunas for m in CURRENT_MARKERS) else 'legacy'


def fingerprint(frame: pd.DataFrame) -> str:
  """Identidade dos alvos até a 6a casa: o mesmo critério das duplicatas."""
  alvos = frame[list(TARGETS)].round(FINGERPRINT_DECIMALS)
  digest = hashlib.sha256(pd.util.hash_pandas_object(alvos, index=False).values.tobytes())
  return digest.hexdigest()[:12]


def chaves_alvos(frame: pd.DataFrame) -> set:
  """Linhas de alvos como tuplas de texto: um dataset está contido noutro quando o conjunto está."""
  return set(map(tuple, frame[list(TARGETS)].round(FINGERPRINT_DECIMALS).astype(str).values))


def _pastas() -> list:
  return [('data', caminhos.DATA_DIR), ('upload', caminhos.UPLOADS_DIR)]


def descobrir() -> list:
  """Um descritor por .csv/.zip das duas pastas. Ilegível ou sem colunas vira inutilizável com o motivo."""
  achados, vistos = [], set()
  for origem, pasta in _pastas():
    if not os.path.isdir(pasta):
      continue
    for nome in sorted(os.listdir(pasta)):
      if not nome.endswith(('.csv', '.zip')) or any(m in nome for m in IGNORADOS):
        continue
      path = os.path.join(pasta, nome)
      base = {'id': nome, 'path': path, 'origem': origem, 'usable': False}
      if nome in vistos:
        achados.append(dict(base, error=f'nome repetido: {nome} já existe em data/'))
        continue
      vistos.add(nome)
      try:
        frame = ler(path)
      except Exception as erro:  # o motivo vai para a tela
        achados.append(dict(base, error=str(erro)))
        continue
      faltam = [c for c in ('local',) + TARGETS if c not in frame.columns]
      if faltam:
        achados.append(dict(base, error=f'faltam colunas {faltam}'))
        continue
      achados.append(dict(base, usable=True, rows=int(len(frame)), columns=int(len(frame.columns)),
                          generation=geracao(frame.columns), fingerprint=fingerprint(frame), _frame=frame))
  return achados


def contidos(itens: list) -> dict:
  """{id: id maior} para datasets cujas linhas estão inteiras dentro de outro (0817 dentro de 0827)."""
  veredito, chaves = {}, {}
  for item in itens:
    if item.get('usable'):
      chaves[item['id']] = chaves_alvos(item['_frame'])
  for a, chaves_a in chaves.items():
    for b, chaves_b in chaves.items():
      if a != b and chaves_a and chaves_a <= chaves_b and len(chaves_a) < len(chaves_b):
        veredito[a] = b
  return veredito


def _preferencia(item) -> tuple:
  """Ordem entre datasets com os mesmos alvos: corrigido, depois mais colunas, depois o nome."""
  corrigido = any(m in item['id'].lower() for m in MARCAS_CORRECAO)
  return (not corrigido, -int(item.get('columns') or 0), item['id'])


def duplicatas(itens: list) -> dict:
  """{id: id que fica} para datasets com o mesmo fingerprint: só um do grupo fica."""
  grupos = {}
  for item in itens:
    if item.get('usable'):
      grupos.setdefault(item['fingerprint'], []).append(item)
  duplicata_de = {}
  for grupo in grupos.values():
    primeiro, *resto = sorted(grupo, key=_preferencia)
    for item in resto:
      duplicata_de[item['id']] = primeiro['id']
  return duplicata_de


def ids_padrao(itens: list) -> list:
  """O conjunto padrão: utilizável, geração atual, nem contido nem duplicado."""
  fora = set(contidos(itens)) | set(duplicatas(itens))
  return [d['id'] for d in itens
          if d.get('usable') and d['generation'] == 'current' and d['id'] not in fora]


def descobertos() -> list:
  """descobrir() uma vez por processo: reler o zip de 52 MB a cada requisição travaria as telas."""
  with _lock:
    if _cache['itens'] is None:
      _cache['itens'] = descobrir()
    return _cache['itens']


def esquecer() -> None:
  """Dataset novo: a próxima chamada de descobertos() varre as pastas de novo."""
  with _lock:
    _cache['itens'] = None


def usaveis_por_id(ids, itens: list = None) -> list:
  """Os descritores utilizáveis dos ids, na ordem pedida. ValueError lista os que faltam."""
  itens = descobertos() if itens is None else itens
  por_id = {d['id']: d for d in itens if d.get('usable')}
  faltam = [i for i in ids if i not in por_id]
  if faltam:
    raise ValueError(f'datasets desconhecidos ou inutilizáveis: {faltam}')
  return [por_id[i] for i in ids]


def sobreposicoes(ids, itens: list = None) -> list:
  """Pares entre os escolhidos com os mesmos alvos ou um contido no outro: as amostras contariam duas vezes."""
  chaves = {d['id']: chaves_alvos(d['_frame']) for d in usaveis_por_id(ids, itens)}
  saida = []
  for a in sorted(chaves):
    for b in sorted(chaves):
      if a < b and chaves[a] == chaves[b]:
        saida.append(f'{a} e {b} têm os mesmos alvos')
      elif a != b and chaves[a] and chaves[a] < chaves[b]:
        saida.append(f'{a} está contido em {b}')
  return saida

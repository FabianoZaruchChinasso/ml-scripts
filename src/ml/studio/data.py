"""Descoberta de datasets e montagem do payload do QoE Studio.

Tudo que o navegador precisa vai num payload so: as linhas cruas dos quatro
alvos universais. A capacidade por aplicacao e recalculada no cliente sempre que
os limiares mudam, entao os sliders respondem sem ida ao servidor.
"""

import hashlib
import io
import os
import zipfile

import pandas as pd

from ml.studio.plans import montar_plantas

TARGETS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']

# A geracao de esquema e o que separa `legacy_` do modelo de colunas atual.
# `combo`/`n_clients` (o eixo de contencao) so existem na geracao atual.
CURRENT_MARKERS = ['combo', 'n_clients', 'station_x', 'house_x0']

DATA_DIR = 'data'

# O prefixo `cwpb` deixou de distinguir predio: e o mapa explicito que manda.
# Os coletores sao donos deste bloco.
BUILDINGS = {
  'casa': {
    'label': 'Casa',
    'positions': ['sala', 'quarto', 'suite', '1', '2', '3'],
  },
  'cowork-pedra-branca': {
    'label': 'Cowork Pedra Branca',
    'positions': ['cwpb-1', 'cwpb-2', 'cwpb-2m', 'cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m'],
  },
}

POSITION_LABELS = {'1': 'sala', '2': 'quarto', '3': 'suite'}


def _canonical_local(local_value) -> str:
  """'1.0', 'Sala' e 'sala' precisam cair na mesma chave.

  O transform da residencia reescreve os nomes de comodo como 1/2/3, entao as
  duas grafias chegam aqui e tem de resolver para a mesma posicao.
  """
  text = str(local_value).strip().lower()
  try:
    number = float(text)
  except ValueError:
    return text
  return str(int(number)) if number.is_integer() else text


def _building_of(local_value) -> str:
  key = _canonical_local(local_value)
  for building, meta in BUILDINGS.items():
    if key in meta['positions']:
      return building
  raise ValueError(
    f'local {local_value!r} nao esta em nenhum predio de BUILDINGS. '
    'Acrescente uma regra explicita; nunca deixe um valor desconhecido virar grupo proprio.'
  )


def _read_any(path: str) -> pd.DataFrame:
  """Le CSV ou o unico CSV dentro de um zip, sem gravar nada em disco."""
  if path.endswith('.zip'):
    with zipfile.ZipFile(path) as archive:
      names = [n for n in archive.namelist() if n.endswith('.csv')]
      if len(names) != 1:
        raise ValueError(f'{path}: esperado exatamente 1 CSV no zip, achei {len(names)}')
      with archive.open(names[0]) as handle:
        return pd.read_csv(io.BytesIO(handle.read()), low_memory=False)
  return pd.read_csv(path, low_memory=False)


def _generation(columns) -> str:
  return 'current' if all(m in columns for m in CURRENT_MARKERS) else 'legacy'


def discover() -> list:
  """Varre data/ e devolve um descritor por dataset utilizavel."""
  found = []
  for name in sorted(os.listdir(DATA_DIR)):
    if not (name.endswith('.csv') or name.endswith('.zip')):
      continue
    # Os -qoe.csv carregam qoe_dw_score, cuja formula se perdeu e cujas duas
    # versoes diferem por ~3200x. Ficam de fora ate serem recalculados.
    if '-qoe' in name or 'filllast' in name:
      continue
    path = os.path.join(DATA_DIR, name)
    try:
      frame = _read_any(path)
    except Exception as error:
      found.append({'id': name, 'path': path, 'error': str(error), 'usable': False})
      continue
    if 'local' not in frame.columns or not all(t in frame.columns for t in TARGETS):
      continue
    digest = hashlib.sha256(pd.util.hash_pandas_object(frame[TARGETS], index=False).values.tobytes())
    found.append({
      'id': name,
      'path': path,
      'usable': True,
      'rows': int(len(frame)),
      'columns': int(len(frame.columns)),
      'generation': _generation(frame.columns),
      'fingerprint': digest.hexdigest()[:12],
      '_frame': frame,
    })
  return found


_descobertos = None


def descobertos() -> list:
  """discover() uma vez por processo: reler o zip de 52 MB a cada requisicao travaria as views."""
  global _descobertos
  if _descobertos is None:
    _descobertos = discover()
  return _descobertos


def _superseded(datasets: list) -> dict:
  """Marca datasets cujas linhas estao inteiras dentro de outro (0817 dentro de 0827)."""
  verdict = {}
  keyed = {}
  for item in datasets:
    if not item.get('usable'):
      continue
    frame = item['_frame']
    keys = set(map(tuple, frame[TARGETS].round(6).astype(str).values))
    keyed[item['id']] = keys
  for a, keys_a in keyed.items():
    for b, keys_b in keyed.items():
      if a == b or not keys_a:
        continue
      if keys_a <= keys_b and len(keys_a) < len(keys_b):
        verdict[a] = b
  return verdict


def build_payload() -> dict:
  datasets = descobertos()
  superseded = _superseded(datasets)
  # Fingerprint igual = os mesmos alvos byte a byte. Manter os dois ligados
  # duplica o peso de cada amostra sem avisar.
  seen_fingerprints = {}
  duplicate_of = {}
  for item in datasets:
    if not item.get('usable'):
      continue
    first = seen_fingerprints.setdefault(item['fingerprint'], item['id'])
    if first != item['id']:
      duplicate_of[item['id']] = first
  rows = []
  descriptors = []

  for item in datasets:
    if not item.get('usable'):
      descriptors.append({k: v for k, v in item.items() if k != '_frame'})
      continue
    frame = item['_frame']
    generation = item['generation']
    enabled_default = (generation == 'current'
                       and item['id'] not in superseded
                       and item['id'] not in duplicate_of)

    buildings = set()
    positions = set()
    for _, row in frame.iterrows():
      local = row['local']
      try:
        building = _building_of(local)
      except ValueError:
        continue
      canonical = _canonical_local(local)
      position = POSITION_LABELS.get(canonical, canonical)
      buildings.add(building)
      positions.add(position)
      values = [row[t] for t in TARGETS]
      if any(pd.isna(v) for v in values):
        continue
      record = {
        'ds': item['id'],
        'gen': generation,
        'b': building,
        'p': position,
        'dn': round(float(row[TARGETS[0]]), 3),
        'up': round(float(row[TARGETS[1]]), 3),
        'lat': round(float(row[TARGETS[2]]), 3),
        'jit': round(float(row[TARGETS[3]]), 3),
      }
      if generation == 'current':
        record['n'] = int(row['n_clients']) if not pd.isna(row.get('n_clients')) else None
        record['combo'] = row.get('combo') if not pd.isna(row.get('combo')) else None
        for src, dst in (('station_x', 'x'), ('station_y', 'y'), ('station_z', 'z')):
          value = row.get(src)
          record[dst] = None if pd.isna(value) else float(value)
      rows.append(record)

    descriptors.append({
      'id': item['id'],
      'rows': item['rows'],
      'columns': item['columns'],
      'generation': generation,
      'fingerprint': item['fingerprint'],
      'buildings': sorted(buildings),
      'positions': sorted(positions),
      'enabled': enabled_default,
      'supersededBy': superseded.get(item['id']),
      'duplicateOf': duplicate_of.get(item['id']),
      'hasContention': generation == 'current',
    })

  envelopes = {}
  for item in datasets:
    if not item.get('usable') or item['generation'] != 'current':
      continue
    frame = item['_frame']
    for _, row in frame.iterrows():
      try:
        building = _building_of(row['local'])
      except ValueError:
        continue
      if building in envelopes or pd.isna(row.get('house_x0')):
        continue
      envelopes[building] = {
        'w': float(row['house_x0']), 'h': float(row['house_y0']), 'z': float(row['house_z0']),
        'routerX': float(row['router_x']), 'routerY': float(row['router_y']),
      }

  plantas, plantas_avisos = montar_plantas(envelopes)
  return {
    'datasets': descriptors,
    'rows': rows,
    'buildings': {k: {'label': v['label']} for k, v in BUILDINGS.items()},
    'envelopes': envelopes,
    'plantas': plantas,
    'plantasAvisos': plantas_avisos,
  }

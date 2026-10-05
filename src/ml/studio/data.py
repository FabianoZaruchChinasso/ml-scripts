"""Descoberta de datasets e montagem do payload do QoE Studio.

Tudo que o navegador precisa vai num payload so: as linhas cruas dos quatro
alvos universais. A capacidade por aplicacao e recalculada no cliente sempre que
os limiares mudam, entao os sliders respondem sem ida ao servidor.
"""

from collections import Counter

import pandas as pd

from ml.core import aplicacoes as core_aplicacoes
from ml.core.carga import TARGETS as _TARGETS
from ml.core.carga import _superseded, descobertos, discover, duplicatas
from ml.core.sites import CORPORATE, DOMESTIC
from ml.studio.plans import andar_de, montar_plantas

TARGETS = list(_TARGETS)

# O prefixo `cwpb` deixou de distinguir predio: e o mapa explicito que manda.
# Os coletores sao donos deste bloco. `ambiente` precisa bater com
# core/sites.BUILDING_ENVIRONMENT (o teste garante).
BUILDINGS = {
  'casa': {
    'label': 'Casa',
    'ambiente': DOMESTIC,
    'positions': ['sala', 'quarto', 'suite', '1', '2', '3'],
  },
  'cowork-pedra-branca': {
    'label': 'Cowork Pedra Branca',
    'ambiente': CORPORATE,
    'positions': ['cwpb-1', 'cwpb-2', 'cwpb-2m', 'cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m'],
  },
  'hotmilk': {
    'label': 'Hotmilk',
    'ambiente': CORPORATE,
    'positions': ['hotmilk-copa', 'hotmilk-aquario', 'hotmilk-aquario-fora', 'quarto-marcelo'],
  },
  'casa-marcelo': {
    'label': 'Casa do Marcelo',
    'ambiente': DOMESTIC,
    'positions': ['marcelo-copa', 'marcelo-copa-split', 'marcelo-inf-ext', 'marcelo-inf-quarto',
                  'marcelo-inf-quarto-split', 'marcelo-inf-sala', 'marcelo-inf-sala-split',
                  'marcelo-quarto', 'marcelo-quarto-split', 'marcelo-sala-estar'],
  },
}

AMBIENTES = {DOMESTIC: 'Doméstico', CORPORATE: 'Corporativo'}

# quarto-marcelo: rotulo antigo que o 20260917-metrics-fix regravou como hotmilk-aquario.
POSITION_LABELS = {'1': 'sala', '2': 'quarto', '3': 'suite', 'quarto-marcelo': 'hotmilk-aquario'}


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


def build_payload() -> dict:
  datasets = descobertos()
  superseded = _superseded(datasets)
  duplicate_of = duplicatas(datasets)
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

  # Vence o envelope mais frequente do prédio, não o da primeira linha: a coleta do
  # 20260925 abriu com 4 linhas do envelope de outro prédio (410x1386).
  votos = {}
  for item in datasets:
    if not item.get('usable') or item['generation'] != 'current':
      continue
    frame = item['_frame']
    for _, row in frame.iterrows():
      try:
        building = _building_of(row['local'])
      except ValueError:
        continue
      if pd.isna(row.get('house_x0')):
        continue
      chave = (float(row['house_x0']), float(row['house_y0']), float(row['house_z0']),
               float(row['router_x']), float(row['router_y']),
               None if pd.isna(row.get('router_z')) else float(row['router_z']))
      votos.setdefault(building, Counter())[chave] += 1
  envelopes = {}
  for building, contagem in votos.items():
    w, h, z, router_x, router_y, router_z = contagem.most_common(1)[0][0]
    envelopes[building] = {'w': w, 'h': h, 'z': z,
                           'routerX': router_x, 'routerY': router_y, 'routerZ': router_z}

  plantas, plantas_avisos = montar_plantas(envelopes)
  for record in rows:
    andares = (plantas.get(record['b']) or {}).get('andares')
    if andares:
      record['andar'] = andar_de(record.get('z'), andares)
  return {
    'datasets': descriptors,
    'rows': rows,
    'buildings': {k: {'label': v['label'], 'ambiente': v['ambiente']} for k, v in BUILDINGS.items()},
    'ambientes': AMBIENTES,
    'aplicacoes': core_aplicacoes.carregar(),
    'envelopes': envelopes,
    'plantas': plantas,
    'plantasAvisos': plantas_avisos,
  }

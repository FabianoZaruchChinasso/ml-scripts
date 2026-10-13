"""Descoberta de datasets e montagem do payload do QoE Studio.

Tudo que o navegador precisa vai num payload so: as linhas cruas dos quatro
alvos universais. A capacidade por aplicacao e recalculada no cliente sempre que
os limiares mudam, entao os sliders respondem sem ida ao servidor.
"""

from collections import Counter
from functools import lru_cache

import pandas as pd

from ml.core import aplicacoes as core_aplicacoes
from ml.core.carga import TARGETS as _TARGETS
from ml.core.carga import _superseded, descobertos, discover, duplicatas
from ml.core.sites import CORPORATE, DOMESTIC, resolve_site_id
from ml.studio.plans import andar_de, montar_plantas

TARGETS = list(_TARGETS)

# Rótulo e ambiente de cada prédio do Studio. Qual posição é de qual prédio é
# decidido só por core/sites.py (PREDIO_DO_CORE): assim o Studio e o treino nunca
# discordam, e uma posição nova não some do Studio sem aviso.
BUILDINGS = {
  'casa': {'label': 'Casa', 'ambiente': DOMESTIC},
  'cowork-pedra-branca': {'label': 'Cowork Pedra Branca', 'ambiente': CORPORATE},
  'hotmilk': {'label': 'Hotmilk', 'ambiente': CORPORATE},
  'casa-marcelo': {'label': 'Casa do Marcelo', 'ambiente': DOMESTIC},
}

# Prédio de core/sites.py -> chave do Studio (as chaves do Studio já estão em plantas.json).
PREDIO_DO_CORE = {
  'residencia': 'casa',
  'coworking': 'cowork-pedra-branca',
  'hotmilk': 'hotmilk',
  'casa-marcelo': 'casa-marcelo',
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


@lru_cache(maxsize=None)
def _building_de_texto(texto: str) -> str:
  return PREDIO_DO_CORE[resolve_site_id(pd.Series([texto]), level='building').iloc[0]]


def _building_of(local_value) -> str:
  """Prédio do Studio para um valor de `local`, pela regra de core/sites.py.

  Levanta ValueError para valor vazio ou que o core não conhece: nunca vira grupo próprio.
  """
  if pd.isna(local_value):
    raise ValueError('local vazio')
  return _building_de_texto(str(local_value))


def build_payload() -> dict:
  datasets = descobertos()
  superseded = _superseded(datasets)
  duplicate_of = duplicatas(datasets)
  rows = []
  descriptors = []
  locais_desconhecidos = []

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
    desconhecidos = Counter()
    for _, row in frame.iterrows():
      local = row['local']
      try:
        building = _building_of(local)
      except ValueError:
        desconhecidos[str(local)] += 1
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

    if desconhecidos:
      locais_desconhecidos.append({'dataset': item['id'], 'valores': sorted(desconhecidos),
                                   'linhas': int(sum(desconhecidos.values()))})
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
    'locaisDesconhecidos': locais_desconhecidos,
  }

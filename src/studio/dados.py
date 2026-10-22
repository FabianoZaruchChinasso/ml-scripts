"""Payload da área Dados: as linhas cruas dos quatro alvos, e o navegador agrega.

Porta de ml/studio/data.py com o mesmo formato, para que logica.js, dados.js e
planta.js funcionem sem mudança. Diferenças: prédios de config/predios.json,
datasets inutilizáveis à parte e `enabled` posto por com_conjunto() a cada pedido.
"""

from collections import Counter

import pandas as pd

from studio import aplicacoes, catalogo, predios
from studio.plantas import andar_de, montar_plantas

TARGETS = list(catalogo.TARGETS)
AMBIENTES = {predios.DOMESTICO: 'Doméstico', predios.CORPORATIVO: 'Corporativo'}
# quarto-marcelo: rótulo antigo que o 20260917-metrics-fix regravou como hotmilk-aquario.
POSITION_LABELS = {'1': 'sala', '2': 'quarto', '3': 'suite', 'quarto-marcelo': 'hotmilk-aquario'}


def predios_studio(registro: dict) -> dict:
  """{chave do Studio: {'label', 'ambiente'}} de todos os prédios do cadastro."""
  return {p['studio']: {'label': p['rotulo'], 'ambiente': p['ambiente']} for p in registro['predios'].values()}


def _canonical_local(local_value) -> str:
  """'1.0', 'Sala' e 'sala' precisam cair na mesma chave."""
  text = str(local_value).strip().lower()
  try:
    number = float(text)
  except ValueError:
    return text
  return str(int(number)) if number.is_integer() else text


def _resolvedor(registro: dict):
  """local -> chave do Studio do prédio, com memória por valor. ValueError para vazio ou desconhecido."""
  memoria = {}

  def predio_de(local_value) -> str:
    if pd.isna(local_value):
      raise ValueError('local vazio')
    texto = str(local_value)
    if texto not in memoria:
      try:
        nome = predios.resolver(pd.Series([texto]), 'predio', registro).iloc[0]
        memoria[texto] = registro['predios'][nome]['studio']
      except ValueError:
        memoria[texto] = None
    if memoria[texto] is None:
      raise ValueError(f'local desconhecido: {texto!r}')
    return memoria[texto]

  return predio_de


def _registro_linha(item: dict, row, building: str, position: str) -> dict:
  record = {
    'ds': item['id'],
    'gen': item['generation'],
    'b': building,
    'p': position,
    'dn': round(float(row[TARGETS[0]]), 3),
    'up': round(float(row[TARGETS[1]]), 3),
    'lat': round(float(row[TARGETS[2]]), 3),
    'jit': round(float(row[TARGETS[3]]), 3),
  }
  if item['generation'] == 'current':
    record['n'] = int(row['n_clients']) if not pd.isna(row.get('n_clients')) else None
    record['combo'] = row.get('combo') if not pd.isna(row.get('combo')) else None
    for src, dst in (('station_x', 'x'), ('station_y', 'y'), ('station_z', 'z')):
      value = row.get(src)
      record[dst] = None if pd.isna(value) else float(value)
  return record


def _envelopes(itens: list, predio_de) -> dict:
  """Vence o envelope mais frequente do prédio, não o da primeira linha (o 20260925 abriu com
  4 linhas do envelope de outro prédio)."""
  votos = {}
  for item in itens:
    if not item.get('usable') or item['generation'] != 'current':
      continue
    for _, row in item['_frame'].iterrows():
      try:
        building = predio_de(row['local'])
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
    envelopes[building] = {'w': w, 'h': h, 'z': z, 'routerX': router_x, 'routerY': router_y, 'routerZ': router_z}
  return envelopes


def montar_payload(itens: list = None) -> dict:
  itens = catalogo.descobertos() if itens is None else itens
  registro = predios.atual()
  predio_de = _resolvedor(registro)
  substituidos, duplicados = catalogo.contidos(itens), catalogo.duplicatas(itens)
  padrao = set(catalogo.ids_padrao(itens))
  rows, descriptors, inutilizaveis, locais_desconhecidos = [], [], [], []

  for item in itens:
    if not item.get('usable'):
      inutilizaveis.append({'id': item['id'], 'origem': item['origem'], 'erro': item.get('error')})
      continue
    buildings, positions, desconhecidos = set(), set(), Counter()
    for _, row in item['_frame'].iterrows():
      local = row['local']
      try:
        building = predio_de(local)
      except ValueError:
        desconhecidos[str(local)] += 1
        continue
      canonical = _canonical_local(local)
      position = POSITION_LABELS.get(canonical, canonical)
      buildings.add(building)
      positions.add(position)
      if any(pd.isna(row[t]) for t in TARGETS):
        continue
      rows.append(_registro_linha(item, row, building, position))

    if desconhecidos:
      locais_desconhecidos.append({'dataset': item['id'], 'valores': sorted(desconhecidos),
                                   'linhas': int(sum(desconhecidos.values()))})
    descriptors.append({
      'id': item['id'],
      'origem': item['origem'],
      'rows': item['rows'],
      'columns': item['columns'],
      'generation': item['generation'],
      'fingerprint': item['fingerprint'],
      'buildings': sorted(buildings),
      'positions': sorted(positions),
      'enabled': item['id'] in padrao,
      'supersededBy': substituidos.get(item['id']),
      'duplicateOf': duplicados.get(item['id']),
      'hasContention': item['generation'] == 'current',
    })

  envelopes = _envelopes(itens, predio_de)
  plantas, plantas_avisos = montar_plantas(envelopes)
  for record in rows:
    andares = (plantas.get(record['b']) or {}).get('andares')
    if andares:
      record['andar'] = andar_de(record.get('z'), andares)
  return {
    'datasets': descriptors,
    'inutilizaveis': inutilizaveis,
    'rows': rows,
    'buildings': predios_studio(registro),
    'ambientes': AMBIENTES,
    'aplicacoes': aplicacoes.carregar(),
    'envelopes': envelopes,
    'plantas': plantas,
    'plantasAvisos': plantas_avisos,
    'locaisDesconhecidos': locais_desconhecidos,
  }


def com_conjunto(payload: dict, ativos) -> dict:
  """Cópia rasa do payload com `enabled` de cada dataset vindo do conjunto ativo."""
  ativos = set(ativos)
  return dict(payload, datasets=[dict(d, enabled=d['id'] in ativos) for d in payload['datasets']])

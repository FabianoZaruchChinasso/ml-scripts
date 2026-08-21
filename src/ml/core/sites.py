import math

import pandas as pd

OFFICE_PREFIX = 'cwpb'
RESIDENCE_BUILDING = 'residencia'
COWORKING_BUILDING = 'coworking'

# `local` grava a POSIÇÃO de medição dentro de um prédio, não o prédio. O
# transform da residência reescreve os nomes de cômodo como 1/2/3 antes de os
# dados chegarem aqui, então as duas grafias resolvem para a mesma posição.
RESIDENCE_POSITIONS = {
  '1': 'res-sala',
  'sala': 'res-sala',
  '2': 'res-quarto',
  'quarto': 'res-quarto',
  '3': 'res-suite',
  'suite': 'res-suite',
}

GROUP_LEVELS = ('position', 'building')


def _lookup_key(value) -> str:
  """Canonicaliza uma célula de `local`: '1.0' e 'Sala' viram chaves de busca."""
  if pd.isna(value):
    raise ValueError(
      "site resolution failed: 'local' contains an empty value. "
      'Every row must belong to a known position.'
    )
  text = str(value).strip().lower()
  try:
    number = float(text)
  except ValueError:
    return text
  if not math.isfinite(number) or not number.is_integer():
    raise ValueError(
      f'site resolution failed: unrecognised local value {value!r}. '
      'Add an explicit rule in core/sites.py; never let an unknown value form its own group.'
    ) from None
  return str(int(number))


def _resolve_one(value, level: str) -> str:
  key = _lookup_key(value)
  if key.startswith(OFFICE_PREFIX):
    return COWORKING_BUILDING if level == 'building' else key
  if key in RESIDENCE_POSITIONS:
    return RESIDENCE_BUILDING if level == 'building' else RESIDENCE_POSITIONS[key]
  raise ValueError(
    f'site resolution failed: unrecognised local value {value!r}. '
    'Add an explicit rule in core/sites.py; never let an unknown value form its own group.'
  )


def resolve_site_id(local_values: pd.Series, level: str = 'position') -> pd.Series:
  """Mapeia valores brutos de `local` para identificadores canônicos de grupo.

  `local` é a posição de medição dentro de um prédio: a residência usa nomes de
  cômodo (reescritos como 1/2/3 pelo transform) e o coworking usa rótulos de
  distância (`cwpb-*`).

  level='position' -> 7 grupos, um por ponto de medição (padrão, número principal).
  level='building' -> 2 grupos, `residencia` e `coworking` (viabilidade, n=2).
  """
  if level not in GROUP_LEVELS:
    raise ValueError(
      f'unknown group level {level!r}; expected one of {list(GROUP_LEVELS)}')
  return local_values.map(lambda value: _resolve_one(value, level))

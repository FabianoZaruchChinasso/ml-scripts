"""Prédios e posições de coleta: de qual posição, prédio e ambiente é cada `local`.

O registro vive em predios.json, versionado e gravado pelo QoE Studio (cadastro de
prédio novo no upload de dados). Treino e Studio leem o mesmo arquivo, então nunca
discordam sobre de qual prédio é uma linha.
"""

import copy
import json
import math
import os
import re
import threading

import pandas as pd

from ml.core.arquivos import gravar_json_atomico

PREDIOS_PATH = os.path.join(os.path.dirname(__file__), 'predios.json')

# Ambiente de cada local de coleta. Doméstico e corporativo diferem em
# densidade de redes vizinhas, perfil de tráfego e distâncias: é o eixo que
# decide se um modelo treinado num pode ser usado no outro.
DOMESTIC = 'domestico'
CORPORATE = 'corporativo'
ENVIRONMENTS = (DOMESTIC, CORPORATE)
GROUP_LEVELS = ('position', 'building')

NOME = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
CAMPOS_OBRIGATORIOS = {'rotulo', 'studio', 'ambiente', 'prefixos'}
CAMPOS = CAMPOS_OBRIGATORIOS | {'posicoes', 'tetos_wan'}
CAMPOS_NOVO = {'chave', 'rotulo', 'ambiente', 'prefixo'}

# Preenchidos por recarregar() e mutados no lugar: carga.py, studio/api.py e os
# testes importam estes nomes, e uma reatribuição deixaria quem importou com a cópia velha.
BUILDING_ENVIRONMENT = {}
# Teto do plano de WAN por prédio e por alvo (Mbps): acima disto o speedtest mede a
# internet, não o Wi-Fi. Inferido pelo p99 em 2026-10-05 na residência. Prédio
# ausente = sem teto conhecido.
TETOS_WAN = {}
_estado = {'path': PREDIOS_PATH, 'registro': None}
_lock = threading.Lock()


def _texto(valor) -> bool:
  return isinstance(valor, str) and bool(valor.strip())


def _validar_predio(chave: str, p) -> None:
  if not NOME.match(chave):
    raise ValueError(f'{chave!r}: chave de prédio inválida (minúsculas, dígitos e hífen, 2 a 40 caracteres)')
  if not isinstance(p, dict) or not CAMPOS_OBRIGATORIOS <= set(p) <= CAMPOS:
    raise ValueError(f'{chave!r}: campos inválidos {sorted(p) if isinstance(p, dict) else p!r}; '
                     f'obrigatórios {sorted(CAMPOS_OBRIGATORIOS)}')
  if not _texto(p['rotulo']) or len(p['rotulo']) > 60:
    raise ValueError(f'{chave!r}: rótulo obrigatório, de até 60 caracteres')
  if not isinstance(p['studio'], str) or not NOME.match(p['studio']):
    raise ValueError(f"{chave!r}: chave do Studio {p['studio']!r} inválida")
  if p['ambiente'] not in ENVIRONMENTS:
    raise ValueError(f"{chave!r}: ambiente {p['ambiente']!r} inválido; esperado um de {list(ENVIRONMENTS)}")
  prefixos = p['prefixos']
  if not isinstance(prefixos, list) or not all(isinstance(x, str) and NOME.match(x) for x in prefixos):
    raise ValueError(f'{chave!r}: prefixos precisam ser minúsculas, dígitos e hífen, 2 a 40 caracteres')
  posicoes = p.get('posicoes', {})
  if not isinstance(posicoes, dict) or not all(
      isinstance(k, str) and k == k.strip().lower() and _texto(v) for k, v in posicoes.items()):
    raise ValueError(f'{chave!r}: posicoes precisa ser {{valor em minúsculas: posição}}')
  if not prefixos and not posicoes:
    raise ValueError(f'{chave!r}: prédio sem prefixos precisa de posicoes')
  tetos = p.get('tetos_wan', {})
  if not isinstance(tetos, dict) or not all(
      isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in tetos.values()):
    raise ValueError(f'{chave!r}: tetos_wan precisa ser {{alvo: Mbps positivo}}')


def validar_predios(registro) -> None:
  """Levanta ValueError com a causa; não devolve nada quando o registro é válido."""
  if not isinstance(registro, dict) or set(registro) != {'predios', 'aliases'}:
    raise ValueError("predios.json precisa ter exatamente as chaves 'predios' e 'aliases'")
  predios, aliases = registro['predios'], registro['aliases']
  if not isinstance(predios, dict) or not predios:
    raise ValueError('predios.json precisa de pelo menos um prédio')
  if not isinstance(aliases, dict) or not all(_texto(k) and _texto(v) for k, v in aliases.items()):
    raise ValueError('aliases precisa ser {valor antigo: valor corrigido}')
  donos_studio, prefixos = {}, []
  for chave, p in predios.items():
    _validar_predio(chave, p)
    if p['studio'] in donos_studio:
      raise ValueError(f"{chave!r}: chave do Studio {p['studio']!r} já usada por {donos_studio[p['studio']]!r}")
    donos_studio[p['studio']] = chave
    prefixos += [(x, chave) for x in p['prefixos']]
  # `startswith` decide o prédio: dois prefixos em que um começa com o outro
  # tornariam a resolução dependente da ordem do arquivo.
  for i, (a, dono_a) in enumerate(prefixos):
    for b, dono_b in prefixos[i + 1:]:
      if a.startswith(b) or b.startswith(a):
        raise ValueError(f'prefixos em conflito: {a!r} ({dono_a}) e {b!r} ({dono_b}); um começa com o outro')
  soltos = [k for p in predios.values() for k in p.get('posicoes', {})] + list(aliases)
  for valor in soltos:
    for prefixo, dono in prefixos:
      if valor.startswith(prefixo):
        raise ValueError(f'{valor!r} começa com o prefixo {prefixo!r} de {dono!r}: a resolução ficaria ambígua')


def carregar_predios(path: str = None) -> dict:
  with open(path or _estado['path'], encoding='utf-8') as handle:
    registro = json.load(handle)
  validar_predios(registro)
  return registro


def _aplicar(registro: dict) -> None:
  _estado['registro'] = registro
  BUILDING_ENVIRONMENT.clear()
  BUILDING_ENVIRONMENT.update({k: p['ambiente'] for k, p in registro['predios'].items()})
  TETOS_WAN.clear()
  TETOS_WAN.update({k: dict(p['tetos_wan']) for k, p in registro['predios'].items() if p.get('tetos_wan')})


def recarregar(path: str = None) -> None:
  """Relê o registro (de `path`, que passa a ser o arquivo em uso, ou do atual)."""
  with _lock:
    if path:
      _estado['path'] = path
    _aplicar(carregar_predios(_estado['path']))


def registro_atual() -> dict:
  """Cópia do registro em uso: quem altera a cópia não altera o registro."""
  return copy.deepcopy(_estado['registro'])


def _entrada_nova(novo) -> tuple:
  if not isinstance(novo, dict) or set(novo) != CAMPOS_NOVO or not all(_texto(novo[c]) for c in CAMPOS_NOVO):
    raise ValueError(f'prédio novo precisa de {sorted(CAMPOS_NOVO)} preenchidos')
  chave = novo['chave'].strip()
  return chave, {'rotulo': novo['rotulo'].strip(), 'studio': chave, 'ambiente': novo['ambiente'],
                 'prefixos': [novo['prefixo'].strip().lower()]}


def com_novos(registro: dict, novos) -> dict:
  """Cópia de `registro` com os prédios novos ({chave, rotulo, ambiente, prefixo}). Não valida o todo."""
  saida = copy.deepcopy(registro)
  for novo in novos:
    chave, entrada = _entrada_nova(novo)
    if chave in saida['predios']:
      raise ValueError(f'o prédio {chave!r} já existe')
    saida['predios'][chave] = entrada
  return saida


def cadastrar_predios(novos) -> dict:
  """Acrescenta prédios ao arquivo em uso. Valida o registro inteiro antes de gravar."""
  with _lock:
    path = _estado['path']
    registro = com_novos(carregar_predios(path), novos)
    validar_predios(registro)
    gravar_json_atomico(path, registro)
    _aplicar(registro)
  return copy.deepcopy(registro)


def teto_wan(predio: str, alvo: str):
  """Teto de WAN do prédio para o alvo, ou None quando não há teto conhecido."""
  return TETOS_WAN.get(predio, {}).get(alvo)


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
      'Register its building in core/predios.json; never let an unknown value form its own group.'
    ) from None
  return str(int(number))


def _resolve_one(value, level: str, registro: dict) -> str:
  key = _lookup_key(value)
  key = registro['aliases'].get(key, key)
  for chave, p in registro['predios'].items():
    if any(key.startswith(prefixo) for prefixo in p['prefixos']):
      return chave if level == 'building' else key
  for chave, p in registro['predios'].items():
    posicao = p.get('posicoes', {}).get(key)
    if posicao is not None:
      return chave if level == 'building' else posicao
  raise ValueError(
    f'site resolution failed: unrecognised local value {value!r}. '
    'Register its building in core/predios.json (QoE Studio: Conjunto > Adicionar dados); '
    'never let an unknown value form its own group.'
  )


def resolve_site_id(local_values: pd.Series, level: str = 'position', registro: dict = None) -> pd.Series:
  """Mapeia valores brutos de `local` para identificadores canônicos de grupo.

  `local` é a posição de medição dentro de um prédio: a residência usa nomes de
  cômodo (reescritos como 1/2/3 pelo transform), os demais usam um prefixo por
  prédio (`cwpb-*`, `hotmilk-*`, `marcelo-*`), tudo em predios.json.

  level='position' -> um grupo por ponto de medição.
  level='building' -> um grupo por local de coleta: é o nível que não vaza o
  prédio entre treino e teste.
  `registro` permite resolver contra um registro que ainda não foi gravado (prévia do upload).
  """
  if level not in GROUP_LEVELS:
    raise ValueError(
      f'unknown group level {level!r}; expected one of {list(GROUP_LEVELS)}')
  reg = registro if registro is not None else _estado['registro']
  return local_values.map(lambda value: _resolve_one(value, level, reg))


def resolve_environment(local_values: pd.Series) -> pd.Series:
  """Mapeia valores brutos de `local` para o ambiente: `domestico` ou `corporativo`."""
  return resolve_site_id(local_values, level='building').map(BUILDING_ENVIRONMENT)


recarregar()

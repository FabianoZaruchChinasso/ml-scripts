"""Cadastro de prédios do Studio: de qual prédio e posição é cada `local`.

Vive em src/studio/config/predios.json, copiado de src/ml/core/predios.json em
2026-10-22 e independente dele desde então. O Studio nunca lê nem grava o arquivo
do core: ele decide o agrupamento por prédio do benchmark.
"""

import copy
import json
import math
import re
import threading

import pandas as pd

from studio import caminhos
from studio.arquivos import gravar_json_atomico

DOMESTICO = 'domestico'
CORPORATIVO = 'corporativo'
AMBIENTES = (DOMESTICO, CORPORATIVO)
NIVEIS = ('posicao', 'predio')

NOME = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
CAMPOS_OBRIGATORIOS = {'rotulo', 'studio', 'ambiente', 'prefixos'}
CAMPOS = CAMPOS_OBRIGATORIOS | {'posicoes', 'tetos_wan'}
CAMPOS_NOVO = {'chave', 'rotulo', 'ambiente', 'prefixo'}

_cache = {'path': None, 'registro': None}
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
  if p['ambiente'] not in AMBIENTES:
    raise ValueError(f"{chave!r}: ambiente {p['ambiente']!r} inválido; esperado um de {list(AMBIENTES)}")
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


def validar(registro) -> None:
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


def carregar(path: str = None) -> dict:
  with open(path or caminhos.PREDIOS_PATH, encoding='utf-8') as handle:
    registro = json.load(handle)
  validar(registro)
  return registro


def atual() -> dict:
  """Cópia do registro em uso. Relê quando caminhos.PREDIOS_PATH aponta para outro arquivo."""
  with _lock:
    if _cache['registro'] is None or _cache['path'] != caminhos.PREDIOS_PATH:
      _cache['registro'] = carregar(caminhos.PREDIOS_PATH)
      _cache['path'] = caminhos.PREDIOS_PATH
    return copy.deepcopy(_cache['registro'])


def esquecer() -> None:
  with _lock:
    _cache['registro'] = None


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


def cadastrar(novos) -> dict:
  """Acrescenta prédios a config/predios.json. Valida o registro inteiro antes de gravar."""
  with _lock:
    path = caminhos.PREDIOS_PATH
    registro = com_novos(carregar(path), novos)
    validar(registro)
    gravar_json_atomico(path, registro)
    _cache['registro'], _cache['path'] = registro, path
  return copy.deepcopy(registro)


def teto_wan(predio: str, alvo: str, registro: dict = None):
  """Teto de WAN do prédio para o alvo (Mbps), ou None quando não há teto cadastrado."""
  reg = registro if registro is not None else atual()
  return reg['predios'].get(predio, {}).get('tetos_wan', {}).get(alvo)


def _chave_local(valor) -> str:
  """Canonicaliza uma célula de `local`: '1.0' e 'Sala' viram chaves de busca."""
  if pd.isna(valor):
    raise ValueError("local vazio: toda linha precisa de uma posição conhecida")
  texto = str(valor).strip().lower()
  try:
    numero = float(texto)
  except ValueError:
    return texto
  if not math.isfinite(numero) or not numero.is_integer():
    raise ValueError(f'local desconhecido: {valor!r}')
  return str(int(numero))


def _resolver_um(valor, nivel: str, registro: dict) -> str:
  chave = _chave_local(valor)
  chave = registro['aliases'].get(chave, chave)
  for nome, p in registro['predios'].items():
    if any(chave.startswith(prefixo) for prefixo in p['prefixos']):
      return nome if nivel == 'predio' else chave
  for nome, p in registro['predios'].items():
    posicao = p.get('posicoes', {}).get(chave)
    if posicao is not None:
      return nome if nivel == 'predio' else posicao
  raise ValueError(f'local desconhecido: {valor!r}. Cadastre o prédio em src/studio/config/predios.json '
                   '(Conjunto > Adicionar dados).')


def resolver(valores: pd.Series, nivel: str = 'posicao', registro: dict = None) -> pd.Series:
  """Valores brutos de `local` -> prédio (nivel='predio') ou posição (nivel='posicao')."""
  if nivel not in NIVEIS:
    raise ValueError(f'nível {nivel!r} desconhecido; esperado um de {list(NIVEIS)}')
  reg = registro if registro is not None else atual()
  return valores.map(lambda valor: _resolver_um(valor, nivel, reg))

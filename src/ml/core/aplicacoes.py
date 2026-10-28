"""Limiares de QoE por aplicação: o que cada uma precisa de download, upload, latência e jitter.

Dois perfis. 'atual' vive em aplicacoes.json (lido por carregar(), que o
classification_benchmark.py também usa: formato e retorno não mudam). 'norma' vive em
aplicacoes_norma.json, com fonte publicada, URL e nota em cada limiar.
"""

import hashlib
import json
import os

APLICACOES_PATH = os.path.join(os.path.dirname(__file__), 'aplicacoes.json')
APLICACOES_NORMA_PATH = os.path.join(os.path.dirname(__file__), 'aplicacoes_norma.json')
PERFIS = ('atual', 'norma')
CAMPOS_NORMA = {'valor', 'fonte', 'url', 'nota'}
# dn/up em Mbps (mínimo), lat/jit em ms (máximo). Os nomes curtos são os do studio.js.
CHAVES = ('dn', 'up', 'lat', 'jit')


def validar(dados) -> None:
  if not isinstance(dados, dict) or set(dados) != {'aplicacoes'}:
    raise ValueError("aplicacoes.json precisa ter exatamente a chave 'aplicacoes'")
  apps = dados['aplicacoes']
  if not isinstance(apps, dict) or not apps:
    raise ValueError('aplicacoes.json precisa de pelo menos uma aplicação')
  for nome, limiares in apps.items():
    if not isinstance(limiares, dict) or set(limiares) != set(CHAVES):
      raise ValueError(f'{nome!r}: esperado exatamente as chaves {list(CHAVES)}')
    for chave in CHAVES:
      valor = limiares[chave]
      if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
        raise ValueError(f'{nome!r}.{chave}: precisa ser número não negativo, veio {valor!r}')


def carregar(path: str = APLICACOES_PATH) -> dict:
  with open(path, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar(dados)
  return dados['aplicacoes']


def validar_norma(dados) -> None:
  """Perfil de norma: cada limiar é {'valor', 'fonte', 'url'?, 'nota'?}, com fonte não vazia."""
  if not isinstance(dados, dict) or set(dados) != {'perfil', 'aplicacoes'} or dados.get('perfil') != 'norma':
    raise ValueError("aplicacoes_norma.json precisa ter exatamente as chaves 'perfil' (= 'norma') e 'aplicacoes'")
  apps = dados['aplicacoes']
  if not isinstance(apps, dict) or not apps:
    raise ValueError('aplicacoes_norma.json precisa de pelo menos uma aplicação')
  for nome, limiares in apps.items():
    if not isinstance(limiares, dict) or set(limiares) != set(CHAVES):
      raise ValueError(f'{nome!r}: esperado exatamente as chaves {list(CHAVES)}')
    for chave in CHAVES:
      item = limiares[chave]
      if not isinstance(item, dict) or 'valor' not in item:
        raise ValueError(f'{nome!r}.{chave}: esperado {{"valor": ..., "fonte": ...}}, faltou valor')
      extras = set(item) - CAMPOS_NORMA
      if extras:
        raise ValueError(f'{nome!r}.{chave}: campos desconhecidos {sorted(extras)}')
      if not isinstance(item.get('fonte'), str) or not item['fonte'].strip():
        raise ValueError(f'{nome!r}.{chave}: fonte obrigatória')
      for campo in ('url', 'nota'):
        if campo in item and not isinstance(item[campo], str):
          raise ValueError(f'{nome!r}.{chave}: {campo} precisa ser texto, veio {item[campo]!r}')
  validar({'aplicacoes': {nome: {c: lim[c]['valor'] for c in CHAVES} for nome, lim in apps.items()}})


def _ler_norma(path: str) -> dict:
  with open(path, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar_norma(dados)
  return dados['aplicacoes']


def _norma_do_perfil(perfil: str, path: str = None):
  """Limiares com fonte do perfil de norma, ou None no perfil atual (sem fontes)."""
  if perfil == 'atual':
    return None
  if perfil == 'norma':
    return _ler_norma(path or APLICACOES_NORMA_PATH)
  raise ValueError(f'perfil {perfil!r} desconhecido; esperado um de {list(PERFIS)}')


def carregar_perfil(perfil: str, path: str = None) -> dict:
  """Limiares do perfil no formato de carregar(): {aplicação: {'dn', 'up', 'lat', 'jit'}}."""
  norma = _norma_do_perfil(perfil, path if perfil == 'norma' else None)
  if norma is None:
    return carregar(path or APLICACOES_PATH)
  return {nome: {c: lim[c]['valor'] for c in CHAVES} for nome, lim in norma.items()}


def fontes(perfil: str, path: str = None) -> dict:
  """{aplicação: {chave: {'fonte', 'url', 'nota'}}}; vazio no perfil atual, que não tem fontes."""
  norma = _norma_do_perfil(perfil, path)
  if norma is None:
    return {}
  return {nome: {c: {'fonte': lim[c]['fonte'], 'url': lim[c].get('url', ''), 'nota': lim[c].get('nota', '')}
                 for c in CHAVES} for nome, lim in norma.items()}


def versao(path: str = None) -> str:
  """Hash curto do arquivo: entra na chave de cache do Studio, como as versões da tabela e do registro."""
  try:
    with open(path or APLICACOES_PATH, 'rb') as handle:
      return hashlib.sha256(handle.read()).hexdigest()[:12]
  except OSError:
    return 'ausente'

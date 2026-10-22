"""Conjunto ativo: quais datasets do catálogo as telas e o treino usam por padrão.

Gravado em .studio/conjunto.json. Sem arquivo (ou ilegível), vale o conjunto
padrão do catálogo; ids que sumiram do catálogo saem na leitura.
"""

import json

from studio import caminhos, catalogo
from studio.arquivos import gravar_json_atomico


def _usaveis(itens: list) -> set:
  return {d['id'] for d in itens if d.get('usable')}


def ler(itens: list = None) -> list:
  itens = catalogo.descobertos() if itens is None else itens
  try:
    with open(caminhos.CONJUNTO_PATH, encoding='utf-8') as handle:
      ids = json.load(handle)['datasets']
  except FileNotFoundError:
    return catalogo.ids_padrao(itens)
  except (ValueError, KeyError, TypeError):
    return catalogo.ids_padrao(itens)
  usaveis = _usaveis(itens)
  return [i for i in ids if i in usaveis]


def gravar(ids, itens: list = None) -> list:
  itens = catalogo.descobertos() if itens is None else itens
  desconhecidos = sorted(set(ids) - _usaveis(itens))
  if desconhecidos:
    raise ValueError(f'datasets desconhecidos ou inutilizáveis: {desconhecidos}')
  saida = sorted(set(ids))
  gravar_json_atomico(caminhos.CONJUNTO_PATH, {'datasets': saida})
  return saida

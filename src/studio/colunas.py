"""Colunas que o formulário de treino oferece, com a marca de vazamento.

A lista de vazamento vem de config/colunas.json (semeado de column_provenance.json):
os contadores router_* são deltas da janela do speedtest e carregam o próprio alvo.
"""

import json

import pandas as pd

from studio import caminhos, catalogo

CHAVES = {'vazamento', 'vazamento_prefixos', 'excluir'}


def carregar(path: str = None) -> dict:
  with open(path or caminhos.COLUNAS_PATH, encoding='utf-8') as handle:
    cfg = json.load(handle)
  if not isinstance(cfg, dict) or set(cfg) != CHAVES or not all(isinstance(cfg[k], list) for k in CHAVES):
    raise ValueError(f'colunas.json precisa ter exatamente as listas {sorted(CHAVES)}')
  return cfg


def com_vazamento(coluna: str, cfg: dict) -> bool:
  return coluna in cfg['vazamento'] or any(coluna.startswith(p) for p in cfg['vazamento_prefixos'])


def disponiveis(ids, itens: list = None) -> list:
  """Colunas numéricas presentes em todos os datasets escolhidos, sem alvos nem identificadores."""
  escolhidos = catalogo.usaveis_por_id(ids, itens)
  if not escolhidos:
    return []
  cfg = carregar()
  numericas = [{c for c in d['_frame'].columns if pd.api.types.is_numeric_dtype(d['_frame'][c])} for d in escolhidos]
  comuns = set.intersection(*numericas) - set(cfg['excluir']) - set(catalogo.TARGETS)
  junto = pd.concat([d['_frame'][sorted(comuns)] for d in escolhidos], ignore_index=True)
  return [{'coluna': c, 'vazamento': com_vazamento(c, cfg), 'preenchimento': round(float(junto[c].notna().mean()), 4)}
          for c in sorted(comuns)]

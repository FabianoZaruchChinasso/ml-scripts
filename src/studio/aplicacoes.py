"""Limiares de QoE por aplicação: o que cada uma precisa de download, upload, latência e jitter.

Vive em src/studio/config/aplicacoes.json, copiado do core em 2026-10-22 e
independente dele desde então.
"""

import json

from studio import caminhos

# dn/up em Mbps (mínimo), lat/jit em ms (máximo). Os nomes curtos são os do logica.js.
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


def carregar(path: str = None) -> dict:
  with open(path or caminhos.APLICACOES_PATH, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar(dados)
  return dados['aplicacoes']

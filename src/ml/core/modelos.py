"""Registro das versões de modelo: quais features cada versão usa.

Vive em modelos.json, versionado e gravado pelo QoE Studio. Uma versão salva é
imutável; mudar uma feature cria uma versão nova. Só a definição fica aqui: o
modelo treinado é refeito a partir dela (e registrado no MLflow quando for para
produção).
"""

import hashlib
import json
import os
import re
import threading
from datetime import date
from typing import Optional

from ml.core import features as F
from ml.core.arquivos import gravar_json_atomico

MODELOS_PATH = os.path.join(os.path.dirname(__file__), 'modelos.json')
NOME = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
CAMPOS = {'features', 'descricao', 'origem', 'criado_em', 'avaliacao', 'selecao'}

_lock = threading.Lock()


def validar_registro(registro) -> None:
  if not isinstance(registro, dict) or set(registro) != {'ativo', 'versoes'}:
    raise ValueError("o registro precisa ter exatamente as chaves 'ativo' e 'versoes'")
  versoes = registro['versoes']
  if not isinstance(versoes, dict) or not versoes:
    raise ValueError('o registro precisa de pelo menos uma versão')
  for nome, versao in versoes.items():
    if not NOME.match(nome):
      raise ValueError(f'{nome!r}: nome inválido (minúsculas, dígitos e hífen, 2 a 40 caracteres)')
    if not isinstance(versao, dict) or not {'features', 'descricao'} <= set(versao) <= CAMPOS:
      raise ValueError(f'{nome!r}: campos inválidos {sorted(versao) if isinstance(versao, dict) else versao!r}')
    feats = versao['features']
    if not isinstance(feats, list) or not feats or not all(isinstance(f, str) for f in feats):
      raise ValueError(f'{nome!r}: features precisa ser uma lista não vazia de nomes')
    if len(set(feats)) != len(feats):
      raise ValueError(f'{nome!r}: features repetidas')
  if registro['ativo'] not in versoes:
    raise ValueError(f"versão ativa {registro['ativo']!r} não existe no registro")


def carregar(path: str = MODELOS_PATH) -> dict:
  with open(path, encoding='utf-8') as handle:
    registro = json.load(handle)
  validar_registro(registro)
  return registro


def versao_registro(path: str = MODELOS_PATH) -> str:
  try:
    with open(path, 'rb') as handle:
      return hashlib.sha256(handle.read()).hexdigest()[:12]
  except OSError:
    return 'ausente'


def ativo(registro: dict) -> list:
  return list(registro['versoes'][registro['ativo']]['features'])


def classificar_features(features, tabela: dict) -> dict:
  """Classe de cada feature, olhando o catálogo de derivadas antes da tabela."""
  derivadas = {d.nome: d for d in F.catalogo_completo()}
  saida = {}
  for nome in features:
    if nome in derivadas:
      saida[nome] = F.classificar_derivada(derivadas[nome], tabela)
    else:
      saida[nome] = F.classificar(nome, tabela)
  return saida


def fora_do_tr069(features, tabela: dict) -> list:
  classes = classificar_features(features, tabela)
  return [f for f in features if classes[f] is None or classes[f].classe != 'tr069']


def salvar_versao(nome: str, features, descricao: str, colunas_conhecidas, tabela: dict,
                  origem: str = 'studio', avaliacao: Optional[dict] = None,
                  selecao: Optional[dict] = None, path: str = MODELOS_PATH) -> dict:
  """Acrescenta uma versão. Recusa nome existente, feature desconhecida e vazamento."""
  features = list(features)
  if not isinstance(descricao, str) or not descricao.strip() or len(descricao) > 500:
    raise ValueError('descrição obrigatória, de até 500 caracteres')
  desconhecidas = [f for f in features if f not in colunas_conhecidas]
  if desconhecidas:
    raise ValueError(f'features que não existem nos datasets nem no catálogo: {desconhecidas}')
  classes = classificar_features(features, tabela)
  sem_classe = [f for f in features if classes[f] is None]
  if sem_classe:
    raise ValueError(f'features sem classificação: {sem_classe}. Classifique na view Features antes.')
  vazadas = [f for f in features if classes[f].vazamento]
  if vazadas:
    raise ValueError(f'features com vazamento não entram em modelo: {vazadas}')
  with _lock:
    registro = carregar(path)
    if nome in registro['versoes']:
      raise ValueError(f'a versão {nome!r} já existe e é imutável; escolha outro nome')
    versao = {'features': features, 'descricao': descricao.strip(), 'origem': origem,
              'criado_em': date.today().isoformat()}
    if avaliacao:
      versao['avaliacao'] = avaliacao
    if selecao:
      versao['selecao'] = selecao
    registro['versoes'][nome] = versao
    validar_registro(registro)
    gravar_json_atomico(path, registro)
  return registro


def definir_ativo(nome: str, path: str = MODELOS_PATH) -> dict:
  with _lock:
    registro = carregar(path)
    if nome not in registro['versoes']:
      raise ValueError(f'versão {nome!r} não existe')
    registro['ativo'] = nome
    gravar_json_atomico(path, registro)
  return registro

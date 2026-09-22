"""Proveniência das colunas coletadas e catálogo curado de features derivadas.

A tabela vive em column_provenance.json, versionada e gravada pelo QoE Studio.
Coluna sem regra nunca é adivinhada: `classificar` devolve None.
"""

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ml.core.arquivos import gravar_json_atomico

TABELA_PATH = os.path.join(os.path.dirname(__file__), 'column_provenance.json')

CLASSES = ('tr069', 'sniffer', 'cliente', 'ambiente', 'geometria', 'identificador', 'alvo')
# Só derivadas recebem esta classe: algum insumo não é TR-069.
CLASSE_AUXILIAR = 'auxiliar'

# Cópia de compare_protocols.FEATURES. Unificar as duas listas está fora do escopo.
MODELO_ATUAL = (
  'router_expected_throughput_mbps', 'router_noise', 'router_rx_drop_misc',
  'router_rx_duration_us', 'router_rx_rate_mbps', 'router_signal_avg_dbm',
  'router_signal_dbm', 'router_snr', 'router_tx_duration_us', 'router_tx_failed',
  'router_tx_rate_mbps', 'router_tx_retries', 'router_opportunity_medium_use',
  'client_opportunity_medium_use',
)

_lock = threading.Lock()


@dataclass(frozen=True)
class Classificacao:
  classe: str
  vazamento: bool
  parametro: Optional[str]
  origem: str


def validar_regra(nome: str, regra) -> None:
  if not isinstance(regra, dict) or regra.get('classe') not in CLASSES:
    raise ValueError(f'{nome!r}: classe inválida em {regra!r}; esperado uma de {list(CLASSES)}')
  extras = set(regra) - {'classe', 'vazamento', 'parametro'}
  if extras:
    raise ValueError(f'{nome!r}: campos desconhecidos {sorted(extras)}')
  if not isinstance(regra.get('vazamento', False), bool):
    raise ValueError(f'{nome!r}: vazamento precisa ser booleano')
  parametro = regra.get('parametro')
  if parametro is not None and (not isinstance(parametro, str) or len(parametro) > 200):
    raise ValueError(f'{nome!r}: parametro precisa ser texto de até 200 caracteres')


def validar_tabela(tabela) -> None:
  if not isinstance(tabela, dict) or set(tabela) != {'prefixos', 'colunas'}:
    raise ValueError("a tabela precisa ter exatamente as chaves 'prefixos' e 'colunas'")
  for secao in ('prefixos', 'colunas'):
    for nome, regra in tabela[secao].items():
      validar_regra(nome, regra)


def carregar_tabela(path: str = TABELA_PATH) -> dict:
  with open(path, encoding='utf-8') as handle:
    tabela = json.load(handle)
  validar_tabela(tabela)
  return tabela


def versao_tabela(path: str = TABELA_PATH) -> str:
  try:
    with open(path, 'rb') as handle:
      return hashlib.sha256(handle.read()).hexdigest()[:12]
  except OSError:
    return 'ausente'


def classificar(coluna: str, tabela: dict) -> Optional[Classificacao]:
  regra = tabela['colunas'].get(coluna)
  origem = 'exata'
  if regra is None:
    casados = [p for p in tabela['prefixos'] if coluna.startswith(p)]
    if not casados:
      return None
    regra = tabela['prefixos'][max(casados, key=len)]
    origem = 'prefixo'
  return Classificacao(regra['classe'], bool(regra.get('vazamento', False)),
                       regra.get('parametro'), origem)


def _tokens_em_comum(a, b) -> int:
  n = 0
  for x, y in zip(a, b):
    if not x or x != y:
      break
    n += 1
  return n


def sugerir(coluna: str, tabela: dict) -> Optional[str]:
  """Classe da coluna já declarada com mais tokens iniciais em comum (mínimo 1).

  Serve só para pré-selecionar a interface. Empate entre classes diferentes devolve None.
  """
  tokens = coluna.split('_')
  melhor, classes = 0, set()
  for nome, regra in tabela['colunas'].items():
    comum = _tokens_em_comum(tokens, nome.split('_'))
    if comum == 0:
      continue
    if comum > melhor:
      melhor, classes = comum, {regra['classe']}
    elif comum == melhor:
      classes.add(regra['classe'])
  return next(iter(classes)) if len(classes) == 1 else None


def gravar_classificacao(coluna: str, classe: str, vazamento: bool, parametro: Optional[str],
                         colunas_conhecidas, path: str = TABELA_PATH) -> dict:
  if not isinstance(coluna, str) or not coluna.strip():
    raise ValueError('coluna vazia')
  regra = {'classe': classe}
  if vazamento:
    regra['vazamento'] = vazamento
  if parametro:
    regra['parametro'] = parametro
  validar_regra(coluna, regra)
  with _lock:
    tabela = carregar_tabela(path)
    if coluna not in colunas_conhecidas and coluna not in tabela['colunas']:
      raise ValueError(f'coluna {coluna!r} não existe em nenhum dataset')
    tabela['colunas'][coluna] = regra
    gravar_json_atomico(path, tabela)
  return tabela


@dataclass(frozen=True)
class Derivada:
  nome: str
  insumos: tuple
  calcular: Callable[[pd.DataFrame], pd.Series]
  descricao: str
  normaliza_volume: bool = False


def _razao(numerador: str, denominador: str):
  return lambda df: df[numerador] / df[denominador].replace(0, np.nan)


CATALOGO_VERSAO = '2026-09-18.1'

CATALOGO = (
  Derivada('retry_por_pacote', ('router_tx_retries', 'router_tx_packets'),
           _razao('router_tx_retries', 'router_tx_packets'),
           'Retransmissões por pacote enviado: qualidade do enlace, sem depender do volume.',
           normaliza_volume=True),
  Derivada('falha_por_pacote', ('router_tx_failed', 'router_tx_packets'),
           _razao('router_tx_failed', 'router_tx_packets'),
           'Falhas de envio por pacote.', normaliza_volume=True),
  Derivada('bytes_por_pacote_tx', ('router_tx_bytes', 'router_tx_packets'),
           _razao('router_tx_bytes', 'router_tx_packets'),
           'Tamanho médio do quadro enviado; depende do tipo de tráfego do teste.'),
  Derivada('eficiencia_phy', ('router_expected_throughput_mbps', 'router_tx_rate_mbps'),
           _razao('router_expected_throughput_mbps', 'router_tx_rate_mbps'),
           'Throughput esperado pelo rate control sobre a taxa PHY de envio.'),
  Derivada('instabilidade_sinal', ('router_signal_dbm', 'router_signal_avg_dbm'),
           lambda df: df['router_signal_dbm'] - df['router_signal_avg_dbm'],
           'Sinal instantâneo menos a média: variação do enlace.'),
  Derivada('assimetria_phy', ('router_tx_rate_mbps', 'router_rx_rate_mbps'),
           _razao('router_tx_rate_mbps', 'router_rx_rate_mbps'),
           'Taxa PHY de envio sobre a de recepção.'),
  Derivada('fracao_airtime_tx', ('router_tx_duration_us', 'router_rx_duration_us'),
           lambda df: df['router_tx_duration_us']
           / (df['router_tx_duration_us'] + df['router_rx_duration_us']).replace(0, np.nan),
           'Fração do tempo de rádio gasta enviando.'),
  Derivada('largura_x_nss', ('router_bandwith_TX_station', 'router_NSS_TX_Station'),
           lambda df: df['router_bandwith_TX_station'] * df['router_NSS_TX_Station'],
           'Largura de canal vezes fluxos espaciais: capacidade nominal do enlace.'),
  Derivada('assimetria_enlace', ('RSSI', 'router_signal_dbm'),
           lambda df: df['RSSI'] - df['router_signal_dbm'],
           'RSSI visto pelo cliente menos o sinal visto pelo roteador.'),
)


def classificar_derivada(derivada: Derivada, tabela: dict) -> Optional[Classificacao]:
  insumos = [classificar(c, tabela) for c in derivada.insumos]
  if any(c is None for c in insumos):
    return None
  classe = 'tr069' if all(c.classe == 'tr069' for c in insumos) else CLASSE_AUXILIAR
  vazamento = any(c.vazamento for c in insumos) and not derivada.normaliza_volume
  return Classificacao(classe, vazamento, None, 'derivada')


def aplicar_derivadas(df: pd.DataFrame, catalogo=CATALOGO):
  """Devolve (df com as derivadas calculáveis, avisos das que faltaram insumo)."""
  novas, avisos = {}, []
  for derivada in catalogo:
    faltando = [c for c in derivada.insumos if c not in df.columns]
    if faltando:
      avisos.append(f'derivada {derivada.nome} omitida: faltam {faltando}')
      continue
    novas[derivada.nome] = derivada.calcular(df).astype(float)
  if not novas:
    return df.copy(), avisos
  return pd.concat([df, pd.DataFrame(novas, index=df.index)], axis=1), avisos

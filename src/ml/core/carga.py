"""Carga canônica dos datasets do QoE: descoberta, duplicatas, concorrência, descartes e teto de WAN.

Só lê: nada aqui grava em data/. Toda correção é regra aplicada em memória, para
que o QoE Studio e os scripts de treino vejam exatamente o mesmo conjunto.
"""

import hashlib
import io
import os
import zipfile
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ml.core import features as F
from ml.core.data import descartar_testes_falhos
from ml.core.sites import BUILDING_ENVIRONMENT, ENVIRONMENTS, resolve_site_id, teto_wan

TARGETS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')

# A geracao de esquema e o que separa `legacy_` do modelo de colunas atual.
# `combo`/`n_clients` (o eixo de contencao) so existem na geracao atual.
CURRENT_MARKERS = ['combo', 'n_clients', 'station_x', 'house_x0']

DATA_DIR = 'data'

# Casas decimais do fingerprint. As versoes -fix/-distcalc recalculam os alvos
# e diferem da original em ~1e-14: sem arredondar, o dedupe nao as reconhece.
FINGERPRINT_DECIMALS = 6


def _read_any(path: str) -> pd.DataFrame:
  """Le CSV ou o unico CSV dentro de um zip, sem gravar nada em disco."""
  if path.endswith('.zip'):
    with zipfile.ZipFile(path) as archive:
      names = [n for n in archive.namelist() if n.endswith('.csv')]
      if len(names) != 1:
        raise ValueError(f'{path}: esperado exatamente 1 CSV no zip, achei {len(names)}')
      with archive.open(names[0]) as handle:
        return pd.read_csv(io.BytesIO(handle.read()), low_memory=False)
  return pd.read_csv(path, low_memory=False)


def _generation(columns) -> str:
  return 'current' if all(m in columns for m in CURRENT_MARKERS) else 'legacy'


def discover() -> list:
  """Varre data/ e devolve um descritor por dataset utilizavel."""
  found = []
  for name in sorted(os.listdir(DATA_DIR)):
    if not (name.endswith('.csv') or name.endswith('.zip')):
      continue
    # Os -qoe.csv carregam qoe_dw_score, cuja formula se perdeu e cujas duas
    # versoes diferem por ~3200x. Ficam de fora ate serem recalculados.
    if '-qoe' in name or 'filllast' in name:
      continue
    path = os.path.join(DATA_DIR, name)
    try:
      frame = _read_any(path)
    except Exception as error:
      found.append({'id': name, 'path': path, 'error': str(error), 'usable': False})
      continue
    if 'local' not in frame.columns or not all(t in frame.columns for t in TARGETS):
      continue
    alvos = frame[list(TARGETS)].round(FINGERPRINT_DECIMALS)
    digest = hashlib.sha256(pd.util.hash_pandas_object(alvos, index=False).values.tobytes())
    found.append({
      'id': name,
      'path': path,
      'usable': True,
      'rows': int(len(frame)),
      'columns': int(len(frame.columns)),
      'generation': _generation(frame.columns),
      'fingerprint': digest.hexdigest()[:12],
      '_frame': frame,
    })
  return found


_descobertos = None


def descobertos() -> list:
  """discover() uma vez por processo: reler o zip de 52 MB a cada requisicao travaria as views."""
  global _descobertos
  if _descobertos is None:
    _descobertos = discover()
  return _descobertos


def _superseded(datasets: list) -> dict:
  """Marca datasets cujas linhas estao inteiras dentro de outro (0817 dentro de 0827)."""
  verdict = {}
  keyed = {}
  for item in datasets:
    if not item.get('usable'):
      continue
    frame = item['_frame']
    keys = set(map(tuple, frame[list(TARGETS)].round(FINGERPRINT_DECIMALS).astype(str).values))
    keyed[item['id']] = keys
  for a, keys_a in keyed.items():
    for b, keys_b in keyed.items():
      if a == b or not keys_a:
        continue
      if keys_a <= keys_b and len(keys_a) < len(keys_b):
        verdict[a] = b
  return verdict


def duplicatas(datasets: list) -> dict:
  """Fingerprint igual = os mesmos alvos ate a 6a casa: o segundo e duplicata do primeiro.

  Manter os dois ligados duplica o peso de cada amostra sem avisar.
  """
  vistos, duplicata_de = {}, {}
  for item in datasets:
    if not item.get('usable'):
      continue
    primeiro = vistos.setdefault(item['fingerprint'], item['id'])
    if primeiro != item['id']:
      duplicata_de[item['id']] = primeiro
  return duplicata_de


def ids_padrao(datasets: list) -> list:
  """O conjunto canônico: geração atual, nem substituído nem duplicado."""
  substituidos, duplicados = _superseded(datasets), duplicatas(datasets)
  return [d['id'] for d in datasets
          if d.get('usable') and d['generation'] == 'current'
          and d['id'] not in substituidos and d['id'] not in duplicados]


# Testes simultâneos: mesma rodada (`run_id`) da mesma sessão e do mesmo `combo`.
# `run_id` se repete mais tarde na mesma sessão (hotmilk), então o grupo também é
# cortado no tempo: linhas a mais de JANELA_SIMULTANEO_S da primeira abrem outro.
JANELA_SIMULTANEO_S = 60
CHAVE_SIMULTANEO = ('_ds', 'session_id', 'run_id', 'combo')
COLUNAS_CONCORRENCIA = CHAVE_SIMULTANEO + ('_time', 'n_clients', 'bssid')
# Colunas que a carga sempre produz quando os insumos existem: entram em
# `colunas_conhecidas` para poderem ser classificadas e usadas em versões.
COLUNAS_CALCULADAS = ('concorrentes_mesmo_radio',)


def _blocos_no_tempo(tempos: pd.Series) -> list:
  """Corta um grupo em blocos de até JANELA_SIMULTANEO_S a partir da primeira linha de cada bloco."""
  blocos, inicio, atual = [], None, []
  for indice, instante in tempos.sort_values().items():
    if inicio is None or (instante - inicio).total_seconds() > JANELA_SIMULTANEO_S:
      if atual:
        blocos.append(atual)
      inicio, atual = instante, []
    atual.append(indice)
  if atual:
    blocos.append(atual)
  return blocos


def concorrentes_mesmo_radio(df: pd.DataFrame) -> pd.Series:
  """Clientes em teste simultâneo no mesmo `bssid` (a própria linha incluída).

  Mesmo `bssid` = mesmo rádio do mesmo roteador: é onde há disputa de ar. NaN quando
  o tamanho do grupo difere de `n_clients` (faltou a linha de um cliente, ou duas
  rodadas caíram na mesma janela), ou quando falta `bssid` na linha.
  """
  saida = pd.Series(np.nan, index=df.index, dtype=float)
  tempo = pd.to_datetime(df['_time'], utc=True, errors='coerce')
  chave = list(CHAVE_SIMULTANEO)
  validas = df[chave].notna().all(axis=1) & tempo.notna() & df['n_clients'].notna()
  for indices in df[validas].groupby(chave, sort=False).groups.values():
    for bloco in _blocos_no_tempo(tempo.loc[indices]):
      sub = df.loc[bloco]
      if len(sub) != int(sub['n_clients'].iloc[0]):
        continue
      contagem = sub['bssid'].map(sub['bssid'].value_counts())
      saida.loc[bloco] = contagem.where(sub['bssid'].notna()).astype(float)
  return saida


# Campos de enlace do TR-069. Sem nenhum deles a linha não tem o que o modelo lê
# em produção (AX3000 da casa-marcelo e o 20260925 não trazem stats de estação).
ENLACE = ('router_tx_rate_mbps', 'router_rx_rate_mbps', 'router_snr', 'router_signal_dbm')
# Fração do teto a partir da qual o speedtest pode estar medindo a WAN.
LIMIAR_TETO = 0.85


def descartar_sem_enlace(df: pd.DataFrame):
  """Remove linhas em que todos os campos de ENLACE presentes estão vazios.

  Se nenhum deles existe no conjunto, a regra não se aplica. Devolve (df, quantas saíram).
  """
  presentes = [c for c in ENLACE if c in df.columns]
  if not presentes:
    return df, 0
  vazias = df[presentes].isna().all(axis=1)
  return df[~vazias].reset_index(drop=True), int(vazias.sum())


def marcar_limitado_wan(df: pd.DataFrame, alvo: str) -> pd.Series:
  """Verdadeiro quando o alvo está no teto de WAN do prédio e o Wi-Fi podia entregar mais.

  Condições: o prédio tem teto para o alvo, alvo >= LIMIAR_TETO * teto e
  router_expected_throughput_mbps > teto. Latência e jitter nunca marcam.
  """
  marca = pd.Series(False, index=df.index)
  if 'router_expected_throughput_mbps' not in df.columns:
    return marca
  tetos = df['_site'].map(lambda predio: teto_wan(predio, alvo)).astype(float)
  esperado = pd.to_numeric(df['router_expected_throughput_mbps'], errors='coerce')
  y = pd.to_numeric(df[alvo], errors='coerce')
  return (tetos.notna() & (y >= LIMIAR_TETO * tetos) & (esperado > tetos)).fillna(False).astype(bool)


# `_site` é o grupo dos folds: o local de coleta (prédio). Deixar só um cômodo
# de fora mantinha os outros cômodos do mesmo prédio no treino — mesmo roteador,
# mesmo ambiente, mesmo dia — e inflava o R² (ver CHANGELOG).
# `_pos` é o cômodo; `_amb` é doméstico/corporativo; `_linha` é a chave estável
# da linha ('<dataset>:<linha no arquivo>'), igual para todos os alvos;
# `_limitado_wan` marca o alvo no teto do plano de internet.
_INTERNAS = ('_ds', '_site', '_pos', '_amb', '_limitado_wan', '_linha')


@dataclass
class Conjunto:
  df: pd.DataFrame
  alvo: str
  datasets: list
  classes: dict
  tabela: dict
  avisos: list = field(default_factory=list)
  catalogo: tuple = F.CATALOGO


def preparar(frames: dict, alvo: str, tabela: dict, ambiente: str = None, catalogo=None) -> Conjunto:
  """Junta os frames, calcula a concorrência, aplica os descartes e marca o teto de WAN.

  `ambiente` ('domestico' ou 'corporativo') restringe o conjunto a esse tipo de
  local de coleta; None mantém todos. `catalogo` é o de derivadas (padrão: o curado
  mais as desenhadas no Studio, F.catalogo_completo()).
  """
  catalogo = F.catalogo_completo() if catalogo is None else tuple(catalogo)
  if alvo not in TARGETS:
    raise ValueError(f'alvo {alvo!r} desconhecido; esperado um de {list(TARGETS)}')
  if ambiente is not None and ambiente not in ENVIRONMENTS:
    raise ValueError(f'ambiente {ambiente!r} desconhecido; esperado um de {list(ENVIRONMENTS)}')
  if not frames:
    raise ValueError('nenhum dataset não-legacy ativo')
  avisos = []
  df = pd.concat([f.assign(_ds=ds, _linha=[f'{ds}:{i}' for i in range(len(f))])
                  for ds, f in frames.items()], ignore_index=True)
  if alvo not in df.columns:
    raise ValueError(f'o alvo {alvo!r} não existe nos datasets ativos')

  # Antes de qualquer descarte: um teste que falhou também disputava o ar.
  faltam = [c for c in COLUNAS_CONCORRENCIA if c not in df.columns]
  if faltam:
    avisos.append(f'concorrentes_mesmo_radio omitida: faltam {faltam}')
  else:
    df = df.assign(concorrentes_mesmo_radio=concorrentes_mesmo_radio(df))

  sem_alvo = int(df[alvo].isna().sum())
  if sem_alvo:
    avisos.append(f'{sem_alvo} linhas sem {alvo} descartadas')
  df = df[df[alvo].notna()]
  df, falhos = descartar_testes_falhos(df, alvo)
  if falhos:
    avisos.append(f'{falhos} testes que falharam ({alvo} = 0) descartados')

  posicoes, predios = {}, {}
  desconhecidos = []
  for valor in df['local'].dropna().unique():
    try:
      posicoes[valor] = resolve_site_id(pd.Series([valor])).iloc[0]
      predios[valor] = resolve_site_id(pd.Series([valor]), level='building').iloc[0]
    except ValueError:
      desconhecidos.append(str(valor))
  fora = int((~df['local'].isin(list(posicoes))).sum())
  if fora:
    avisos.append(f'{fora} linhas com local desconhecido em core/sites.py descartadas: '
                  f'{sorted(desconhecidos)}')
  df = df[df['local'].isin(list(posicoes))].reset_index(drop=True)
  df = df.assign(_site=df['local'].map(predios), _pos=df['local'].map(posicoes))
  df = df.assign(_amb=df['_site'].map(BUILDING_ENVIRONMENT))
  if ambiente is not None:
    df = df[df['_amb'] == ambiente].reset_index(drop=True)
    if df.empty:
      raise ValueError(f'nenhuma linha de ambiente {ambiente!r} nos datasets ativos')

  df, sem_enlace = descartar_sem_enlace(df)
  if sem_enlace:
    avisos.append(f'{sem_enlace} linhas sem stats de estação (taxa PHY, SNR e sinal vazios) descartadas')
  df = df.assign(_limitado_wan=marcar_limitado_wan(df, alvo))
  limitadas = int(df['_limitado_wan'].sum())
  if limitadas:
    avisos.append(f'{limitadas} linhas no teto de WAN: fora do treino, previsão cortada no teto')
  if 'concorrentes_mesmo_radio' in df.columns:
    sem_grupo = int(df['concorrentes_mesmo_radio'].isna().sum())
    if sem_grupo:
      avisos.append(f'{sem_grupo} linhas sem concorrentes_mesmo_radio '
                    '(grupo simultâneo incompleto ou sem bssid)')

  df, avisos_derivadas = F.aplicar_derivadas(df, catalogo)
  avisos += avisos_derivadas

  derivadas = {d.nome: d for d in catalogo}
  classes = {}
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    if coluna in derivadas:
      classes[coluna] = F.classificar_derivada(derivadas[coluna], tabela)
    else:
      classes[coluna] = F.classificar(coluna, tabela)
  return Conjunto(df, alvo, sorted(frames), classes, tabela, avisos, catalogo)


def carregar(alvo: str, ids=None, tabela: dict = None, ambiente: str = None, catalogo=None) -> Conjunto:
  """Conjunto canônico para os scripts de treino: os mesmos datasets e regras do Studio.

  `ids` são nomes de arquivo em DATA_DIR; vazio = ids_padrao(). `tabela` padrão é
  column_provenance.json.
  """
  datasets = descobertos()
  por_id = {d['id']: d for d in datasets if d.get('usable')}
  ids = list(ids) if ids else ids_padrao(datasets)
  desconhecidos = [i for i in ids if i not in por_id]
  if desconhecidos:
    raise ValueError(f'datasets desconhecidos em {DATA_DIR}: {desconhecidos}')
  legacy = [i for i in ids if por_id[i]['generation'] != 'current']
  if legacy:
    raise ValueError(f'datasets da geração antiga não entram na régua: {legacy}')
  tabela = F.carregar_tabela() if tabela is None else tabela
  return preparar({i: por_id[i]['_frame'] for i in ids}, alvo, tabela, ambiente, catalogo)

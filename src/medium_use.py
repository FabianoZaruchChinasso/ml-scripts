"""Contagem de vizinhos no mesmo canal (oportunidade de uso do meio).

Usado por get-metrics.py. Separado para ser testável sem o cliente do InfluxDB.

Regra: devolve None (vazio no CSV) quando a medição não existe ou não é
interpretável, e 0 só quando o scan existe e não tem vizinho no canal. Antes os
dois casos viravam 0, e "sem scan" se confundia com "canal limpo".
"""

import json

CHANNELS_24G = {1: 2412, 2: 2417, 3: 2422, 4: 2427, 5: 2432, 6: 2437, 7: 2442, 8: 2447,
                9: 2452, 10: 2457, 11: 2462, 12: 2467, 13: 2472}
CHANNELS_5G = {32: 5160, 36: 5180, 40: 5200, 44: 5220, 48: 5240, 52: 5260, 56: 5280, 60: 5300,
               64: 5320, 68: 5340, 72: 5360, 76: 5380, 80: 5400, 84: 5420, 88: 5440, 92: 5460,
               96: 5480, 100: 5500, 104: 5520, 108: 5540, 112: 5560, 116: 5580, 120: 5600,
               124: 5620, 128: 5640, 132: 5660, 136: 5680, 140: 5700, 144: 5720, 149: 5745,
               153: 5765, 157: 5785, 161: 5805, 165: 5825, 169: 5845, 173: 5865, 177: 5885}


def target_frequency(channel_value, radio):
  """Frequência central do canal do AP, ou None se o canal for ausente ou desconhecido."""
  if channel_value is None:
    return None
  try:
    channel = int(float(channel_value))
  except (ValueError, TypeError):
    return None
  channels = CHANNELS_5G if radio == '5ghz' else CHANNELS_24G
  return channels.get(channel)


def count_same_channel(survey, target_freq, freq_key):
  """Vizinhos do scan na frequência alvo; None se o scan faltar ou não for uma lista JSON."""
  if target_freq is None or survey is None or survey == '':
    return None
  try:
    neighbors = json.loads(survey) if isinstance(survey, str) else survey
  except (ValueError, TypeError):
    return None
  if not isinstance(neighbors, list):
    return None
  return sum(1 for n in neighbors if isinstance(n, dict) and n.get(freq_key) == target_freq)


def medium_use(row_data):
  """(router_opportunity_medium_use, client_opportunity_medium_use) de uma linha do InfluxDB."""
  target = target_frequency(row_data.get('AP_channel'), row_data.get('radio'))
  router = count_same_channel(row_data.get('router_site_survey_ap'), target, 'freq_mhz')
  client = count_same_channel(row_data.get('site_survey_client'), target, 'frequency')
  return router, client

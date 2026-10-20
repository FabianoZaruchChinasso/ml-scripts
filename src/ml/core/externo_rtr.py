"""Prior externo do RTR-Netztest (Áustria, CC BY 4.0): throughput de Wi-Fi por RSSI e banda.

Experimento de 2026-10-16 (docs/superpowers/plans/2026-10-16-prior-rtr-netztest.md). O prior
é treinado só no RTR, então a coluna que ele gera não viu nenhuma linha nossa: não vaza
entre os folds por prédio.
"""

import zipfile

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

COLUNAS_RTR = ['cat_technology', 'platform', 'signal_strength', 'channel_number',
               'download_kbit', 'upload_kbit', 'implausible']
# Alvo da régua → coluna do RTR preparado.
ALVO_RTR = {'speedtest_down_mbps': 'down_mbps', 'speedtest_up_mbps': 'up_mbps'}
# RSSI >= 0 é leitura inválida dos dois lados (o coletor grava 0 e até +7 dBm).
RSSI_MAXIMO = -1.0


def banda_por_frequencia(mhz: pd.Series) -> pd.Series:
  """Frequência do canal em MHz → '2.4ghz' ou '5ghz', o vocabulário de `radio`.

  6 GHz vira NaN: nenhuma coleta nossa usa a banda.
  """
  f = pd.to_numeric(mhz, errors='coerce')
  banda = pd.Series(np.nan, index=f.index, dtype=object)
  banda[f.between(2400, 2500)] = '2.4ghz'
  banda[f.between(5150, 5925)] = '5ghz'
  return banda


def limpar_rssi(rssi: pd.Series) -> pd.Series:
  r = pd.to_numeric(rssi, errors='coerce')
  return r.where(r <= RSSI_MAXIMO)


def preparar_rtr(bruto: pd.DataFrame) -> pd.DataFrame:
  """Testes WLAN de Android, plausíveis, com RSSI, em 2,4 ou 5 GHz.

  Colunas: rssi (dBm), radio, down_mbps, up_mbps.
  """
  plausivel = ~bruto['implausible'].fillna(False).astype(bool)
  w = bruto[(bruto['cat_technology'] == 'WLAN') & (bruto['platform'] == 'Android') & plausivel]
  saida = pd.DataFrame({'rssi': limpar_rssi(w['signal_strength']),
                        'radio': banda_por_frequencia(w['channel_number']),
                        'down_mbps': w['download_kbit'] / 1000.0,
                        'up_mbps': w['upload_kbit'] / 1000.0})
  return saida.dropna(subset=['rssi', 'radio']).reset_index(drop=True)


def ler_rtr(caminho_zip: str) -> pd.DataFrame:
  """Lê o CSV mensal de dentro do zip do RTR e aplica preparar_rtr."""
  with zipfile.ZipFile(caminho_zip) as arquivo:
    nome = next(n for n in arquivo.namelist() if n.endswith('.csv'))
    with arquivo.open(nome) as handle:
      bruto = pd.read_csv(handle, usecols=COLUNAS_RTR, low_memory=False)
  return preparar_rtr(bruto)


def _x(rssi: pd.Series, radio: pd.Series) -> pd.DataFrame:
  radio = pd.Series(radio).reset_index(drop=True)
  cinco = np.where(radio.isna(), np.nan, (radio == '5ghz').astype(float))
  return pd.DataFrame({'rssi': limpar_rssi(pd.Series(rssi)).reset_index(drop=True), 'cinco_ghz': cinco})


def treinar_prior(rtr: pd.DataFrame, coluna_alvo: str, quantil: float) -> HistGradientBoostingRegressor:
  """Quantil `quantil` do throughput dado RSSI e banda.

  Restrição monotônica no RSSI: mais sinal nunca prevê menos.
  """
  modelo = HistGradientBoostingRegressor(loss='quantile', quantile=quantil, monotonic_cst=[1, 0],
                                         max_iter=300, random_state=42)
  modelo.fit(_x(rtr['rssi'], rtr['radio']), rtr[coluna_alvo].to_numpy(dtype=float))
  return modelo


def aplicar_prior(modelo, rssi: pd.Series, radio: pd.Series) -> np.ndarray:
  """Previsão do prior para as nossas linhas. RSSI inválido vira NaN, e o imputer da régua cuida."""
  x = _x(rssi, radio)
  previsto = modelo.predict(x)
  return np.where(x['rssi'].isna().to_numpy(), np.nan, previsto)
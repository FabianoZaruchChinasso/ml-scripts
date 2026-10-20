import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import externo_rtr as R


class TestLeitura(unittest.TestCase):
  def test_banda_por_frequencia(self):
    banda = R.banda_por_frequencia(pd.Series([2412, 5180, 5745, 6115, np.nan]))
    self.assertEqual(banda.iloc[:3].tolist(), ['2.4ghz', '5ghz', '5ghz'])
    self.assertTrue(banda.iloc[3:].isna().all())

  def test_limpar_rssi_descarta_zero_e_positivo(self):
    r = R.limpar_rssi(pd.Series([-60, 0, 7, -1]))
    self.assertEqual(r.iloc[0], -60)
    self.assertTrue(r.iloc[1:3].isna().all())
    self.assertEqual(r.iloc[3], -1)

  def test_preparar_rtr_fica_so_com_wlan_android_plausivel(self):
    bruto = pd.DataFrame({
      'cat_technology': ['WLAN', 'LAN', 'WLAN', 'WLAN', 'WLAN', 'WLAN'],
      'platform': ['Android', 'Android', 'iOS', 'Android', 'Android', 'Android'],
      'signal_strength': [-55, -55, -55, -55, np.nan, -55],
      'channel_number': [5180, 5180, 5180, 5180, 5180, 6115],
      'download_kbit': [50000, 1, 1, 1, 1, 1],
      'upload_kbit': [20000, 1, 1, 1, 1, 1],
      'implausible': [False, False, False, True, False, False],
    })
    rtr = R.preparar_rtr(bruto)
    self.assertEqual(len(rtr), 1)
    self.assertEqual(rtr.loc[0, 'radio'], '5ghz')
    self.assertAlmostEqual(rtr.loc[0, 'down_mbps'], 50.0)
    self.assertAlmostEqual(rtr.loc[0, 'up_mbps'], 20.0)
    self.assertEqual(rtr.loc[0, 'rssi'], -55)

  def test_preparar_rtr_implausible_vazio_conta_como_plausivel(self):
    bruto = pd.DataFrame({'cat_technology': ['WLAN'], 'platform': ['Android'], 'signal_strength': [-50],
                          'channel_number': [2437], 'download_kbit': [10000], 'upload_kbit': [5000],
                          'implausible': [np.nan]})
    self.assertEqual(len(R.preparar_rtr(bruto)), 1)


def _rtr_sintetico(n=4000, semente=0):
  """Throughput sobe com o RSSI, e 5 GHz entrega três vezes mais que 2,4 GHz."""
  rng = np.random.default_rng(semente)
  rssi = rng.uniform(-90, -30, n)
  radio = np.where(rng.random(n) < 0.5, '5ghz', '2.4ghz')
  base = (rssi + 100) * np.where(radio == '5ghz', 3.0, 1.0)
  down = base * rng.uniform(0.5, 1.5, n)
  return pd.DataFrame({'rssi': rssi, 'radio': radio, 'down_mbps': down, 'up_mbps': down / 2})


class TestPrior(unittest.TestCase):
  def test_prior_sobe_com_sinal_e_com_5ghz(self):
    modelo = R.treinar_prior(_rtr_sintetico(), 'down_mbps', 0.5)
    p = R.aplicar_prior(modelo, pd.Series([-80.0, -40.0, -50.0, -50.0]),
                        pd.Series(['5ghz', '5ghz', '2.4ghz', '5ghz']))
    self.assertLess(p[0], p[1])
    self.assertLess(p[2], p[3])

  def test_q90_fica_acima_do_q50(self):
    rtr = _rtr_sintetico()
    rssi, radio = pd.Series([-60.0]), pd.Series(['5ghz'])
    q50 = R.aplicar_prior(R.treinar_prior(rtr, 'down_mbps', 0.5), rssi, radio)[0]
    q90 = R.aplicar_prior(R.treinar_prior(rtr, 'down_mbps', 0.9), rssi, radio)[0]
    self.assertGreater(q90, q50)

  def test_rssi_invalido_vira_nan(self):
    modelo = R.treinar_prior(_rtr_sintetico(), 'down_mbps', 0.5)
    p = R.aplicar_prior(modelo, pd.Series([0.0, np.nan, -50.0]), pd.Series(['5ghz', '5ghz', '5ghz']))
    self.assertTrue(np.isnan(p[0]))
    self.assertTrue(np.isnan(p[1]))
    self.assertFalse(np.isnan(p[2]))

  def test_aplicar_prior_ignora_indice_do_dataframe(self):
    modelo = R.treinar_prior(_rtr_sintetico(), 'down_mbps', 0.5)
    rssi = pd.Series([-50.0, -70.0], index=[10, 20])
    radio = pd.Series(['5ghz', '5ghz'], index=[10, 20])
    self.assertEqual(len(R.aplicar_prior(modelo, rssi, radio)), 2)



if __name__ == '__main__':
  unittest.main()

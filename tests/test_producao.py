import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import features as F
from ml.core import producao as P

FEATURES = ['router_snr', 'radio', 'client_mode']


class TestContrato(unittest.TestCase):
  def setUp(self):
    self.df = pd.DataFrame({'router_snr': [10.0, 20.0, 30.0], 'radio': ['2.4ghz', '5ghz', '5ghz'],
                            'client_mode': ['WiFi 4 (11n)', 'WiFi 5 (11ac)', None]})
    self.contrato = P.contrato(self.df, FEATURES)

  def test_guarda_as_colunas_da_matriz_e_as_categorias(self):
    self.assertEqual(self.contrato['colunas'], ['router_snr', 'radio_2.4ghz', 'radio_5ghz',
                                                'client_mode_WiFi 4 (11n)', 'client_mode_WiFi 5 (11ac)'])
    self.assertEqual(self.contrato['categorias'], {'radio': ['2.4ghz', '5ghz'],
                                                   'client_mode': ['WiFi 4 (11n)', 'WiFi 5 (11ac)']})
    self.assertEqual(self.contrato['features'], FEATURES)

  def test_a_matriz_do_treino_e_reproduzida(self):
    X, avisos = P.preparar_entrada(self.df, self.contrato)
    pd.testing.assert_frame_equal(X, F.matriz(self.df, FEATURES))
    self.assertEqual(avisos, [])

  def test_uma_linha_do_acs_vira_as_mesmas_colunas(self):
    linha = pd.DataFrame({'router_snr': [25.0], 'radio': ['5GHz'], 'client_mode': ['WiFi 5 (11ac)']})
    X, avisos = P.preparar_entrada(linha, self.contrato)
    self.assertEqual(list(X.columns), self.contrato['colunas'])
    self.assertEqual(X.iloc[0].tolist(), [25.0, 0.0, 1.0, 0.0, 1.0])
    self.assertEqual(avisos, [])

  def test_categoria_que_o_treino_nao_viu_vira_zeros_e_avisa(self):
    linha = pd.DataFrame({'router_snr': [25.0], 'radio': ['6GHz'], 'client_mode': ['WiFi 5 (11ac)']})
    X, avisos = P.preparar_entrada(linha, self.contrato)
    self.assertEqual(X[['radio_2.4ghz', 'radio_5ghz']].iloc[0].tolist(), [0.0, 0.0])
    self.assertEqual(len(avisos), 1)
    self.assertIn('6GHz', avisos[0])

  def test_numero_que_chega_como_texto_continua_numero(self):
    linha = pd.DataFrame({'router_snr': ['12.5'], 'radio': ['5ghz'], 'client_mode': [None]})
    X, _ = P.preparar_entrada(linha, self.contrato)
    self.assertEqual(X['router_snr'].iloc[0], 12.5)
    self.assertEqual(list(X.columns), self.contrato['colunas'])

  def test_feature_faltando_levanta(self):
    with self.assertRaisesRegex(ValueError, 'client_mode'):
      P.preparar_entrada(pd.DataFrame({'router_snr': [1.0], 'radio': ['5ghz']}), self.contrato)


if __name__ == '__main__':
  unittest.main()

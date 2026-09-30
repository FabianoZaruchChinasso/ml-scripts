import json
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from medium_use import count_same_channel, medium_use, target_frequency

VIZINHOS_ROTEADOR = json.dumps([{'freq_mhz': 5805}, {'freq_mhz': 5805}, {'freq_mhz': 5180}])
VIZINHOS_CLIENTE = json.dumps([{'frequency': 5805}, {'frequency': 2437}])


class TestMediumUse(unittest.TestCase):
  def test_conta_vizinhos_no_canal(self):
    linha = {'AP_channel': '161', 'radio': '5ghz',
             'router_site_survey_ap': VIZINHOS_ROTEADOR, 'site_survey_client': VIZINHOS_CLIENTE}
    self.assertEqual(medium_use(linha), (2, 1))

  def test_scan_vazio_e_zero_de_verdade(self):
    linha = {'AP_channel': 161, 'radio': '5ghz', 'router_site_survey_ap': '[]', 'site_survey_client': '[]'}
    self.assertEqual(medium_use(linha), (0, 0))

  def test_scan_ausente_vira_vazio_e_nao_zero(self):
    self.assertEqual(medium_use({'AP_channel': 161, 'radio': '5ghz'}), (None, None))
    self.assertEqual(medium_use({'AP_channel': 161, 'radio': '5ghz', 'router_site_survey_ap': ''})[0], None)

  def test_scan_ilegivel_vira_vazio(self):
    for ruim in ('{nao e json', '{"a": 1}', '42'):
      self.assertIsNone(count_same_channel(ruim, 5805, 'freq_mhz'), ruim)

  def test_canal_ausente_ou_desconhecido_vira_vazio(self):
    self.assertIsNone(target_frequency(None, '5ghz'))
    self.assertIsNone(target_frequency('999', '5ghz'))
    self.assertIsNone(target_frequency('abc', '5ghz'))
    self.assertEqual(medium_use({'radio': '5ghz', 'router_site_survey_ap': VIZINHOS_ROTEADOR}), (None, None))

  def test_canal_2g_e_5g(self):
    self.assertEqual(target_frequency('6.0', '2.4ghz'), 2437)
    self.assertEqual(target_frequency(36, '5ghz'), 5180)


if __name__ == '__main__':
  unittest.main()

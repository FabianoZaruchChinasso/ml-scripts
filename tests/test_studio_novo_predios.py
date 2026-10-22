import copy
import json
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, predios as P  # noqa: E402


class TestResolver(unittest.TestCase):
  def setUp(self):
    self.reg = copy.deepcopy(A.PREDIOS)
    self.reg['aliases'] = {'velho-1': 'alfa-1'}
    self.reg['predios']['casa'] = {'rotulo': 'Casa', 'studio': 'casa', 'ambiente': 'domestico', 'prefixos': [],
                                   'posicoes': {'1': 'res-sala', 'sala': 'res-sala'}}

  def test_prefixo_resolve_predio_e_posicao(self):
    s = pd.Series(['alfa-1', 'BETA-sala'])
    self.assertEqual(list(P.resolver(s, 'predio', self.reg)), ['alfa', 'beta'])
    self.assertEqual(list(P.resolver(s, 'posicao', self.reg)), ['alfa-1', 'beta-sala'])

  def test_posicao_numerica_e_alias(self):
    s = pd.Series(['1.0', 'Sala', 'velho-1'])
    self.assertEqual(list(P.resolver(s, 'predio', self.reg)), ['casa', 'casa', 'alfa'])
    self.assertEqual(list(P.resolver(s, 'posicao', self.reg)), ['res-sala', 'res-sala', 'alfa-1'])

  def test_local_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      P.resolver(pd.Series(['zeta-1']), 'predio', self.reg)

  def test_teto_wan(self):
    self.assertEqual(P.teto_wan('alfa', 'speedtest_down_mbps', A.PREDIOS), 100.0)
    self.assertIsNone(P.teto_wan('beta', 'speedtest_down_mbps', A.PREDIOS))


class TestCadastro(unittest.TestCase):
  def test_config_real_do_studio_e_valida(self):
    P.carregar(caminhos.PREDIOS_PATH)

  def test_cadastrar_grava_so_no_arquivo_apontado(self):
    with A.pastas_temporarias() as p:
      P.cadastrar([{'chave': 'delta', 'rotulo': 'Delta', 'ambiente': 'domestico', 'prefixo': 'delta'}])
      with open(p.predios_path, encoding='utf-8') as handle:
        self.assertIn('delta', json.load(handle)['predios'])
      self.assertIn('delta', P.atual()['predios'])

  def test_prefixo_em_conflito_recusa(self):
    with A.pastas_temporarias():
      with self.assertRaises(ValueError):
        P.cadastrar([{'chave': 'alfa-dois', 'rotulo': 'A2', 'ambiente': 'domestico', 'prefixo': 'alfa'}])

  def test_atual_rele_quando_o_caminho_muda(self):
    with A.pastas_temporarias():
      self.assertEqual(set(P.atual()['predios']), {'alfa', 'beta', 'gama'})
    self.assertNotIn('gama', P.atual()['predios'])


if __name__ == '__main__':
  unittest.main()

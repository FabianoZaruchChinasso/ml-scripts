import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from studio import aplicacoes, caminhos


class TestAplicacoes(unittest.TestCase):
  def test_config_do_studio_carrega(self):
    apps = aplicacoes.carregar()
    self.assertIn('Chamada de vídeo', apps)
    self.assertEqual(set(apps['Chamada de vídeo']), {'dn', 'up', 'lat', 'jit'})

  def test_chave_faltando_recusa(self):
    with tempfile.TemporaryDirectory() as pasta:
      path = os.path.join(pasta, 'a.json')
      with open(path, 'w', encoding='utf-8') as handle:
        json.dump({'aplicacoes': {'X': {'dn': 1, 'up': 1, 'lat': 1}}}, handle)
      with self.assertRaises(ValueError):
        aplicacoes.carregar(path)

  def test_config_aponta_para_o_studio_e_nao_para_o_core(self):
    self.assertTrue(caminhos.APLICACOES_PATH.endswith(os.path.join('src', 'studio', 'config', 'aplicacoes.json')))
    self.assertTrue(caminhos.PREDIOS_PATH.endswith(os.path.join('src', 'studio', 'config', 'predios.json')))


if __name__ == '__main__':
  unittest.main()

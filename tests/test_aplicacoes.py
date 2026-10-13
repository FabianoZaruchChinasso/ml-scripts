import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import aplicacoes as AP


def app(**valores):
  base = {'dn': 1, 'up': 1, 'lat': 1, 'jit': 1}
  base.update(valores)
  return base


class TestAplicacoes(unittest.TestCase):
  def test_arquivo_do_repositorio_e_valido_e_igual_ao_studio(self):
    apps = AP.carregar()
    self.assertEqual(list(apps), ['Navegação', 'Chamada de vídeo', 'Streaming 4K', 'Jogo em nuvem'])
    self.assertEqual(apps['Chamada de vídeo'], {'dn': 3.8, 'up': 3.8, 'lat': 150, 'jit': 30})

  def test_chave_raiz_errada_levanta(self):
    with self.assertRaises(ValueError):
      AP.validar({'apps': {'X': app()}})

  def test_sem_aplicacao_levanta(self):
    with self.assertRaises(ValueError):
      AP.validar({'aplicacoes': {}})

  def test_chave_faltando_nomeia_a_aplicacao(self):
    with self.assertRaisesRegex(ValueError, 'Navegação'):
      AP.validar({'aplicacoes': {'Navegação': {'dn': 1, 'up': 1, 'lat': 1}}})

  def test_valor_negativo_nomeia_o_campo(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn"):
      AP.validar({'aplicacoes': {'X': app(dn=-1)}})

  def test_booleano_nao_conta_como_numero(self):
    with self.assertRaises(ValueError):
      AP.validar({'aplicacoes': {'X': app(dn=True)}})


  def test_versao_muda_com_o_conteudo(self):
    with tempfile.TemporaryDirectory() as pasta:
      path = os.path.join(pasta, 'aplicacoes.json')
      with open(path, 'w', encoding='utf-8') as handle:
        handle.write('{"a": 1}')
      antes = AP.versao(path)
      with open(path, 'w', encoding='utf-8') as handle:
        handle.write('{"a": 2}')
      self.assertNotEqual(antes, AP.versao(path))
      self.assertEqual(AP.versao(os.path.join(pasta, 'nao-existe.json')), 'ausente')

  def test_chave_de_cache_do_studio_inclui_as_aplicacoes(self):
    from ml.studio import api
    with mock.patch.object(AP, 'versao', return_value='x1'):
      antes = api._chave_versoes()
    with mock.patch.object(AP, 'versao', return_value='x2'):
      depois = api._chave_versoes()
    self.assertNotEqual(antes, depois)


if __name__ == '__main__':
  unittest.main()

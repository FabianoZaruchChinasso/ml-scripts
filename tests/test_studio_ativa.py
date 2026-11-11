import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import modelos as M
from ml.studio import api
from isolamento_mlflow import isolar as setUpModule, restaurar as tearDownModule  # noqa: E402,F401

REGISTRO = {'versoes': {'v1': {'features': ['a']}, 'v5': {'features': ['a', 'b']}}}


class TestAtivaNoStudio(unittest.TestCase):
  def test_sem_alias(self):
    self.assertIsNone(api._ativa(REGISTRO))
    with self.assertRaises(api.HTTPException) as erro:
      api._base(None, REGISTRO)
    self.assertEqual(erro.exception.status_code, 409)
    self.assertIn('ativar_mlflow.py', erro.exception.detail)
    self.assertEqual(api._base('v1', REGISTRO), 'v1')

  def test_com_alias(self):
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v5'):
      self.assertEqual(api._ativa(REGISTRO), 'v5')
      self.assertEqual(api._base(None, REGISTRO), 'v5')
      self.assertEqual(api._base('v1', REGISTRO), 'v1')
      self.assertEqual(api._features_ativa(REGISTRO), ['a', 'b'])

  def test_alias_para_definicao_apagada_conta_como_sem_ativa(self):
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v3-velha'):
      self.assertIsNone(api._ativa(REGISTRO))

  def test_troca_do_alias_muda_a_chave_dos_caches(self):
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v1'):
      antes = api._chave_versoes()
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v5'):
      self.assertNotEqual(api._chave_versoes(), antes)

  def test_features_de(self):
    self.assertEqual(M.features_de(REGISTRO, 'v5'), ['a', 'b'])
    with self.assertRaises(KeyError):
      M.features_de(REGISTRO, 'v9')


if __name__ == '__main__':
  unittest.main()

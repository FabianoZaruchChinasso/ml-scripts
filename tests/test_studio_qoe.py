import os
import sys
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api
from isolamento_mlflow import isolar as setUpModule, restaurar as tearDownModule  # noqa: E402,F401

REGISTRO = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr', 'router_noise'], 'descricao': 'x'},
  'v2': {'features': ['router_tx_retries'], 'descricao': 'so vazamento'}}}


class TestListagem(unittest.TestCase):
  def test_versao_sem_campo_aparece_como_atual(self):
    with mock.patch.object(api, '_registro', return_value=(REGISTRO, None)):
      r = api.modelos_listar()
    self.assertEqual(r['versoes'][0]['perfil_qoe'], 'atual')

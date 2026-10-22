import json
import os
import sys
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api


class TestDataMudou(unittest.TestCase):
  def test_compara_o_mtime_de_data_com_a_ultima_leitura(self):
    with mock.patch.dict(api._cache, {'lido_em': 1000.0}, clear=True):
      with mock.patch.object(api.os.path, 'getmtime', return_value=1010.0):
        self.assertTrue(api._data_mudou())
      with mock.patch.object(api.os.path, 'getmtime', return_value=990.0):
        self.assertFalse(api._data_mudou())
      with mock.patch.object(api.os.path, 'getmtime', side_effect=OSError):
        self.assertFalse(api._data_mudou())

  def test_sem_leitura_ainda_nao_avisa(self):
    with mock.patch.dict(api._cache, {}, clear=True):
      self.assertFalse(api._data_mudou())

  def test_payload_leva_o_aviso(self):
    with mock.patch.object(api, '_payload', return_value={'rows': []}), \
         mock.patch.object(api, '_data_mudou', return_value=True):
      corpo = json.loads(api.payload().body)
    self.assertEqual(corpo, {'rows': [], 'dataMudou': True})


if __name__ == '__main__':
  unittest.main()

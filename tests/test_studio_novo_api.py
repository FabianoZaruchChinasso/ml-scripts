import json
import os
import socket
import sys
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import api, portas  # noqa: E402

LOCAL = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))


class TestApi(unittest.TestCase):
  def setUp(self):
    api.dados_mudaram()

  def tearDown(self):
    api.dados_mudaram()

  def test_conjunto_gravado_aparece_no_payload(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], n=3, semente=2))
      api.dados_mudaram()
      self.assertEqual(api.conjunto_gravar(api.Conjunto(datasets=['b.csv']), LOCAL), {'datasets': ['b.csv']})
      corpo = json.loads(api.payload().body)
      self.assertEqual({d['id']: d['enabled'] for d in corpo['datasets']}, {'a.csv': False, 'b.csv': True})
      api.dados_mudaram()

  def test_conjunto_com_dataset_desconhecido_da_422(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      api.dados_mudaram()
      with self.assertRaises(HTTPException) as ctx:
        api.conjunto_gravar(api.Conjunto(datasets=['x.csv']), LOCAL)
      self.assertEqual(ctx.exception.status_code, 422)
      api.dados_mudaram()

  def test_post_de_fora_e_recusado(self):
    with self.assertRaises(HTTPException):
      api._so_local(SimpleNamespace(client=SimpleNamespace(host='10.0.0.2')))
    self.assertFalse(api._post_permitido('evil.example', None))
    self.assertFalse(api._post_permitido('127.0.0.1:8100', 'http://evil.example'))
    self.assertTrue(api._post_permitido('127.0.0.1:8100', None))


class TestPortas(unittest.TestCase):
  def test_porta_ocupada_e_livre(self):
    with socket.socket() as s:
      s.bind(('127.0.0.1', 0))
      s.listen()
      porta = s.getsockname()[1]
      self.assertFalse(portas.livre(porta))
    self.assertTrue(portas.livre(porta))


if __name__ == '__main__':
  unittest.main()

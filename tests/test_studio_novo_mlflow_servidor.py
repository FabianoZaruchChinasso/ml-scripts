import os
import socket
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, mlflow_servidor, portas, rastreio  # noqa: E402


class TestServidor(unittest.TestCase):
  def test_comando_usa_o_store_do_studio_e_so_loopback(self):
    cmd = mlflow_servidor.comando(5100)
    self.assertEqual(cmd[cmd.index('--backend-store-uri') + 1],
                     'sqlite:///' + os.path.join(caminhos.REPO, '.studio', 'mlflow.db'))
    self.assertEqual(cmd[cmd.index('--artifacts-destination') + 1], os.path.join(caminhos.REPO, '.studio', 'artefatos'))
    self.assertEqual(cmd[cmd.index('--host') + 1], '127.0.0.1')
    self.assertEqual(cmd[cmd.index('--port') + 1], '5100')

  def test_porta_ocupada_recusa_sem_subir_nada(self):
    with socket.socket() as s:
      s.bind(('127.0.0.1', 0))
      s.listen()
      porta = s.getsockname()[1]
      with mock.patch('subprocess.Popen') as popen:
        with self.assertRaisesRegex(RuntimeError, 'ocupada'):
          mlflow_servidor.iniciar(porta)
        popen.assert_not_called()

  def test_saudavel_falso_sem_servidor(self):
    with socket.socket() as s:
      s.bind(('127.0.0.1', 0))
      porta = s.getsockname()[1]
    self.assertTrue(portas.livre(porta))
    self.assertFalse(mlflow_servidor.saudavel(f'http://127.0.0.1:{porta}', timeout=0.3))

  def test_disponivel_com_sqlite_dispensa_servidor(self):
    with A.mlflow_temporario():
      self.assertTrue(rastreio.disponivel())


if __name__ == '__main__':
  unittest.main()

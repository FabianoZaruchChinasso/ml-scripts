import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, rastreio  # noqa: E402


class TestRastreio(unittest.TestCase):
  def test_recusa_o_mlflow_da_raiz(self):
    for uri in ('sqlite:///' + os.path.join(caminhos.REPO, 'mlflow.db'),
                'file://' + os.path.join(caminhos.REPO, 'mlruns'), '', 'http://example.com:5000'):
      with mock.patch.object(caminhos, 'MLFLOW_URI', uri):
        with self.assertRaises(RuntimeError, msg=uri):
          rastreio.uri()

  def test_aceita_o_servidor_do_studio_e_sqlite_fora_da_raiz(self):
    with mock.patch.object(caminhos, 'MLFLOW_URI', 'http://127.0.0.1:5100'):
      self.assertEqual(rastreio.uri(), 'http://127.0.0.1:5100')
    with A.mlflow_temporario():
      self.assertTrue(rastreio.uri().startswith('sqlite:///'))

  def test_experimento_criado_uma_vez(self):
    with A.mlflow_temporario():
      cli = rastreio.cliente()
      self.assertEqual(rastreio.experimento_id(cli), rastreio.experimento_id(cli))
      self.assertEqual(cli.get_experiment_by_name('QoE Studio').name, 'QoE Studio')

  def test_nomes_e_links(self):
    self.assertEqual(rastreio.nome_modelo('latency_ms'), 'studio-latency_ms')
    with self.assertRaises(ValueError):
      rastreio.nome_modelo('qoe_dw_score')
    with mock.patch.object(caminhos, 'MLFLOW_UI', 'http://127.0.0.1:5100'):
      self.assertEqual(rastreio.link_run('3', 'abc'), 'http://127.0.0.1:5100/#/experiments/3/runs/abc')
      self.assertEqual(rastreio.link_versao('studio-jitter_ms', '2'),
                       'http://127.0.0.1:5100/#/models/studio-jitter_ms/versions/2')


if __name__ == '__main__':
  unittest.main()

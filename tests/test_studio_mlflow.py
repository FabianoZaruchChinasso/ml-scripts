import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import studio_mlflow
from ml.core import registro_mlflow as R

REGISTRO = {'ativo': 'v2', 'versoes': {
  'v1': {'features': ['a'], 'avaliacao': {'comodo': {'nota': 0.6}}},
  'v2': {'features': ['a', 'b'], 'avaliacao': {'comodo': {'nota': 0.7}}}}}


class TestScript(unittest.TestCase):
  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{tmp.name}/mlflow.db'})
    env.start()
    self.addCleanup(env.stop)
    carregar = mock.patch.object(studio_mlflow.core_modelos, 'carregar', return_value=REGISTRO)
    carregar.start()
    self.addCleanup(carregar.stop)

  def runs(self):
    cli = R.cliente()
    return list(cli.search_runs([cli.get_experiment_by_name(R.EXPERIMENTO).experiment_id]))

  def test_registra_todas_com_evento_script(self):
    os.environ.pop('MODELO', None)
    studio_mlflow.main()
    tags = {r.data.tags['modelo']: r.data.tags for r in self.runs()}
    self.assertEqual(sorted(tags), ['v1', 'v2'])
    self.assertEqual({t['evento'] for t in tags.values()}, {'script'})
    self.assertNotIn('ativo', tags['v2'])

  def test_modelo_limita_a_uma_versao(self):
    with mock.patch.dict(os.environ, {'MODELO': 'v1'}):
      studio_mlflow.main()
    self.assertEqual([r.data.tags['modelo'] for r in self.runs()], ['v1'])

  def test_modelo_inexistente_para_com_mensagem(self):
    with mock.patch.dict(os.environ, {'MODELO': 'v9'}):
      with self.assertRaises(SystemExit) as ctx:
        studio_mlflow.main()
    self.assertIn('v9', str(ctx.exception))


if __name__ == '__main__':
  unittest.main()

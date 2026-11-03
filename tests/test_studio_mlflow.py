import os
import sys
import tempfile
import unittest

import mlflow

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import studio_mlflow


def versao_sintetica() -> dict:
  return {
    'features': ['a', 'b'],
    'denominador': {'speedtest_down_mbps': {'coluna': 'x', 'radio': '5ghz'}},
    'cobertura': {'nivel': 'parcial'},
    'avaliacao': {
      'perfil': 'residencial',
      'comodo': {'ambiente': 'todos', 'datasets': ['d1.zip', 'd2.csv'], 'nota': 0.7, 'intervalo': [0.6, 0.8],
                 'piso': {'nota': 0.45}, 'contra_piso': {'diferenca': 0.27}, 'graves': 2,
                 'jogo': {'nota': 0.64, 'intervalo': [0.5, 0.78], 'piso': {'nota': 0.55}},
                 'versao_comodo': 'v-c', 'posicoes': [{'pos': 'p1'}], 'piso_posicoes': [{'pos': 'p2'}]},
      'atende_completo': {'media': 0.66}, 'atende_throughput': {'media': 0.65},
      'speedtest_down_mbps': {'pooled': 0.75, 'mae': 59.0, 'mae_log': 0.6, 'versao_regua': 'r1'},
      'latency_ms': {'pooled': -0.1, 'mae': 22.8, 'quantis': {'cobertura': {'q50': 0.5, 'q90': 0.91}}},
    },
  }


class TestParametrosEMetricas(unittest.TestCase):
  def test_parametros(self):
    params, _ = studio_mlflow.parametros_e_metricas('v9', versao_sintetica(), True)
    self.assertEqual(params['modelo'], 'v9')
    self.assertTrue(params['ativo'])
    self.assertEqual(params['features'], 'a,b')
    self.assertEqual(params['n_features'], 2)
    self.assertEqual(params['datasets'], 'd1.zip,d2.csv')
    self.assertEqual(params['perfil'], 'residencial')
    self.assertEqual(params['cobertura_tr069'], 'parcial')
    self.assertEqual(params['versao_comodo'], 'v-c')
    self.assertEqual(params['versao_regua'], 'r1')
    self.assertIn('radio', params['denominador'])

  def test_denominador_ausente(self):
    versao = versao_sintetica()
    versao['denominador'] = None
    params, _ = studio_mlflow.parametros_e_metricas('v9', versao, False)
    self.assertEqual(params['denominador'], 'nenhum')
    self.assertFalse(params['ativo'])

  def test_metricas_e_ausentes_ignoradas(self):
    _, m = studio_mlflow.parametros_e_metricas('v9', versao_sintetica(), False)
    self.assertEqual(m['comodo_nota'], 0.7)
    self.assertEqual(m['comodo_lo90'], 0.6)
    self.assertEqual(m['comodo_hi90'], 0.8)
    self.assertEqual(m['comodo_piso'], 0.45)
    self.assertEqual(m['comodo_contra_piso'], 0.27)
    self.assertEqual(m['comodo_graves'], 2)
    self.assertEqual(m['jogo_nota'], 0.64)
    self.assertEqual(m['jogo_piso'], 0.55)
    self.assertEqual(m['atende_completo'], 0.66)
    self.assertEqual(m['down_pooled'], 0.75)
    self.assertEqual(m['down_mae_log'], 0.6)
    self.assertEqual(m['lat_cobertura_q90'], 0.91)
    for ausente in ('atende_ajustado', 'up_pooled', 'jit_mae', 'jit_cobertura_q90', 'down_cobertura_q90'):
      self.assertNotIn(ausente, m)
    self.assertNotIn('lat_mae_log', m)

  def test_bloco_comodo_ausente(self):
    versao = versao_sintetica()
    del versao['avaliacao']['comodo']
    params, m = studio_mlflow.parametros_e_metricas('v9', versao, False)
    self.assertEqual(params['datasets'], '')
    self.assertFalse([k for k in m if k.startswith(('comodo_', 'jogo_'))])


class TestRegistro(unittest.TestCase):
  def test_registrar_versao(self):
    with tempfile.TemporaryDirectory() as tmp:
      mlflow.set_tracking_uri(f'sqlite:///{tmp}/mlflow.db')
      mlflow.set_experiment('teste')
      studio_mlflow.registrar_versao('v9', versao_sintetica(), True)
      run = mlflow.search_runs(output_format='list')[0]
      self.assertEqual(run.info.run_name, 'v9-studio')
      self.assertEqual(run.data.metrics['comodo_nota'], 0.7)
      nomes = {a.path for a in mlflow.MlflowClient().list_artifacts(run.info.run_id)}
      self.assertEqual(nomes, {'avaliacao.json', 'posicoes.json'})


if __name__ == '__main__':
  unittest.main()

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import comodo_benchmark as B


class TestMetricasMlflow(unittest.TestCase):
  def test_parametros_e_metricas(self):
    r = {'nota': 0.7, 'intervalo': [0.6, 0.8]}
    por_predio = {'hotmilk': (3, 5), 'residencia': (4, 4)}
    params, metricas = B.metricas_mlflow('experimento', ['RSSI', 'radio'], 'sozinhas', r, -0.05, 1, por_predio)
    self.assertEqual(params['linha'], 'experimento')
    self.assertEqual(params['features'], 'RSSI,radio')
    self.assertEqual(params['treino'], 'sozinhas')
    self.assertIn('versao_comodo', params)
    self.assertEqual(metricas['comodo_nota'], 0.7)
    self.assertEqual((metricas['comodo_lo90'], metricas['comodo_hi90']), (0.6, 0.8))
    self.assertEqual(metricas['vs_ativa'], -0.05)
    self.assertEqual(metricas['graves'], 1)
    self.assertAlmostEqual(metricas['acerto_hotmilk'], 0.6)
    self.assertEqual(metricas['acerto_residencia'], 1.0)

  def test_sem_intervalo(self):
    _, metricas = B.metricas_mlflow('piso', ['radio'], 'todas', {'nota': 0.4, 'intervalo': None}, 0.0, 0, {})
    self.assertNotIn('comodo_lo90', metricas)


class TestDenominadorExperimento(unittest.TestCase):
  def test_sem_coluna_e_none(self):
    self.assertIsNone(B.denominador_experimento(None))
    self.assertIsNone(B.denominador_experimento(''))

  def test_download_e_upload_no_5ghz(self):
    d = B.denominador_experimento('link_speed_mbps')
    esperado = {'coluna': 'link_speed_mbps', 'radio': '5ghz'}
    self.assertEqual(d, {B.core_comodo.DN: esperado, B.core_comodo.UP: esperado})


class TestMetricasMlflowDenominador(unittest.TestCase):
  def test_registra_o_denominador(self):
    params, _ = B.metricas_mlflow('experimento', ['RSSI'], 'todas', {'nota': 0.6, 'intervalo': None}, -0.1, 0, {},
                                  denominador='link_speed_mbps')
    self.assertEqual(params['denominador'], 'link_speed_mbps')

  def test_sem_denominador_vira_nenhum(self):
    params, _ = B.metricas_mlflow('piso', ['radio'], 'todas', {'nota': 0.4, 'intervalo': None}, 0.0, 0, {})
    self.assertEqual(params['denominador'], 'nenhum')


class TestMetricasMlflowReferencia(unittest.TestCase):
  def test_referencia_padrao_real(self):
    params, _ = B.metricas_mlflow('v5', ['a'], 'todas', {'nota': 0.7, 'intervalo': None}, 0.0, 0, {})
    self.assertEqual(params['referencia'], 'real')

  def test_referencia_prevista(self):
    params, _ = B.metricas_mlflow('v5', ['a'], 'todas', {'nota': 0.7, 'intervalo': None}, 0.0, 0, {},
                                  referencia='prevista')
    self.assertEqual(params['referencia'], 'prevista')


if __name__ == '__main__':
  unittest.main()

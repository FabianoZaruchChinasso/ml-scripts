import os
import sys
import unittest

import numpy as np
import pandas as pd
import torch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import rede_pre as P


class TestSinal(unittest.TestCase):
  def test_normalizar_sinal(self):
    s = P.normalizar_sinal(pd.Series([-60.0, -75.0, 0.0, np.nan]))
    np.testing.assert_allclose(s, [0.0, -1.0, 0.0, 0.0])
    self.assertEqual(s.dtype, np.float32)


class TestRede(unittest.TestCase):
  def test_extra_comeca_zerada_e_nao_muda_a_saida(self):
    rede = P.Rede(3, 8)
    self.assertTrue(torch.all(rede.extra.weight == 0))
    xc = torch.randn(5, 2)
    with torch.no_grad():
      torch.testing.assert_close(rede(xc, torch.randn(5, 3)), rede(xc, torch.zeros(5, 3)))

  def test_sem_extra(self):
    rede = P.Rede(0, 8)
    self.assertIsNone(rede.extra)
    self.assertEqual(rede(torch.randn(4, 2)).shape, (4,))

  def test_pesos_pre_nao_levam_a_entrada_extra(self):
    pesos = P.Rede(3, 8).pesos_pre()
    self.assertTrue(pesos)
    self.assertFalse([k for k in pesos if k.startswith('extra.')])


def _rtr(n=3000, semente=0):
  """Throughput sobe com o sinal, e 5 GHz entrega três vezes mais que 2,4 GHz."""
  rng = np.random.default_rng(semente)
  rssi = rng.uniform(-90, -30, n)
  radio = np.where(rng.random(n) < 0.5, '5ghz', '2.4ghz')
  down = (rssi + 100) * np.where(radio == '5ghz', 3.0, 1.0) * rng.uniform(0.8, 1.2, n)
  return pd.DataFrame({'rssi': rssi, 'radio': radio, 'down_mbps': down, 'up_mbps': down / 2})


class TestPreTreino(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.rtr = _rtr()
    cls.pre = P.pre_treinar(cls.rtr, 'down_mbps', oculta=16, epocas=30, lr=1e-2)

  def test_devolve_pesos_oculta_e_teto(self):
    self.assertEqual(self.pre['oculta'], 16)
    self.assertAlmostEqual(self.pre['teto_mbps'], float(np.quantile(self.rtr['down_mbps'], 0.999)))
    self.assertIn('comum.weight', self.pre['pesos'])

  def test_aprende_sinal_e_banda(self):
    rede = P.Rede(0, 16)
    rede.load_state_dict(self.pre['pesos'], strict=False)
    xc = P._comum(pd.Series([-80.0, -40.0, -50.0, -50.0]), np.array([1.0, 1.0, 0.0, 1.0]))
    with torch.no_grad():
      p = rede(xc)
    self.assertLess(p[0], p[1])
    self.assertLess(p[2], p[3])


from sklearn.base import clone


def _nossos(n=80, semente=1):
  """Mesma física do _rtr, mais contenção: o throughput se divide por n_clients."""
  rng = np.random.default_rng(semente)
  sinal = rng.uniform(-80, -40, n)
  cinco = (rng.random(n) < 0.5).astype(float)
  n_clients = rng.integers(1, 4, n).astype(float)
  y = (sinal + 100) * np.where(cinco == 1, 3.0, 1.0) / n_clients
  X = pd.DataFrame({'router_signal_dbm': sinal, 'radio_2.4ghz': 1 - cinco, 'radio_5ghz': cinco,
                    'n_clients': n_clients})
  return X, pd.Series(y)


class TestMLPAjustado(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.pre = P.pre_treinar(_rtr(), 'down_mbps', oculta=16, epocas=30, lr=1e-2)
    cls.X, cls.y = _nossos()

  def test_sem_ajuste_e_a_rede_pre_treinada(self):
    est = P.MLPAjustado(pre=self.pre, epocas=0, n_redes=1).fit(self.X, self.y)
    outro = self.X.assign(n_clients=99.0)
    np.testing.assert_allclose(est.predict(self.X), est.predict(outro), rtol=1e-6)
    rede = P.Rede(0, 16)
    rede.load_state_dict(self.pre['pesos'], strict=False)
    with torch.no_grad():
      esperado = np.expm1(rede(P._comum(self.X['router_signal_dbm'], self.X['radio_5ghz'])).numpy())
    np.testing.assert_allclose(est.predict(self.X), np.clip(esperado, 0, est.teto_), rtol=1e-5)

  def test_clone_ajusta_e_respeita_o_teto(self):
    est = clone(P.MLPAjustado(pre=self.pre, epocas=50, n_redes=2)).fit(self.X, self.y)
    p = est.predict(self.X)
    self.assertEqual(len(p), len(self.X))
    self.assertTrue((p >= 0).all() and (p <= est.teto_).all())
    self.assertGreaterEqual(est.teto_, self.pre['teto_mbps'])

  def test_controle_e_reprodutivel(self):
    a = P.MLPAjustado(pre=None, epocas=50, n_redes=2).fit(self.X, self.y).predict(self.X)
    b = P.MLPAjustado(pre=None, epocas=50, n_redes=2).fit(self.X, self.y).predict(self.X)
    np.testing.assert_allclose(a, b)

  def test_ajuste_aprende_a_feature_extra(self):
    est = P.MLPAjustado(pre=self.pre, epocas=500, lr=1e-2, n_redes=1).fit(self.X, self.y)
    linhas = pd.DataFrame({'router_signal_dbm': [-50.0, -50.0], 'radio_2.4ghz': [0.0, 0.0],
                           'radio_5ghz': [1.0, 1.0], 'n_clients': [1.0, 3.0]})
    p = est.predict(linhas)
    self.assertGreater(p[0], p[1])

  def test_nan_nas_extras_usa_a_mediana_do_treino(self):
    est = P.MLPAjustado(pre=None, epocas=10, n_redes=1).fit(self.X, self.y)
    com_nan = self.X.iloc[:3].assign(n_clients=np.nan)
    self.assertFalse(np.isnan(est.predict(com_nan)).any())


if __name__ == '__main__':
  unittest.main()

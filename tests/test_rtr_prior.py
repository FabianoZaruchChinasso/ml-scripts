import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import rtr_prior as E


class TestRtrPrior(unittest.TestCase):
  def test_variantes_tem_controle_e_quatro_priores(self):
    v = E.variantes()
    self.assertEqual(v['ctrl_rssi'], ['RSSI'])
    self.assertEqual(sorted(k for k in v if k.startswith('prior_')),
                     ['prior_q50_ap', 'prior_q50_rssi', 'prior_q90_ap', 'prior_q90_rssi'])
    self.assertEqual(v['prior_q90_ap'], ['prior_rtr_q90_ap'])

  def test_mae_faixa_alta_so_conta_acima_de_267(self):
    prev = pd.DataFrame({'y': [100.0, 300.0, 500.0], 'yhat': [0.0, 250.0, 400.0]})
    self.assertEqual(E.mae_faixa_alta(prev), 75.0)

  def test_mae_faixa_alta_sem_linhas_altas(self):
    self.assertIsNone(E.mae_faixa_alta(pd.DataFrame({'y': [10.0], 'yhat': [5.0]})))


if __name__ == '__main__':
  unittest.main()

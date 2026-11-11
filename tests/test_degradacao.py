import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import degradacao as D
from ml.core import pacote as P
from test_studio_features import TABELA, frame

FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
ZERO = {'down_mae': 0.0, 'up_mae': 0.0, 'lat_pinball_q90': 0.0, 'jit_pinball_q90': 0.0}
ALTO = {chave: 1e9 for chave in ZERO}


class TestMedir(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    antigos = {alvo: C.preparar({'a.csv': frame(seed=1)}, alvo, TABELA) for alvo in P.PREFIXOS}
    cls.pacote = P.treinar(antigos, FEATURES, None)
    cls.conjs = {alvo: C.preparar({'a.csv': frame(seed=1), 'b.csv': frame(seed=2)}, alvo, TABELA)
                 for alvo in P.PREFIXOS}

  def test_mede_so_as_linhas_novas(self):
    r = D.medir(self.pacote, self.conjs, ['a.csv'], ALTO)
    self.assertEqual(set(r), set(D.SAIDA))
    for alvo, bloco in r.items():
      df = self.conjs[alvo].df
      self.assertEqual(bloco['n'], int(((df['_ds'] == 'b.csv') & df[alvo].notna()).sum()))
      self.assertEqual(bloco['datasets'], ['b.csv'])
      self.assertIsNotNone(bloco['intervalo'])
    self.assertEqual([r[a]['resultado'] for a in A.ALVOS_COM_TETO], ['estavel', 'estavel'])
    self.assertIn('cobertura', r['latency_ms'])

  def test_erro_acima_do_esperado_degrada(self):
    r = D.medir(self.pacote, self.conjs, ['a.csv'], ZERO)
    self.assertEqual(r['speedtest_down_mbps']['resultado'], 'degradou')
    self.assertIn('esperado', r['speedtest_down_mbps']['motivo'])
    self.assertTrue(D.degradou(r))

  def test_sem_linhas_novas_volta_vazio(self):
    self.assertEqual(D.medir(self.pacote, self.conjs, ['a.csv', 'b.csv'], ALTO), {})
    self.assertFalse(D.degradou({}))

  def test_sem_esperado_vazao_nao_degrada_pelo_erro(self):
    r = D.medir(self.pacote, self.conjs, ['a.csv'], {})
    self.assertEqual([r[a]['resultado'] for a in A.ALVOS_COM_TETO], ['estavel', 'estavel'])
    self.assertIsNone(r['speedtest_down_mbps']['esperado'])


if __name__ == '__main__':
  unittest.main()

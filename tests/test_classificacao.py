import os
import sys
import unittest
import warnings

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import classificacao as K

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {**{a: {'classe': 'alvo'} for a in ALVOS},
                      'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']
LIM = {'dn': 30.0, 'up': 10.0, 'lat': 100, 'jit': 30}


class Lembra(BaseEstimator, ClassifierMixin):
  """Prevê sempre `classe` e guarda o índice das linhas de treino de cada ajuste."""
  vistos = []

  def __init__(self, classe=1):
    self.classe = classe

  def fit(self, X, y):
    self.classes_ = np.unique(y)
    Lembra.vistos.append(list(X.index))
    return self

  def predict(self, X):
    return np.full(len(X), self.classe)


def frame(n_por_local=10, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({'local': np.repeat(LOCAIS, n_por_local), 'speedtest_down_mbps': 2 * snr,
                       'speedtest_up_mbps': snr / 2, 'latency_ms': 10.0, 'jitter_ms': 2.0,
                       'router_snr': snr, 'router_tx_bytes': snr})


def conjuntos(f=None):
  f = frame() if f is None else f
  return (C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA, catalogo=()),
          C.preparar({'a.csv': f}, 'speedtest_up_mbps', TABELA, catalogo=()))


class TestAlvo(unittest.TestCase):
  def test_atende_com_os_dois_limiares_e_so_linhas_comuns(self):
    f = frame()
    f.loc[0, 'speedtest_up_mbps'] = np.nan
    dn, up = conjuntos(f)
    df = K.alvo_atende(dn, up, LIM)
    self.assertNotIn('a.csv:0', df['_linha'].tolist())
    esperado = (df['speedtest_down_mbps'] >= 30) & (df['_linha'].map(up.df.set_index('_linha')['speedtest_up_mbps']) >= 10)
    self.assertTrue((df['_atende'] == esperado).all())


class TestClassificacao(unittest.TestCase):
  def setUp(self):
    Lembra.vistos = []

  def test_treino_nunca_tem_o_predio_de_teste(self):
    dn, up = conjuntos()
    df = K.alvo_atende(dn, up, LIM)
    prev = K.prever_classe_fora_do_fold(df, ['router_snr'], [], Lembra())
    self.assertEqual(sorted(prev['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    for indices in Lembra.vistos:
      self.assertEqual(df.loc[indices, '_site'].nunique(), 2)

  def test_fold_com_uma_classe_no_treino_e_pulado(self):
    dn, up = conjuntos()
    df = K.alvo_atende(dn, up, LIM)
    df['_atende'] = df['_site'] == 'residencia'
    with warnings.catch_warnings(record=True) as avisos:
      warnings.simplefilter('always')
      prev = K.prever_classe_fora_do_fold(df, ['router_snr'], [], Lembra())
    self.assertNotIn('residencia', prev['_site'].unique())
    self.assertTrue(any('uma classe' in str(a.message) for a in avisos))

  def test_vazamento_levanta(self):
    dn, up = conjuntos()
    df = K.alvo_atende(dn, up, LIM)
    with self.assertRaises(AssertionError):
      K.prever_classe_fora_do_fold(df, ['router_tx_bytes'], ['router_tx_bytes'], Lembra())


class TestResumo(unittest.TestCase):
  def test_valores_conferidos_a_mao(self):
    prev = pd.DataFrame({'_linha': ['a', 'b', 'c', 'd'], 'y': [True, False, True, False],
                         'yhat': [True, False, False, True], '_site': ['s1', 's1', 's2', 's2'],
                         '_pos': ['p1', 'p2', 'p3', 'p4']})
    r = K.resumir_classe(prev)
    self.assertEqual(r['pooled'], 0.5)
    self.assertEqual(r['por_local'], {'s1': 1.0, 's2': 0.0})
    self.assertEqual(r['n'], 4)

  def test_vazio(self):
    r = K.resumir_classe(pd.DataFrame(columns=['_linha', 'y', 'yhat', '_site', '_pos']))
    self.assertEqual((r['pooled'], r['por_local'], r['intervalo'], r['n']), (None, {}, None, 0))


class TestReferencia(unittest.TestCase):
  def test_atende_tirado_das_previsoes_de_regressao(self):
    def p(y, yhat):
      return pd.DataFrame({'_linha': ['a', 'b'], 'y': y, 'yhat': yhat, '_site': ['s', 's'], '_pos': ['p', 'q']})
    ref = K.referencia_regua(p([40.0, 40.0], [40.0, 10.0]), p([20.0, 20.0], [20.0, 20.0]), LIM)
    self.assertEqual(ref['y'].tolist(), [True, True])
    self.assertEqual(ref['yhat'].tolist(), [True, False])


if __name__ == '__main__':
  unittest.main()

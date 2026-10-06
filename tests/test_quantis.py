import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import quantis as Q

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {**{a: {'classe': 'alvo'} for a in ALVOS},
                      'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


class Constante(BaseEstimator, RegressorMixin):
  """Prevê sempre `valor` (na escala em que é treinado, a log)."""

  def __init__(self, valor=0.0):
    self.valor = valor

  def fit(self, X, y):
    self.n_ = len(X)
    return self

  def predict(self, X):
    return np.full(len(X), self.valor)


def frame(n_por_local=12, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({
    'local': np.repeat(LOCAIS, n_por_local),
    'speedtest_down_mbps': 3 * snr, 'speedtest_up_mbps': snr,
    'latency_ms': 300 / snr * rng.lognormal(0, 0.3, n),
    'jitter_ms': 100 / snr * rng.lognormal(0, 0.5, n),
    'router_snr': snr, 'router_tx_bytes': snr * 1000,
  })


def conjunto(alvo='latency_ms'):
  return C.preparar({'a.csv': frame()}, alvo, TABELA, catalogo=())


class TestMetricas(unittest.TestCase):
  def test_pinball_valores_conhecidos(self):
    # erros +2 e -2 com q=0,9: max(1,8; -0,2) = 1,8 e max(-1,8; 0,2) = 0,2 -> média 1,0
    self.assertAlmostEqual(Q.pinball([10.0, 10.0], [8.0, 12.0], 0.9), 1.0)

  def test_cobertura(self):
    self.assertEqual(Q.cobertura([1.0, 2.0, 3.0, 4.0], [2.0, 2.0, 2.0, 2.0]), 0.5)

  def test_modelo_quantil_usa_perda_quantilica(self):
    m = Q.modelo_quantil(0.9)
    self.assertEqual((m.loss, m.quantile), ('quantile', 0.9))


class TestPrevisoes(unittest.TestCase):
  def test_folds_por_predio_e_colunas(self):
    conj = conjunto()
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    self.assertEqual(list(prev.columns), ['_linha', 'y', 'q50', 'q90', 'cruzado', 'correcao', 'sem_correcao',
                                          '_site', '_pos'])
    self.assertEqual(sorted(prev['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    self.assertEqual(sorted(prev['_linha']), sorted(conj.df['_linha']))
    self.assertTrue((prev['q90'] >= prev['q50']).all())

  def test_volta_da_escala_log(self):
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(np.log1p(20.0))}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est, conformal=False)
    np.testing.assert_allclose(prev['q50'], 5.0)
    np.testing.assert_allclose(prev['q90'], 20.0)
    self.assertFalse(prev['cruzado'].any())

  def test_corta_em_zero_e_corrige_cruzamento(self):
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(-10.0)}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est, conformal=False)
    np.testing.assert_allclose(prev['q90'], prev['q50'])
    self.assertTrue(prev['cruzado'].all())

  def test_y_fica_em_ms(self):
    conj = conjunto()
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    reais = conj.df.set_index('_linha')['latency_ms']
    np.testing.assert_allclose(prev.set_index('_linha')['y'].sort_index(), reais.sort_index())

  def test_vazamento_levanta(self):
    conj = conjunto()
    with self.assertRaises(AssertionError):
      Q.prever_quantis_fora_do_fold(conj.df, ['router_tx_bytes'], conj.alvo, ['router_tx_bytes'])

  def test_conformal_soma_a_correcao_ao_p90_em_escala_log(self):
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(0.0)}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est)
    self.assertTrue((prev['correcao'] > 0).all())
    self.assertFalse(prev['sem_correcao'].any())
    np.testing.assert_allclose(prev['q90'], np.maximum(np.expm1(prev['correcao']), prev['q50']))

  def test_correcao_do_fold_vem_so_dos_predios_de_treino(self):
    from ml.core.features import matriz
    conj = conjunto()
    est = {0.5: Constante(np.log1p(5.0)), 0.9: Constante(0.0)}
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimadores=est)
    treino = conj.df[conj.df['_site'] != 'residencia']
    esperado = Q.correcao_conformal(matriz(treino, ['router_snr']),
                                    np.log1p(treino['latency_ms'].astype(float)), treino['_site'], 0.9,
                                    estimador=Constante(0.0))
    np.testing.assert_allclose(prev.loc[prev['_site'] == 'residencia', 'correcao'], esperado)

  def test_um_predio_de_treino_fica_sem_correcao(self):
    f = frame()
    f = f[f['local'].isin(['sala', 'quarto', 'cwpb-1', 'cwpb-2'])]
    conj = C.preparar({'a.csv': f}, 'latency_ms', TABELA, catalogo=())
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [])
    self.assertTrue(prev['sem_correcao'].all())
    self.assertTrue((prev['correcao'] == 0).all())

  def test_sem_conformal_nao_corrige(self):
    conj = conjunto()
    prev = Q.prever_quantis_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], conformal=False)
    self.assertTrue((prev['correcao'] == 0).all())
    self.assertFalse(prev['sem_correcao'].any())


def previsto(y, q50, q90, sites=None, linhas=None):
  n = len(y)
  return pd.DataFrame({'_linha': linhas or [f'a:{i}' for i in range(n)], 'y': y, 'q50': q50, 'q90': q90,
                       'cruzado': [False] * n, '_site': sites or ['s1', 's1', 's2', 's2'][:n],
                       '_pos': ['p1', 'p2', 'p3', 'p4'][:n]})


class TestResumo(unittest.TestCase):
  def test_metricas_pooled_e_por_predio(self):
    prev = previsto([10.0, 20.0, 30.0, 40.0], [10.0, 20.0, 30.0, 40.0], [15.0, 25.0, 25.0, 45.0])
    prev.loc[0, 'cruzado'] = True
    r = Q.resumir_quantis(prev, 3)
    self.assertEqual(r['cobertura']['q90'], 0.75)
    self.assertEqual(r['cobertura']['q50'], 1.0)
    self.assertEqual(r['pinball']['q50'], 0.0)
    self.assertEqual(r['por_local']['s2']['cobertura']['q90'], 0.5)
    self.assertEqual(r['cruzados'], 1)
    self.assertEqual(r['mediana_mae'], 0.0)
    self.assertEqual(r['n'], 3)
    for chave in ('pinball_q50', 'pinball_q90', 'cobertura_q50', 'cobertura_q90'):
      self.assertIn(chave, r['intervalos'])

  def test_vazio_nao_quebra(self):
    r = Q.resumir_quantis(pd.DataFrame(columns=['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos']), 0)
    self.assertEqual((r['pinball'], r['cobertura'], r['intervalos'], r['mediana_mae']), ({}, {}, {}, None))

  def test_traz_versao_da_regua(self):
    from ml.core import avaliacao as A
    self.assertEqual(Q.resumir_quantis(previsto([1.0, 2.0], [1.0, 2.0], [1.0, 2.0]), 1)['versao_regua'],
                     A.VERSAO_REGUA)

  def test_sem_coluna_de_correcao(self):
    r = Q.resumir_quantis(previsto([1.0, 2.0], [1.0, 2.0], [1.0, 2.0]), 1)
    self.assertEqual((r['correcao_por_local'], r['sem_correcao']), ({}, 0))

  def test_correcao_por_predio(self):
    prev = previsto([10.0, 20.0, 30.0, 40.0], [10.0, 20.0, 30.0, 40.0], [15.0, 25.0, 35.0, 45.0])
    prev['correcao'] = [0.5, 0.5, 0.8, 0.8]
    prev['sem_correcao'] = [False, False, False, False]
    r = Q.resumir_quantis(prev, 1)
    self.assertEqual(r['correcao_por_local'], {'s1': 0.5, 's2': 0.8})
    self.assertEqual(r['sem_correcao'], 0)

  def test_vazio_traz_campos_de_correcao(self):
    r = Q.resumir_quantis(pd.DataFrame(columns=['_linha', 'y', 'q50', 'q90', 'cruzado', '_site', '_pos']), 0)
    self.assertEqual((r['correcao_por_local'], r['sem_correcao']), ({}, 0))


def delta(valor, lo, hi):
  return {'valor': valor, 'intervalo': [lo, hi], 'pinball_base': 5.0, 'n': 10}


class TestVeredito(unittest.TestCase):
  def test_delta_pinball_da_nova_perfeita(self):
    y = [10.0, 20.0, 30.0, 40.0]
    nova = previsto(y, y, y)
    base = previsto(y, y, [v + 10 for v in y])
    d = Q.delta_pinball(nova, base)
    # base: erro -10 com q=0,9 -> max(-9; 1) = 1 por linha; nova: 0
    self.assertEqual((d['valor'], d['pinball_base'], d['n']), (-1.0, 1.0, 4))
    self.assertLess(d['intervalo'][1], 0)

  def test_sem_linhas_em_comum_levanta(self):
    with self.assertRaises(ValueError):
      Q.delta_pinball(previsto([1.0], [1.0], [1.0]), previsto([1.0], [1.0], [1.0], linhas=['b:0']))

  def test_cobertura_fora_da_faixa_e_pior_mesmo_com_pinball_melhor(self):
    self.assertEqual(Q.veredito_quantis(delta(-1.5, -2.0, -1.0), 0.70)['resultado'], 'pior')

  def test_pinball_pior_e_pior(self):
    self.assertEqual(Q.veredito_quantis(delta(0.8, 0.5, 1.0), 0.90)['resultado'], 'pior')

  def test_pinball_melhor_com_cobertura_boa_e_melhor(self):
    self.assertEqual(Q.veredito_quantis(delta(-1.5, -2.0, -1.0), 0.90)['resultado'], 'melhor')

  def test_intervalo_com_zero_e_empate(self):
    self.assertEqual(Q.veredito_quantis(delta(0.0, -1.0, 1.0), 0.90)['resultado'], 'empate')


def pontual(y, yhat, linhas):
  n = len(y)
  return pd.DataFrame({'_linha': linhas, 'y': y, 'yhat': yhat,
                       '_site': ['s1', 's1', 's2', 's2', 's2'][:n], '_pos': ['p1', 'p2', 'p3', 'p4', 'p5'][:n]})


APPS = {'Jogo': {'dn': 10, 'up': 1, 'lat': 40, 'jit': 10},
        'Tudo': {'dn': 0, 'up': 0, 'lat': 10000, 'jit': 10000}}
LINHAS = ['a:0', 'a:1', 'a:2', 'a:3']


class TestAtendeCompleto(unittest.TestCase):
  def test_quatro_limiares_com_p90_em_latencia_e_jitter(self):
    dn = pontual([30.0] * 5, [30.0] * 5, LINHAS + ['a:9'])
    up = pontual([10.0] * 4, [10.0] * 4, LINHAS)
    lat = previsto([20.0, 20.0, 80.0, 20.0], [15.0] * 4, [30.0, 50.0, 90.0, 30.0])
    jit = previsto([5.0, 5.0, 5.0, 20.0], [4.0] * 4, [5.0] * 4)
    r = Q.atende_completo(dn, up, lat, jit, APPS)
    # Jogo: real [T, T, F, F]; previsto pelo p90 [T, F, F, T] -> (1/2 + 1/2) / 2 = 0,5
    self.assertEqual(r['por_aplicacao'], {'Jogo': 0.5})
    self.assertEqual((r['media'], r['n']), (0.5, 4))
    self.assertTrue(any('Tudo' in a for a in r['avisos']))

  def test_sem_linha_comum_levanta(self):
    dn = pontual([30.0], [30.0], ['x:0'])
    with self.assertRaises(ValueError):
      Q.atende_completo(dn, dn, previsto([1.0], [1.0], [1.0]), previsto([1.0], [1.0], [1.0]), APPS)


class TestCorrecaoConformal(unittest.TestCase):
  def test_nivel_de_amostra_finita_com_escores_juntos(self):
    # Estimador constante 0: os escores são os próprios y. Com n = 30 escores, o nível é
    # ceil(31 * 0,9) / 30 = 0,9333, e o quantil 'higher' dá 29 (o quantil 0,9 ingênuo daria 28).
    X = pd.DataFrame({'x': np.arange(30, dtype=float)})
    y = pd.Series(np.arange(1, 31, dtype=float))
    sites = pd.Series(['a'] * 10 + ['b'] * 10 + ['c'] * 10)
    self.assertEqual(Q.correcao_conformal(X, y, sites, 0.9, estimador=Constante(0.0)), 29.0)

  def test_um_predio_so_devolve_none(self):
    X = pd.DataFrame({'x': np.arange(5, dtype=float)})
    y = pd.Series(np.arange(5, dtype=float))
    self.assertIsNone(Q.correcao_conformal(X, y, pd.Series(['a'] * 5), 0.9, estimador=Constante(0.0)))

  def test_usa_o_modelo_quantilico_por_padrao(self):
    conj = conjunto()
    from ml.core.features import matriz
    X = matriz(conj.df, ['router_snr'])
    y = np.log1p(conj.df['latency_ms'].astype(float))
    c = Q.correcao_conformal(X, y, conj.df['_site'], 0.9)
    self.assertIsInstance(c, float)


if __name__ == '__main__':
  unittest.main()

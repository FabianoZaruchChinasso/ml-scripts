import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.studio import features as SF

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {**{a: {'classe': 'alvo'} for a in ALVOS},
                      'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


class Constante(BaseEstimator, RegressorMixin):
  """Prevê sempre `valor` e guarda o índice das linhas de treino."""

  def __init__(self, valor=1000.0):
    self.valor = valor

  def fit(self, X, y):
    self.indices_ = list(X.index)
    return self

  def predict(self, X):
    return np.full(len(X), self.valor)


def frame(n_por_local=10, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({
    'local': np.repeat(LOCAIS, n_por_local),
    'speedtest_down_mbps': 3 * snr + rng.normal(0, 1, n),
    'speedtest_up_mbps': snr + rng.normal(0, 1, n),
    'latency_ms': rng.normal(20, 2, n), 'jitter_ms': rng.normal(3, 1, n),
    'router_snr': snr, 'router_tx_bytes': snr * 1000,
  })


def conjunto(alvo='speedtest_down_mbps', f=None):
  return C.preparar({'a.csv': frame() if f is None else f}, alvo, TABELA, catalogo=())


class Base(unittest.TestCase):
  def setUp(self):
    self._arvores = A.ARVORES
    A.ARVORES = 15

  def tearDown(self):
    A.ARVORES = self._arvores


class TestPrevisoes(Base):
  def test_cada_linha_e_prevista_sem_o_proprio_predio(self):
    conj = conjunto()
    vistos = []
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [],
                                 ao_ajustar=lambda fold, m: vistos.append((fold.test_site, fold.train_sites)))
    self.assertEqual(sorted(prev['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    for teste, treino in vistos:
      self.assertNotIn(teste, treino)
    self.assertEqual(sorted(prev['_linha']), sorted(conj.df['_linha']))

  def test_linha_limitada_sai_do_treino_e_fica_no_teste(self):
    conj = conjunto()
    limitadas = conj.df.index[conj.df['_site'] == 'residencia'][:3]
    conj.df.loc[limitadas, '_limitado_wan'] = True
    treinos = []
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(),
                                 ao_ajustar=lambda fold, m: treinos.append(set(m.indices_)))
    for treino in treinos:
      self.assertFalse(set(limitadas) & treino)
    self.assertTrue(set(limitadas) <= set(prev.index))

  def test_previsao_cortada_no_teto_do_predio(self):
    conj = conjunto()
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(1000.0))
    por_site = prev.groupby('_site')['yhat'].unique().map(list).to_dict()
    self.assertEqual(por_site['residencia'], [154.0])
    self.assertEqual(por_site['hotmilk'], [1000.0])

  def test_latencia_nao_tem_teto(self):
    conj = conjunto('latency_ms')
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(1000.0))
    self.assertEqual(prev['yhat'].unique().tolist(), [1000.0])

  def test_vazamento_levanta(self):
    conj = conjunto()
    with self.assertRaises(AssertionError):
      A.prever_fora_do_fold(conj.df, ['router_tx_bytes'], conj.alvo, ['router_tx_bytes'])

  def test_formato_antigo_do_logo(self):
    conj = conjunto()
    por_local, reais, previstos, mae = A._logo(conj.df, ['router_snr'], conj.alvo, [])
    self.assertEqual(sorted(por_local), ['coworking', 'hotmilk', 'residencia'])
    self.assertEqual(len(reais), len(conj.df))
    self.assertEqual(sorted(mae), sorted(por_local))

  def test_studio_reexporta_a_regua(self):
    self.assertIs(SF.avaliar, A.avaliar)
    self.assertIs(SF._logo, A._logo)


class TestMaeLog(Base):
  def test_previsao_negativa_conta_como_zero(self):
    self.assertAlmostEqual(A.mae_log([0.0, 9.0], [-5.0, 9.0]), 0.0)

  def test_valor_conhecido(self):
    self.assertAlmostEqual(A.mae_log([np.e - 1], [0.0]), 1.0)

  def test_resumo_traz_mae_log_e_versao(self):
    conj = conjunto()
    r = A.avaliar(conj, ['router_snr'], [])
    self.assertEqual(r['versao_regua'], A.VERSAO_REGUA)
    self.assertGreater(r['mae_log'], 0)
    self.assertEqual(sorted(r['mae_log_por_local']), ['coworking', 'hotmilk', 'residencia'])

  def test_resumo_vazio_nao_quebra(self):
    r = A.resumir(pd.DataFrame(columns=['_linha', 'y', 'yhat', '_site', '_pos']), 0)
    self.assertIsNone(r['mae_log'])


class TestBootstrap(Base):
  def setUp(self):
    super().setUp()
    self.site = pd.Series(['a'] * 4 + ['b'] * 6)
    self.pos = pd.Series(['a1', 'a1', 'a2', 'a2', 'b1', 'b1', 'b1', 'b2', 'b3', 'b3'])

  def test_deterministico(self):
    r1 = A.reamostras(self.pos, self.site, n=20)
    r2 = A.reamostras(self.pos, self.site, n=20)
    self.assertTrue(all(np.array_equal(x, y) for x, y in zip(r1, r2)))

  def test_todo_predio_em_toda_reamostragem(self):
    for idx in A.reamostras(self.pos, self.site, n=50):
      self.assertEqual(set(self.site.iloc[idx]), {'a', 'b'})

  def test_posicao_entra_inteira(self):
    tamanho = self.pos.value_counts()
    for idx in A.reamostras(self.pos, self.site, n=50):
      contagem = self.pos.iloc[idx].value_counts()
      for p, c in contagem.items():
        self.assertEqual(c % tamanho[p], 0)

  def test_resumo_traz_intervalos(self):
    r = A.avaliar(conjunto(), ['router_snr'], [])
    for chave in ('pooled', 'mae', 'mae_log'):
      lo, hi = r['intervalos'][chave]
      self.assertLessEqual(lo, hi)


def previsoes(linhas, y, yhat, sites=None, pos=None):
  n = len(linhas)
  return pd.DataFrame({'_linha': linhas, 'y': y, 'yhat': yhat,
                       '_site': sites or ['s1', 's1', 's2', 's2', 's2'][:n],
                       '_pos': pos or ['p1', 'p2', 'p3', 'p4', 'p5'][:n]})


APPS = {'Video': {'dn': 10, 'up': 5, 'lat': 150, 'jit': 30},
        'Tudo': {'dn': 0, 'up': 0, 'lat': 500, 'jit': 100}}


class TestAtende(Base):
  def test_acuracia_balanceada_e_aplicacao_de_classe_unica_fora(self):
    dn = previsoes(['a:0', 'a:1', 'a:2', 'a:3', 'a:9'], [30, 1, 30, 1, 30], [30, 1, 1, 30, 30])
    up = previsoes(['a:0', 'a:1', 'a:2', 'a:3'], [10, 10, 10, 10], [10, 10, 10, 10])
    r = A.atende(dn, up, APPS)
    # Video: real [T, F, T, F], previsto [T, F, F, T] -> (1/2 + 1/2) / 2 = 0,5
    self.assertEqual(r['por_aplicacao'], {'Video': 0.5})
    self.assertEqual(r['media'], 0.5)
    self.assertEqual(r['n'], 4)
    self.assertTrue(any('Tudo' in a for a in r['avisos']))

  def test_previsao_perfeita_da_1(self):
    dn = previsoes(['a:0', 'a:1', 'a:2', 'a:3'], [30, 1, 30, 1], [30, 1, 30, 1])
    up = previsoes(['a:0', 'a:1', 'a:2', 'a:3'], [10, 10, 10, 10], [10, 10, 10, 10])
    self.assertEqual(A.atende(dn, up, APPS)['media'], 1.0)


def delta(valor, lo, hi, mae_base=None):
  d = {'valor': valor, 'intervalo': [lo, hi]}
  if mae_base is not None:
    d['mae_base'] = mae_base
  return d


class TestPromocao(Base):
  def setUp(self):
    super().setUp()
    linhas = [f'a:{i}' for i in range(5)]
    y = [30.0, 1.0, 30.0, 1.0, 20.0]
    self.base = previsoes(linhas, y, [v + 10 for v in y])
    self.nova = previsoes(linhas, y, y)

  def test_delta_mae_da_nova_perfeita(self):
    d = A.delta_mae(self.nova, self.base)
    self.assertEqual(d['valor'], -10.0)
    self.assertLess(d['intervalo'][1], 0)
    self.assertEqual(d['mae_base'], 10.0)

  def test_delta_mae_sem_linhas_em_comum_levanta(self):
    outra = previsoes(['b:0'], [1.0], [1.0])
    with self.assertRaises(ValueError):
      A.delta_mae(self.nova, outra)

  def test_delta_atende(self):
    up = previsoes([f'a:{i}' for i in range(5)], [10.0] * 5, [10.0] * 5)
    ruim = previsoes([f'a:{i}' for i in range(5)], [30.0, 1.0, 30.0, 1.0, 20.0], [1.0] * 5)
    d = A.delta_atende(self.nova, up, ruim, up, APPS)
    self.assertEqual(d['valor'], 0.5)

  def test_delta_atende_sem_aplicacao_com_duas_classes_e_none(self):
    tudo = {'Tudo': APPS['Tudo']}
    self.assertIsNone(A.delta_atende(self.nova, self.nova, self.base, self.base, tudo))

  def test_mae_melhor_sem_piorar_atende_e_melhor(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), delta(0.0, -0.01, 0.01))
    self.assertEqual(v['resultado'], 'melhor')

  def test_atende_melhor_sem_piorar_mae_e_melhor(self):
    v = A.veredito_promocao(delta(0.5, -1.0, 2.0, 40.0), delta(0.05, 0.01, 0.09))
    self.assertEqual(v['resultado'], 'melhor')

  def test_atende_pior_e_pior_mesmo_com_mae_melhor(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), delta(-0.05, -0.09, -0.01))
    self.assertEqual(v['resultado'], 'pior')

  def test_intervalos_com_zero_e_empate(self):
    v = A.veredito_promocao(delta(-1.0, -3.0, 1.0, 40.0), delta(0.01, -0.02, 0.03))
    self.assertEqual(v['resultado'], 'empate')

  def test_latencia_decide_so_pelo_mae(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), None)
    self.assertEqual(v['resultado'], 'melhor')


class TestDenominador(Base):
  def conj_com_den(self, valores, alvo='speedtest_down_mbps'):
    f = frame()
    f['router_tx_rate_mbps'] = valores(f)
    return conjunto(alvo, f)

  def test_previsao_e_constante_vezes_denominador(self):
    conj = self.conj_com_den(lambda f: np.where(f['local'].str.startswith('hotmilk'), 600.0, 100.0))
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador='router_tx_rate_mbps')
    por_site = prev.groupby('_site')['yhat'].unique().map(list).to_dict()
    self.assertEqual(por_site['hotmilk'], [300.0])
    self.assertEqual(por_site['coworking'], [50.0])
    self.assertFalse(prev['den_imputado'].any())

  def test_treina_na_eficiencia(self):
    conj = self.conj_com_den(lambda f: np.full(len(f), 10.0))
    alvos = []

    class Espiao(Constante):
      def fit(self, X, y):
        alvos.append(np.asarray(y, dtype=float))
        return super().fit(X, y)

    A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Espiao(0.0),
                          denominador='router_tx_rate_mbps')
    reais = conj.df['speedtest_down_mbps'].to_numpy(dtype=float) / 10.0
    self.assertTrue(all(np.all(np.isin(np.round(a, 6), np.round(reais, 6))) for a in alvos))

  def test_teto_depois_da_multiplicacao(self):
    conj = self.conj_com_den(lambda f: np.full(len(f), 1000.0))
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador='router_tx_rate_mbps')
    por_site = prev.groupby('_site')['yhat'].unique().map(list).to_dict()
    self.assertEqual(por_site['residencia'], [154.0])
    self.assertEqual(por_site['hotmilk'], [500.0])

  def test_den_vazio_usa_a_mediana_do_treino_do_fold(self):
    def valores(f):
      v = np.where(f['local'].str.startswith('hotmilk'), 1000.0, 100.0)
      v[(f['local'] == 'hotmilk-copa').to_numpy()] = np.nan
      return v
    conj = self.conj_com_den(valores)
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(0.5),
                                 denominador='router_tx_rate_mbps')
    copa, aquario = prev[prev['_pos'] == 'hotmilk-copa'], prev[prev['_pos'] == 'hotmilk-aquario']
    # O treino do fold do hotmilk é residência + coworking, todos com 100: a mediana é 100, não 1000.
    self.assertEqual(copa['yhat'].unique().tolist(), [50.0])
    self.assertTrue(copa['den_imputado'].all())
    self.assertEqual(aquario['yhat'].unique().tolist(), [500.0])
    self.assertFalse(aquario['den_imputado'].any())
    self.assertEqual(A.avaliar(conj, ['router_snr'], [], denominador='router_tx_rate_mbps')['den_imputados'],
                     len(copa))

  def test_sem_denominador_nada_muda(self):
    conj = conjunto()
    a = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(7.0))
    b = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(7.0), denominador=None)
    np.testing.assert_allclose(a['yhat'], b['yhat'])
    self.assertFalse(a['den_imputado'].any())

  def test_denominador_inexistente_levanta(self):
    conj = conjunto()
    with self.assertRaisesRegex(ValueError, 'nao_existe'):
      A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], denominador='nao_existe')

  def test_resumir_sem_a_coluna(self):
    r = A.resumir(pd.DataFrame({'_linha': ['a', 'b'], 'y': [1.0, 2.0], 'yhat': [1.0, 2.0],
                                '_site': ['s', 's'], '_pos': ['p', 'q']}), 1)
    self.assertEqual(r['den_imputados'], 0)


if __name__ == '__main__':
  unittest.main()

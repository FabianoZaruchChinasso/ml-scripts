import os
import sys
import types
import unittest
import unittest.mock

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from xgboost import XGBClassifier

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import qoe as Q

LIM = {'App': {'dn': 10, 'up': 5, 'lat': 50, 'jit': 10}}


def linhas(**colunas):
  base = {'_linha': ['a:0', 'a:1', 'a:2'], '_site': ['s1', 's1', 's2'], '_pos': ['p1', 'p1', 'p2'],
          'speedtest_down_mbps': [20.0, 20.0, 20.0], 'speedtest_up_mbps': [8.0, 8.0, 8.0],
          'latency_ms': [10.0, 10.0, 10.0], 'jitter_ms': [2.0, 2.0, 2.0]}
  base.update(colunas)
  return pd.DataFrame(base)


def conj(df):
  return types.SimpleNamespace(df=df)


class TestConjunto(unittest.TestCase):
  def test_so_linhas_presentes_nos_quatro_alvos(self):
    dn = linhas()
    up = dn.drop(index=1)
    conjs = {'speedtest_down_mbps': conj(dn), 'speedtest_up_mbps': conj(up),
             'latency_ms': conj(dn), 'jitter_ms': conj(dn)}
    df = Q.conjunto_qoe(conjs)
    self.assertEqual(df['_linha'].tolist(), ['a:0', 'a:2'])
    self.assertEqual(list(df.index), [0, 1])

  def test_cada_alvo_vem_do_seu_conjunto(self):
    dn = linhas()
    lat = linhas(latency_ms=[99.0, 99.0, 99.0])
    conjs = {'speedtest_down_mbps': conj(dn), 'speedtest_up_mbps': conj(dn),
             'latency_ms': conj(lat), 'jitter_ms': conj(dn)}
    self.assertEqual(Q.conjunto_qoe(conjs)['latency_ms'].tolist(), [99.0, 99.0, 99.0])

  def test_alvo_nan_levanta(self):
    jit = linhas(jitter_ms=[2.0, np.nan, 2.0])
    conjs = {'speedtest_down_mbps': conj(linhas()), 'speedtest_up_mbps': conj(linhas()),
             'latency_ms': conj(linhas()), 'jitter_ms': conj(jit)}
    with self.assertRaisesRegex(ValueError, 'jitter_ms'):
      Q.conjunto_qoe(conjs)

  def test_linha_duplicada_levanta(self):
    up = linhas(_linha=['a:0', 'a:0', 'a:2'])
    conjs = {'speedtest_down_mbps': conj(linhas()), 'speedtest_up_mbps': conj(up),
             'latency_ms': conj(linhas()), 'jitter_ms': conj(linhas())}
    with self.assertRaisesRegex(ValueError, 'duplicada'):
      Q.conjunto_qoe(conjs)

  def test_falta_alvo_levanta(self):
    with self.assertRaisesRegex(ValueError, 'jitter_ms'):
      Q.conjunto_qoe({'speedtest_down_mbps': conj(linhas()), 'speedtest_up_mbps': conj(linhas()),
                      'latency_ms': conj(linhas())})


class TestRotulos(unittest.TestCase):
  def test_cada_criterio_derruba_sozinho(self):
    df = pd.DataFrame({'speedtest_down_mbps': [20, 9, 20, 20, 20], 'speedtest_up_mbps': [8, 8, 4, 8, 8],
                       'latency_ms': [10, 10, 10, 51, 10], 'jitter_ms': [2, 2, 2, 2, 11]})
    self.assertEqual(Q.rotulos(df, LIM)['App'].tolist(), [True, False, False, False, False])

  def test_limiar_incluso(self):
    df = pd.DataFrame({'speedtest_down_mbps': [10], 'speedtest_up_mbps': [5], 'latency_ms': [50], 'jitter_ms': [10]})
    self.assertEqual(Q.rotulos(df, LIM)['App'].tolist(), [True])


class TestRestricoes(unittest.TestCase):
  def test_taxas_sobem_contencao_desce_resto_livre(self):
    cols = ['router_tx_rate_mbps', 'router_rx_rate_mbps', 'n_clients', 'concorrentes_mesmo_radio',
            'router_signal_dbm', 'router_snr', 'router_noise', 'radio_5ghz', 'coluna_nova']
    self.assertEqual(Q.restricoes(cols), (1, 1, -1, -1, 0, 0, 0, 0, 0))


class Lembra(BaseEstimator, ClassifierMixin):
  """Prevê sempre 1 e guarda o índice de cada treino."""
  vistos = []

  def fit(self, X, y):
    self.classes_ = np.unique(y)
    Lembra.vistos.append(list(X.index))
    return self

  def predict(self, X):
    return np.ones(len(X), dtype=int)


def sintetico(n=40, seed=0):
  """Três prédios; atende quando a taxa PHY passa de 300."""
  rng = np.random.default_rng(seed)
  df = pd.DataFrame({'_site': np.repeat(['a', 'b', 'c'], n), '_pos': np.repeat(['a1', 'b1', 'c1'], n),
                     'router_tx_rate_mbps': rng.uniform(50, 600, 3 * n),
                     'router_signal_dbm': rng.uniform(-80, -40, 3 * n),
                     'radio': np.tile(['5ghz', '2.4ghz'], 3 * n // 2)})
  return df, {'App': (df['router_tx_rate_mbps'] > 300).to_numpy()}


class TestPrever(unittest.TestCase):
  def setUp(self):
    self.df, self.rot = sintetico()
    Lembra.vistos = []

  def test_treino_nunca_tem_o_predio_de_teste(self):
    prev, _ = Q.prever_fora_do_fold(self.df, ['router_tx_rate_mbps'], self.rot, lambda cols: Lembra())
    self.assertEqual(len(prev['App']), len(self.df))
    predios = [tuple(sorted(set(self.df.loc[idx, '_site']))) for idx in Lembra.vistos]
    self.assertEqual(sorted(predios), [('a', 'b'), ('a', 'c'), ('b', 'c')])

  def test_treino_de_uma_classe_preve_essa_classe_e_avisa(self):
    rot = {'App': (self.df['_site'] == 'a').to_numpy()}
    prev, uma = Q.prever_fora_do_fold(self.df, ['router_tx_rate_mbps'], rot, lambda cols: Lembra())
    # Sem 'a' no treino, só sobra "não atende": o prédio 'a' recebe False.
    self.assertFalse(prev['App'][(self.df['_site'] == 'a').to_numpy()].any())
    self.assertIn(('App', 'a'), uma)

  def test_indice_repetido_levanta(self):
    df = self.df.copy()
    df.index = [0] * len(df)
    with self.assertRaisesRegex(ValueError, 'único'):
      Q.prever_fora_do_fold(df, ['router_tx_rate_mbps'], self.rot, lambda cols: Lembra())

  def test_vazamento_levanta(self):
    with self.assertRaises(AssertionError):
      Q.prever_fora_do_fold(self.df, ['router_tx_rate_mbps'], self.rot, lambda cols: Lembra(),
                            vazadas=['router_tx_rate_mbps'])

  def test_xgboost_aprende_a_fronteira(self):
    prev, _ = Q.prever_fora_do_fold(self.df, ['router_tx_rate_mbps', 'radio'], self.rot, Q.modelo_qoe)
    self.assertGreater(np.mean(prev['App'] == self.rot['App']), 0.9)

  def test_restricoes_alinham_com_as_colunas_da_matriz(self):
    X = Q.matriz(self.df, ['router_tx_rate_mbps', 'radio'])
    colunas = list(X.columns)
    r = dict(zip(colunas, Q.restricoes(colunas)))
    self.assertEqual(r['router_tx_rate_mbps'], 1)
    outras = [c for c in colunas if c != 'router_tx_rate_mbps']
    self.assertTrue(outras)
    self.assertTrue(all(r[c] == 0 for c in outras))

  def test_monotonia_na_taxa_e_respeitada(self):
    # Alvo ruidoso e não monotônico na taxa: sem a restrição o modelo oscila; com ela, não desce.
    rng = np.random.default_rng(1)
    n = 600
    x = rng.uniform(50, 600, n)
    df = pd.DataFrame({'router_tx_rate_mbps': x, 'router_signal_dbm': rng.uniform(-80, -40, n)})
    y = (np.sin(8 * x / 600) + rng.normal(0, 0.3, n) > 0).astype(int)
    X = Q.matriz(df, ['router_tx_rate_mbps', 'router_signal_dbm'])
    colunas = list(X.columns)
    grade = pd.DataFrame({'router_tx_rate_mbps': np.linspace(50, 600, 200), 'router_signal_dbm': -60.0})
    com = Q.modelo_qoe(colunas).fit(X, y)
    sem = Q.Balanceado(XGBClassifier(**dict(Q.modelo_qoe(colunas).estimador.get_params(),
                                            monotone_constraints=(0,) * len(colunas)))).fit(X, y)
    self.assertTrue(np.all(np.diff(com.predict_proba(grade)[:, 1]) >= -1e-9))
    self.assertFalse(np.all(np.diff(sem.predict_proba(grade)[:, 1]) >= -1e-9))

  def test_referencia_roda_com_categorica(self):
    prev, _ = Q.prever_fora_do_fold(self.df, ['radio', 'router_tx_rate_mbps'], self.rot, Q.modelo_referencia)
    self.assertEqual(prev['App'].dtype, bool)
    self.assertGreater(np.mean(prev['App'] == self.rot['App']), 0.9)


def caso():
  """Prédio 'grande' (8 linhas) e 'pequeno' (2 linhas) com as duas classes; 'bom' só atende."""
  df = pd.DataFrame({'_site': ['grande'] * 8 + ['pequeno'] * 2 + ['bom'] * 4,
                     '_pos': ['g1', 'g1', 'g1', 'g1', 'g2', 'g2', 'g2', 'g2', 'p1', 'p1', 'b1', 'b1', 'b2', 'b2']})
  real = np.array([1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1], dtype=bool)
  # grande acerta tudo (acurácia 1); pequeno prevê o contrário nas duas linhas (acurácia 0); bom: 1 alarme em 4.
  prev = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0], dtype=bool)
  return df, {'App': real}, {'App': prev}


class TestResumir(unittest.TestCase):
  def test_nota_e_media_por_predio_e_nao_pooled(self):
    df, rot, prev = caso()
    r = Q.resumir(df, rot, prev, amostras=[np.arange(len(df))])
    # grande 1,0 e pequeno 0,0 pesam igual: 0,5. Pooled (10 linhas com as duas classes + bom) seria outra conta.
    self.assertEqual(r['nota'], 0.5)
    self.assertEqual(r['predios_na_nota'], ['grande', 'pequeno'])
    self.assertEqual(r['predios_fora_da_nota'], ['bom'])

  def test_predio_de_uma_classe_vira_alarme_falso(self):
    df, rot, prev = caso()
    r = Q.resumir(df, rot, prev, amostras=[np.arange(len(df))])
    self.assertEqual(r['por_predio']['bom']['App'], {'classes': 1, 'atende': True, 'erro': 0.25})
    self.assertEqual(r['por_predio']['grande']['App'], {'classes': 2, 'acuracia': 1.0})

  def test_predio_onde_nada_atende_vira_perda(self):
    df = pd.DataFrame({'_site': ['x', 'x', 'y', 'y'], '_pos': ['x1', 'x2', 'y1', 'y2']})
    rot = {'App': np.array([1, 0, 0, 0], dtype=bool)}
    prev = {'App': np.array([1, 0, 1, 0], dtype=bool)}
    r = Q.resumir(df, rot, prev, amostras=[np.arange(4)])
    self.assertEqual(r['por_predio']['y']['App'], {'classes': 1, 'atende': False, 'erro': 0.5})

  def test_predio_pesa_so_pela_aplicacao_de_duas_classes(self):
    df = pd.DataFrame({'_site': ['x'] * 4 + ['y'] * 4, '_pos': ['x1', 'x1', 'x2', 'x2', 'y1', 'y1', 'y2', 'y2']})
    rot = {'A': np.array([1, 1, 0, 0, 1, 0, 1, 0], dtype=bool), 'B': np.array([1, 1, 1, 1, 1, 0, 1, 0], dtype=bool)}
    prev = {'A': rot['A'].copy(), 'B': np.array([0, 0, 0, 0, 1, 0, 1, 0], dtype=bool)}
    r = Q.resumir(df, rot, prev, amostras=[np.arange(8)])
    # No 'x', B tem uma classe só (erro 1,0) e fica fora da nota; só A (acurácia 1) conta.
    self.assertEqual(r['por_predio']['x']['B'], {'classes': 1, 'atende': True, 'erro': 1.0})
    self.assertEqual(r['por_predio']['x']['A'], {'classes': 2, 'acuracia': 1.0})
    self.assertEqual(r['nota'], 1.0)

  def test_intervalo_e_contagens(self):
    df, rot, prev = caso()
    r = Q.resumir(df, rot, prev)
    self.assertEqual(len(r['intervalo']), 2)
    self.assertLessEqual(r['intervalo'][0], r['intervalo'][1])
    self.assertEqual((r['n'], r['n_predios'], r['n_posicoes']), (14, 3, 5))


def tudo(df):
  return [np.arange(len(df))]


class TestVeredito(unittest.TestCase):
  def setUp(self):
    self.df, self.rot, self.prev = caso()

  def com(self, **trocas):
    p = self.prev['App'].copy()
    for i, v in trocas.items():
      p[int(i[1:])] = v
    return {'App': p}

  def test_melhor_quando_o_intervalo_fica_acima_de_zero(self):
    # Nova perfeita (nota 1, sem alarme no 'bom') contra a base do caso (nota 0,5).
    v = Q.veredito(self.df, self.rot, self.rot, self.prev, amostras=tudo(self.df))
    self.assertEqual((v['resultado'], v['delta'], v['alarmes']), ('melhor', 0.5, []))

  def test_pior_quando_o_intervalo_fica_abaixo_de_zero(self):
    v = Q.veredito(self.df, self.rot, {'App': ~self.rot['App']}, self.rot, amostras=tudo(self.df))
    self.assertEqual(v['resultado'], 'pior')
    self.assertIn('caiu', v['motivo'])
    # O alarme também dispara aqui (o 'bom' vira tudo "não atende"), mas o motivo é o do intervalo.
    self.assertTrue(v['alarmes'])

  def test_trava_de_alarme_falso(self):
    # Mesma nota nos prédios de duas classes; no 'bom', a nova erra 2 de 4 (50%) e a base 0.
    nova = self.com(i12=False, i13=False)
    base = self.com(i13=True)
    v = Q.veredito(self.df, self.rot, nova, base, amostras=tudo(self.df))
    self.assertEqual(v['resultado'], 'pior')
    self.assertEqual(v['alarmes'], [{'predio': 'bom', 'aplicacao': 'App', 'nova': 0.5, 'base': 0.0}])

  def test_alarme_pequeno_nao_trava(self):
    v = Q.veredito(self.df, self.rot, self.prev, self.prev, amostras=tudo(self.df))
    self.assertEqual(v['resultado'], 'empate')
    self.assertEqual(v['alarmes'], [])

  def test_intervalo_que_cruza_zero_e_empate(self):
    # Nova melhora o 'pequeno' (+0,5) e piora o 'grande' (-0,25). Reamostra com os dois: +0,125; sem o 'pequeno': -0,25.
    nova = self.com(i8=True, i0=False, i1=False)
    sem_pequeno = np.array([i for i in range(len(self.df)) if i not in (8, 9)])
    v = Q.veredito(self.df, self.rot, nova, self.prev, amostras=[np.arange(len(self.df)), sem_pequeno])
    self.assertLess(v['intervalo'][0], 0)
    self.assertGreater(v['intervalo'][1], 0)
    self.assertEqual((v['resultado'], v['alarmes']), ('empate', []))

  def test_predios_contra(self):
    nova = self.com(i0=False, i1=False)
    v = Q.veredito(self.df, self.rot, nova, self.prev, amostras=tudo(self.df))
    self.assertEqual(v['predios_contra'], ['grande'])


class TestAvaliar(unittest.TestCase):
  def conjs(self):
    df, _ = sintetico(n=30)
    df['_linha'] = [f'a:{i}' for i in range(len(df))]
    df['speedtest_down_mbps'] = df['router_tx_rate_mbps'] / 10
    df['speedtest_up_mbps'] = 10.0
    df['latency_ms'] = 10.0
    df['jitter_ms'] = 2.0
    return {a: conj(df) for a in Q.ALVOS}

  def avaliar(self, *args, **kwargs):
    lim = {'App': {'dn': 30, 'up': 1, 'lat': 50, 'jit': 10}}
    with unittest.mock.patch.object(Q.core_aplicacoes, 'carregar_perfil', return_value=lim), \
         unittest.mock.patch.object(Q.core_aplicacoes, 'fontes', return_value={}):
      return Q.avaliar(self.conjs(), *args, **kwargs)

  def test_avaliar_de_ponta_a_ponta_no_sintetico(self):
    r = self.avaliar(['router_tx_rate_mbps', 'radio', 'nao_existe'], [], 'norma',
                     features_base=['router_signal_dbm'])
    self.assertEqual(r['perfil'], 'norma')
    self.assertEqual(r['versao_qoe'], Q.VERSAO_QOE)
    self.assertEqual(r['features'], ['router_tx_rate_mbps', 'radio'])
    self.assertEqual(r['ausentes'], ['nao_existe'])
    self.assertEqual(r['descartadas'], [])
    self.assertEqual(r['restricoes'], {'router_tx_rate_mbps': 1})
    for chave in ('modelo', 'referencia', 'piso'):
      self.assertIn('nota', r[chave])
    self.assertIsInstance(r['supera_piso'], bool)
    self.assertEqual(set(r['folds_uma_classe']), {'modelo', 'referencia', 'piso'})
    self.assertIn(r['promocao_qoe']['resultado'], ('melhor', 'empate', 'pior'))
    self.assertIn('nota_base', r['promocao_qoe'])

  def test_descartadas_sem_base_e_nota_base(self):
    r = self.avaliar(['router_tx_rate_mbps', 'router_signal_dbm', 'radio'], ['router_signal_dbm'], 'norma')
    self.assertEqual(r['descartadas'], ['router_signal_dbm'])
    self.assertEqual(r['features'], ['router_tx_rate_mbps', 'radio'])
    self.assertIsNone(r['promocao_qoe'])
    com_base = self.avaliar(['router_tx_rate_mbps', 'radio'], [], 'norma', features_base=['router_tx_rate_mbps'])
    sozinha = self.avaliar(['router_tx_rate_mbps'], [], 'norma')
    self.assertEqual(com_base['promocao_qoe']['nota_base'], sozinha['modelo']['nota'])

  def test_base_inutilizavel_explica(self):
    r = self.avaliar(['router_tx_rate_mbps'], [], 'norma', features_base=['nao_existe'])
    self.assertIsNone(r['promocao_qoe'])
    self.assertEqual(r['promocao_qoe_motivo'], 'nenhuma feature da base utilizável')

  def test_sem_feature_utilizavel_levanta(self):
    df = linhas()
    conjs = {a: conj(df) for a in Q.ALVOS}
    with unittest.mock.patch.object(Q.core_aplicacoes, 'carregar_perfil', return_value=LIM), \
         unittest.mock.patch.object(Q.core_aplicacoes, 'fontes', return_value={}):
      with self.assertRaisesRegex(ValueError, 'nenhuma feature'):
        Q.avaliar(conjs, ['router_tx_bytes'], ['router_tx_bytes'], 'norma')

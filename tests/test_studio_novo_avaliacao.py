import math
import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from studio import avaliacao  # noqa: E402

ALVO = 'speedtest_down_mbps'
ZERO = {'up': 0, 'lat': 0, 'jit': 0}


class TestMetricas(unittest.TestCase):
  # erros: +2, -2, +3, 0
  y = [10.0, 20.0, 30.0, 40.0]
  pred = [12.0, 18.0, 33.0, 40.0]
  grupos = ['a', 'a', 'b', 'b']
  apps = {'X': {'dn': 25, **ZERO}, 'Y': {'dn': 19, **ZERO}, 'Tudo Passa': {'dn': 0, **ZERO}}

  def test_regressao_global_e_por_predio(self):
    m = avaliacao.metricas(self.y, self.pred, self.grupos, ALVO, self.apps)
    self.assertAlmostEqual(m['mae'], 1.75)
    self.assertAlmostEqual(m['rmse'], math.sqrt(17 / 4))
    self.assertAlmostEqual(m['r2'], 1 - 17 / 500)
    self.assertAlmostEqual(m['mae__a'], 2.0)
    self.assertAlmostEqual(m['mae__b'], 1.5)
    self.assertEqual((m['linhas'], m['predios']), (4, 2))

  def test_atende_acuracia_balanceada(self):
    m = avaliacao.metricas(self.y, self.pred, self.grupos, ALVO, self.apps)
    # limiar 25: real [F,F,T,T], previsto [F,F,T,T]
    self.assertAlmostEqual(m['atende_bacc__x'], 1.0)
    # limiar 19: real [F,T,T,T], previsto [F,F,T,T] -> (1 + 2/3) / 2
    self.assertAlmostEqual(m['atende_bacc__y'], (1 + 2 / 3) / 2)
    # limiar 0: todas atendem, acurácia balanceada indefinida
    self.assertNotIn('atende_bacc__tudo_passa', m)

  def test_latencia_atende_com_menor_ou_igual(self):
    self.assertEqual(list(avaliacao.atende(np.array([50.0, 100.0, 150.0]), 'latency_ms', 100)), [True, True, False])
    self.assertEqual(list(avaliacao.atende(np.array([5.0, 25.0]), ALVO, 25)), [False, True])

  def test_slug_de_aplicacao(self):
    self.assertEqual(avaliacao.slug('Chamada de vídeo'), 'chamada_de_video')
    self.assertEqual(avaliacao.slug('Streaming 4K'), 'streaming_4k')


class TestLogo(unittest.TestCase):
  def test_cada_predio_e_previsto_sem_ele_no_treino(self):
    X = pd.DataFrame({'f': [1.0, 2.0, 3.0, 4.0]})
    y = pd.Series([10.0, 20.0, 30.0, 40.0])
    grupos = pd.Series(['a', 'a', 'b', 'b'])
    pred = avaliacao.fora_do_fold(DummyRegressor(), X, y, grupos)
    self.assertEqual(list(pred), [35.0, 35.0, 15.0, 15.0])


class TestRegras(unittest.TestCase):
  def setUp(self):
    self.df = pd.DataFrame({
      '_predio': ['alfa', 'alfa', 'alfa', 'alfa', 'beta', 'alfa'],
      ALVO: [0.0, 50.0, 95.0, 90.0, 95.0, np.nan],
      'router_expected_throughput_mbps': [200.0, 200.0, 200.0, 80.0, 200.0, 200.0],
    })
    self.tetos = {'alfa': 100.0}

  def test_padrao_tira_vazio_e_zero(self):
    df, removidas = avaliacao.aplicar_regras(self.df, ALVO, avaliacao.REGRAS_PADRAO, self.tetos)
    self.assertEqual(list(df[ALVO]), [50.0, 95.0, 90.0, 95.0])
    self.assertEqual(removidas, {'alvo_vazio': 1, 'descartar_alvo_zero': 1})

  def test_teto_wan_tira_so_quem_esta_no_teto_e_podia_mais(self):
    regras = {'descartar_alvo_zero': True, 'teto_wan': True}
    df, removidas = avaliacao.aplicar_regras(self.df, ALVO, regras, self.tetos)
    # 95 >= 0,85 x 100 e esperado 200 > 100: sai. 90 com esperado 80: fica. beta não tem teto: fica.
    self.assertEqual(list(df[ALVO]), [50.0, 90.0, 95.0])
    self.assertEqual(removidas['teto_wan'], 1)

  def test_sem_regras_so_tira_vazio(self):
    df, removidas = avaliacao.aplicar_regras(self.df, ALVO, {'descartar_alvo_zero': False, 'teto_wan': False}, {})
    self.assertEqual(len(df), 5)
    self.assertEqual(removidas, {'alvo_vazio': 1})


if __name__ == '__main__':
  unittest.main()

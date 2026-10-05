import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.studio import features as SF
from ml.studio import selecao as S

TABELA = {
  'prefixos': {'router_': {'classe': 'tr069'}, 'stats_80211_': {'classe': 'sniffer'}},
  'colunas': {'speedtest_down_mbps': {'classe': 'alvo'}, 'speedtest_up_mbps': {'classe': 'alvo'},
              'latency_ms': {'classe': 'alvo'}, 'jitter_ms': {'classe': 'alvo'},
              'local': {'classe': 'identificador'},
              'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}},
}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


def frame(n_por_local=30, seed=1):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({
    'local': np.repeat(LOCAIS, n_por_local),
    'speedtest_down_mbps': 3 * snr + rng.normal(0, 1, n),
    'speedtest_up_mbps': snr, 'latency_ms': rng.normal(20, 2, n), 'jitter_ms': rng.normal(3, 1, n),
    'router_snr': snr,
    'router_ruido_a': rng.normal(0, 1, n),
    'router_ruido_b': rng.normal(0, 1, n),
    'router_tx_duration_us': rng.normal(0, 1, n),
    'router_tx_bytes': snr * 1000,
    'stats_80211_x': snr + rng.normal(0, 0.1, n),
  })


class Base(unittest.TestCase):
  def setUp(self):
    self._antes = (S.ARVORES_BUSCA, A.ARVORES)
    S.ARVORES_BUSCA, A.ARVORES = 15, 15
    self.conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.inv = SF.inventario(self.conj, ['router_snr'])

  def tearDown(self):
    S.ARVORES_BUSCA, A.ARVORES = self._antes


class TestSelecao(Base):
  def test_candidatas_sao_so_tr069_sem_vazamento(self):
    c = S.candidatas_tr069(self.inv)
    self.assertIn('router_snr', c)
    self.assertNotIn('router_tx_bytes', c)
    self.assertNotIn('stats_80211_x', c)

  def test_gulosa_escolhe_primeiro_a_feature_informativa_e_para(self):
    feats, passos = S.gulosa(self.conj.df, ['router_ruido_a', 'router_snr', 'router_ruido_b'],
                             'speedtest_down_mbps')
    self.assertEqual(feats[0], 'router_snr')
    self.assertEqual(passos[0]['ganho'], None)
    self.assertLess(len(feats), 3)

  def test_aninhada_nunca_ve_o_local_de_teste(self):
    vistos = []
    original = S.gulosa

    def espiao(df, candidatas, alvo, *a, **k):
      vistos.append(set(df['_site']))
      return original(df, candidatas, alvo, *a, **k)
    S.gulosa = espiao
    try:
      r = S.aninhada(self.conj.df, ['router_snr', 'router_ruido_a'], 'speedtest_down_mbps')
    finally:
      S.gulosa = original
    locais = sorted(self.conj.df['_site'].unique())
    self.assertEqual(sorted(r['escolhas_por_local']), locais)
    for local, visto in zip(locais, vistos):
      self.assertNotIn(local, visto)

  def test_desenhar_traz_as_duas_notas(self):
    r = S.desenhar(self.conj, self.inv)
    self.assertEqual(r['features'][0], 'router_snr')
    for chave in ('pooled', 'mae', 'por_local'):
      self.assertIn(chave, r['nota_selecao'])
      self.assertIn(chave, r['nota_aninhada'])

  def test_sem_volume_tira_os_contadores_brutos(self):
    eventos = []
    r = S.desenhar(self.conj, self.inv, eventos.append, sem_volume=True)
    self.assertNotIn('router_tx_duration_us', r['candidatas'])
    self.assertTrue(set(S.CONTADORES_VOLUME) <= set(r['parametros']['excluidas']))
    self.assertTrue(any('fase' in e for e in eventos))


if __name__ == '__main__':
  unittest.main()

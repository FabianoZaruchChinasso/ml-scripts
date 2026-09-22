import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import features as SF

TABELA = {
  'prefixos': {'router_': {'classe': 'tr069'}, 'stats_80211_': {'classe': 'sniffer'}},
  'colunas': {
    'speedtest_down_mbps': {'classe': 'alvo'},
    'speedtest_up_mbps': {'classe': 'alvo'},
    'latency_ms': {'classe': 'alvo'},
    'jitter_ms': {'classe': 'alvo'},
    'local': {'classe': 'identificador'},
    'client_id': {'classe': 'identificador'},
    'router_tx_bytes': {'classe': 'tr069', 'vazamento': True},
    'AP_channel': {'classe': 'cliente'},
    'radio': {'classe': 'tr069'},
  },
}

LOCAIS = ['sala', 'quarto', 'suite', 'cwpb-1', 'cwpb-2']


def frame(locais=LOCAIS, linhas_por_local=12, seed=0):
  rng = np.random.default_rng(seed)
  n = len(locais) * linhas_por_local
  snr = np.tile([10.0, 20.0, 30.0, 40.0], n // 4 + 1)[:n]
  sinal = rng.normal(-60, 5, n)
  down = 2 * snr + rng.normal(0, 1, n)
  potencia = rng.normal(20, 1, n)
  potencia[::2] = np.nan
  dup = rng.normal(0, 1, n)
  return pd.DataFrame({
    'local': np.repeat(locais, linhas_por_local),
    'client_id': np.arange(n),
    'speedtest_down_mbps': down,
    'speedtest_up_mbps': down / 2,
    'latency_ms': rng.normal(20, 2, n),
    'jitter_ms': rng.normal(3, 1, n),
    'router_snr': snr,
    'router_signal_dbm': sinal,
    'router_power_dbm': potencia,
    'router_nss': rng.integers(1, 3, n).astype(float),
    'router_tx_bytes': down * 1000,
    'AP_channel': snr * 10,
    'radio': np.where(np.arange(n) % 2, '2.4ghz', '5ghz'),
    'stats_80211_a': dup,
    'stats_80211_b': dup,
    'stats_80211_zero': 0.0,
    'mystery_col': rng.normal(0, 1, n),
  })


class Base(unittest.TestCase):
  def setUp(self):
    self._arvores = (SF.ARVORES, SF.ARVORES_PROXY)
    SF.ARVORES, SF.ARVORES_PROXY = 25, 25

  def tearDown(self):
    SF.ARVORES, SF.ARVORES_PROXY = self._arvores


class TestPreparar(Base):
  def test_descarta_linhas_sem_alvo_e_avisa(self):
    f = frame()
    f.loc[0, 'speedtest_down_mbps'] = np.nan
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(len(conj.df), len(f) - 1)
    self.assertTrue(any('1 linhas sem' in a for a in conj.avisos))

  def test_posicoes_e_dataset_de_origem(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(sorted(conj.df['_site'].unique()),
                     ['cwpb-1', 'cwpb-2', 'res-quarto', 'res-sala', 'res-suite'])
    self.assertEqual(set(conj.df['_ds']), {'a.csv'})

  def test_alvo_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      SF.preparar({'a.csv': frame()}, 'router_snr', TABELA)


class TestInventario(Base):
  def setUp(self):
    super().setUp()
    self.inv = SF.inventario(SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA))
    self.por_nome = {c['coluna']: c for c in self.inv['colunas']}

  def test_coluna_sem_regra_vai_para_sem_classificacao(self):
    self.assertEqual([c['coluna'] for c in self.inv['sem_classificacao']], ['mystery_col'])
    self.assertNotIn('mystery_col', self.por_nome)

  def test_constante_e_cobertura(self):
    self.assertTrue(self.por_nome['stats_80211_zero']['constante'])
    self.assertEqual(self.por_nome['router_power_dbm']['cobertura'], 0.5)

  def test_grupos_identicos_ignoram_constantes(self):
    self.assertEqual(self.inv['grupos_identicos'], [['stats_80211_a', 'stats_80211_b']])

  def test_suspeita_so_sem_vazamento(self):
    self.assertTrue(self.por_nome['router_snr']['suspeita'])
    self.assertFalse(self.por_nome['router_tx_bytes']['suspeita'])

  def test_alvo_nao_tem_rho(self):
    self.assertIsNone(self.por_nome['speedtest_up_mbps']['rho'])

  def test_candidatas_excluem_modelo_vazamento_e_baixa_cobertura(self):
    self.assertIn('router_nss', self.inv['candidatas'])
    self.assertNotIn('router_snr', self.inv['candidatas'])
    self.assertNotIn('router_tx_bytes', self.inv['candidatas'])
    self.assertNotIn('router_power_dbm', self.inv['candidatas'])

  def test_categorica_de_baixa_cardinalidade(self):
    self.assertEqual(self.por_nome['radio']['tipo'], 'categorica')


class TestElegiveis(Base):
  def test_filtros(self):
    inv = SF.inventario(SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA))
    ok = SF.elegiveis(inv)
    for fora in ('router_tx_bytes', 'stats_80211_zero', 'router_power_dbm', 'client_id',
                 'speedtest_down_mbps', 'stats_80211_b'):
      self.assertNotIn(fora, ok)
    for dentro in ('router_snr', 'radio', 'AP_channel', 'stats_80211_a'):
      self.assertIn(dentro, ok)


class TestAjuste(Base):
  def test_vazamento_nunca_chega_ao_ajuste(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    with self.assertRaises(AssertionError):
      SF.r2_por_posicao(conj.df, ['router_snr', 'router_tx_bytes'], 'speedtest_down_mbps',
                        ['router_tx_bytes'])

  def test_ajuste_completo(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    aj = SF.ajuste(conj, SF.inventario(conj))
    self.assertEqual(set(aj['teto']), {'atual', 'tr069', 'tudo'})
    self.assertEqual(len(aj['teto']['tudo']['por_posicao']), 5)
    self.assertTrue(all(g['posicoes'] == 5 for g in aj['ganho']))
    canal = next(p for p in aj['proxy'] if p['coluna'] == 'AP_channel')
    self.assertTrue(canal['parece_tr069'])
    self.assertEqual(aj['avisos'], [])

  def test_poucas_posicoes_vira_aviso(self):
    conj = SF.preparar({'a.csv': frame(locais=['sala', 'quarto', 'suite'])}, 'speedtest_down_mbps', TABELA)
    aj = SF.ajuste(conj, SF.inventario(conj))
    self.assertTrue(any(a.startswith('só 3 posições') for a in aj['avisos']))


if __name__ == '__main__':
  unittest.main()

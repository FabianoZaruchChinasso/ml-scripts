import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core.sites import BUILDING_ENVIRONMENT, resolve_site_id
from ml.studio import data as SD
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

LOCAIS = ['sala', 'quarto', 'suite', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


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

  def test_fold_e_o_local_de_coleta_e_posicao_fica_para_exibicao(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(sorted(conj.df['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    self.assertEqual(sorted(conj.df['_pos'].unique()),
                     ['cwpb-1', 'cwpb-2', 'hotmilk-aquario', 'hotmilk-copa',
                      'res-quarto', 'res-sala', 'res-suite'])
    self.assertEqual(set(conj.df['_ds']), {'a.csv'})

  def test_ambiente_de_cada_linha(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    por_local = conj.df.groupby('_site')['_amb'].unique().map(list).to_dict()
    self.assertEqual(por_local, {'residencia': ['domestico'], 'coworking': ['corporativo'],
                                 'hotmilk': ['corporativo']})

  def test_filtro_de_ambiente(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, 'corporativo')
    self.assertEqual(sorted(conj.df['_site'].unique()), ['coworking', 'hotmilk'])
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, 'domestico')
    self.assertEqual(sorted(conj.df['_site'].unique()), ['residencia'])

  def test_ambiente_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, 'industrial')

  def test_ambiente_sem_linhas_levanta(self):
    with self.assertRaises(ValueError):
      SF.preparar({'a.csv': frame(locais=['sala', 'quarto'])}, 'speedtest_down_mbps', TABELA,
                  'corporativo')

  def test_local_desconhecido_e_nomeado_no_aviso(self):
    conj = SF.preparar({'a.csv': frame(locais=['sala', 'garagem'])}, 'speedtest_down_mbps', TABELA)
    self.assertTrue(any("['garagem']" in a for a in conj.avisos))

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
      SF.r2_por_local(conj.df, ['router_snr', 'router_tx_bytes'], 'speedtest_down_mbps',
                        ['router_tx_bytes'])

  def test_ajuste_completo(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    aj = SF.ajuste(conj, SF.inventario(conj))
    self.assertEqual(set(aj['teto']), {'atual', 'tr069', 'tudo'})
    self.assertEqual(set(aj['teto']['tudo']['por_local']), {'coworking', 'hotmilk', 'residencia'})
    self.assertEqual(aj['locais'], ['coworking', 'hotmilk', 'residencia'])
    self.assertTrue(all(g['locais'] == 3 for g in aj['ganho']))
    canal = next(p for p in aj['proxy'] if p['coluna'] == 'AP_channel')
    self.assertTrue(canal['parece_tr069'])
    self.assertEqual(aj['avisos'], ['só 3 locais de coleta: a dispersão por local não é '
                                    'interpretável e a estimativa é instável'])

  def test_resumo_traz_pooled_e_mae(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    tudo = SF.ajuste(conj, SF.inventario(conj))['teto']['tudo']
    self.assertIsNotNone(tudo['pooled'])
    self.assertGreater(tudo['mae'], 0)

  def test_nenhum_predio_aparece_no_treino_e_no_teste(self):
    # Com folds por cômodo, sala sairia para teste com quarto/suíte no treino.
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    vistos = []
    original = SF.outer_logo_folds

    def espiao(X, y, grupos):
      folds = original(X, y, grupos)
      vistos.extend(folds)
      return folds
    SF.outer_logo_folds = espiao
    try:
      SF.r2_por_local(conj.df, ['router_snr'], 'speedtest_down_mbps', [])
    finally:
      SF.outer_logo_folds = original
    self.assertEqual(len(vistos), 3)
    for fold in vistos:
      self.assertNotIn(fold.test_site, fold.train_sites)

  def test_ambiente_com_um_local_so_recusa_o_ajuste(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, 'domestico')
    with self.assertRaises(ValueError) as ctx:
      SF.ajuste(conj, SF.inventario(conj))
    self.assertIn('só 1 local de coleta', str(ctx.exception))

  def test_poucos_locais_vira_aviso(self):
    conj = SF.preparar({'a.csv': frame(locais=['sala', 'quarto', 'cwpb-1'])}, 'speedtest_down_mbps', TABELA)
    aj = SF.ajuste(conj, SF.inventario(conj))
    self.assertTrue(any(a.startswith('só 2 locais de coleta') for a in aj['avisos']))


class TestDados(unittest.TestCase):
  def test_ambiente_do_studio_bate_com_o_core(self):
    for predio, meta in SD.BUILDINGS.items():
      for posicao in meta['positions']:
        core = resolve_site_id(pd.Series([posicao]), level='building').iloc[0]
        self.assertEqual(BUILDING_ENVIRONMENT[core], meta['ambiente'], f'{predio}/{posicao}')

  def test_rotulo_antigo_do_hotmilk_vira_a_posicao_corrigida(self):
    self.assertEqual(SD.POSITION_LABELS['quarto-marcelo'], 'hotmilk-aquario')
    self.assertEqual(SD._building_of('quarto-marcelo'), 'hotmilk')

  def test_versoes_com_ruido_de_float_sao_duplicatas(self):
    base = frame()[['local'] + list(SD.TARGETS)]
    ruido = base.copy()
    ruido[list(SD.TARGETS)] += 1e-14
    with tempfile.TemporaryDirectory() as pasta:
      base.to_csv(os.path.join(pasta, 'a-fix.csv'), index=False)
      ruido.to_csv(os.path.join(pasta, 'a.csv'), index=False)
      antes = SD.DATA_DIR
      SD.DATA_DIR = pasta
      try:
        achados = {d['id']: d for d in SD.discover()}
      finally:
        SD.DATA_DIR = antes
    self.assertEqual(achados['a-fix.csv']['fingerprint'], achados['a.csv']['fingerprint'])


if __name__ == '__main__':
  unittest.main()

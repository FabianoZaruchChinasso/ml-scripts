import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import features as F
from ml.core.sites import teto_wan
from ml.studio import features as SF

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']


def alvos(n, inicio=0.0):
  valores = np.arange(n, dtype=float) + inicio + 1
  return pd.DataFrame({'local': ['sala'] * n, **{a: valores for a in ALVOS}})


T0 = pd.Timestamp('2026-09-17T19:00:00Z')


def simultaneos(linhas):
  """linhas: (ds, run_id, combo, n_clients, bssid, segundos depois de T0)."""
  return pd.DataFrame([{'_ds': ds, 'session_id': 1, 'run_id': run, 'combo': combo, 'n_clients': n,
                        'bssid': bssid, '_time': (T0 + pd.Timedelta(seconds=s)).isoformat()}
                       for ds, run, combo, n, bssid, s in linhas])


class TestTetoWan(unittest.TestCase):
  def test_teto_da_residencia(self):
    self.assertEqual(teto_wan('residencia', 'speedtest_down_mbps'), 154.0)
    self.assertEqual(teto_wan('residencia', 'speedtest_up_mbps'), 99.0)

  def test_sem_teto_conhecido(self):
    self.assertIsNone(teto_wan('hotmilk', 'speedtest_down_mbps'))
    self.assertIsNone(teto_wan('residencia', 'latency_ms'))



class TestDescoberta(unittest.TestCase):
  def test_ids_padrao_exclui_legacy_duplicata_e_substituido(self):
    b = alvos(4)
    datasets = [
      {'id': 'a-fix.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f1', '_frame': alvos(3, 100)},
      {'id': 'a.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f1', '_frame': alvos(3, 100)},
      {'id': 'b.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f2', '_frame': b},
      {'id': 'parte.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f3', '_frame': b.iloc[:2]},
      {'id': 'velho.csv', 'usable': True, 'generation': 'legacy', 'fingerprint': 'f4', '_frame': alvos(2, 500)},
      {'id': 'quebrado.csv', 'usable': False, 'error': 'x'},
    ]
    self.assertEqual(C.duplicatas(datasets), {'a.csv': 'a-fix.csv'})
    self.assertEqual(C._superseded(datasets), {'parte.csv': 'b.csv'})
    self.assertEqual(C.ids_padrao(datasets), ['a-fix.csv', 'b.csv'])

  def test_discover_le_zip_e_csv_da_pasta(self):
    with tempfile.TemporaryDirectory() as pasta:
      alvos(2).to_csv(os.path.join(pasta, 'x.csv'), index=False)
      antes = C.DATA_DIR
      C.DATA_DIR = pasta
      try:
        achados = {d['id']: d for d in C.discover()}
      finally:
        C.DATA_DIR = antes
    self.assertEqual(achados['x.csv']['rows'], 2)
    self.assertEqual(achados['x.csv']['generation'], 'legacy')


class TestConcorrencia(unittest.TestCase):
  def test_dois_bssid_no_mesmo_grupo_contam_separado(self):
    df = simultaneos([('a', 1, 'ABC', 3, 'x', 0), ('a', 1, 'ABC', 3, 'x', 5), ('a', 1, 'ABC', 3, 'y', 9)])
    self.assertEqual(C.concorrentes_mesmo_radio(df).tolist(), [2.0, 2.0, 1.0])

  def test_grupo_incompleto_vira_nan(self):
    df = simultaneos([('a', 2, 'AB', 2, 'x', 0)])
    self.assertTrue(C.concorrentes_mesmo_radio(df).isna().all())

  def test_grupo_maior_que_n_clients_vira_nan(self):
    df = simultaneos([('a', 3, 'A', 1, 'x', 0), ('a', 3, 'A', 1, 'x', 5)])
    self.assertTrue(C.concorrentes_mesmo_radio(df).isna().all())

  def test_run_id_repetido_depois_da_janela_e_outro_grupo(self):
    df = simultaneos([('a', 4, 'C', 1, 'x', 0), ('a', 4, 'C', 1, 'x', 600)])
    self.assertEqual(C.concorrentes_mesmo_radio(df).tolist(), [1.0, 1.0])

  def test_sem_bssid_vira_nan_so_na_linha(self):
    df = simultaneos([('a', 5, 'AB', 2, 'x', 0), ('a', 5, 'AB', 2, None, 4)])
    r = C.concorrentes_mesmo_radio(df)
    self.assertEqual(r.iloc[0], 1.0)
    self.assertTrue(np.isnan(r.iloc[1]))

  def test_datasets_diferentes_nao_se_misturam(self):
    df = simultaneos([('a', 6, 'A', 1, 'x', 0), ('b', 6, 'A', 1, 'x', 1)])
    self.assertEqual(C.concorrentes_mesmo_radio(df).tolist(), [1.0, 1.0])


class TestSemEnlace(unittest.TestCase):
  def test_linha_sem_os_quatro_campos_sai_e_com_um_fica(self):
    df = pd.DataFrame({'router_tx_rate_mbps': [np.nan, np.nan], 'router_rx_rate_mbps': [np.nan, np.nan],
                       'router_snr': [np.nan, 30.0], 'router_signal_dbm': [np.nan, np.nan]})
    saida, n = C.descartar_sem_enlace(df)
    self.assertEqual(n, 1)
    self.assertEqual(saida['router_snr'].tolist(), [30.0])

  def test_so_as_colunas_presentes_contam(self):
    df = pd.DataFrame({'router_snr': [np.nan, 20.0]})
    saida, n = C.descartar_sem_enlace(df)
    self.assertEqual((n, len(saida)), (1, 1))

  def test_sem_nenhuma_coluna_de_enlace_nao_descarta(self):
    df = pd.DataFrame({'outra': [1.0, 2.0]})
    saida, n = C.descartar_sem_enlace(df)
    self.assertEqual((n, len(saida)), (0, 2))


class TestLimitadoWan(unittest.TestCase):
  def setUp(self):
    self.df = pd.DataFrame({
      '_site': ['residencia'] * 4 + ['hotmilk'],
      'speedtest_down_mbps': [150.0, 150.0, 100.0, 150.0, 600.0],
      'latency_ms': [5.0] * 5,
      'router_expected_throughput_mbps': [300.0, 100.0, 300.0, np.nan, 900.0],
    })

  def test_so_marca_com_as_duas_condicoes(self):
    # 1: no teto e Wi-Fi acima dele. 2: Wi-Fi abaixo do teto. 3: abaixo de 85% do teto.
    # 4: sem expected_throughput. 5: prédio sem teto.
    self.assertEqual(C.marcar_limitado_wan(self.df, 'speedtest_down_mbps').tolist(),
                     [True, False, False, False, False])

  def test_latencia_nunca_marca(self):
    self.assertFalse(C.marcar_limitado_wan(self.df, 'latency_ms').any())

  def test_sem_expected_throughput_nao_marca(self):
    df = self.df.drop(columns=['router_expected_throughput_mbps'])
    self.assertFalse(C.marcar_limitado_wan(df, 'speedtest_down_mbps').any())


TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {a: {'classe': 'alvo'} for a in ALVOS}}


def rodada(n_por_local=4):
  """Uma linha por teste, todos individuais (combo de 1), em 3 prédios."""
  locais = ['sala', 'cwpb-1', 'hotmilk-copa']
  linhas = []
  for i, local in enumerate(np.repeat(locais, n_por_local)):
    linhas.append({'local': local, 'session_id': 1, 'run_id': i, 'combo': 'A', 'n_clients': 1,
                   'bssid': f'b{i}', '_time': (T0 + pd.Timedelta(minutes=i)).isoformat(),
                   'speedtest_down_mbps': 50.0 + i, 'speedtest_up_mbps': 20.0 + i,
                   'latency_ms': 10.0, 'jitter_ms': 1.0, 'router_snr': 30.0,
                   'router_expected_throughput_mbps': 100.0})
  return pd.DataFrame(linhas)


class TestPreparar(unittest.TestCase):
  def test_studio_usa_o_mesmo_preparar(self):
    self.assertIs(SF.preparar, C.preparar)
    self.assertIs(SF.Conjunto, C.Conjunto)

  def test_concorrencia_e_calculada_antes_de_descartar_alvo_zero(self):
    f = rodada()
    f.loc[1, ['run_id', 'combo', 'n_clients', 'bssid', '_time']] = [0, 'AB', 2, 'b0', f.loc[0, '_time']]
    f.loc[0, ['combo', 'n_clients']] = ['AB', 2]
    f.loc[1, 'speedtest_down_mbps'] = 0.0
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(conj.df.loc[conj.df['_linha'] == 'a.csv:0', 'concorrentes_mesmo_radio'].tolist(), [2.0])

  def test_sem_colunas_de_concorrencia_avisa_e_omite(self):
    f = rodada().drop(columns=['bssid'])
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertNotIn('concorrentes_mesmo_radio', conj.df.columns)
    self.assertTrue(any('concorrentes_mesmo_radio omitida' in a for a in conj.avisos))

  def test_descarta_sem_enlace_e_avisa(self):
    f = rodada()
    f.loc[0, 'router_snr'] = np.nan
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(len(conj.df), len(f) - 1)
    self.assertTrue(any('1 linhas sem stats de estação' in a for a in conj.avisos))

  def test_marca_limitado_wan_e_avisa(self):
    f = rodada()
    f.loc[0, ['speedtest_down_mbps', 'router_expected_throughput_mbps']] = [150.0, 300.0]
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(conj.df.loc[conj.df['_limitado_wan'], '_linha'].tolist(), ['a.csv:0'])
    self.assertTrue(any('1 linhas no teto de WAN' in a for a in conj.avisos))

  def test_linha_estavel_entre_alvos(self):
    f = rodada()
    f.loc[2, 'speedtest_down_mbps'] = np.nan
    dn = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    up = C.preparar({'a.csv': f}, 'speedtest_up_mbps', TABELA)
    self.assertNotIn('a.csv:2', dn.df['_linha'].tolist())
    self.assertIn('a.csv:2', up.df['_linha'].tolist())
    self.assertEqual(set(dn.df['_linha']) - set(up.df['_linha']), set())


class TestCarregar(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.TemporaryDirectory()
    atual = rodada().assign(station_x=1.0, house_x0=1.0)
    atual.to_csv(os.path.join(self.pasta.name, 'novo.csv'), index=False)
    alvos(3).to_csv(os.path.join(self.pasta.name, 'velho.csv'), index=False)
    self.antes = (C.DATA_DIR, C._descobertos)
    C.DATA_DIR, C._descobertos = self.pasta.name, None

  def tearDown(self):
    C.DATA_DIR, C._descobertos = self.antes
    self.pasta.cleanup()

  def test_padrao_e_o_conjunto_canonico(self):
    conj = C.carregar('speedtest_down_mbps', tabela=TABELA)
    self.assertEqual(conj.datasets, ['novo.csv'])
    self.assertEqual(len(conj.df), 12)

  def test_id_desconhecido_levanta(self):
    with self.assertRaisesRegex(ValueError, 'nao_existe.csv'):
      C.carregar('speedtest_down_mbps', ids=['nao_existe.csv'], tabela=TABELA)

  def test_legacy_nao_entra_na_regua(self):
    with self.assertRaisesRegex(ValueError, 'velho.csv'):
      C.carregar('speedtest_down_mbps', ids=['velho.csv'], tabela=TABELA)


class TestClassificacao(unittest.TestCase):
  def test_concorrencia_e_tr069_no_repositorio(self):
    tabela = F.carregar_tabela()
    for coluna in ('n_clients', 'concorrentes_mesmo_radio'):
      c = F.classificar(coluna, tabela)
      self.assertEqual((c.classe, c.vazamento), ('tr069', False), coluna)
      self.assertIn('depende do coletor', c.parametro)


if __name__ == '__main__':
  unittest.main()

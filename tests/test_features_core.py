import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import features as F


def tabela_exemplo():
  return {
    'prefixos': {
      'router_': {'classe': 'tr069'},
      'router_tx_': {'classe': 'tr069', 'vazamento': True},
      'stats_80211_': {'classe': 'sniffer'},
    },
    'colunas': {
      'router_x': {'classe': 'geometria'},
      'RSSI': {'classe': 'cliente'},
      'client_id': {'classe': 'identificador'},
      'client_mode': {'classe': 'tr069'},
      'site_survey_total_aps': {'classe': 'cliente'},
    },
  }


class TestClassificar(unittest.TestCase):
  def test_entrada_exata_vence_prefixo(self):
    c = F.classificar('router_x', tabela_exemplo())
    self.assertEqual((c.classe, c.origem), ('geometria', 'exata'))

  def test_prefixo_mais_longo_vence(self):
    c = F.classificar('router_tx_bytes', tabela_exemplo())
    self.assertEqual((c.classe, c.vazamento, c.origem), ('tr069', True, 'prefixo'))
    c = F.classificar('router_snr', tabela_exemplo())
    self.assertEqual((c.classe, c.vazamento), ('tr069', False))

  def test_coluna_sem_regra_devolve_none(self):
    self.assertIsNone(F.classificar('temperature_c', tabela_exemplo()))


class TestSugerir(unittest.TestCase):
  def test_mais_tokens_em_comum_vence(self):
    self.assertEqual(F.sugerir('site_survey_new_metric', tabela_exemplo()), 'cliente')

  def test_empate_entre_classes_devolve_none(self):
    # client_id (identificador) e client_mode (tr069) empatam em 1 token.
    self.assertIsNone(F.sugerir('client_power', tabela_exemplo()))

  def test_sem_token_em_comum_devolve_none(self):
    self.assertIsNone(F.sugerir('humidity_pct', tabela_exemplo()))


class TestValidar(unittest.TestCase):
  def test_classe_invalida_levanta(self):
    with self.assertRaises(ValueError):
      F.validar_regra('x', {'classe': 'router'})

  def test_campo_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      F.validar_regra('x', {'classe': 'tr069', 'nota': 'oi'})

  def test_tabela_sem_secao_levanta(self):
    with self.assertRaises(ValueError):
      F.validar_tabela({'colunas': {}})


class TestGravar(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'tabela.json')
    with open(self.path, 'w', encoding='utf-8') as handle:
      json.dump(tabela_exemplo(), handle)

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def test_grava_e_le_de_volta(self):
    F.gravar_classificacao('temperature_c', 'ambiente', False, None, {'temperature_c'}, path=self.path)
    c = F.classificar('temperature_c', F.carregar_tabela(self.path))
    self.assertEqual((c.classe, c.vazamento, c.origem), ('ambiente', False, 'exata'))

  def test_vazamento_e_parametro_sao_gravados(self):
    F.gravar_classificacao('AP_channel', 'tr069', True, 'Device.WiFi.Radio.{i}.Channel',
                           {'AP_channel'}, path=self.path)
    regra = F.carregar_tabela(self.path)['colunas']['AP_channel']
    self.assertEqual(regra, {'classe': 'tr069', 'vazamento': True,
                             'parametro': 'Device.WiFi.Radio.{i}.Channel'})

  def test_chaves_ordenadas_e_sem_temporario(self):
    F.gravar_classificacao('temperature_c', 'ambiente', False, None, {'temperature_c'}, path=self.path)
    with open(self.path, encoding='utf-8') as handle:
      texto = handle.read()
    self.assertLess(texto.index('"RSSI"'), texto.index('"client_id"'))
    self.assertTrue(texto.endswith('\n'))
    self.assertEqual(os.listdir(self.pasta), ['tabela.json'])

  def _ler(self):
    with open(self.path, encoding='utf-8') as handle:
      return handle.read()

  def test_classe_invalida_nao_grava(self):
    antes = self._ler()
    with self.assertRaises(ValueError):
      F.gravar_classificacao('temperature_c', 'clima', False, None, {'temperature_c'}, path=self.path)
    self.assertEqual(self._ler(), antes)

  def test_coluna_inexistente_levanta(self):
    with self.assertRaises(ValueError):
      F.gravar_classificacao('nao_existe', 'ambiente', False, None, {'temperature_c'}, path=self.path)


class TestDerivadas(unittest.TestCase):
  def test_classe_tr069_so_se_todos_insumos_forem_tr069(self):
    t = tabela_exemplo()
    so_tr069 = F.Derivada('d', ('router_snr', 'router_noise'), lambda df: df.router_snr, '')
    mista = F.Derivada('d', ('RSSI', 'router_snr'), lambda df: df.RSSI, '')
    self.assertEqual(F.classificar_derivada(so_tr069, t).classe, 'tr069')
    self.assertEqual(F.classificar_derivada(mista, t).classe, F.CLASSE_AUXILIAR)

  def test_vazamento_herdado_e_anulado_por_normaliza_volume(self):
    t = tabela_exemplo()
    herda = F.Derivada('d', ('router_tx_bytes', 'router_snr'), lambda df: df.router_snr, '')
    normaliza = F.Derivada('d', ('router_tx_bytes', 'router_snr'), lambda df: df.router_snr, '',
                           normaliza_volume=True)
    self.assertTrue(F.classificar_derivada(herda, t).vazamento)
    self.assertFalse(F.classificar_derivada(normaliza, t).vazamento)

  def test_insumo_sem_classificacao_devolve_none(self):
    d = F.Derivada('d', ('temperature_c',), lambda df: df.temperature_c, '')
    self.assertIsNone(F.classificar_derivada(d, tabela_exemplo()))

  def test_divisao_por_zero_vira_nan(self):
    df = pd.DataFrame({'router_tx_retries': [4.0, 3.0], 'router_tx_packets': [2.0, 0.0]})
    saida, _ = F.aplicar_derivadas(df, catalogo=[F.CATALOGO[0]])
    self.assertEqual(saida['retry_por_pacote'].iloc[0], 2.0)
    self.assertTrue(np.isnan(saida['retry_por_pacote'].iloc[1]))

  def test_insumo_ausente_omite_com_aviso(self):
    df = pd.DataFrame({'router_tx_retries': [1.0]})
    saida, avisos = F.aplicar_derivadas(df, catalogo=[F.CATALOGO[0]])
    self.assertNotIn('retry_por_pacote', saida.columns)
    self.assertEqual(len(avisos), 1)


class TestSemente(unittest.TestCase):
  def test_semente_do_repositorio_e_valida(self):
    tabela = F.carregar_tabela()
    self.assertEqual(F.classificar('router_expected_throughput_mbps', tabela).vazamento, False)
    self.assertEqual(F.classificar('client_opportunity_medium_use', tabela).classe, 'cliente')
    self.assertTrue(F.classificar('router_tx_bytes', tabela).vazamento)


if __name__ == '__main__':
  unittest.main()

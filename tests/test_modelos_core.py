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
from ml.core import modelos as M

TABELA = {
  'prefixos': {'router_': {'classe': 'tr069'}, 'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}},
  'colunas': {'RSSI': {'classe': 'cliente'}, 'client_opportunity_medium_use': {'classe': 'cliente'}},
}
CONHECIDAS = {'router_snr', 'router_noise', 'router_tx_bytes', 'RSSI', 'mystery',
              'router_power_dbm', 'router_signal_dbm', 'perda_percurso_db'}


class Base(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'modelos.json')
    with open(self.path, 'w', encoding='utf-8') as h:
      json.dump({'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'semente'}}}, h)

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def salvar(self, nome='v2', features=('router_snr', 'router_noise'), descricao='teste'):
    return M.salvar_versao(nome, features, descricao, CONHECIDAS, TABELA, path=self.path)


class TestRegistro(Base):
  def test_salva_e_le_de_volta(self):
    self.salvar()
    reg = M.carregar(self.path)
    self.assertEqual(reg['versoes']['v2']['features'], ['router_snr', 'router_noise'])
    self.assertEqual(reg['ativo'], 'v1')

  def test_versao_existente_e_imutavel(self):
    with self.assertRaises(ValueError):
      self.salvar(nome='v1')
    self.assertEqual(M.carregar(self.path)['versoes']['v1']['features'], ['router_snr'])

  def test_recusa_vazamento(self):
    with self.assertRaises(ValueError):
      self.salvar(features=['router_snr', 'router_tx_bytes'])

  def test_recusa_desconhecida_e_sem_classificacao(self):
    with self.assertRaises(ValueError):
      self.salvar(features=['nao_existe'])
    with self.assertRaises(ValueError):
      self.salvar(features=['mystery'])

  def test_recusa_nome_invalido_e_descricao_vazia(self):
    with self.assertRaises(ValueError):
      self.salvar(nome='V 2')
    with self.assertRaises(ValueError):
      self.salvar(descricao='  ')

  def test_recusa_features_repetidas(self):
    with self.assertRaises(ValueError):
      self.salvar(features=['router_snr', 'router_snr'])

  def test_metadados_da_selecao_sao_gravados(self):
    M.salvar_versao('v2', ['router_snr'], 'desenho', CONHECIDAS, TABELA,
                    selecao={'nota_aninhada': {'pooled': 0.1}}, path=self.path)
    self.assertEqual(M.carregar(self.path)['versoes']['v2']['selecao']['nota_aninhada']['pooled'], 0.1)

  def test_definir_ativo(self):
    self.salvar()
    M.definir_ativo('v2', path=self.path)
    self.assertEqual(M.ativo(M.carregar(self.path)), ['router_snr', 'router_noise'])
    with self.assertRaises(ValueError):
      M.definir_ativo('v9', path=self.path)

  def test_fora_do_tr069_olha_derivadas(self):
    self.assertEqual(M.fora_do_tr069(['router_snr', 'RSSI', 'perda_percurso_db'], TABELA), ['RSSI'])


class TestSemente(unittest.TestCase):
  def test_registro_do_repositorio(self):
    reg = M.carregar()
    self.assertIn('v1', reg['versoes'])
    self.assertEqual(reg['ativo'], 'v1')
    self.assertEqual(reg['versoes']['v1']['features'], list(F.MODELO_ATUAL))
    self.assertNotIn('avaliacao', reg['versoes']['v1'])


class TestDerivadasNovas(unittest.TestCase):
  def calcular(self, nome, df):
    derivada = next(d for d in F.CATALOGO if d.nome == nome)
    return F.aplicar_derivadas(df, catalogo=[derivada])[0][nome]

  def test_perda_de_percurso(self):
    df = pd.DataFrame({'router_power_dbm': [23.0], 'router_signal_dbm': [-40.0]})
    self.assertEqual(self.calcular('perda_percurso_db', df).iloc[0], 63.0)

  def test_eficiencia_espectral_divide_por_largura_e_fluxos(self):
    df = pd.DataFrame({'router_tx_rate_mbps': [400.0, 100.0], 'router_bandwith_TX_station': [80.0, 0.0],
                       'router_NSS_TX_Station': [2.0, 1.0]})
    saida = self.calcular('eficiencia_espectral_tx', df)
    self.assertEqual(saida.iloc[0], 2.5)
    self.assertTrue(np.isnan(saida.iloc[1]))

  def test_derivadas_novas_sao_tr069_na_tabela_do_repositorio(self):
    tabela = F.carregar_tabela()
    for nome in ('perda_percurso_db', 'eficiencia_espectral_tx', 'eficiencia_espectral_rx',
                 'vazao_esperada_por_mhz'):
      derivada = next(d for d in F.CATALOGO if d.nome == nome)
      c = F.classificar_derivada(derivada, tabela)
      self.assertEqual((c.classe, c.vazamento), ('tr069', False), nome)

  def test_descarte_por_pacote_rx_herda_vazamento_do_contador(self):
    derivada = next(d for d in F.CATALOGO if d.nome == 'descarte_por_pacote_rx')
    c = F.classificar_derivada(derivada, F.carregar_tabela())
    self.assertEqual((c.classe, c.vazamento), ('tr069', True))


class TestAvaliacaoComRegua(unittest.TestCase):
  def test_registro_aceita_avaliacao_com_versao_da_regua_e_atende(self):
    M.validar_registro({'ativo': 'v1', 'versoes': {'v1': {
      'features': ['router_snr'], 'descricao': 'x',
      'avaliacao': {'speedtest_down_mbps': {'pooled': 0.5, 'versao_regua': '2026-10-05.1'},
                    'atende_throughput': {'media': 0.8}}}}})


class TestDenominador(Base):
  def registro(self, denominador):
    return {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x',
                                              'denominador': denominador}}}

  def test_denominador_valido(self):
    M.validar_registro(self.registro({'speedtest_down_mbps': 'router_tx_rate_mbps',
                                      'speedtest_up_mbps': 'router_rx_rate_mbps'}))

  def test_denominador_invalido(self):
    for ruim in ({'latency_ms': 'router_snr'}, {'speedtest_down_mbps': ''},
                 {'speedtest_down_mbps': 3}, {}, ['router_snr'], 'router_snr'):
      with self.assertRaises(ValueError, msg=repr(ruim)):
        M.validar_registro(self.registro(ruim))

  def test_salvar_grava_e_le_o_denominador(self):
    M.salvar_versao('v2', ['router_snr'], 'eficiência', CONHECIDAS, TABELA,
                    denominador={'speedtest_down_mbps': 'router_signal_dbm'}, path=self.path)
    reg = M.carregar(self.path)
    self.assertEqual(M.denominador_de(reg, 'v2', 'speedtest_down_mbps'), 'router_signal_dbm')
    self.assertIsNone(M.denominador_de(reg, 'v2', 'speedtest_up_mbps'))
    self.assertIsNone(M.denominador_de(reg, 'v1', 'speedtest_down_mbps'))
    self.assertIsNone(M.denominador_de(reg, 'nao-existe', 'speedtest_down_mbps'))

  def test_salvar_recusa_denominador_desconhecido_ou_com_vazamento(self):
    for coluna in ('nao_existe', 'router_tx_bytes', 'RSSI'):
      with self.assertRaises(ValueError, msg=coluna):
        M.salvar_versao('v2', ['router_snr'], 'x', CONHECIDAS, TABELA,
                        denominador={'speedtest_down_mbps': coluna}, path=self.path)


class TestDenominadorPorBanda(Base):
  def registro(self, valor):
    return {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x',
                                              'denominador': {'speedtest_down_mbps': valor}}}}

  def test_forma_condicional_valida(self):
    M.validar_registro(self.registro({'coluna': 'router_tx_rate_mbps', 'radio': '5ghz'}))
    M.validar_registro(self.registro('router_tx_rate_mbps'))

  def test_forma_condicional_invalida(self):
    for ruim in ({'coluna': 'x'}, {'coluna': 'x', 'radio': ''}, {'coluna': '', 'radio': '5ghz'},
                 {'coluna': 'x', 'radio': '5ghz', 'extra': 1}, {'coluna': 3, 'radio': '5ghz'}):
      with self.assertRaises(ValueError, msg=repr(ruim)):
        M.validar_registro(self.registro(ruim))

  def test_coluna_do_denominador(self):
    self.assertEqual(M.coluna_do_denominador('router_tx_rate_mbps'), 'router_tx_rate_mbps')
    self.assertEqual(M.coluna_do_denominador({'coluna': 'router_rx_rate_mbps', 'radio': '5ghz'}),
                     'router_rx_rate_mbps')
    self.assertIsNone(M.coluna_do_denominador(None))

  def test_salvar_checa_a_coluna_dentro_do_dicionario(self):
    with self.assertRaises(ValueError):
      M.salvar_versao('v2', ['router_snr'], 'x', CONHECIDAS, TABELA,
                      denominador={'speedtest_down_mbps': {'coluna': 'router_tx_bytes', 'radio': '5ghz'}},
                      path=self.path)
    den = {'speedtest_down_mbps': {'coluna': 'router_signal_dbm', 'radio': '5ghz'}}
    M.salvar_versao('v3', ['router_snr'], 'x', CONHECIDAS, TABELA, denominador=den, path=self.path)
    self.assertEqual(M.denominador_de(M.carregar(self.path), 'v3', 'speedtest_down_mbps'),
                     {'coluna': 'router_signal_dbm', 'radio': '5ghz'})


if __name__ == '__main__':
  unittest.main()

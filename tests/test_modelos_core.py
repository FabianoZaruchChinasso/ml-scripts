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
    self.assertEqual(reg['versoes']['v1-legado']['features'], list(F.MODELO_ATUAL))
    self.assertEqual(reg['ativo'], 'v1-legado')
    sem = reg['versoes']['v1-sem-cliente']['features']
    self.assertEqual(sem, [f for f in F.MODELO_ATUAL if f != 'client_opportunity_medium_use'])
    self.assertEqual(M.fora_do_tr069(sem, F.carregar_tabela()), [])


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
                 'vazao_esperada_por_mhz', 'descarte_por_pacote_rx'):
      derivada = next(d for d in F.CATALOGO if d.nome == nome)
      c = F.classificar_derivada(derivada, tabela)
      self.assertEqual((c.classe, c.vazamento), ('tr069', False), nome)


if __name__ == '__main__':
  unittest.main()

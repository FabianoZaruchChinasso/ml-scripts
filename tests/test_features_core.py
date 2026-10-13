import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import carga as C
from ml.core import features as F


def tabela_exemplo():
  return {
    'prefixos': {
      'router_': {'classe': 'tr069', 'tr181': {'status': 'padrao', 'caminho': 'Device.WiFi.teste'}},
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

  def test_tr181_e_gravado_e_preservado_ao_reclassificar(self):
    tr181 = {'status': 'padrao', 'caminho': 'Device.WiFi.Radio.{i}.Channel'}
    F.gravar_classificacao('AP_channel', 'tr069', False, None, {'AP_channel'}, path=self.path, tr181=tr181)
    F.gravar_classificacao('AP_channel', 'cliente', False, 'canal visto pelo celular', {'AP_channel'}, path=self.path)
    regra = F.carregar_tabela(self.path)['colunas']['AP_channel']
    self.assertEqual(regra, {'classe': 'cliente', 'parametro': 'canal visto pelo celular', 'tr181': tr181})

  def test_tr181_invalido_nao_grava(self):
    antes = self._ler()
    with self.assertRaises(ValueError):
      F.gravar_classificacao('AP_channel', 'tr069', False, None, {'AP_channel'}, path=self.path,
                             tr181={'status': 'padrao'})
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

  def test_razao_herda_vazamento(self):
    t = tabela_exemplo()
    razao = F.Derivada('d', ('router_tx_bytes', 'router_snr'), lambda df: df.router_snr, '')
    self.assertTrue(F.classificar_derivada(razao, t).vazamento)

  def test_derivada_nao_aceita_normaliza_volume(self):
    with self.assertRaises(TypeError):
      F.Derivada('d', ('router_snr',), lambda df: df.router_snr, '', normaliza_volume=True)

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


class TestContadoresJanela(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'tabela.json')
    with open(self.path, 'w', encoding='utf-8') as h:
      json.dump(tabela_exemplo(), h)

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def test_estados_e_efeito_na_classificacao(self):
    self.assertEqual(F.estado_contadores(F.carregar_tabela(self.path)), 'nao_sei')
    for estado, vaz, pend in (('sim', True, False), ('nao', False, False), ('nao_sei', False, True)):
      F.gravar_estado_contadores(estado, self.path)
      t = F.carregar_tabela(self.path)
      self.assertEqual(F.estado_contadores(t), estado)
      c = F.classificar('router_tx_duration_us', t)
      self.assertEqual((c.classe, c.vazamento, c.pendente), ('tr069', vaz, pend), estado)

  def test_estado_dos_contadores_preserva_tr181(self):
    t = F.carregar_tabela(self.path)
    t['colunas']['router_tx_retries'] = {'classe': 'tr069', 'tr181': {
      'status': 'padrao', 'caminho': 'Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.Stats.RetransCount'}}
    with open(self.path, 'w', encoding='utf-8') as h:
      json.dump(t, h)
    F.gravar_estado_contadores('sim', self.path)
    regra = F.carregar_tabela(self.path)['colunas']['router_tx_retries']
    self.assertTrue(regra['vazamento'])
    self.assertEqual(regra['tr181']['status'], 'padrao')

  def test_estado_invalido(self):
    with self.assertRaises(ValueError):
      F.gravar_estado_contadores('talvez', self.path)

  def test_pendente_e_vazamento_juntos_sao_invalidos(self):
    with self.assertRaises(ValueError):
      F.validar_regra('x', {'classe': 'tr069', 'vazamento': True, 'pendente': True})

  def test_derivada_herda_pendente(self):
    F.gravar_estado_contadores('nao_sei', self.path)
    t = F.carregar_tabela(self.path)
    d = F.Derivada('d', ('router_tx_duration_us', 'router_snr'), lambda df: df.router_snr, '')
    c = F.classificar_derivada(d, t)
    self.assertTrue(c.pendente)
    self.assertFalse(c.vazamento)

  def test_vazado_e_pendente_juntos_viram_so_vazado(self):
    F.gravar_estado_contadores('nao_sei', self.path)
    t = F.carregar_tabela(self.path)
    # router_tx_bytes vaza pelo prefixo router_tx_; router_rx_duration_us está pendente.
    d = F.Derivada('d', ('router_tx_bytes', 'router_rx_duration_us'), lambda df: df.router_tx_bytes, '')
    c = F.classificar_derivada(d, t)
    self.assertTrue(c.vazamento)
    self.assertFalse(c.pendente)


def tabela_tr181():
  return {
    'prefixos': {'router_': {'classe': 'tr069'}},
    'colunas': {
      'router_signal_dbm': {'classe': 'tr069', 'tr181': {
        'status': 'padrao', 'caminho': 'Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.SignalStrength'}},
      'router_snr': {'classe': 'tr069', 'tr181': {'status': 'derivavel', 'nota': 'sinal menos ruído'}},
      'router_expected_throughput_mbps': {'classe': 'tr069', 'tr181': {'status': 'extensao', 'nota': 'rate control'}},
      'n_clients': {'classe': 'ambiente', 'tr181': {
        'status': 'proxy', 'caminho': 'Device.WiFi.AccessPoint.{i}.AssociatedDeviceNumberOfEntries'}},
      'RSSI': {'classe': 'cliente'},
    },
  }


class TestTr181(unittest.TestCase):
  def test_regra_com_tr181_valida(self):
    F.validar_regra('x', {'classe': 'tr069', 'tr181': {'status': 'padrao', 'caminho': 'Device.WiFi.X', 'nota': 'n'}})
    F.validar_regra('x', {'classe': 'tr069', 'tr181': {'status': 'desconhecido'}})

  def test_regra_com_tr181_invalido_levanta(self):
    for tr181 in ({'status': 'talvez'}, {'status': 'padrao'}, {'status': 'proxy', 'nota': 'sem caminho'},
                  {'status': 'extensao', 'extra': 1}, {'status': 'extensao', 'nota': 'x' * 201}, 'padrao'):
      with self.assertRaises(ValueError, msg=str(tr181)):
        F.validar_regra('x', {'classe': 'tr069', 'tr181': tr181})

  def test_status_da_coluna(self):
    t = tabela_tr181()
    self.assertEqual(F.status_tr181(F.classificar('router_signal_dbm', t)), 'padrao')
    self.assertEqual(F.status_tr181(F.classificar('n_clients', t)), 'proxy')
    # Roteador sem tr181: ninguém classificou. Outras classes não vêm do roteador.
    self.assertEqual(F.status_tr181(F.classificar('router_novo', t)), 'desconhecido')
    self.assertEqual(F.status_tr181(F.classificar('RSSI', t)), 'ausente')
    self.assertEqual(F.status_tr181(None), 'desconhecido')

  def test_derivada_herda_o_pior_status(self):
    t = tabela_tr181()
    casos = {('router_signal_dbm', 'router_snr'): 'derivavel',
             ('router_signal_dbm', 'n_clients'): 'proxy',
             ('router_signal_dbm', 'router_expected_throughput_mbps'): 'extensao',
             ('router_expected_throughput_mbps', 'RSSI'): 'ausente'}
    for insumos, esperado in casos.items():
      d = F.Derivada('d', insumos, lambda df: df[insumos[0]], '')
      self.assertEqual(F.status_tr181(F.classificar_derivada(d, t)), esperado, insumos)

  def test_cobertura_100_proxy_e_parcial(self):
    t = tabela_tr181()
    self.assertEqual(F.cobertura_tr069(['router_signal_dbm', 'router_snr'], t, catalogo=())['nivel'], '100%')
    proxy = F.cobertura_tr069(['router_signal_dbm', 'n_clients'], t, catalogo=())
    self.assertEqual(proxy['nivel'], 'proxy')
    self.assertEqual(proxy['lacunas'], [{'feature': 'n_clients', 'status': 'proxy',
                                         'caminho': 'Device.WiFi.AccessPoint.{i}.AssociatedDeviceNumberOfEntries',
                                         'nota': None}])
    parcial = F.cobertura_tr069(['n_clients', 'router_expected_throughput_mbps', 'nao_existe'], t, catalogo=())
    self.assertEqual(parcial['nivel'], 'parcial')
    self.assertEqual(parcial['por_feature'], {'n_clients': 'proxy', 'router_expected_throughput_mbps': 'extensao',
                                              'nao_existe': 'desconhecido'})

  def test_cobertura_olha_derivadas_do_catalogo(self):
    t = tabela_tr181()
    d = F.Derivada('mistura', ('router_signal_dbm', 'router_expected_throughput_mbps'), lambda df: df.router_snr, '')
    self.assertEqual(F.cobertura_tr069(['mistura'], t, catalogo=(d,))['por_feature'], {'mistura': 'extensao'})


class TestSemente(unittest.TestCase):
  def test_semente_do_repositorio_e_valida(self):
    tabela = F.carregar_tabela()
    self.assertEqual(F.classificar('router_expected_throughput_mbps', tabela).vazamento, False)
    self.assertEqual(F.classificar('client_opportunity_medium_use', tabela).classe, 'cliente')
    self.assertTrue(F.classificar('router_tx_bytes', tabela).vazamento)

  def test_contadores_da_janela_sao_vazamento(self):
    tabela = F.carregar_tabela()
    self.assertEqual(F.estado_contadores(tabela), 'sim')
    for coluna in F.CONTADORES_JANELA:
      c = F.classificar(coluna, tabela)
      self.assertEqual((c.classe, c.vazamento, c.pendente), ('tr069', True, False), coluna)
    derivadas = {d.nome: d for d in F.CATALOGO}
    for nome in ('retry_por_pacote', 'falha_por_pacote', 'descarte_por_pacote_rx', 'fracao_airtime_tx'):
      self.assertTrue(F.classificar_derivada(derivadas[nome], tabela).vazamento, nome)

  def test_tabela_tr181_do_repositorio(self):
    tabela = F.carregar_tabela()
    datasets = C.descobertos()
    padrao = set(C.ids_padrao(datasets))
    colunas = set()
    for d in datasets:
      if d['id'] in padrao:
        colunas.update(d['_frame'].columns)
    roteador = sorted(c for c in colunas if c.startswith('router_') and F.classificar(c, tabela).classe == 'tr069')
    self.assertEqual([c for c in roteador if 'tr181' not in tabela['colunas'].get(c, {})], [])
    status = lambda c: F.status_tr181(F.classificar(c, tabela))
    self.assertEqual({c: status(c) for c in ('router_tx_rate_mbps', 'router_rx_rate_mbps', 'router_signal_dbm',
                                             'radio', 'channel_width', 'client_mode')},
                     dict.fromkeys(('router_tx_rate_mbps', 'router_rx_rate_mbps', 'router_signal_dbm',
                                    'radio', 'channel_width', 'client_mode'), 'padrao'))
    self.assertEqual(status('router_snr'), 'derivavel')
    self.assertEqual(status('router_expected_throughput_mbps'), 'extensao')
    for coluna in ('n_clients', 'concorrentes_mesmo_radio'):
      c = F.classificar(coluna, tabela)
      self.assertEqual((c.classe, F.status_tr181(c)), ('ambiente', 'proxy'), coluna)
    derivadas = {d.nome: d for d in F.CATALOGO}
    for nome, esperado in (('eficiencia_espectral_tx', 'extensao'), ('perda_percurso_db', 'extensao'),
                           ('assimetria_phy', 'derivavel')):
      self.assertEqual(F.status_tr181(F.classificar_derivada(derivadas[nome], tabela)), esperado, nome)
    # Contadores continuam vazamento, agora com o caminho TR-181.
    self.assertEqual(F.estado_contadores(tabela), 'sim')


if __name__ == '__main__':
  unittest.main()

import os
import sys
import time
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import features as F
from ml.core import formulas
from ml.studio import api
from ml.studio import features as SF
from ml.studio import receitas as R
from test_studio_features import TABELA, Base, frame


def delta(pooled, mae, por_local=None):
  return {'pooled': pooled, 'mae': mae,
          'por_local': por_local if por_local is not None else {'a': pooled, 'b': pooled}}


class TestVeredito(unittest.TestCase):
  def test_melhor_no_limiar(self):
    self.assertEqual(SF.veredito(delta(0.02, 0.0), 4)['resultado'], 'melhor')

  def test_abaixo_do_ruido_e_empate(self):
    v = SF.veredito(delta(0.019, -1.0), 4)
    self.assertEqual(v['resultado'], 'empate')
    self.assertIn('menor que o ruído', v['motivo'])

  def test_um_local_piorando_alem_do_ruido_segura_em_empate(self):
    v = SF.veredito(delta(0.05, -2.0, {'a': 0.1, 'b': -0.021}), 4)
    self.assertEqual(v['resultado'], 'empate')
    self.assertIn('piorou em b', v['motivo'])

  def test_queda_no_limiar_e_pior(self):
    self.assertEqual(SF.veredito(delta(-0.02, -1.0), 4)['resultado'], 'pior')

  def test_mae_subiu_sem_ganho_de_r2_e_pior(self):
    v = SF.veredito(delta(0.01, 0.5), 4, unidade='ms')
    self.assertEqual(v['resultado'], 'pior')
    self.assertEqual(v['motivo'], 'O MAE subiu 0,5 ms e o R² não subiu além do ruído.')

  def test_mae_subiu_com_ganho_de_r2_e_empate(self):
    self.assertEqual(SF.veredito(delta(0.03, 0.5), 4)['resultado'], 'empate')

  def test_sem_pooled_e_empate(self):
    self.assertEqual(SF.veredito(delta(None, None, {}), 4)['resultado'], 'empate')

  def test_motivo_do_melhor_usa_a_unidade(self):
    self.assertEqual(SF.veredito(delta(0.05, -4.1), 4, unidade='Mbps')['motivo'],
                     'O R² subiu 0,05 e o MAE caiu 4,1 Mbps, sem piorar nenhum local.')

  def test_provisorio_com_poucos_locais(self):
    v = SF.veredito(delta(0.05, -1.0), 3)
    self.assertTrue(v['provisorio'])
    self.assertEqual(v['motivos_provisorio'], ['só 3 locais de coleta'])

  def test_provisorio_com_pendente(self):
    v = SF.veredito(delta(0.05, -1.0), 4, ['router_tx_retries'])
    self.assertTrue(v['provisorio'])
    self.assertEqual(v['motivos_provisorio'], ['depende de vazamento não confirmado: router_tx_retries'])

  def test_nao_provisorio(self):
    v = SF.veredito(delta(0.05, -1.0), 4)
    self.assertEqual((v['provisorio'], v['motivos_provisorio']), (False, []))


class TestGanhoMaisUm(Base):
  def setUp(self):
    super().setUp()
    self.conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)

  def test_igual_ao_ganho_do_ajuste(self):
    inv = SF.inventario(self.conj, ['router_snr'])
    ok = SF.elegiveis(inv)
    candidatas = [c for c in inv['candidatas'] if c in ok]
    # r2_por_local usa RandomForestRegressor com n_jobs=-1: threads paralelas podem
    # somar as previsões em ordem diferente a cada chamada, e duas avaliações
    # independentes do mesmo conjunto podem discordar no 4º dígito perto de zero.
    # Cacheia por conjunto de colunas para as duas chamadas abaixo reaproveitarem
    # o mesmo resultado — o teste prova que ajuste() delega para ganho_mais_um,
    # não que o RandomForest é determinístico entre chamadas.
    original = SF.r2_por_local
    cache = {}

    def estavel(df, colunas, y_col, vazadas, **kwargs):
      chave = tuple(sorted(colunas))
      if chave not in cache:
        cache[chave] = original(df, colunas, y_col, vazadas, **kwargs)
      return cache[chave]
    SF.r2_por_local = estavel
    try:
      g = SF.ganho_mais_um(self.conj, ['router_snr'], candidatas, SF.vazadas_do_conjunto(self.conj))
      self.assertEqual(g, SF.ajuste(self.conj, inv)['ganho'])
    finally:
      SF.r2_por_local = original
    self.assertTrue(g)

  def test_progresso_uma_vez_por_candidata(self):
    eventos = []
    SF.ganho_mais_um(self.conj, ['router_snr'], ['router_signal_dbm', 'router_nss'], [], eventos.append)
    self.assertEqual([(e['feito'], e['total'], e['coluna']) for e in eventos],
                     [(1, 2, 'router_signal_dbm'), (2, 2, 'router_nss')])

  def test_base_vazia_devolve_lista_vazia(self):
    self.assertEqual(SF.ganho_mais_um(self.conj, [], ['router_snr'], []), [])

  def test_vazamento_na_base_sai_da_conta(self):
    g = SF.ganho_mais_um(self.conj, ['router_snr', 'router_tx_bytes'], ['router_nss'], ['router_tx_bytes'])
    self.assertEqual([x['coluna'] for x in g], ['router_nss'])


HIPOTESE = F.Derivada('snr_x_sinal', ('router_snr', 'router_signal_dbm'),
                      lambda df: df['router_snr'] * df['router_signal_dbm'], 'produto de teste',
                      formula='router_snr * router_signal_dbm', status='hipotese')


class TestListaAssistente(Base):
  def setUp(self):
    super().setUp()
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, catalogo=(HIPOTESE,))
    inv = SF.inventario(conj, ['router_snr', 'AP_channel'])
    self.lista = {c['coluna']: c for c in SF.lista_assistente(inv, conj.catalogo)}

  def test_tr069_elegivel_e_liberada(self):
    c = self.lista['router_signal_dbm']
    self.assertTrue(c['liberada'])
    self.assertIsNone(c['motivo'])

  def test_vazamento_nao_e_liberado(self):
    c = self.lista['router_tx_bytes']
    self.assertFalse(c['liberada'])
    self.assertTrue(c['motivo'].startswith('vazamento'))

  def test_feature_da_base_fora_do_tr069_vem_com_motivo(self):
    c = self.lista['AP_channel']
    self.assertFalse(c['liberada'])
    self.assertTrue(c['no_modelo'])
    self.assertIn('fora do TR-069', c['motivo'])

  def test_cobertura_baixa(self):
    self.assertEqual(self.lista['router_power_dbm']['motivo'], 'cobertura baixa')

  def test_identificador_e_alvo_ficam_de_fora(self):
    self.assertNotIn('client_id', self.lista)
    self.assertNotIn('speedtest_down_mbps', self.lista)

  def test_hipotese_nao_e_liberada_e_traz_descricao(self):
    c = self.lista['snr_x_sinal']
    self.assertEqual((c['liberada'], c['hipotese'], c['derivada']), (False, True, True))
    self.assertEqual(c['descricao'], 'produto de teste')


class TestMotivoBloqueioRamosRestantes(Base):
  def test_constante(self):
    f = frame().assign(router_constante=1.0)
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    inv = SF.inventario(conj)
    lista = {c['coluna']: c for c in SF.lista_assistente(inv, conj.catalogo)}
    self.assertEqual(lista['router_constante']['motivo'], 'constante neste conjunto')

  def test_categorica_alta(self):
    f = frame()
    f = f.assign(router_categoria=[f'v{i}' for i in range(len(f))])
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    inv = SF.inventario(conj)
    lista = {c['coluna']: c for c in SF.lista_assistente(inv, conj.catalogo)}
    self.assertEqual(lista['router_categoria']['motivo'], 'categórica com muitos valores')

  def test_duplicata_identica(self):
    f = frame().assign(router_dup_a=lambda d: d['router_snr'], router_dup_b=lambda d: d['router_snr'])
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    inv = SF.inventario(conj)
    lista = {c['coluna']: c for c in SF.lista_assistente(inv, conj.catalogo)}
    self.assertIsNone(lista['router_dup_a']['motivo'])
    self.assertEqual(lista['router_dup_b']['motivo'], 'idêntica a outra coluna')


class TestReceitas(unittest.TestCase):
  def test_cada_receita_gera_formula_e_nome_validos(self):
    colunas = ['router_tx_retries', 'router_tx_packets', 'router_NSS_TX_Station']
    for r in R.listar():
      m = R.montar(r['id'], colunas[:r['colunas']], set())
      formulas.analisar(m['formula'])
      self.assertRegex(m['nome'], F.NOME_DERIVADA)
      self.assertTrue(m['descricao'].endswith('(receita do assistente).'))

  def test_razao(self):
    self.assertEqual(R.montar('razao', ['router_tx_retries', 'router_tx_packets'], set()), {
      'formula': 'router_tx_retries / router_tx_packets',
      'nome': 'tx_retries_por_tx_packets',
      'descricao': 'Razão entre router_tx_retries e router_tx_packets (receita do assistente).'})

  def test_fracao_repete_a_primeira_coluna(self):
    m = R.montar('fracao', ['router_tx_duration_us', 'router_rx_duration_us'], set())
    self.assertEqual(m['formula'], 'router_tx_duration_us / (router_tx_duration_us + router_rx_duration_us)')
    self.assertEqual(m['nome'], 'fracao_tx_duration_us')

  def test_maiusculas_viram_minusculas(self):
    m = R.montar('produto', ['router_bandwith_TX_station', 'router_NSS_TX_Station'], set())
    self.assertEqual(m['nome'], 'bandwith_tx_station_x_nss_tx_station')

  def test_nome_longo_e_cortado_em_40(self):
    m = R.montar('razao', ['router_expected_throughput_mbps', 'router_bandwith_TX_station'], set())
    self.assertEqual(m['nome'], 'expected_throughput_mbps_por_bandwith_tx')

  def test_colisao_ganha_sufixo(self):
    m = R.montar('razao', ['router_tx_retries', 'router_tx_packets'], {'tx_retries_por_tx_packets'})
    self.assertEqual(m['nome'], 'tx_retries_por_tx_packets_2')

  def test_quantidade_errada_de_colunas(self):
    with self.assertRaises(ValueError):
      R.montar('por_canal', ['router_tx_rate_mbps', 'router_bandwith_TX_station'], set())

  def test_colunas_repetidas(self):
    with self.assertRaises(ValueError):
      R.montar('razao', ['router_snr', 'router_snr'], set())

  def test_receita_desconhecida(self):
    with self.assertRaises(ValueError):
      R.montar('logaritmo', ['router_snr'], set())

  def test_nome_gerado_muito_curto_levanta(self):
    with self.assertRaises(ValueError):
      R.montar('produto', ['router_', 'ROUTER_'], set())


REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'teste'}}}


class TestRotasAssistente(Base):
  def setUp(self):
    super().setUp()
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.patches = [mock.patch.object(api, '_conjunto', return_value=(conj, None)),
                    mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
                    mock.patch.object(api, '_colunas_conhecidas', return_value={'router_snr'})]
    for p in self.patches:
      p.start()
    api._modelos_cache.clear()
    api._desenhos.clear()

  def tearDown(self):
    for p in self.patches:
      p.stop()
    super().tearDown()

  def test_avaliar_com_base_traz_veredito(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    self.assertIn(r['veredito']['resultado'], {'melhor', 'empate', 'pior'})
    self.assertTrue(r['veredito']['provisorio'])

  def test_avaliar_com_base_traz_promocao_da_regua(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    self.assertIn(r['promocao']['veredito']['resultado'], {'melhor', 'empate', 'pior'})
    self.assertEqual(r['promocao']['versao_regua'], A.VERSAO_REGUA)
    self.assertIn('intervalo', r['promocao']['delta_mae'])

  def test_resumo_traz_intervalos(self):
    r = api.modelos_avaliar(features='router_snr', ds='a.csv')
    self.assertIn('pooled', r['resumo']['intervalos'])

  def test_listar_traz_versao_da_regua(self):
    self.assertEqual(api.modelos_listar()['versao_regua'], A.VERSAO_REGUA)

  def test_avaliacao_completa_traz_atende_e_versao(self):
    av = api.avaliacao_completa('a.csv', '', ['router_snr'])
    self.assertEqual(av['speedtest_down_mbps']['versao_regua'], A.VERSAO_REGUA)
    self.assertIn('media', av['atende_throughput'])

  def test_avaliar_sem_base_nao_traz_veredito(self):
    r = api.modelos_avaliar(features='router_snr', ds='a.csv')
    self.assertNotIn('veredito', r)

  def test_colunas_do_assistente(self):
    colunas = {c['coluna']: c for c in api.assistente_colunas(ds='a.csv')['colunas']}
    self.assertTrue(colunas['router_signal_dbm']['liberada'])
    self.assertFalse(colunas['router_tx_bytes']['liberada'])

  def test_job_de_sugestoes_termina(self):
    job_id = api.assistente_sugestoes(ds='a.csv', base='v1')['id']
    fim = time.time() + 120
    while api.assistente_sugestoes_status(job_id)['status'] == 'rodando' and time.time() < fim:
      time.sleep(0.2)
    job = api.assistente_sugestoes_status(job_id)
    self.assertEqual(job['status'], 'pronto', job.get('erro'))
    self.assertEqual(job['resultado']['base'], 'v1')
    self.assertEqual(job['resultado']['ganho_min'], 0.01)
    self.assertNotIn('router_snr', [g['coluna'] for g in job['resultado']['ganho']])
    self.assertTrue(job['progresso'])

  def test_receitas(self):
    self.assertEqual([r['id'] for r in api.receitas_listar()['receitas']][0], 'razao')
    m = api.receitas_montar(api.MontarReceita(receita='razao', colunas=['router_tx_retries', 'router_tx_packets']))
    self.assertEqual(m['nome'], 'tx_retries_por_tx_packets')

  def test_receita_invalida_vira_422(self):
    with self.assertRaises(api.HTTPException) as ctx:
      api.receitas_montar(api.MontarReceita(receita='razao', colunas=['router_snr']))
    self.assertEqual(ctx.exception.status_code, 422)

  def test_avaliacao_completa_traz_quantis_e_atende_completo(self):
    av = api.avaliacao_completa('a.csv', '', ['router_snr'])
    self.assertIn('q90', av['latency_ms']['quantis']['cobertura'])
    self.assertIn('q90', av['jitter_ms']['quantis']['pinball'])
    self.assertNotIn('quantis', av['speedtest_down_mbps'])
    self.assertIn('media', av['atende_completo'])
    self.assertIn('media', av['atende_throughput'])

  def test_promocao_em_latencia_usa_quantis(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', alvo='latency_ms', base='v1')
    p = r['promocao']
    self.assertIn('intervalo', p['delta_pinball'])
    self.assertNotIn('delta_mae', p)
    self.assertGreaterEqual(p['cobertura'], 0.0)
    self.assertIn(p['veredito']['resultado'], {'melhor', 'empate', 'pior'})

  def test_promocao_em_download_nao_muda(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    self.assertIn('delta_mae', r['promocao'])


REGISTRO_DEN = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr'], 'descricao': 'teste', 'denominador': {'speedtest_down_mbps': 'router_snr'}},
  'v2': {'features': ['router_snr'], 'descricao': 'absoluta'}}}


class TestDenominadorNaApi(Base):
  def setUp(self):
    super().setUp()
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.patches = [mock.patch.object(api, '_conjunto', return_value=(conj, None)),
                    mock.patch.object(api, '_registro', return_value=(REGISTRO_DEN, None)),
                    mock.patch.object(api, '_colunas_conhecidas', return_value={'router_snr', 'router_signal_dbm'})]
    for p in self.patches:
      p.start()
    api._modelos_cache.clear()

  def tearDown(self):
    for p in self.patches:
      p.stop()
    super().tearDown()

  def denominadores_usados(self, chamada):
    with mock.patch.object(A, 'prever_fora_do_fold', wraps=A.prever_fora_do_fold) as espiao:
      chamada()
    return [c.kwargs.get('denominador') for c in espiao.call_args_list]

  def test_rascunho_herda_o_denominador_da_base(self):
    usados = self.denominadores_usados(lambda: api.modelos_avaliar(features='router_snr,router_signal_dbm',
                                                                   ds='a.csv', base='v1'))
    self.assertIn('router_snr', usados)
    self.assertNotIn(None, usados)

  def test_promocao_contra_base_absoluta(self):
    usados = self.denominadores_usados(lambda: api.modelos_avaliar(features='router_snr,router_signal_dbm',
                                                                   ds='a.csv', base='v2'))
    self.assertEqual(set(usados), {None})

  def test_comparar_usa_o_denominador_de_cada_versao(self):
    r = api.modelos_comparar(ds='a.csv')
    por_nome = {v['nome']: v for v in r['versoes']}
    self.assertEqual(por_nome['v1']['denominador'], 'router_snr')
    self.assertIsNone(por_nome['v2']['denominador'])

  def test_salvar_copia_o_denominador_da_base(self):
    pedido = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
    corpo = api.NovaVersao(nome='v9', features=['router_snr'], descricao='x', ds='a.csv', base='v1')
    with mock.patch.object(api.core_modelos, 'salvar_versao') as salvar:
      api.modelos_salvar(corpo, pedido)
    self.assertEqual(salvar.call_args.kwargs['denominador'], {'speedtest_down_mbps': 'router_snr'})


if __name__ == '__main__':
  unittest.main()

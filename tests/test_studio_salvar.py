import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api


def conj(alvo):
  return types.SimpleNamespace(alvo=alvo, datasets=['a.csv'], df=None)


class TestAvaliacaoCompleta(unittest.TestCase):
  """O peso (LOGO, quantis, limiar) vai para mocks: aqui só importa o que entra em cada etapa."""

  def rodar(self, features, progresso=None):
    patches = {
      'conjunto': mock.patch.object(api, '_conjunto', side_effect=lambda ds, alvo, amb='': (conj(alvo), None)),
      'vazadas': mock.patch.object(api.core_completa, '_vazadas', return_value=['router_tx_retries']),
      'avaliar': mock.patch.object(api.core_avaliacao, 'avaliar', return_value=({'n': 10}, 'prev')),
      'quantis': mock.patch.object(api.core_completa, 'prever_quantis', return_value='q'),
      'resumir_quantis': mock.patch.object(api.core_quantis, 'resumir_quantis', return_value={}),
      'atende': mock.patch.object(api.core_avaliacao, 'atende', return_value={}),
      'decisoes': mock.patch.object(api.core_limiar, 'decisoes_atende', return_value={}),
      'resumir_decisoes': mock.patch.object(api.core_limiar, 'resumir_decisoes', return_value={}),
      'fatores': mock.patch.object(api.core_limiar, 'fatores_producao', return_value={}),
      'completo': mock.patch.object(api.core_quantis, 'atende_completo', return_value={}),
      'aplicacoes': mock.patch.object(api.core_aplicacoes, 'carregar_perfil', return_value={}),
      'de_previsoes': mock.patch.object(api.core_comodo, 'de_previsoes', return_value='prev4'),
      'comodo': mock.patch.object(api.core_completa, 'bloco_comodo', return_value={'nota': 0.7}),
    }
    m = {k: p.start() for k, p in patches.items()}
    self.addCleanup(lambda: [p.stop() for p in patches.values()])
    return api.avaliacao_completa('a.csv', '', features, None, progresso=progresso, perfil_qoe='norma'), m

  def test_colunas_com_vazamento_saem_da_conta_e_ficam_registradas(self):
    saida, m = self.rodar(['router_snr', 'router_tx_retries'])
    for chamada in m['avaliar'].call_args_list:
      self.assertEqual(chamada.args[1], ['router_snr'])
    for chamada in m['quantis'].call_args_list:
      self.assertEqual(chamada.args[1], ['router_snr'])
    self.assertEqual(m['decisoes'].call_args.args[2], ['router_snr'])
    self.assertEqual(m['fatores'].call_args.args[2], ['router_snr'])
    self.assertEqual(saida['removidas_por_vazamento'], ['router_tx_retries'])
    self.assertEqual(saida['speedtest_down_mbps']['removidas_por_vazamento'], ['router_tx_retries'])

  def test_progresso_tem_as_seis_etapas_em_ordem(self):
    eventos = []
    self.rodar(['router_snr'], eventos.append)
    self.assertEqual([e['etapa'] for e in eventos], ['download', 'upload', 'latência', 'jitter', 'atende', 'cômodo'])
    self.assertEqual([e['passo'] for e in eventos], [0, 1, 2, 3, 4, 5])
    self.assertTrue(all(e['passos'] == 6 for e in eventos))

  def test_comodo_com_as_previsoes_ja_calculadas_e_sem_qoe(self):
    saida, m = self.rodar(['router_snr', 'router_tx_retries'])
    m['aplicacoes'].assert_called_with('norma')
    self.assertEqual(m['de_previsoes'].call_args.args[1:], ('prev', 'prev', 'q', 'q'))
    conjs, prev, ambiente = m['comodo'].call_args.args
    self.assertEqual(sorted(conjs), sorted(api.core_qoe.ALVOS))
    self.assertEqual((prev, ambiente), ('prev4', ''))
    self.assertEqual(saida['comodo'], {'nota': 0.7})
    self.assertNotIn('qoe', saida)
    self.assertEqual(saida['perfil'], 'norma')

  def test_sem_vazamento_nada_e_removido(self):
    saida, _ = self.rodar(['router_snr'])
    self.assertEqual(saida['removidas_por_vazamento'], [])


PEDIDO = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x'}}}
AVAL = {'atende_completo': {'media': 0.6}}
GRAVADO = {'ativo': 'v1', 'versoes': {'v2': {'features': ['router_snr'], 'descricao': 'teste', 'avaliacao': AVAL}}}


def sincrono(chave, tarefa):
  """_iniciar_job sem thread: a tarefa roda na hora e o resultado volta no lugar do id."""
  return {'resultado': tarefa(lambda evento: None)}


def classes(features, tabela):
  return {f: types.SimpleNamespace(vazamento=f == 'router_tx_retries') for f in features}


class TestSalvarRota(unittest.TestCase):
  def setUp(self):
    patches = [mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
               mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)),
               mock.patch.object(api, '_colunas_conhecidas', return_value={'router_snr', 'router_tx_retries'}),
               mock.patch.object(api.core_modelos, 'classificar_features', side_effect=classes)]
    for p in patches:
      p.start()
      self.addCleanup(p.stop)
    self.job = mock.patch.object(api, '_iniciar_job', side_effect=sincrono).start()
    self.mlflow = mock.patch.object(api, 'core_registro_mlflow').start()
    self.addCleanup(mock.patch.stopall)

  def salvar(self, ativar_falha=None, aval=AVAL, **campos):
    corpo = api.NovaVersao(**{'nome': 'v2', 'features': ['router_snr'], 'descricao': 'teste', **campos})
    with mock.patch.object(api, 'avaliacao_completa', side_effect=[aval] if isinstance(aval, dict) else aval) as a, \
         mock.patch.object(api.core_modelos, 'salvar_versao', return_value=GRAVADO) as s, \
         mock.patch.object(api.core_modelos, 'definir_ativo', side_effect=ativar_falha) as d:
      try:
        r = api.modelos_salvar(corpo, PEDIDO)
      except Exception as erro:  # 422 e falhas do job voltam para o teste examinar
        r = erro
    return r, a, s, d

  def test_salva_dentro_do_job_com_progresso(self):
    r, aval, salvar, ativar = self.salvar()
    self.assertEqual(r['resultado'], {'nome': 'v2', 'ativa': False, 'erro_ativar': None, 'aviso_mlflow': None})
    self.assertEqual(salvar.call_args.kwargs['avaliacao'], AVAL)
    self.assertIn('progresso', aval.call_args.kwargs)
    ativar.assert_not_called()
    self.assertEqual(self.job.call_args.args[0][:2], ('salvar', 'v2'))

  def test_perfil_vai_para_a_avaliacao_e_para_o_registro(self):
    r, aval, salvar, _ = self.salvar(perfil_qoe='atual')
    self.assertEqual(aval.call_args.kwargs['perfil_qoe'], 'atual')
    self.assertEqual(salvar.call_args.kwargs['perfil_qoe'], 'atual')

  def test_perfil_padrao_e_norma(self):
    _, aval, salvar, _ = self.salvar()
    self.assertEqual(salvar.call_args.kwargs['perfil_qoe'], 'norma')

  def test_perfil_invalido_e_422_sem_job(self):
    r, _, salvar, _ = self.salvar(perfil_qoe='outro')
    self.assertIsInstance(r, api.HTTPException)
    self.assertEqual(r.status_code, 422)
    self.job.assert_not_called()
    salvar.assert_not_called()

  def test_perfis_diferentes_tem_chaves_de_job_diferentes(self):
    self.salvar(perfil_qoe='atual')
    self.salvar(perfil_qoe='norma')
    chaves = [c.args[0] for c in self.job.call_args_list]
    self.assertEqual(len(chaves), 2)
    self.assertNotEqual(chaves[0], chaves[1])

  def test_ativar_no_mesmo_job(self):
    r, _, _, ativar = self.salvar(ativar=True)
    ativar.assert_called_once_with('v2')
    self.assertTrue(r['resultado']['ativa'])

  def test_falha_ao_ativar_mantem_a_versao_salva(self):
    r, _, salvar, _ = self.salvar(ativar=True, ativar_falha=ValueError('registro travado'))
    salvar.assert_called_once()
    self.assertEqual(r['resultado']['ativa'], False)
    self.assertIn('registro travado', r['resultado']['erro_ativar'])

  def test_vazamento_recusa_na_requisicao_sem_job(self):
    r, aval, _, _ = self.salvar(features=['router_snr', 'router_tx_retries'])
    self.assertIsInstance(r, api.HTTPException)
    self.assertEqual(r.status_code, 422)
    self.assertIn('router_tx_retries', r.detail)
    self.assertIn('Tire-as do rascunho', r.detail)
    aval.assert_not_called()
    self.job.assert_not_called()

  def test_nome_repetido_e_base_inexistente_sao_422_sem_job(self):
    for campos in ({'nome': 'v1'}, {'base': 'v9'}):
      r, _, _, _ = self.salvar(**campos)
      self.assertIsInstance(r, api.HTTPException)
      self.assertEqual(r.status_code, 422)
    self.job.assert_not_called()

  def test_falha_na_avaliacao_nao_grava(self):
    r, _, salvar, _ = self.salvar(aval=[RuntimeError('sem memória')])
    self.assertIn('sem memória', str(r))
    salvar.assert_not_called()

  def test_registra_no_mlflow_a_versao_gravada(self):
    r, _, _, _ = self.salvar()
    self.mlflow.registrar_avaliacao.assert_called_once_with('v2', GRAVADO['versoes']['v2'], 'salvar', ativo=False)
    self.mlflow.marcar_ativo.assert_not_called()
    self.assertIsNone(r['resultado']['aviso_mlflow'])

  def test_ativar_marca_a_ativa_no_mlflow(self):
    self.salvar(ativar=True)
    self.mlflow.registrar_avaliacao.assert_called_once_with('v2', GRAVADO['versoes']['v2'], 'salvar', ativo=True)
    self.mlflow.marcar_ativo.assert_called_once_with('v2')

  def test_ativacao_que_falha_nao_marca_no_mlflow(self):
    self.salvar(ativar=True, ativar_falha=ValueError('registro travado'))
    self.assertFalse(self.mlflow.registrar_avaliacao.call_args.kwargs['ativo'])
    self.mlflow.marcar_ativo.assert_not_called()

  def test_falha_do_mlflow_vira_aviso_e_a_versao_fica_salva(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('database is locked')
    r, _, salvar, _ = self.salvar()
    salvar.assert_called_once()
    self.assertEqual(r['resultado']['aviso_mlflow'], 'não registrou no MLflow: database is locked')
    self.assertIsNone(r['resultado']['erro_ativar'])

  def test_falha_no_registro_ainda_marca_a_ativa(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('database is locked')
    r, _, _, _ = self.salvar(ativar=True)
    self.mlflow.marcar_ativo.assert_called_once_with('v2')
    self.assertEqual(r['resultado']['aviso_mlflow'], 'não registrou no MLflow: database is locked')

  def test_duas_falhas_juntam_os_avisos(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('a')
    self.mlflow.marcar_ativo.side_effect = OSError('b')
    r, _, _, _ = self.salvar(ativar=True)
    self.assertEqual(r['resultado']['aviso_mlflow'], 'não registrou no MLflow: a; não registrou no MLflow: b')

  def test_falha_na_avaliacao_nao_registra(self):
    self.salvar(aval=[RuntimeError('sem memória')])
    self.mlflow.registrar_avaliacao.assert_not_called()


class TestReavaliarProgresso(unittest.TestCase):
  def test_reavaliar_repassa_a_etapa_com_o_nome_da_versao(self):
    eventos = []

    def job(chave, tarefa):
      return {'resultado': tarefa(eventos.append)}

    def aval(ds, amb, feats, den, progresso=None, perfil_qoe='atual'):
      progresso({'etapa': 'download', 'passo': 0, 'passos': 5})
      return AVAL

    with mock.patch.object(api, '_registro', return_value=(REGISTRO, None)), \
         mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)), \
         mock.patch.object(api, '_iniciar_job', side_effect=job), \
         mock.patch.object(api, 'avaliacao_completa', side_effect=aval), \
         mock.patch.object(api.core_features, 'cobertura_tr069', return_value={}), \
         mock.patch.object(api.core_modelos, 'reavaliar'), \
         mock.patch.object(api, 'core_registro_mlflow'):
      api.modelos_reavaliar(api.Reavaliacao(nomes=['v1'], ds='a.csv'), PEDIDO)
    self.assertEqual(eventos[-1], {'nome': 'v1', 'i': 0, 'total': 1, 'etapa': 'download', 'passo': 0, 'passos': 5})


class TestAtivarRota(unittest.TestCase):
  def setUp(self):
    self.mlflow = mock.patch.object(api, 'core_registro_mlflow').start()
    mock.patch.object(api, 'modelos_listar', return_value={'ativo': 'v2', 'versoes': []}).start()
    self.addCleanup(mock.patch.stopall)

  def test_ativar_marca_no_mlflow(self):
    with mock.patch.object(api.core_modelos, 'definir_ativo') as definir:
      r = api.modelos_ativo(api.Ativo(nome='v2'), PEDIDO)
    definir.assert_called_once_with('v2')
    self.mlflow.marcar_ativo.assert_called_once_with('v2')
    self.assertEqual(r, {'ativo': 'v2', 'versoes': [], 'aviso_mlflow': None})

  def test_falha_do_mlflow_vira_aviso_e_a_ativacao_fica(self):
    self.mlflow.marcar_ativo.side_effect = OSError('database is locked')
    with mock.patch.object(api.core_modelos, 'definir_ativo') as definir:
      r = api.modelos_ativo(api.Ativo(nome='v2'), PEDIDO)
    definir.assert_called_once_with('v2')
    self.assertEqual(r['aviso_mlflow'], 'não registrou no MLflow: database is locked')

  def test_ativacao_recusada_nao_mexe_no_mlflow(self):
    with mock.patch.object(api.core_modelos, 'definir_ativo', side_effect=ValueError('não existe')):
      with self.assertRaises(api.HTTPException):
        api.modelos_ativo(api.Ativo(nome='v9'), PEDIDO)
    self.mlflow.marcar_ativo.assert_not_called()


class TestRegistrarMlflow(unittest.TestCase):
  def test_aviso_usa_so_a_primeira_linha_do_erro(self):
    def falha():
      raise OSError('(sqlite3.OperationalError) database is locked\n[SQL: SELECT experiments.experiment_id]\n'
                    '(Background on this error at: https://sqlalche.me/e/20/e3q8)')
    self.assertEqual(api._registrar_mlflow(falha),
                     'não registrou no MLflow: (sqlite3.OperationalError) database is locked')

  def test_aviso_longo_e_cortado(self):
    def falha():
      raise OSError('x' * 500)
    aviso = api._registrar_mlflow(falha)
    self.assertEqual(aviso, 'não registrou no MLflow: ' + 'x' * 200 + '...')

  def test_erro_sem_mensagem_usa_o_nome_da_excecao(self):
    def falha():
      raise OSError()
    self.assertEqual(api._registrar_mlflow(falha), 'não registrou no MLflow: OSError')

  def test_sem_erro_devolve_none(self):
    self.assertIsNone(api._registrar_mlflow(lambda: None))


if __name__ == '__main__':
  unittest.main()

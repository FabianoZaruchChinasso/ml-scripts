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
      'vazadas': mock.patch.object(api.studio_features, 'vazadas_do_conjunto', return_value=['router_tx_retries']),
      'avaliar': mock.patch.object(api.core_avaliacao, 'avaliar', return_value=({'n': 10}, 'prev')),
      'quantis': mock.patch.object(api, '_prever_quantis', return_value='q'),
      'resumir_quantis': mock.patch.object(api.core_quantis, 'resumir_quantis', return_value={}),
      'atende': mock.patch.object(api.core_avaliacao, 'atende', return_value={}),
      'decisoes': mock.patch.object(api.core_limiar, 'decisoes_atende', return_value={}),
      'resumir_decisoes': mock.patch.object(api.core_limiar, 'resumir_decisoes', return_value={}),
      'fatores': mock.patch.object(api.core_limiar, 'fatores_producao', return_value={}),
      'completo': mock.patch.object(api.core_quantis, 'atende_completo', return_value={}),
      'aplicacoes': mock.patch.object(api.core_aplicacoes, 'carregar', return_value={}),
    }
    m = {k: p.start() for k, p in patches.items()}
    self.addCleanup(lambda: [p.stop() for p in patches.values()])
    return api.avaliacao_completa('a.csv', '', features, None, progresso=progresso), m

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

  def test_progresso_tem_as_cinco_etapas_em_ordem(self):
    eventos = []
    self.rodar(['router_snr'], eventos.append)
    self.assertEqual([e['etapa'] for e in eventos], ['download', 'upload', 'latência', 'jitter', 'atende'])
    self.assertEqual([e['passo'] for e in eventos], [0, 1, 2, 3, 4])
    self.assertTrue(all(e['passos'] == 5 for e in eventos))

  def test_sem_vazamento_nada_e_removido(self):
    saida, _ = self.rodar(['router_snr'])
    self.assertEqual(saida['removidas_por_vazamento'], [])


PEDIDO = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x'}}}
AVAL = {'atende_completo': {'media': 0.6}}


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
    self.addCleanup(mock.patch.stopall)

  def salvar(self, ativar_falha=None, aval=AVAL, **campos):
    corpo = api.NovaVersao(**{'nome': 'v2', 'features': ['router_snr'], 'descricao': 'teste', **campos})
    with mock.patch.object(api, 'avaliacao_completa', side_effect=[aval] if isinstance(aval, dict) else aval) as a, \
         mock.patch.object(api.core_modelos, 'salvar_versao') as s, \
         mock.patch.object(api.core_modelos, 'definir_ativo', side_effect=ativar_falha) as d:
      try:
        r = api.modelos_salvar(corpo, PEDIDO)
      except Exception as erro:  # 422 e falhas do job voltam para o teste examinar
        r = erro
    return r, a, s, d

  def test_salva_dentro_do_job_com_progresso(self):
    r, aval, salvar, ativar = self.salvar()
    self.assertEqual(r['resultado'], {'nome': 'v2', 'ativa': False, 'erro_ativar': None})
    self.assertEqual(salvar.call_args.kwargs['avaliacao'], AVAL)
    self.assertIn('progresso', aval.call_args.kwargs)
    ativar.assert_not_called()
    self.assertEqual(self.job.call_args.args[0][:2], ('salvar', 'v2'))

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


class TestReavaliarProgresso(unittest.TestCase):
  def test_reavaliar_repassa_a_etapa_com_o_nome_da_versao(self):
    eventos = []

    def job(chave, tarefa):
      return {'resultado': tarefa(eventos.append)}

    def aval(ds, amb, feats, den, progresso=None):
      progresso({'etapa': 'download', 'passo': 0, 'passos': 5})
      return AVAL

    with mock.patch.object(api, '_registro', return_value=(REGISTRO, None)), \
         mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)), \
         mock.patch.object(api, '_iniciar_job', side_effect=job), \
         mock.patch.object(api, 'avaliacao_completa', side_effect=aval), \
         mock.patch.object(api.core_features, 'cobertura_tr069', return_value={}), \
         mock.patch.object(api.core_modelos, 'reavaliar'):
      api.modelos_reavaliar(api.Reavaliacao(nomes=['v1'], ds='a.csv'), PEDIDO)
    self.assertEqual(eventos[-1], {'nome': 'v1', 'i': 0, 'total': 1, 'etapa': 'download', 'passo': 0, 'passos': 5})


if __name__ == '__main__':
  unittest.main()

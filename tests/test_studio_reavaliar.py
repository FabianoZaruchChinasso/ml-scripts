import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api

PEDIDO = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'))
ANTIGA = {'speedtest_down_mbps': {'datasets': ['a.csv'], 'ambiente': 'todos'}, 'atende_completo': {'media': 0.5}}
NOVA = {'speedtest_down_mbps': {'datasets': ['a.csv', 'villa.csv'], 'ambiente': 'todos'},
        'atende_completo': {'media': 0.6}}
REGISTRO = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr'], 'descricao': 'x', 'avaliacao': ANTIGA},
  'v2': {'features': ['router_snr', 'router_noise'], 'descricao': 'y', 'perfil_qoe': 'norma',
         'denominador': {'speedtest_down_mbps': 'router_snr'}}}}

REGRAVADO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'avaliacao': NOVA},
                                        'v2': {'features': ['router_snr', 'router_noise'], 'avaliacao': NOVA}}}


def sincrono(chave, tarefa):
  """_iniciar_job sem thread: a tarefa roda na hora e o resultado volta no lugar do id."""
  return {'resultado': tarefa(lambda evento: None)}


class TestReavaliarRota(unittest.TestCase):
  def setUp(self):
    self.patches = [mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
                    mock.patch.object(api, '_tabela', return_value=({'prefixos': {}, 'colunas': {}}, None)),
                    mock.patch.object(api, '_iniciar_job', side_effect=sincrono),
                    mock.patch.object(api.core_features, 'cobertura_tr069', return_value={'c': 1})]
    for p in self.patches:
      p.start()
    self.mlflow_patch = mock.patch.object(api, 'core_registro_mlflow')
    self.mlflow = self.mlflow_patch.start()
    self.addCleanup(self.mlflow_patch.stop)

  def tearDown(self):
    for p in self.patches:
      p.stop()

  def rodar(self, nomes, avaliacoes):
    corpo = api.Reavaliacao(nomes=nomes, ds='a.csv,villa.csv', ambiente='')
    with mock.patch.object(api, 'avaliacao_completa', side_effect=avaliacoes) as aval, \
         mock.patch.object(api.core_modelos, 'reavaliar', return_value=REGRAVADO) as reav:
      try:
        r = api.modelos_reavaliar(corpo, PEDIDO)
      except Exception as erro:  # a falha no meio do lote volta para o teste examinar
        r = erro
    return r, aval, reav

  def test_reavalia_em_ordem_com_o_denominador_da_versao(self):
    r, aval, reav = self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2'], 'avisos_mlflow': []})
    self.assertEqual(aval.call_args_list[1].args, ('a.csv,villa.csv', '', ['router_snr', 'router_noise'],
                                                   {'speedtest_down_mbps': 'router_snr'}))
    nome, avaliacao, cobertura, nota = reav.call_args_list[0].args
    self.assertEqual((nome, avaliacao, cobertura), ('v1', NOVA, {'c': 1}))
    self.assertIn('+villa.csv', nota)
    self.assertIn('0,50 → 0,60', nota)

  def test_reavalia_no_perfil_da_versao(self):
    r, aval, _ = self.rodar(['v1', 'v2'], [NOVA, NOVA])
    perfis = [c.kwargs['perfil_qoe'] for c in aval.call_args_list]
    self.assertEqual(perfis, ['atual', 'norma'])

  def test_falha_no_meio_mantem_as_anteriores_e_cita_a_versao(self):
    r, _, reav = self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertEqual(reav.call_count, 1)
    self.assertIn('v2', str(r))
    self.assertIn("['v1']", str(r))

  def test_recusa_lista_vazia_e_nome_inexistente(self):
    for nomes in ([], ['v9']):
      with self.assertRaises(api.HTTPException) as ctx:
        api.modelos_reavaliar(api.Reavaliacao(nomes=nomes), PEDIDO)
      self.assertEqual(ctx.exception.status_code, 422)

  def test_registra_cada_versao_reavaliada_com_a_ativa_marcada(self):
    self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(self.mlflow.registrar_avaliacao.call_args_list, [
      mock.call('v1', REGRAVADO['versoes']['v1'], 'reavaliar', ativo=True),
      mock.call('v2', REGRAVADO['versoes']['v2'], 'reavaliar', ativo=False)])

  def test_falha_do_mlflow_vira_aviso_e_nao_para_o_lote(self):
    self.mlflow.registrar_avaliacao.side_effect = [OSError('database is locked'), None]
    r, _, reav = self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(reav.call_count, 2)
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2'], 'avisos_mlflow': [
      {'nome': 'v1', 'aviso': 'não registrou no MLflow: database is locked'}]})

  def test_falha_na_avaliacao_registra_so_as_que_terminaram(self):
    self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertEqual([c.args[0] for c in self.mlflow.registrar_avaliacao.call_args_list], ['v1'])


  def test_falha_na_avaliacao_leva_os_avisos_do_mlflow_das_que_terminaram(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('database is locked')
    r, _, _ = self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertIn('parou em v2', str(r))
    self.assertIn('MLflow: v1: não registrou no MLflow: database is locked', str(r))

  def test_falha_na_avaliacao_sem_aviso_nao_cita_o_mlflow(self):
    r, _, _ = self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertNotIn('MLflow', str(r))


if __name__ == '__main__':
  unittest.main()

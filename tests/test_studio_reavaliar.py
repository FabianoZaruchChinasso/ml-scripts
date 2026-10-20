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
  'v2': {'features': ['router_snr', 'router_noise'], 'descricao': 'y',
         'denominador': {'speedtest_down_mbps': 'router_snr'}}}}


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

  def tearDown(self):
    for p in self.patches:
      p.stop()

  def rodar(self, nomes, avaliacoes):
    corpo = api.Reavaliacao(nomes=nomes, ds='a.csv,villa.csv', ambiente='')
    with mock.patch.object(api, 'avaliacao_completa', side_effect=avaliacoes) as aval, \
         mock.patch.object(api.core_modelos, 'reavaliar') as reav:
      try:
        r = api.modelos_reavaliar(corpo, PEDIDO)
      except Exception as erro:  # a falha no meio do lote volta para o teste examinar
        r = erro
    return r, aval, reav

  def test_reavalia_em_ordem_com_o_denominador_da_versao(self):
    r, aval, reav = self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2']})
    self.assertEqual(aval.call_args_list[1].args, ('a.csv,villa.csv', '', ['router_snr', 'router_noise'],
                                                   {'speedtest_down_mbps': 'router_snr'}))
    nome, avaliacao, cobertura, nota = reav.call_args_list[0].args
    self.assertEqual((nome, avaliacao, cobertura), ('v1', NOVA, {'c': 1}))
    self.assertIn('+villa.csv', nota)
    self.assertIn('0,50 → 0,60', nota)

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


if __name__ == '__main__':
  unittest.main()

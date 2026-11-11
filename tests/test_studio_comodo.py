import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api
from isolamento_mlflow import com_ativa  # noqa: E402

setUpModule, tearDownModule = com_ativa('v1')

JOGO_BASE = {'nota': 0.7, 'intervalo': [0.5, 0.8], 'piso': {'nota': 0.5, 'intervalo': [0.4, 0.6]}}
BLOCO = {'versao_comodo': 'x', 'nota': 0.6, 'jogo': JOGO_BASE}
REGISTRO = {'versoes': {
  'v1': {'features': ['router_snr'], 'descricao': 'x', 'denominador': {'speedtest_down_mbps': 'router_tx_rate_mbps'},
         'avaliacao': {'comodo': BLOCO}},
  'v2': {'features': ['router_snr'], 'descricao': 'sem cômodo', 'avaliacao': {'atende_completo': {'media': 0.6}}}}}
NOVO = {'nota': 0.7, 'intervalo': [0.6, 0.8], 'piso': {'nota': 0.45, 'intervalo': [0.3, 0.5]},
        'contra_piso': {'diferenca': 0.25, 'intervalo': [0.1, 0.4], 'resultado': 'melhor'}, 'por_predio': {'s1': [2, 3]},
        'jogo': {'nota': 0.8, 'intervalo': [0.6, 0.9], 'piso': {'nota': 0.5, 'intervalo': [0.4, 0.6]}}}
COMP = {'diferenca': 0.1, 'intervalo': [0.01, 0.2], 'resultado': 'melhor', 'nota': 0.7, 'nota_base': 0.6}


def conj(alvo):
  return types.SimpleNamespace(alvo=alvo, datasets=['a.csv'], df=None, classes={})


class TestAvaliarComodo(unittest.TestCase):
  def setUp(self):
    api._modelos_cache.clear()
    self.m = {}
    for nome, p in (('registro', mock.patch.object(api, '_registro', return_value=(REGISTRO, None))),
                    ('conjunto', mock.patch.object(api, '_conjunto',
                                                   side_effect=lambda ds, alvo, amb='': (conj(alvo), None))),
                    ('vazadas', mock.patch.object(api.studio_features, 'vazadas_do_conjunto',
                                                  return_value=['router_tx_retries'])),
                    ('prever', mock.patch.object(api.core_comodo, 'prever', return_value='prev')),
                    ('bloco', mock.patch.object(api, '_bloco_comodo', return_value=NOVO)),
                    ('comparar', mock.patch.object(api.core_comodo, 'comparar_blocos', return_value=COMP))):
      self.m[nome] = p.start()
      self.addCleanup(p.stop)

  def test_preve_so_o_rascunho_e_compara_com_o_bloco_guardado(self):
    r = api.modelos_avaliar_comodo(features='router_snr', contra='v1', ds='a.csv', base='v1')
    conjs, feats, vazadas, den = self.m['prever'].call_args.args
    self.assertEqual(sorted(conjs), sorted(api.core_qoe.ALVOS))
    self.assertEqual(feats, ['router_snr'])
    self.assertEqual(vazadas['speedtest_down_mbps'], ['router_tx_retries'])
    self.assertEqual(den, {'speedtest_down_mbps': 'router_tx_rate_mbps'})
    self.assertEqual(self.m['comparar'].call_args.args, (NOVO, BLOCO))
    self.assertEqual((r['nota'], r['nota_base'], r['diferenca'], r['intervalo_diferenca'], r['resultado']),
                     (0.7, 0.6, 0.1, [0.01, 0.2], 'melhor'))
    self.assertEqual(r['piso'], NOVO['piso'])
    self.assertEqual(r['por_predio'], NOVO['por_predio'])
    self.assertEqual(r['jogo'], NOVO['jogo'])
    self.assertEqual(r['jogo_base'], JOGO_BASE)

  def test_jogo_base_ausente_vira_none(self):
    sem_jogo = {'versoes': {'v1': dict(REGISTRO['versoes']['v1'],
                                                      avaliacao={'comodo': {'versao_comodo': 'x', 'nota': 0.6}})}}
    self.m['registro'].return_value = (sem_jogo, None)
    self.assertIsNone(api.modelos_avaliar_comodo(features='router_snr', contra='v1')['jogo_base'])

  def test_denominador_da_base_ou_da_ativa(self):
    api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(self.m['prever'].call_args.args[3], {'speedtest_down_mbps': 'router_tx_rate_mbps'})
    api.modelos_avaliar_comodo(features='router_snr', contra='v1', base='v2')
    self.assertIsNone(self.m['prever'].call_args.args[3])

  def test_cache_nao_recalcula(self):
    api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(self.m['prever'].call_count, 1)

  def test_contra_sem_bloco_comodo_e_409_sem_prever(self):
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar_comodo(features='router_snr', contra='v2')
    self.assertEqual(erro.exception.status_code, 409)
    self.assertIn('reavalie v2', erro.exception.detail)
    self.m['prever'].assert_not_called()

  def test_avaliacao_incompativel_e_409(self):
    self.m['comparar'].side_effect = ValueError('datasets diferente')
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(erro.exception.status_code, 409)
    self.assertIn('datasets diferente', erro.exception.detail)

  def test_erros_de_entrada(self):
    casos = [({'features': '', 'contra': 'v1'}, 422), ({'features': 'router_snr', 'contra': 'v9'}, 404),
             ({'features': 'router_snr', 'contra': 'v1', 'base': 'v9'}, 404)]
    for kwargs, codigo in casos:
      with self.assertRaises(api.HTTPException) as erro:
        api.modelos_avaliar_comodo(**kwargs)
      self.assertEqual(erro.exception.status_code, codigo)

  def test_valueerror_do_core_vira_422(self):
    self.m['prever'].side_effect = ValueError('nenhuma feature utilizável')
    with self.assertRaises(api.HTTPException) as erro:
      api.modelos_avaliar_comodo(features='router_snr', contra='v1')
    self.assertEqual(erro.exception.status_code, 422)

  def test_rota_do_qoe_saiu(self):
    rotas = [getattr(r, 'path', '') for r in api.app.routes]
    self.assertIn('/api/modelos/avaliar_comodo', rotas)
    self.assertNotIn('/api/modelos/avaliar_qoe', rotas)
    self.assertFalse(hasattr(api, 'modelos_avaliar_qoe'))


class TestBlocoComodo(unittest.TestCase):
  def setUp(self):
    api._piso_comodo_cache.clear()

  def test_piso_calculado_uma_vez_por_conjunto(self):
    conjs = {a: conj(a) for a in api.core_qoe.ALVOS}
    with mock.patch.object(api.core_qoe, 'conjunto_qoe', return_value='df'), \
         mock.patch.object(api.core_completa, '_vazadas', return_value=[]), \
         mock.patch.object(api.core_comodo, 'prever', return_value='prev_piso') as prever, \
         mock.patch.object(api.core_comodo, 'tabela_posicoes', side_effect=lambda df, prev, lim: 'tab:' + prev), \
         mock.patch.object(api.core_comodo, 'bloco', return_value={'nota': 0.7}) as bloco:
      api._bloco_comodo(conjs, 'prev_v1', '')
      self.assertEqual(api._bloco_comodo(conjs, 'prev_v2', ''), {'nota': 0.7})
    self.assertEqual(prever.call_count, 1)
    self.assertEqual(prever.call_args.args[1], ['radio'])
    self.assertEqual(bloco.call_args.args, ('tab:prev_v2', 'tab:prev_piso', {'datasets': ['a.csv'], 'ambiente': 'todos'}))


class TestDadosMudaram(unittest.TestCase):
  def test_dados_novos_esvaziam_o_piso_em_cache(self):
    api._piso_comodo_cache[('a.csv', 'todos', 'v')] = 'tabela'
    with mock.patch.object(api.core_carga, 'esquecer_descobertos'), \
         mock.patch.object(api.studio_data, 'limpar_cache_predios'):
      api._dados_mudaram()
    self.assertEqual(api._piso_comodo_cache, {})

  def test_dados_novos_esvaziam_o_cache_que_a_avaliacao_completa_usa(self):
    api.core_completa._piso_cache[('a.csv', 'todos', 'v')] = 'tabela'
    with mock.patch.object(api.core_carga, 'esquecer_descobertos'), \
         mock.patch.object(api.studio_data, 'limpar_cache_predios'):
      api._dados_mudaram()
    self.assertEqual(api.core_completa._piso_cache, {})


if __name__ == '__main__':
  unittest.main()

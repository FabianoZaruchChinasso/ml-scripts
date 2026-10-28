import os
import sys
import types
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import api

REGISTRO = {'ativo': 'v1', 'versoes': {
  'v1': {'features': ['router_snr', 'router_noise'], 'descricao': 'x'},
  'v2': {'features': ['router_tx_retries'], 'descricao': 'so vazamento'}}}


def conj(alvo):
  return types.SimpleNamespace(alvo=alvo, datasets=['a.csv'], df=None, classes={})


class TestAvaliarQoe(unittest.TestCase):
  def setUp(self):
    api._modelos_cache.clear()
    for p in (mock.patch.object(api, '_registro', return_value=(REGISTRO, None)),
              mock.patch.object(api, '_conjunto', side_effect=lambda ds, alvo, amb='': (conj(alvo), None)),
              mock.patch.object(api.studio_features, 'vazadas_do_conjunto', return_value=['router_tx_retries'])):
      p.start()
      self.addCleanup(p.stop)

  def test_passa_as_features_da_versao_contra_e_o_perfil(self):
    with mock.patch.object(api.core_qoe, 'avaliar', return_value={'ok': 1}) as av:
      r = api.modelos_avaliar_qoe(features='router_snr', ds='a.csv', contra='v1', perfil='atual')
    self.assertEqual(r, {'ok': 1})
    conjs, feats, vazadas, perfil = av.call_args.args
    self.assertEqual(sorted(conjs), sorted(api.core_qoe.ALVOS))
    self.assertEqual((feats, vazadas, perfil), (['router_snr'], ['router_tx_retries'], 'atual'))
    self.assertEqual(av.call_args.kwargs['features_base'], ['router_snr', 'router_noise'])

  def test_cache_nao_recalcula(self):
    with mock.patch.object(api.core_qoe, 'avaliar', return_value={'ok': 1}) as av:
      api.modelos_avaliar_qoe(features='router_snr', contra='v1', perfil='norma')
      api.modelos_avaliar_qoe(features='router_snr', contra='v1', perfil='norma')
    self.assertEqual(av.call_count, 1)

  def test_acerto_de_cache_nao_carrega_conjuntos_e_chave_muda_com_perfil_e_contra(self):
    with mock.patch.object(api.core_qoe, 'avaliar', return_value={'ok': 1}) as av:
      api.modelos_avaliar_qoe(features='router_snr', contra='v1', perfil='norma')
      carregados = api._conjunto.call_count
      self.assertEqual(carregados, len(api.core_qoe.ALVOS))
      api.modelos_avaliar_qoe(features='router_snr', contra='v1', perfil='norma')
      self.assertEqual(api._conjunto.call_count, carregados)
      api.modelos_avaliar_qoe(features='router_snr', contra='v1', perfil='atual')
      self.assertEqual(av.call_count, 2)
      api.modelos_avaliar_qoe(features='router_snr', contra='v2', perfil='atual')
      self.assertEqual(av.call_count, 3)

  def test_sem_promocao_o_dicionario_passa_como_esta(self):
    saida = {'promocao_qoe': None, 'promocao_qoe_motivo': 'a base só tem colunas com vazamento'}
    with mock.patch.object(api.core_qoe, 'avaliar', return_value=saida):
      r = api.modelos_avaliar_qoe(features='router_snr', contra='v2', perfil='norma')
    self.assertEqual(r, saida)

  def test_erros_viram_http(self):
    casos = [({'features': ''}, 422), ({'features': 'router_snr', 'perfil': 'x'}, 422),
             ({'features': 'router_snr', 'contra': 'v9'}, 404)]
    for kwargs, codigo in casos:
      with self.assertRaises(api.HTTPException) as erro:
        api.modelos_avaliar_qoe(**kwargs)
      self.assertEqual(erro.exception.status_code, codigo)

  def test_valueerror_do_core_vira_422(self):
    with mock.patch.object(api.core_qoe, 'avaliar', side_effect=ValueError('nenhuma feature')):
      with self.assertRaises(api.HTTPException) as erro:
        api.modelos_avaliar_qoe(features='router_snr', perfil='norma')
    self.assertEqual(erro.exception.status_code, 422)


class TestListagem(unittest.TestCase):
  def test_versao_sem_campo_aparece_como_atual(self):
    with mock.patch.object(api, '_registro', return_value=(REGISTRO, None)):
      r = api.modelos_listar()
    self.assertEqual(r['versoes'][0]['perfil_qoe'], 'atual')

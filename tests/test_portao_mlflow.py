import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

import mlflow

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import portao_mlflow as M
from ml.core import portao as T
from test_registry_mlflow import ComBanco, G

DEN = {'speedtest_down_mbps': {'coluna': 'router_tx_rate_mbps', 'radio': '5ghz'}}
REGISTRO = {'versoes': {'v1': {'features': ['a']}, 'v5': {'features': ['a', 'b'], 'denominador': DEN}}}
DESCOBERTOS = [{'id': 'a.zip', 'fingerprint': 'abc', 'usable': True},
               {'id': 'b.zip', 'fingerprint': 'def', 'usable': True},
               {'id': 'c.zip', 'fingerprint': 'ghi', 'usable': True}]


def por_alvo(*resultados):
  return {alvo: {'veredito': {'resultado': r, 'motivo': 'x'}} for alvo, r in zip(T.ALVOS, resultados)}


class TestPortao(ComBanco):
  def setUp(self):
    super().setUp()
    self.m = {}
    for nome, alvo, extra in (
        ('registro', (M.core_modelos, 'carregar'), {'return_value': REGISTRO}),
        ('descobertos', (M.core_carga, 'descobertos'), {'return_value': DESCOBERTOS}),
        ('carregar', (M.core_carga, 'carregar'), {'side_effect': lambda alvo, ids=None: mock.Mock(alvo=alvo)}),
        ('comparar', (M.core_portao, 'comparar'), {'return_value': por_alvo('melhor', 'empate', 'empate', 'empate')}),
        ('dado_novo', (M.core_portao, 'comparar_dado_novo'),
         {'return_value': por_alvo('empate', 'empate', 'empate', 'empate')}),
        ('degradacao', (M.core_degradacao, 'medir'),
         {'return_value': {'speedtest_down_mbps': {'resultado': 'degradou', 'motivo': 'x'}}}),
        ('pacote', (M.core_pacote_mlflow, 'carregar'), {'return_value': 'pacote-da-ativa'})):
      p = mock.patch.object(*alvo, **extra)
      self.m[nome] = p.start()
      self.addCleanup(p.stop)
    for chave in ('VERSAO', 'SIMULAR'):
      os.environ.pop(chave, None)

  def rodar(self, **env) -> str:
    saida = io.StringIO()
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(saida):
      M.main()
    return saida.getvalue()

  def tags_run(self, versao):
    return G.core_registro_mlflow.cliente().get_run(G.info_versao(versao)['run_id']).data.tags

  def relatorio(self, versao):
    caminho = mlflow.artifacts.download_artifacts(run_id=G.info_versao(versao)['run_id'],
                                                  artifact_path='portao.json', dst_path=self.tmp)
    with open(caminho, encoding='utf-8') as f:
      return json.load(f)

  def ativa_v1_candidata_v5(self):
    self.registrar('v1')
    G.ativar(1)
    self.registrar('v5')

  def test_sem_ativa_promove_a_primeira(self):
    self.registrar('v5')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual(self.tags_run(1)['portao'], 'primeira')
    self.assertEqual(self.tags_run(1)['portao_contra'], 'nenhuma')
    self.m['comparar'].assert_not_called()

  def test_candidata_ja_ativa_nao_grava(self):
    self.registrar('v5')
    G.ativar(1)
    self.assertIn('já é a ativa', self.rodar())
    self.assertNotIn('portao', self.tags_run(1))

  def test_melhor_promove_e_grava_o_veredito(self):
    self.ativa_v1_candidata_v5()
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 2)
    tags = self.tags_run(2)
    self.assertEqual((tags['portao'], tags['portao_promovida'], tags['portao_contra'], tags['portao_simulado']),
                     ('melhor', 'sim', '1', 'nao'))
    versao = G.core_registro_mlflow.cliente().get_model_version(G.NOME_MODELO, '2').tags
    self.assertEqual((versao['portao'], versao['portao_contra']), ('melhor', '1'))
    rel = self.relatorio(2)
    self.assertTrue(rel['decisao']['promover'])
    self.assertEqual(rel['ativa']['definicao'], 'v1')
    self.assertIn('auxiliares', rel)
    self.assertEqual(self.m['carregar'].call_args.kwargs['ids'], ['a.zip', 'b.zip'])
    self.m['degradacao'].assert_not_called()   # mesmos datasets: não há linha nova
    self.assertEqual(tags['portao_degradacao'], 'sem_dado_novo')
    candidata, ativa = self.m['comparar'].call_args.args[1:]
    self.assertEqual(candidata, {'features': ['a', 'b'], 'denominador': DEN})
    self.assertEqual(ativa, {'features': ['a'], 'denominador': None})

  def test_outra_definicao_com_dado_novo_mede_a_degradacao(self):
    self.m['degradacao'].return_value = {'speedtest_down_mbps': {'resultado': 'estavel', 'motivo': 'x'}}
    self.registrar('v1')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(self.m['degradacao'].call_args.args[2], ['a.zip', 'b.zip'])
    self.assertEqual(self.tags_run(2)['portao_degradacao'], 'nao')

  def test_pior_mantem_a_ativa(self):
    self.m['comparar'].return_value = por_alvo('melhor', 'pior', 'empate', 'empate')
    self.ativa_v1_candidata_v5()
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual((self.tags_run(2)['portao'], self.tags_run(2)['portao_promovida']), ('pior', 'nao'))

  def test_simular_grava_sem_mover_o_alias(self):
    self.ativa_v1_candidata_v5()
    self.rodar(SIMULAR='1')
    self.assertEqual(G.ativa()['versao'], 1)
    tags = self.tags_run(2)
    self.assertEqual((tags['portao'], tags['portao_promovida'], tags['portao_simulado']), ('melhor', 'nao', 'sim'))

  def test_mesma_definicao_com_dado_novo_compara_os_dois_treinos(self):
    self.registrar('v5')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 2)
    self.assertEqual(self.tags_run(2)['portao'], 'dado_novo')
    self.m['comparar'].assert_not_called()
    conjs, definicao = self.m['dado_novo'].call_args.args
    self.assertEqual(definicao, {'features': ['a', 'b'], 'denominador': DEN})
    self.assertEqual(self.m['dado_novo'].call_args.kwargs['ids_antigos'], ['a.zip', 'b.zip'])
    self.assertEqual(self.m['carregar'].call_args.kwargs['ids'], ['a.zip', 'b.zip', 'c.zip'])
    pacote, _, antigos, _ = self.m['degradacao'].call_args.args
    self.assertEqual((pacote, antigos), ('pacote-da-ativa', ['a.zip', 'b.zip']))
    self.assertEqual(self.m['pacote'].call_args.args[0], f'models:/{G.NOME_MODELO}/1')
    self.assertEqual(self.tags_run(2)['portao_degradacao'], 'sim')
    self.assertIn('speedtest_down_mbps', self.relatorio(2)['degradacao'])

  def test_dado_novo_que_piora_nao_promove(self):
    self.m['dado_novo'].return_value = por_alvo('empate', 'pior', 'empate', 'empate')
    self.registrar('v5')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['abc', 'def', 'ghi'], 'p1')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual(self.tags_run(2)['portao'], 'pior')

  def test_mesma_definicao_e_mesmos_dados_nao_carrega(self):
    self.registrar('v5')
    G.ativar(1)
    self.registrar('v5')
    self.rodar()
    self.assertEqual(G.ativa()['versao'], 1)
    self.assertEqual(self.tags_run(2)['portao'], 'igual')
    self.m['carregar'].assert_not_called()

  def test_dado_da_candidata_fora_de_data_para_antes_de_carregar(self):
    self.registrar('v1')
    G.ativar(1)
    G.registrar(self.modelo(), 'v5', ['zzz'], 'p1')
    with self.assertRaises(SystemExit) as erro:
      self.rodar()
    self.assertIn('data/', str(erro.exception))
    self.m['carregar'].assert_not_called()
    self.assertEqual(G.ativa()['versao'], 1)

  def test_versao_escolhida_e_invalida(self):
    self.ativa_v1_candidata_v5()
    self.registrar('v5')
    self.rodar(VERSAO='2')
    self.assertEqual(G.ativa()['versao'], 2)
    self.assertNotIn('portao', self.tags_run(3))
    for valor, trecho in (('x', 'número'), ('9', 'versão 9')):
      with self.subTest(valor=valor):
        with self.assertRaises(SystemExit) as erro:
          self.rodar(VERSAO=valor)
        self.assertIn(trecho, str(erro.exception))


if __name__ == '__main__':
  unittest.main()

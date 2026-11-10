import os
import sys
import tempfile
import unittest
from unittest import mock

import mlflow
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import versao_mlflow as V
from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import pacote_mlflow as PM
from ml.core import registro_mlflow as R
from test_studio_features import TABELA, frame

DN, UP, LAT, JIT = P.PREFIXOS
FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
POR_BANDA = {DN: {'coluna': 'router_snr', 'radio': '5ghz'}, UP: {'coluna': 'router_snr', 'radio': '5ghz'}}
REGISTRO = {'ativo': 'v1', 'versoes': {'v1': {'features': FEATURES + ['router_tx_bytes'], 'descricao': 'teste',
                                              'denominador': POR_BANDA}}}


def avaliacao() -> dict:
  def alvo(pooled, mae):
    return {'pooled': pooled, 'mae': mae, 'mae_log': 0.6, 'versao_regua': 'r1',
            'intervalos': {'pooled': [pooled - 0.1, pooled + 0.1], 'mae': [mae - 5, mae + 5], 'mae_log': [0.5, 0.7]},
            'por_local': {'casa-a': 0.4, 'casa-b': None}, 'mae_por_local': {'casa-a': 12.5, 'casa-b': 30.0}}
  quantis = {'cobertura': {'q50': 0.5, 'q90': 0.91}, 'pinball': {'q50': 4.0, 'q90': 11.2}}
  return {
    'perfil': 'norma', 'removidas_por_vazamento': [],
    'comodo': {'ambiente': 'todos', 'datasets': ['a.csv'], 'nota': 0.7, 'intervalo': [0.6, 0.8],
               'piso': {'nota': 0.45}, 'contra_piso': {'diferenca': 0.25}, 'graves': 2,
               'jogo': {'nota': 0.64, 'intervalo': [0.5, 0.78], 'piso': {'nota': 0.55}},
               'versao_comodo': 'v-c', 'posicoes': [{'pos': 'p1'}], 'piso_posicoes': [{'pos': 'p2'}]},
    'atende_completo': {'media': 0.66}, 'atende_throughput': {'media': 0.65}, 'atende_ajustado': {'media': 0.8},
    DN: alvo(0.75, 59.0), UP: alvo(0.74, 56.0),
    LAT: dict(alvo(-0.1, 22.5), quantis=quantis), JIT: dict(alvo(-0.08, 15.7), quantis=quantis),
  }


class TestMetricasDoPipeline(unittest.TestCase):
  def test_intervalos_por_predio_e_pinball(self):
    m = V.metricas_do_pipeline(avaliacao())
    self.assertEqual((m['down_pooled_lo90'], m['down_pooled_hi90']), (0.65, 0.85))
    self.assertEqual((m['up_mae_lo90'], m['up_mae_hi90']), (51.0, 61.0))
    self.assertEqual(m['down_r2_casa-a'], 0.4)
    self.assertEqual(m['jit_mae_casa-b'], 30.0)
    self.assertEqual(m['lat_pinball_q90'], 11.2)

  def test_valor_ausente_fica_de_fora(self):
    m = V.metricas_do_pipeline(avaliacao())
    self.assertNotIn('down_r2_casa-b', m)       # R² None: o prédio não teve como ser medido
    self.assertNotIn('down_pinball_q90', m)     # download não tem quantis
    self.assertFalse([k for k in m if 'mae_log' in k])
    self.assertEqual(V.metricas_do_pipeline({}), {})


class ComBancoTemporario(unittest.TestCase):
  """Cada teste com um mlflow.db próprio; 25 árvores no modelo da régua."""

  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    cls.conjs = {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}
    cls.pacote = P.treinar(cls.conjs, FEATURES, POR_BANDA)

  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    self.tmp = tmp.name
    self.addCleanup(mlflow.set_tracking_uri, mlflow.get_tracking_uri())
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{self.tmp}/mlflow.db'})
    env.start()
    self.addCleanup(env.stop)

  def registrar(self):
    versao = {'features': FEATURES, 'denominador': POR_BANDA, 'cobertura': {'nivel': 'proxy'}}
    return V.registrar('v9', versao, self.conjs, avaliacao(), self.pacote, ['abc123', 'def456'])


class TestRegistrar(ComBancoTemporario):
  def test_run_tem_parametros_tags_dado_e_arquivos(self):
    cli = R.cliente()
    run = cli.get_run(self.registrar())
    self.assertEqual(run.info.status, 'FINISHED')
    self.assertEqual(run.info.run_name, 'v9-pipeline')
    experimento = cli.get_experiment(run.info.experiment_id)
    self.assertEqual(experimento.name, 'MLflow Wifi Pipeline')
    self.assertEqual(experimento.artifact_location, os.path.join(self.tmp, 'mlruns', 'pipeline'))
    p = run.data.params
    self.assertEqual((p['modelo'], p['features'], p['cobertura_tr069']), ('v9', ','.join(FEATURES), 'proxy'))
    self.assertEqual((p['fingerprints'], p['versao_pacote']), ('abc123,def456', P.VERSAO_PACOTE))
    for chave in ('versao_tabela', 'versao_catalogo', 'removidas_por_vazamento', 'datasets', 'denominador'):
      self.assertIn(chave, p)
    tags = run.data.tags
    self.assertEqual((tags['modelo'], tags['metrica_principal']), ('v9', 'erro_das_previsoes'))
    self.assertEqual((tags['versao_comodo'], tags['versao_regua']), ('v-c', 'r1'))
    self.assertNotIn('atual', tags)   # atual e ativo são do experimento do Studio
    self.assertNotIn('ativo', tags)
    m = run.data.metrics
    for chave in ('down_pooled', 'down_mae', 'down_pooled_lo90', 'down_r2_casa-a', 'lat_cobertura_q90',
                  'lat_pinball_q90', 'comodo_nota', 'atende_completo'):
      self.assertIn(chave, m)
    dado = run.inputs.dataset_inputs[0]
    self.assertEqual((dado.dataset.name, len(dado.dataset.digest)), ('qoe-wifi', 8))
    self.assertEqual([t.value for t in dado.tags], ['treino'])
    self.assertEqual(sorted(a.path for a in cli.list_artifacts(run.info.run_id)),
                     ['avaliacao.json', 'cobertura_tr069.json', 'posicoes.json', 'receita.json'])

  def test_pacote_do_run_carrega_e_preve_igual(self):
    volta = PM.carregar(f'runs:/{self.registrar()}/{PM.NOME}')
    linhas = self.conjs[DN].df.head(7)
    np.testing.assert_allclose(P.prever(volta, linhas)[0].to_numpy(), P.prever(self.pacote, linhas)[0].to_numpy(),
                               rtol=1e-12)

  def test_nao_cria_o_experimento_do_studio(self):
    self.registrar()
    self.assertIsNone(R.cliente().get_experiment_by_name(R.EXPERIMENTO))

  def test_falha_ao_gravar_o_pacote_deixa_o_run_failed(self):
    with mock.patch.object(V.core_pacote_mlflow, 'gravar', side_effect=RuntimeError('disco cheio')):
      with self.assertRaisesRegex(RuntimeError, 'disco cheio'):
        self.registrar()
    cli = R.cliente()
    runs = cli.search_runs([cli.get_experiment_by_name(V.EXPERIMENTO).experiment_id])
    self.assertEqual([r.info.status for r in runs], ['FAILED'])


class TestMain(unittest.TestCase):
  def setUp(self):
    self.conjs = {alvo: mock.Mock(alvo=alvo, datasets=['a.csv'], avisos=[], tabela={'prefixos': {}, 'colunas': {}},
                                  catalogo=()) for alvo in P.PREFIXOS}
    medida = dict(avaliacao(), removidas_por_vazamento=['router_tx_bytes'])
    self.m = {}
    for nome, alvo, extra in (
        ('registro', (V.core_modelos, 'carregar'), {'return_value': REGISTRO}),
        ('carregar', (V.core_carga, 'carregar'), {'side_effect': lambda alvo, ids=None: self.conjs[alvo]}),
        ('descobertos', (V.core_carga, 'descobertos'),
         {'return_value': [{'id': 'a.csv', 'fingerprint': 'abc123', 'usable': True}]}),
        ('avaliar', (V.core_completa, 'avaliacao_completa'), {'return_value': medida}),
        ('treinar', (V.core_pacote, 'treinar'), {'return_value': 'pacote'}),
        ('cobertura', (V.core_features, 'cobertura_tr069'), {'return_value': {'nivel': 'proxy'}}),
        ('registrar', (V, 'registrar'), {'return_value': 'run-1'})):
      p = mock.patch.object(*alvo, **extra)
      self.m[nome] = p.start()
      self.addCleanup(p.stop)
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': 'sqlite:////nao/usado.db'})
    env.start()
    self.addCleanup(env.stop)
    os.environ.pop('MODELO', None)
    os.environ.pop('DATASETS', None)

  def test_versao_inexistente_sai_antes_de_carregar_dados(self):
    with mock.patch.dict(os.environ, {'MODELO': 'nao-existe'}):
      with self.assertRaises(SystemExit) as erro:
        V.main()
    self.assertIn('v1', str(erro.exception))
    self.m['carregar'].assert_not_called()
    self.m['registrar'].assert_not_called()

  def test_avalia_com_as_features_da_versao_e_treina_sem_as_de_vazamento(self):
    V.main()
    conjunto, ambiente, features, denominador = self.m['avaliar'].call_args.args
    self.assertEqual(conjunto(LAT), self.conjs[LAT])
    self.assertIsNone(ambiente)
    self.assertEqual(features, FEATURES + ['router_tx_bytes'])
    self.assertEqual(denominador, POR_BANDA)
    self.assertEqual(self.m['treinar'].call_args.args[1:], (FEATURES, POR_BANDA))
    nome, versao, conjs, medida, pacote, fingerprints = self.m['registrar'].call_args.args
    self.assertEqual((nome, pacote, fingerprints), ('v1', 'pacote', ['abc123']))
    self.assertEqual(versao, {'features': FEATURES + ['router_tx_bytes'], 'denominador': POR_BANDA,
                              'cobertura': {'nivel': 'proxy'}})
    self.assertEqual(medida['removidas_por_vazamento'], ['router_tx_bytes'])

  def test_datasets_da_variavel_de_ambiente(self):
    with mock.patch.dict(os.environ, {'DATASETS': 'a.csv,b.zip'}):
      V.main()
    self.assertEqual(self.m['carregar'].call_args.kwargs['ids'], ['a.csv', 'b.zip'])


if __name__ == '__main__':
  unittest.main()

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import rastreio, treino  # noqa: E402

ALVO = 'speedtest_down_mbps'
FEATURES = ['router_snr', 'router_signal_dbm']


def pedido(datasets, features=FEATURES, **extra):
  return treino.Pedido(alvo=ALVO, datasets=list(datasets), features=list(features),
                       hiper=extra.pop('hiper', {'n_estimators': 5}), **extra)


class TestPreparar(unittest.TestCase):
  def test_um_predio_so_e_recusado(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'alfa-2'], semente=1))
      with self.assertRaisesRegex(ValueError, 'prédio'):
        treino.preparar(pedido(['a.csv']))

  def test_feature_ausente_e_recusada(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      with self.assertRaisesRegex(ValueError, 'nao_existe'):
        treino.preparar(pedido(['a.csv'], ['router_snr', 'nao_existe']))

  def test_datasets_sobrepostos_sao_recusados(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      A.gravar_csv(p.data, 'parte.csv', A.frame(['alfa-1'], semente=1))
      with self.assertRaisesRegex(ValueError, 'sobrepostos'):
        treino.preparar(pedido(['a.csv', 'parte.csv']))

  def test_alvo_como_feature_e_hiper_desconhecido_sao_recusados(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      with self.assertRaises(ValueError):
        treino.preparar(pedido(['a.csv'], ['router_snr', 'speedtest_up_mbps']))
      with self.assertRaises(ValueError):
        treino.preparar(pedido(['a.csv'], hiper={'nao_existe': 1}))

  def test_vazamento_marcado_e_regras_completas(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      prep = treino.preparar(pedido(['a.csv'], ['router_snr', 'router_tx_retries']))
      self.assertTrue(prep.contem_vazamento)
      self.assertEqual(prep.pedido.regras, {'descartar_alvo_zero': True, 'teto_wan': False})
      self.assertFalse(treino.preparar(pedido(['a.csv'])).contem_vazamento)


class TestExecutar(unittest.TestCase):
  def test_treino_registra_run_metricas_artefatos_e_versao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1', 'gama-1'], n=15, semente=1))
      etapas = []
      r = treino.executar(treino.preparar(pedido(['a.csv'])), etapas.append)
      self.assertTrue(etapas)
      cli = rastreio.cliente()
      run = cli.get_run(r['run_id'])
      self.assertEqual(run.info.status, 'FINISHED')
      self.assertEqual(run.data.tags['tipo'], 'treino')
      self.assertNotIn('contem_vazamento', run.data.tags)
      self.assertEqual(run.data.params['features'], 'router_snr,router_signal_dbm')
      self.assertEqual(run.data.params['hiper__n_estimators'], '5')
      self.assertEqual(run.data.params['regra__descartar_alvo_zero'], 'True')
      self.assertTrue(run.data.params['fingerprints'].startswith('a.csv:'))
      for k in ('mae', 'rmse', 'r2', 'mae__alfa', 'mae__beta', 'mae__gama', 'linhas', 'predios'):
        self.assertIn(k, run.data.metrics)
      self.assertEqual(run.data.metrics['predios'], 3)
      artefatos = {a.path for a in cli.list_artifacts(r['run_id'])}
      self.assertTrue({'por_predio.csv', 'previsoes_fora_do_fold.csv', 'features.json'} <= artefatos)
      self.assertEqual(r['versao'], '1')
      self.assertEqual(cli.get_model_version('studio-speedtest_down_mbps', '1').run_id, r['run_id'])
      self.assertTrue(r['link_run'].startswith('http://127.0.0.1:5100/#/experiments/'))


if __name__ == '__main__':
  unittest.main()

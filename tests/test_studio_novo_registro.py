import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import rastreio, registro, treino  # noqa: E402

ALVO = 'speedtest_down_mbps'


def treinar(datasets=('a.csv',), features=('router_snr', 'router_signal_dbm')):
  pedido = treino.Pedido(alvo=ALVO, datasets=list(datasets), features=list(features), hiper={'n_estimators': 5})
  return treino.executar(treino.preparar(pedido))


class TestRegistro(unittest.TestCase):
  def test_promover_move_o_alias(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      self.assertIsNone(registro.ativo(ALVO))
      self.assertEqual(registro.versoes(ALVO), [])
      treinar()
      treinar()
      self.assertEqual(registro.promover(ALVO, '1')['versao'], '1')
      self.assertEqual(registro.promover(ALVO, '2')['versao'], '2')
      self.assertEqual(registro.ativo(ALVO)['features'], ['router_snr', 'router_signal_dbm'])
      self.assertEqual([v['versao'] for v in registro.versoes(ALVO)], ['2', '1'])
      with self.assertRaises(KeyError):
        registro.promover(ALVO, '9')

  def test_comparar_avisa_vazamento_e_mesma_versao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      treinar(features=('router_snr', 'router_tx_retries'))
      comp = registro.comparar(ALVO, '1')
      self.assertIsNone(comp['ativo'])
      self.assertTrue(any('vazamento' in a for a in comp['avisos']))
      registro.promover(ALVO, '1')
      self.assertTrue(any('já é a @ativo' in a for a in registro.comparar(ALVO, '1')['avisos']))

  def test_reavaliar_cria_run_sem_versao_nova_e_avisa_sobreposicao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['gama-1'], semente=4))
      treinar()
      prep = registro.preparar_reavaliacao(ALVO, '1', ['a.csv', 'b.csv'])
      self.assertEqual(len(prep['avisos']), 1)
      self.assertIn('a.csv', prep['avisos'][0])
      r = registro.executar_reavaliacao(prep)
      run = rastreio.cliente().get_run(r['run_id'])
      self.assertEqual(run.data.tags['tipo'], 'reavaliacao')
      self.assertEqual(run.data.tags['modelo_versao'], 'studio-speedtest_down_mbps/1')
      self.assertIn('mae__gama', run.data.metrics)
      self.assertEqual([v['versao'] for v in registro.versoes(ALVO)], ['1'])

  def test_reavaliar_recusa_feature_ausente(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['gama-1'], semente=4).drop(columns=['router_signal_dbm']))
      treinar()
      with self.assertRaisesRegex(ValueError, 'router_signal_dbm'):
        registro.preparar_reavaliacao(ALVO, '1', ['b.csv'])


if __name__ == '__main__':
  unittest.main()

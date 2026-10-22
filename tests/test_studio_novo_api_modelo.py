import os
import sys
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import api  # noqa: E402

LOCAL = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))
ALVO = 'speedtest_down_mbps'


class TestApiModelo(unittest.TestCase):
  def setUp(self):
    api.dados_mudaram()

  def tearDown(self):
    api.dados_mudaram()

  def test_treino_vira_job_versao_e_promocao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      api.dados_mudaram()
      self.assertTrue(api.mlflow_status()['ok'])
      corpo = api.PedidoTreino(alvo=ALVO, datasets=['a.csv'], features=['router_snr'], hiper={'n_estimators': 5})
      final = A.esperar_job(api.treinos_iniciar(corpo, LOCAL)['id'])
      self.assertEqual(final['status'], 'concluído', final.get('erro'))
      self.assertEqual(final['resultado']['versao'], '1')
      self.assertEqual(api.modelos_alvo(ALVO)['versoes'][0]['versao'], '1')
      self.assertEqual(api.modelos_promover_comparar(ALVO, '1')['candidata']['versao'], '1')
      api.modelos_promover(ALVO, api.Promocao(versao='1'), LOCAL)
      self.assertEqual(api.modelos_alvo(ALVO)['ativo']['versao'], '1')
      self.assertEqual(api.job(final['id'])['status'], 'concluído')
      api.dados_mudaram()

  def test_treino_com_um_predio_da_422_sem_job(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      api.dados_mudaram()
      antes = len(api.jobs()['jobs'])
      with self.assertRaises(HTTPException) as ctx:
        api.treinos_iniciar(api.PedidoTreino(alvo=ALVO, datasets=['a.csv'], features=['router_snr']), LOCAL)
      self.assertEqual(ctx.exception.status_code, 422)
      self.assertEqual(len(api.jobs()['jobs']), antes)
      api.dados_mudaram()

  def test_alvo_e_versao_desconhecidos(self):
    with A.pastas_temporarias(), A.mlflow_temporario():
      with self.assertRaises(HTTPException) as ctx:
        api.modelos_alvo('qoe_dw_score')
      self.assertEqual(ctx.exception.status_code, 404)
      with self.assertRaises(HTTPException) as ctx:
        api.modelos_promover(ALVO, api.Promocao(versao='7'), LOCAL)
      self.assertEqual(ctx.exception.status_code, 404)

  def test_padroes_do_formulario(self):
    padroes = api.modelos_padroes()
    self.assertEqual(padroes['modelos']['RandomForest']['n_estimators'], 600)
    self.assertEqual(padroes['regras'], {'descartar_alvo_zero': True, 'teto_wan': False})


if __name__ == '__main__':
  unittest.main()

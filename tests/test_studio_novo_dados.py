import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import dados  # noqa: E402


class TestPayload(unittest.TestCase):
  def test_linhas_datasets_inutilizaveis_e_envelope(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], n=6, semente=1))
      A.gravar_csv(p.data, 'quebrado.csv', A.frame(['alfa-1'], n=2).drop(columns=['latency_ms']))
      payload = dados.montar_payload()
      self.assertEqual(len(payload['rows']), 12)
      r = payload['rows'][0]
      self.assertEqual({k: r[k] for k in ('ds', 'gen', 'b', 'p', 'n', 'combo')},
                       {'ds': 'a.csv', 'gen': 'current', 'b': 'alfa', 'p': 'alfa-1', 'n': 1, 'combo': 'c1'})
      self.assertEqual([d['id'] for d in payload['datasets']], ['a.csv'])
      self.assertEqual(payload['datasets'][0]['origem'], 'data')
      self.assertEqual(payload['datasets'][0]['buildings'], ['alfa', 'beta'])
      self.assertEqual([d['id'] for d in payload['inutilizaveis']], ['quebrado.csv'])
      self.assertEqual(set(payload['buildings']), {'alfa', 'beta', 'gama'})
      self.assertEqual(payload['envelopes']['alfa']['w'], 400.0)
      self.assertIn('Chamada de vídeo', payload['aplicacoes'])

  def test_local_desconhecido_vira_aviso(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'zeta-1'], n=3, semente=1))
      payload = dados.montar_payload()
      self.assertEqual(len(payload['rows']), 3)
      self.assertEqual(payload['locaisDesconhecidos'],
                       [{'dataset': 'a.csv', 'valores': ['zeta-1'], 'linhas': 3}])

  def test_com_conjunto_marca_enabled(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], n=3, semente=2))
      payload = dados.montar_payload()
      com = dados.com_conjunto(payload, ['b.csv'])
      self.assertEqual({d['id']: d['enabled'] for d in com['datasets']}, {'a.csv': False, 'b.csv': True})
      self.assertIsNot(com['datasets'], payload['datasets'])


if __name__ == '__main__':
  unittest.main()

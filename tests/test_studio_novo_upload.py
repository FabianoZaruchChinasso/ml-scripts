import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import upload  # noqa: E402


def guardar(df, nome='novo.csv'):
  return upload.guardar(nome, df.to_csv(index=False).encode('utf-8'))


class TestUpload(unittest.TestCase):
  def test_confirmar_grava_em_uploads_e_nunca_em_data(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'base.csv', A.frame(['alfa-1'], semente=1))
      token = guardar(A.frame(['beta-1'], semente=5))
      r = upload.confirmar(token, 'novo.csv')
      self.assertEqual(r, {'dataset': 'novo.csv', 'predios': [], 'linhas': 12})
      self.assertTrue(os.path.exists(os.path.join(p.uploads, 'novo.csv')))
      self.assertEqual(sorted(os.listdir(p.data)), ['base.csv'])

  def test_nome_existente_em_data_ou_uploads_bloqueia(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'base.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.uploads, 'up.csv', A.frame(['gama-1'], semente=2))
      token = guardar(A.frame(['beta-1'], semente=5))
      self.assertIn('já existe data/base.csv', upload.previa(token, 'base.csv')['bloqueios'])
      self.assertIn('já existe .studio/uploads/up.csv', upload.previa(token, 'up.csv')['bloqueios'])

  def test_local_desconhecido_pede_cadastro_e_cadastra_no_config_do_studio(self):
    with A.pastas_temporarias() as p:
      token = guardar(A.frame(['villa_r1'], semente=7))
      previa = upload.previa(token, 'villa.csv')
      self.assertEqual([g['prefixo'] for g in previa['desconhecidos']], ['villa'])
      self.assertTrue(previa['bloqueios'])
      novo = {'chave': 'villa', 'rotulo': 'Villa', 'ambiente': 'domestico', 'prefixo': 'villa'}
      self.assertEqual(upload.previa(token, 'villa.csv', [novo])['bloqueios'], [])
      upload.confirmar(token, 'villa.csv', [novo])
      with open(p.predios_path, encoding='utf-8') as handle:
        self.assertIn('villa', json.load(handle)['predios'])

  def test_duplicata_bloqueia(self):
    with A.pastas_temporarias() as p:
      df = A.frame(['alfa-1'], semente=1)
      A.gravar_csv(p.data, 'base.csv', df)
      token = guardar(df)
      previa = upload.previa(token, 'copia.csv')
      self.assertEqual(previa['duplicata_de'], 'base.csv')
      with self.assertRaises(ValueError):
        upload.confirmar(token, 'copia.csv')

  def test_sem_colunas_obrigatorias_bloqueia(self):
    with A.pastas_temporarias():
      token = guardar(A.frame(['alfa-1']).drop(columns=['jitter_ms']))
      previa = upload.previa(token, 'x.csv')
      self.assertTrue(any('jitter_ms' in b for b in previa['bloqueios']))


if __name__ == '__main__':
  unittest.main()

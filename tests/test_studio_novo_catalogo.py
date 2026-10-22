import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import catalogo  # noqa: E402


class TestDescoberta(unittest.TestCase):
  def test_duplicata_contido_ignorado_inutilizavel_e_origem(self):
    with A.pastas_temporarias() as p:
      base = A.frame(['alfa-1', 'beta-1'], semente=1)
      A.gravar_csv(p.data, 'a.csv', base)
      A.gravar_csv(p.data, 'a-fix.csv', base)
      A.gravar_csv(p.data, 'c.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'x-qoe.csv', base)
      A.gravar_csv(p.data, 'sem_alvo.csv', base.drop(columns=['latency_ms']))
      A.gravar_csv(p.uploads, 'd.csv', A.frame(['gama-1'], semente=2))
      A.gravar_csv(p.uploads, 'a.csv', A.frame(['gama-1'], semente=3))
      itens = catalogo.descobrir()
      por_id = {}
      for d in itens:
        por_id.setdefault(d['id'], []).append(d)
      self.assertNotIn('x-qoe.csv', por_id)
      self.assertFalse(por_id['sem_alvo.csv'][0]['usable'])
      self.assertIn('latency_ms', por_id['sem_alvo.csv'][0]['error'])
      self.assertEqual([d['origem'] for d in por_id['a.csv']], ['data', 'upload'])
      self.assertFalse(por_id['a.csv'][1]['usable'])
      self.assertEqual(por_id['d.csv'][0]['origem'], 'upload')
      self.assertEqual(catalogo.duplicatas(itens), {'a.csv': 'a-fix.csv'})
      self.assertIn(catalogo.contidos(itens)['c.csv'], {'a.csv', 'a-fix.csv'})
      self.assertEqual(catalogo.ids_padrao(itens), ['a-fix.csv', 'd.csv'])

  def test_descobertos_fica_em_cache_ate_esquecer(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      self.assertEqual([d['id'] for d in catalogo.descobertos()], ['a.csv'])
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], semente=2))
      self.assertEqual([d['id'] for d in catalogo.descobertos()], ['a.csv'])
      catalogo.esquecer()
      self.assertEqual([d['id'] for d in catalogo.descobertos()], ['a.csv', 'b.csv'])

  def test_le_zip_com_um_csv(self):
    with A.pastas_temporarias() as p:
      buffer = io.StringIO()
      A.frame(['alfa-1'], n=3).to_csv(buffer, index=False)
      with zipfile.ZipFile(os.path.join(p.data, 'z.zip'), 'w') as arquivo:
        arquivo.writestr('z.csv', buffer.getvalue())
      itens = catalogo.descobrir()
      self.assertEqual([(d['id'], d['usable'], d['rows']) for d in itens], [('z.zip', True, 3)])


if __name__ == '__main__':
  unittest.main()

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import catalogo, conjunto  # noqa: E402


class TestConjunto(unittest.TestCase):
  def test_sem_arquivo_usa_o_conjunto_padrao(self):
    with A.pastas_temporarias() as p:
      df = A.frame(['alfa-1'], semente=1)
      A.gravar_csv(p.data, 'a.csv', df)
      A.gravar_csv(p.data, 'a-fix.csv', df)
      self.assertEqual(conjunto.ler(), ['a-fix.csv'])

  def test_gravar_e_ler(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], semente=2))
      self.assertEqual(conjunto.gravar(['b.csv', 'a.csv']), ['a.csv', 'b.csv'])
      self.assertEqual(conjunto.ler(), ['a.csv', 'b.csv'])
      with open(os.path.join(p.estado, 'conjunto.json'), encoding='utf-8') as handle:
        self.assertEqual(json.load(handle), {'datasets': ['a.csv', 'b.csv']})

  def test_id_desconhecido_recusa(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      with self.assertRaises(ValueError):
        conjunto.gravar(['nao-existe.csv'])

  def test_id_que_sumiu_sai_na_leitura(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], semente=2))
      conjunto.gravar(['a.csv', 'b.csv'])
      os.remove(os.path.join(p.data, 'b.csv'))
      catalogo.esquecer()
      self.assertEqual(conjunto.ler(), ['a.csv'])

  def test_arquivo_ilegivel_cai_no_padrao(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      os.makedirs(p.estado, exist_ok=True)
      with open(os.path.join(p.estado, 'conjunto.json'), 'w', encoding='utf-8') as handle:
        handle.write('isto não é json')
      self.assertEqual(conjunto.ler(), ['a.csv'])


if __name__ == '__main__':
  unittest.main()

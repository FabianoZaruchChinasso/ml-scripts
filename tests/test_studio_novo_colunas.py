import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import catalogo, colunas  # noqa: E402


class TestColunas(unittest.TestCase):
  def test_numericas_comuns_sem_alvos_nem_excluidas(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], n=3, semente=2).drop(columns=['router_signal_dbm']))
      nomes = {c['coluna']: c for c in colunas.disponiveis(['a.csv', 'b.csv'])}
      self.assertIn('router_snr', nomes)
      self.assertNotIn('router_signal_dbm', nomes)
      self.assertNotIn('speedtest_down_mbps', nomes)
      self.assertNotIn('combo', nomes)
      self.assertTrue(nomes['router_tx_retries']['vazamento'])
      self.assertFalse(nomes['router_snr']['vazamento'])
      self.assertEqual(nomes['router_snr']['preenchimento'], 1.0)

  def test_prefixo_de_vazamento(self):
    cfg = colunas.carregar()
    self.assertTrue(colunas.com_vazamento('download_bytes', cfg))
    self.assertFalse(colunas.com_vazamento('router_snr', cfg))


class TestSelecao(unittest.TestCase):
  def test_usaveis_por_id_recusa_desconhecido(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      self.assertEqual([d['id'] for d in catalogo.usaveis_por_id(['a.csv'])], ['a.csv'])
      with self.assertRaises(ValueError):
        catalogo.usaveis_por_id(['a.csv', 'x.csv'])

  def test_sobreposicoes(self):
    with A.pastas_temporarias() as p:
      base = A.frame(['alfa-1', 'beta-1'], semente=1)
      A.gravar_csv(p.data, 'a.csv', base)
      A.gravar_csv(p.data, 'copia.csv', base)
      A.gravar_csv(p.data, 'parte.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'outro.csv', A.frame(['gama-1'], semente=9))
      self.assertEqual(catalogo.sobreposicoes(['a.csv', 'outro.csv']), [])
      self.assertEqual(catalogo.sobreposicoes(['a.csv', 'copia.csv']), ['a.csv e copia.csv têm os mesmos alvos'])
      self.assertEqual(catalogo.sobreposicoes(['parte.csv', 'a.csv']), ['parte.csv está contido em a.csv'])


if __name__ == '__main__':
  unittest.main()

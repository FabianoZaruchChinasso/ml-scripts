import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import portao as T
from test_studio_features import TABELA, frame

RESULTADOS = {'melhor', 'pior', 'empate'}


def por_alvo(*resultados):
  return {alvo: {'veredito': {'resultado': r, 'motivo': 'x'}} for alvo, r in zip(T.ALVOS, resultados)}


class TestDecidir(unittest.TestCase):
  def test_pior_em_um_alvo_nao_promove(self):
    d = T.decidir(por_alvo('melhor', 'melhor', 'pior', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (False, 'pior'))
    self.assertIn('latency_ms', d['motivo'])

  def test_melhor_sem_pior_promove(self):
    d = T.decidir(por_alvo('empate', 'melhor', 'empate', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (True, 'melhor'))
    self.assertIn('speedtest_up_mbps', d['motivo'])

  def test_so_empates_mantem(self):
    d = T.decidir(por_alvo('empate', 'empate', 'empate', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (False, 'empate'))


class TestMesmaDefinicao(unittest.TestCase):
  def test_situacoes(self):
    self.assertEqual(T.situacao_mesma_definicao(['b', 'a'], ['a', 'b']), 'igual')
    self.assertEqual(T.situacao_mesma_definicao(['a', 'b', 'c'], ['a', 'b']), 'dado_novo')
    self.assertEqual(T.situacao_mesma_definicao(['a', 'c'], ['a', 'b']), 'dados_diferentes')
    self.assertEqual(T.situacao_mesma_definicao(['a'], ['a', 'b']), 'dados_diferentes')

  def test_decidir_dado_novo_promove_sem_pior(self):
    d = T.decidir_dado_novo(por_alvo('empate', 'empate', 'empate', 'empate'))
    self.assertEqual((d['promover'], d['resultado']), (True, 'dado_novo'))
    d = T.decidir_dado_novo(por_alvo('melhor', 'empate', 'empate', 'pior'))
    self.assertEqual((d['promover'], d['resultado']), (False, 'pior'))
    self.assertIn('jitter_ms', d['motivo'])

  def test_decisoes_sem_comparacao(self):
    for situacao in ('igual', 'dados_diferentes'):
      with self.subTest(situacao=situacao):
        d = T.decidir_sem_comparar(situacao)
        self.assertEqual((d['promover'], d['resultado']), (False, situacao))
    self.assertIn('ativar_mlflow.py', T.decidir_sem_comparar('dados_diferentes')['motivo'])


class TestComparar(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    cls.conjs = {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}

  def test_quatro_alvos_com_veredito(self):
    r = T.comparar(self.conjs, {'features': ['router_snr', 'router_signal_dbm', 'radio'], 'denominador': None},
                   {'features': ['router_snr'], 'denominador': None})
    self.assertEqual(list(r), list(T.ALVOS))
    for alvo in A.ALVOS_COM_TETO:
      self.assertIn('intervalo', r[alvo]['delta_mae'])
      self.assertIn(r[alvo]['veredito']['resultado'], RESULTADOS)
    for alvo in ('latency_ms', 'jitter_ms'):
      self.assertIn('intervalo', r[alvo]['delta_pinball'])
      self.assertIsInstance(r[alvo]['cobertura'], float)
      self.assertIn(r[alvo]['veredito']['resultado'], RESULTADOS)

  def test_definicao_contra_ela_mesma_tem_diferenca_zero(self):
    d = {'features': ['router_snr', 'radio'], 'denominador': None}
    r = T.comparar(self.conjs, d, d)
    self.assertEqual([r[a]['delta_mae']['valor'] for a in A.ALVOS_COM_TETO], [0.0, 0.0])
    self.assertEqual([r[a]['delta_pinball']['valor'] for a in ('latency_ms', 'jitter_ms')], [0.0, 0.0])

  def test_denominador_por_alvo_chega_na_previsao(self):
    den = {'speedtest_down_mbps': {'coluna': 'router_snr', 'radio': '5ghz'},
           'speedtest_up_mbps': {'coluna': 'router_snr', 'radio': '5ghz'}}
    sem = T.comparar(self.conjs, {'features': ['router_signal_dbm', 'radio'], 'denominador': None},
                     {'features': ['router_signal_dbm', 'radio'], 'denominador': None})
    com = T.comparar(self.conjs, {'features': ['router_signal_dbm', 'radio'], 'denominador': den},
                     {'features': ['router_signal_dbm', 'radio'], 'denominador': None})
    self.assertEqual(sem['speedtest_down_mbps']['delta_mae']['valor'], 0.0)
    self.assertNotEqual(com['speedtest_down_mbps']['delta_mae']['valor'], 0.0)

  def test_dado_novo_com_todo_o_dado_antigo_tem_diferenca_zero(self):
    d = {'features': ['router_snr', 'radio'], 'denominador': None}
    r = T.comparar_dado_novo(self.conjs, d, ids_antigos=['a.csv'])   # tudo é antigo: as duas receitas são iguais
    self.assertEqual(list(r), list(T.ALVOS))
    self.assertEqual([r[a]['delta_mae']['valor'] for a in A.ALVOS_COM_TETO], [0.0, 0.0])
    self.assertEqual([r[a]['delta_pinball']['valor'] for a in ('latency_ms', 'jitter_ms')], [0.0, 0.0])

  def test_dado_novo_compara_nas_mesmas_linhas(self):
    conjs = {alvo: C.preparar({'a.csv': frame(seed=1), 'b.csv': frame(seed=2)}, alvo, TABELA) for alvo in P.PREFIXOS}
    d = {'features': ['router_snr', 'router_signal_dbm'], 'denominador': None}
    r = T.comparar_dado_novo(conjs, d, ids_antigos=['a.csv'])
    for alvo in A.ALVOS_COM_TETO:
      self.assertEqual(r[alvo]['delta_mae']['n'], int(conjs[alvo].df[alvo].notna().sum()))
      self.assertIn(r[alvo]['veredito']['resultado'], RESULTADOS)


if __name__ == '__main__':
  unittest.main()

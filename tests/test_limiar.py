import os
import sys
import unittest
from unittest import mock

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import limiar as L

LIM = {'dn': 5.0, 'up': 1.0, 'lat': 100, 'jit': 30}


def junta(y_dn, p_dn, y_up=None, p_up=None):
  n = len(y_dn)
  y_up = y_up if y_up is not None else [100.0] * n
  p_up = p_up if p_up is not None else [100.0] * n
  return pd.DataFrame({'_site': ['s'] * n, '_pos': [f'p{i}' for i in range(n)], 'y_dn': y_dn, 'p_dn': p_dn,
                       'y_up': y_up, 'p_up': p_up}, index=[f'a:{i}' for i in range(n)])


class TestEscolherFator(unittest.TestCase):
  def test_grade_vai_de_meio_a_dezesseis(self):
    self.assertEqual((L.FATORES[0], L.FATORES[-1]), (0.5, 16.0))
    self.assertIn(1.0, L.FATORES)

  def test_corrige_regressao_que_superestima(self):
    # Real: só as duas últimas atendem (>= 5). A regressão prevê 8 para quem entrega 1.
    # Com k = 1, tudo "atende" (acurácia balanceada 0,5). O primeiro fator da grade com
    # 5·k > 8 e 5·k <= 30 é 2^(0,75) = 1,6818: separa as classes por completo.
    j = junta([1.0, 1.0, 10.0, 10.0], [8.0, 8.0, 30.0, 30.0])
    self.assertEqual(L.escolher_fator(j, LIM), 1.6818)

  def test_empate_fica_com_o_mais_perto_de_um(self):
    j = junta([1.0, 10.0], [1.0, 10.0])
    self.assertEqual(L.escolher_fator(j, LIM), 1.0)

  def test_uma_classe_so_devolve_um(self):
    j = junta([10.0, 10.0], [1.0, 30.0])
    self.assertEqual(L.escolher_fator(j, LIM), 1.0)


ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}}, 'colunas': {a: {'classe': 'alvo'} for a in ALVOS}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']
APPS = {'Baixa': {'dn': 5.0, 'up': 1.0, 'lat': 100, 'jit': 30}, 'Alta': {'dn': 40.0, 'up': 10.0, 'lat': 100, 'jit': 30}}


def frame(n_por_local=12, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(0, 40, n)
  return pd.DataFrame({'local': np.repeat(LOCAIS, n_por_local), 'speedtest_down_mbps': 2 * snr + 0.1,
                       'speedtest_up_mbps': snr / 2 + 0.1, 'latency_ms': 10.0, 'jitter_ms': 2.0,
                       'router_snr': snr + rng.normal(0, 3, n)})


def conjuntos():
  f = frame()
  return (C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA, catalogo=()),
          C.preparar({'a.csv': f}, 'speedtest_up_mbps', TABELA, catalogo=()))


class Base(unittest.TestCase):
  def setUp(self):
    self._arvores = A.ARVORES
    A.ARVORES = 15

  def tearDown(self):
    A.ARVORES = self._arvores


class TestDecisoes(Base):
  def test_fator_de_cada_predio_vem_so_dos_outros(self):
    dn, up = conjuntos()
    chamadas = []
    original = L.prever_fora_do_fold

    def espiao(df, *args, **kwargs):
      chamadas.append(sorted(df['_site'].unique()))
      return original(df, *args, **kwargs)

    with mock.patch.object(L, 'prever_fora_do_fold', side_effect=espiao):
      dec = L.decisoes_atende(dn, up, ['router_snr'], APPS)
    todos = ['coworking', 'hotmilk', 'residencia']
    internas = [c for c in chamadas if c != todos]
    self.assertEqual(len(internas), 2 * len(todos))
    for site in todos:
      self.assertEqual(sum(site not in c for c in internas), 2)
    # O fator do prédio é o que escolher_fator dá sobre o LOGO interno sem ele.
    sem = {a: c.df[c.df['_site'] != 'hotmilk'] for a, c in (('dn', dn), ('up', up))}
    interno = A._juntar(dn=A.prever_fora_do_fold(sem['dn'], ['router_snr'], dn.alvo, []),
                        up=A.prever_fora_do_fold(sem['up'], ['router_snr'], up.alvo, []))
    for app, lim in APPS.items():
      fatores = dec[app].groupby('_site')['fator'].first().to_dict()
      self.assertEqual(fatores['hotmilk'], L.escolher_fator(interno, lim))
      self.assertEqual(list(dec[app].columns), ['_linha', '_site', '_pos', 'real', 'previsto', 'fator'])

  def test_sem_ajuste_reproduz_o_atende_bruto(self):
    dn, up = conjuntos()
    dec = L.decisoes_atende(dn, up, ['router_snr'], APPS, ajustar=False)
    bruto = A.atende(A.prever_fora_do_fold(dn.df, ['router_snr'], dn.alvo, []),
                     A.prever_fora_do_fold(up.df, ['router_snr'], up.alvo, []), APPS)
    r = L.resumir_decisoes(dec)
    self.assertEqual(r['por_aplicacao'], bruto['por_aplicacao'])
    self.assertTrue(all(v == 1.0 for app in r['fatores'].values() for v in app.values()))

  def test_fatores_de_producao_dentro_da_grade(self):
    dn, up = conjuntos()
    fatores = L.fatores_producao(dn, up, ['router_snr'], APPS)
    self.assertEqual(set(fatores), set(APPS))
    self.assertTrue(all(k in L.FATORES for k in fatores.values()))


def decisao(real, previsto, fator=1.0):
  n = len(real)
  return pd.DataFrame({'_linha': [f'a:{i}' for i in range(n)], '_site': ['s1', 's1', 's2', 's2'][:n],
                       '_pos': ['p1', 'p2', 'p3', 'p4'][:n], 'real': real, 'previsto': previsto, 'fator': fator})


class TestResumoEDelta(unittest.TestCase):
  def test_resumo_tem_a_forma_do_atende_e_os_fatores(self):
    dec = {'X': decisao([True, False, True, False], [True, False, False, True], 2.0)}
    r = L.resumir_decisoes(dec)
    self.assertEqual(r['por_aplicacao'], {'X': 0.5})
    self.assertEqual(r['media'], 0.5)
    self.assertEqual(r['fatores'], {'X': {'s1': 2.0, 's2': 2.0}})
    self.assertEqual(r['n'], 4)

  def test_delta_da_nova_perfeita_contra_base_que_diz_sempre_atende(self):
    real = [True, False, True, False]
    nova = {'X': decisao(real, real)}
    base = {'X': decisao(real, [True, True, True, True])}
    d = L.delta_decisoes(nova, base)
    self.assertEqual(d['valor'], 0.5)
    self.assertTrue(d['ajustado'])

  def test_delta_sem_aplicacao_com_duas_classes_e_none(self):
    tudo = {'X': decisao([True] * 4, [True] * 4)}
    self.assertIsNone(L.delta_decisoes(tudo, tudo))


if __name__ == '__main__':
  unittest.main()

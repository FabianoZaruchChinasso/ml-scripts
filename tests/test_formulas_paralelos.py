import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import features as F
from ml.core import formulas
from ml.studio import features as SF
from ml.studio import paralelos as P


class TestFormulas(unittest.TestCase):
  def test_aceita_aritmetica_e_funcoes(self):
    _, cols = formulas.analisar('log10(a) + (b - 2) * c / 3 - -a ** 2')
    self.assertEqual(cols, ['a', 'b', 'c'])

  def test_recusa_construcoes_do_python(self):
    for ruim in ('a.__class__', 'a[0]', '__import__("os")', 'open("x")', 'lambda: a', 'a if b else c',
                 'a < b', '[a]', 'a and b', 'a ** b', 'a ** 10', '"texto"', 'True + a', 'log10', 'log10(a, b)'):
      with self.assertRaises(ValueError, msg=ruim):
        formulas.analisar(ruim)

  def test_recusa_vazia_longa_e_sem_coluna(self):
    for ruim in ('', '   ', '1 + 2', 'a + ' * 100 + 'a'):
      with self.assertRaises(ValueError):
        formulas.analisar(ruim)

  def test_calcula_com_nan_fora_do_dominio(self):
    df = pd.DataFrame({'a': [4.0, 0.0, -1.0], 'b': [2.0, 0.0, 1.0]})
    s = formulas.calcular('a / b', df)
    self.assertEqual(s.iloc[0], 2.0)
    self.assertTrue(np.isnan(s.iloc[1]))
    self.assertTrue(np.isnan(formulas.calcular('log10(a)', df).iloc[2]))
    self.assertTrue(np.isnan(formulas.calcular('sqrt(a)', df).iloc[2]))

  def test_coluna_ausente(self):
    with self.assertRaises(ValueError):
      formulas.calcular('a + z', pd.DataFrame({'a': [1.0]}))


class TestDerivadasUsuario(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'derivadas.json')
    self.conhecidas = {'router_snr', 'router_noise', 'router_tx_bytes'}

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def gravar(self, nome='snr_menos_ruido', formula='router_snr - router_noise'):
    return F.gravar_derivada(nome, formula, 'teste', 'hipotese', None, None, self.conhecidas,
                             '2026-09-25', path=self.path)

  def test_grava_carrega_e_calcula(self):
    self.gravar()
    [d] = F.carregar_derivadas_usuario(self.path)
    self.assertEqual((d.nome, d.status, d.insumos), ('snr_menos_ruido', 'hipotese', ('router_snr', 'router_noise')))
    df = pd.DataFrame({'router_snr': [30.0], 'router_noise': [-90.0]})
    self.assertEqual(d.calcular(df).iloc[0], 120.0)

  def test_nome_imutavel_e_sem_colisao(self):
    self.gravar()
    with self.assertRaises(ValueError):
      self.gravar()
    with self.assertRaises(ValueError):
      self.gravar(nome='router_snr')
    with self.assertRaises(ValueError):
      self.gravar(nome='retry_por_pacote')

  def test_recusa_derivada_de_derivada_e_coluna_desconhecida(self):
    with self.assertRaises(ValueError):
      self.gravar(nome='x_derivada', formula='retry_por_pacote * 2')
    with self.assertRaises(ValueError):
      self.gravar(nome='x_desconhecida', formula='nao_existe * 2')

  def test_arquivo_ausente_e_catalogo_completo(self):
    self.assertEqual(F.carregar_derivadas_usuario(self.path), [])
    self.gravar()
    self.assertEqual(len(F.catalogo_completo(self.path)), len(F.CATALOGO) + 1)

  def test_status_invalido_nao_carrega(self):
    with open(self.path, 'w', encoding='utf-8') as h:
      json.dump({'derivadas': {'abc': {'formula': 'a', 'descricao': 'x', 'status': 'talvez'}}}, h)
    with self.assertRaises(ValueError):
      F.carregar_derivadas_usuario(self.path)


TABELA = {
  'prefixos': {'router_': {'classe': 'tr069'}, 'stats_80211_': {'classe': 'sniffer'}},
  'colunas': {'speedtest_down_mbps': {'classe': 'alvo'}, 'speedtest_up_mbps': {'classe': 'alvo'},
              'latency_ms': {'classe': 'alvo'}, 'jitter_ms': {'classe': 'alvo'},
              'local': {'classe': 'identificador'}, 'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}},
}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


def frame(n=30, seed=3):
  rng = np.random.default_rng(seed)
  total = len(LOCAIS) * n
  a = rng.uniform(1, 10, total)
  b = rng.uniform(1, 10, total)
  return pd.DataFrame({
    'local': np.repeat(LOCAIS, n),
    'speedtest_down_mbps': 5 * (a - b) + rng.normal(0, 0.5, total),
    'speedtest_up_mbps': a, 'latency_ms': rng.normal(20, 2, total), 'jitter_ms': rng.normal(3, 1, total),
    'router_a': a, 'router_b': b, 'router_ruido': rng.normal(0, 1, total),
    'router_tx_bytes': a * 100,
    'stats_80211_diferenca': a - b + rng.normal(0, 0.1, total),
    'stats_80211_ruido': rng.normal(0, 1, total),
  })


class TestParalelos(unittest.TestCase):
  def setUp(self):
    self._antes = (SF.ARVORES, P.ARVORES_PARALELOS)
    SF.ARVORES, P.ARVORES_PARALELOS = 20, 20
    self.conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, catalogo=())
    self.inv = SF.inventario(self.conj, ['router_ruido'])

  def tearDown(self):
    SF.ARVORES, P.ARVORES_PARALELOS = self._antes

  def test_assinatura_exige_mesmo_sinal_em_todos_os_predios(self):
    ass = {a['coluna']: a for a in P.assinatura(self.conj.df, 'stats_80211_diferenca',
                                                ['router_a', 'router_b', 'router_ruido'])}
    self.assertTrue(ass['router_a']['consistente'])
    self.assertTrue(all(v > 0 for v in ass['router_a']['por_local'].values()))
    self.assertTrue(all(v < 0 for v in ass['router_b']['por_local'].values()))
    self.assertFalse(ass['router_ruido']['consistente'])

  def test_veredito(self):
    self.assertEqual(P.veredito(True, True), 'candidata')
    self.assertEqual(P.veredito(True, False), 'so_laboratorio')
    self.assertEqual(P.veredito(False, True), 'ja_no_tr069')
    self.assertEqual(P.veredito(False, False), 'sem_paralelo')

  def test_n_efetivo_de_coluna_constante_por_posicao(self):
    posicoes = sorted(self.conj.df['_pos'].unique())
    df = self.conj.df.assign(manual=self.conj.df['_pos'].map({p: i for i, p in enumerate(posicoes)}))
    self.assertEqual(P.n_efetivo(df, 'manual'), {'grupos': 6, 'constante_por_posicao': True})

  def test_analisar_encontra_o_paralelo(self):
    r = P.analisar(self.conj, self.inv, ['router_ruido'])
    linha = next(c for c in r['colunas'] if c['coluna'] == 'stats_80211_diferenca')
    self.assertTrue(linha['importa'])
    self.assertTrue(linha['reconstroi'])
    self.assertEqual(linha['veredito'], 'candidata')
    self.assertIn('router_a', linha['sugestao'])
    self.assertNotIn('router_tx_bytes', [c['coluna'] for c in r['colunas']])

  def test_receita_boa_e_aprovada_e_ruim_fica_hipotese(self):
    boa = P.testar(self.conj, 'dif_tr069', 'router_a - router_b', ['router_ruido'], 'stats_80211_diferenca')
    self.assertEqual(boa['status'], 'aprovada', boa['criterios'])
    ruim = P.testar(self.conj, 'ruido_x2', 'router_ruido * 2', ['router_ruido'], 'stats_80211_diferenca')
    self.assertEqual(ruim['status'], 'hipotese')

  def test_receita_com_vazamento_ou_fora_do_tr069_nunca_e_aprovada(self):
    vaz = P.testar(self.conj, 'com_bytes', 'router_tx_bytes - router_b * 100', ['router_ruido'])
    self.assertEqual(vaz['status'], 'hipotese')
    self.assertTrue(vaz['vazamento'])
    lab = P.testar(self.conj, 'com_sniffer', 'stats_80211_diferenca * 1', ['router_ruido'])
    self.assertEqual((lab['classe'], lab['status']), (F.CLASSE_AUXILIAR, 'hipotese'))

  def test_previa_recusa_nome_existente(self):
    with self.assertRaises(ValueError):
      P.previa(self.conj, 'router_a', 'router_b * 2')

  def test_hipotese_fica_fora_dos_ajustes_automaticos(self):
    hip = F.Derivada('hip_x', ('router_a',), lambda df: df['router_a'] * 2, '', status='hipotese')
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA, catalogo=(hip,))
    inv = SF.inventario(conj, ['router_ruido'])
    self.assertTrue(next(c for c in inv['colunas'] if c['coluna'] == 'hip_x')['hipotese'])
    self.assertNotIn('hip_x', SF.elegiveis(inv))


if __name__ == '__main__':
  unittest.main()

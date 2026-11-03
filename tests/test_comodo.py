import copy
import json
import os
import sys
import types
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import comodo as C

# Mesmos valores de latência e jitter do perfil de norma (core/aplicacoes_norma.json).
LIM = {'Navegação': {'dn': 2, 'up': 0.5, 'lat': 800, 'jit': 100},
       'Chamada de vídeo': {'dn': 3.0, 'up': 3.8, 'lat': 200, 'jit': 50},
       'Streaming 4K': {'dn': 15, 'up': 0, 'lat': 500, 'jit': 100},
       'Jogo em nuvem': {'dn': 15, 'up': 1, 'lat': 80, 'jit': 10}}
REF = pd.DataFrame({'dn': [100.0], 'up': [100.0]}, index=pd.Index(['s1'], name='_site'))


def linhas(pos, n, dn, up, lat=10.0, jit=2.0, conc=1.0, site='s1'):
  return pd.DataFrame({'_pos': [pos] * n, '_site': [site] * n, C.DN: [float(dn)] * n, C.UP: [float(up)] * n,
                       C.LAT: [lat] * n, C.JIT: [jit] * n, 'concorrentes_mesmo_radio': [conc] * n})


def juntas(*partes):
  return pd.concat(partes, ignore_index=True)


def est(dn, up=100.0, lat=10.0, jit=2.0, site='s1'):
  """Estatísticas de uma posição só, no formato de C.estatisticas."""
  return pd.DataFrame({'_site': [site], 'n': [10], 'dn': [float(dn)], 'up': [float(up)], 'lat': [lat],
                       'jit': [jit]}, index=pd.Index(['p'], name='_pos'))


def classe(dn, up=100.0, lat=10.0, jit=2.0, lim=LIM):
  return C.classificar(est(dn, up, lat, jit), REF, lim)['classe'].iloc[0]


class TestVerdade(unittest.TestCase):
  def test_so_linhas_sozinhas(self):
    df = juntas(linhas('a', 10, 100, 100), linhas('a', 10, 1, 1, conc=2.0), linhas('a', 5, 1, 1, conc=np.nan),
                linhas('b', 10, 50, 50))
    tab, ref = C.verdade(df, LIM)
    self.assertEqual(ref.loc['s1', 'dn'], 100.0)
    self.assertEqual(tab.loc['a', 'classe'], 'bom')
    self.assertAlmostEqual(tab.loc['b', 'razao'], 0.5)
    self.assertEqual(tab.loc['b', 'classe'], 'degradado')

  def test_referencia_ignora_posicao_com_poucas_linhas(self):
    tab, ref = C.verdade(juntas(linhas('a', 10, 100, 100), linhas('b', 9, 400, 400)), LIM)
    self.assertEqual(ref.loc['s1', 'dn'], 100.0)
    self.assertAlmostEqual(tab.loc['b', 'razao'], 4.0)

  def test_predio_sem_referencia_levanta(self):
    with self.assertRaisesRegex(ValueError, 's1'):
      C.verdade(linhas('a', 9, 100, 100), LIM)

  def test_razao_e_o_pior_entre_download_e_upload(self):
    tab, _ = C.verdade(juntas(linhas('a', 10, 100, 100), linhas('b', 10, 100, 20)), LIM)
    self.assertAlmostEqual(tab.loc['b', 'razao'], 0.2)
    self.assertEqual(tab.loc['b', 'classe'], 'ruim')


class TestClassificar(unittest.TestCase):
  def test_cortes_de_capacidade(self):
    self.assertEqual([classe(25), classe(24.99), classe(75), classe(74.99), classe(100)],
                     ['degradado', 'ruim', 'bom', 'degradado', 'bom'])

  def test_falha_em_navegacao_e_ruim(self):
    self.assertEqual(classe(100, lat=900), 'ruim')
    self.assertEqual(classe(100, jit=101), 'ruim')

  def test_falha_em_chamada_e_no_maximo_degradado(self):
    self.assertEqual(classe(100, jit=60), 'degradado')
    self.assertEqual(classe(50, jit=60), 'degradado')
    self.assertEqual(classe(100, lat=250), 'degradado')

  def test_apto_para_jogo_nao_muda_a_classe(self):
    t = C.classificar(est(100, jit=20), REF, LIM)
    self.assertEqual(t['classe'].iloc[0], 'bom')
    self.assertFalse(bool(t['apto_jogo'].iloc[0]))
    self.assertTrue(bool(C.classificar(est(100, lat=50, jit=5), REF, LIM)['apto_jogo'].iloc[0]))

  def test_limiares_vem_do_perfil(self):
    lim = copy.deepcopy(LIM)
    lim['Navegação']['jit'] = 5
    self.assertEqual(classe(100, jit=6, lim=lim), 'ruim')

  def test_predio_sem_referencia_levanta(self):
    with self.assertRaisesRegex(ValueError, 's2'):
      C.classificar(est(100, site='s2'), REF, LIM)


def conjs_sinteticos():
  """3 prédios, 2 posições, 15 linhas cada; uma feature `x` que move os quatro alvos."""
  rng = np.random.default_rng(0)
  partes = []
  for s in ('s1', 's2', 's3'):
    for p in ('a', 'b'):
      x = rng.uniform(0, 1, 15)
      partes.append(pd.DataFrame({'_site': s, '_pos': f'{s}-{p}', 'x': x, C.DN: 10 + 90 * x, C.UP: 5 + 50 * x,
                                  C.LAT: 50 - 30 * x, C.JIT: 10 - 5 * x}))
  df = pd.concat(partes, ignore_index=True)
  df['_linha'] = [f'd:{i}' for i in range(len(df))]
  return {a: types.SimpleNamespace(df=df) for a in (C.DN, C.UP, C.LAT, C.JIT)}, df


class TestPrevisao(unittest.TestCase):
  def test_classe_prevista_usa_a_referencia_dada_e_a_mediana_dos_p90(self):
    prev = pd.DataFrame({'_pos': ['a'] * 3, '_site': ['s1'] * 3, 'dn': [50.0] * 3, 'up': [50.0] * 3,
                         'lat': [10.0, 10.0, 300.0], 'jit': [2.0] * 3})
    t = C.classe_prevista(prev, REF, LIM)
    # Com a referência das próprias previsões a razão seria 1,0; com a da verdade (100) é 0,5.
    self.assertAlmostEqual(t.loc['a', 'razao'], 0.5)
    self.assertEqual(t.loc['a', 'classe'], 'degradado')
    cheio = prev.assign(dn=100.0, up=100.0)
    # Mediana dos p90 previstos (10), não o maior (300): Chamada não falha.
    self.assertEqual(C.classe_prevista(cheio, REF, LIM).loc['a', 'classe'], 'bom')

  def test_prever_casa_os_quatro_alvos_por_linha(self):
    conjs, df = conjs_sinteticos()
    conjs[C.LAT] = types.SimpleNamespace(df=df.iloc[1:])
    prev = C.prever(conjs, ['x'], {a: [] for a in conjs})
    self.assertTrue({'_linha', '_site', '_pos', 'dn', 'up', 'lat', 'jit'} <= set(prev.columns))
    self.assertNotIn('d:0', set(prev['_linha']))
    self.assertEqual(len(prev), len(df) - 1)
    por_linha = df.set_index('_linha')['_pos']
    self.assertTrue((prev['_pos'].to_numpy() == por_linha.loc[prev['_linha']].to_numpy()).all())
    self.assertTrue((prev[['dn', 'up', 'lat', 'jit']] >= 0).all().all())

  def test_prever_sem_feature_utilizavel_levanta(self):
    conjs, _ = conjs_sinteticos()
    vazadas = {a: [] for a in conjs}
    vazadas[C.DN] = ['x']
    with self.assertRaisesRegex(ValueError, C.DN):
      C.prever(conjs, ['x'], vazadas)


def posicoes(real, previsto, site=None):
  site = site or ['s1'] * len(real)
  return pd.DataFrame({'_site': site, 'real': real, 'previsto': previsto},
                      index=pd.Index([f'p{i}' for i in range(len(real))], name='_pos'))


class TestMetricas(unittest.TestCase):
  def test_juntar_fica_com_as_posicoes_comuns_em_ordem(self):
    real = pd.DataFrame({'_site': ['s1'] * 3, 'classe': ['bom', 'ruim', 'bom'], 'apto_jogo': [True, False, True]},
                        index=pd.Index(['b', 'a', 'c'], name='_pos'))
    prev = real.loc[['a', 'b']].assign(classe=['ruim', 'degradado'])
    j = C.juntar(real, prev)
    self.assertEqual(j.index.tolist(), ['a', 'b'])
    self.assertEqual(j['real'].tolist(), ['ruim', 'bom'])
    self.assertEqual(j['previsto'].tolist(), ['ruim', 'degradado'])
    self.assertEqual(j['jogo_real'].tolist(), [False, True])

  def test_nota_conta_posicoes_juntas(self):
    # O prédio A só tem "bom" (como o Villa): numa média entre prédios ele valeria 0,5 fixo.
    pos_df = posicoes(['bom', 'bom', 'bom', 'bom', 'degradado', 'ruim'],
                      ['bom', 'bom', 'bom', 'bom', 'degradado', 'bom'], site=['A', 'A', 'A', 'B', 'B', 'B'])
    r = C.nota(pos_df, [np.arange(6)] * 3)
    self.assertAlmostEqual(r['nota'], 0.6667)

  def test_nota_jogo(self):
    pos_df = posicoes(['bom', 'bom'], ['bom', 'bom']).assign(jogo_real=[True, False], jogo_previsto=[True, True])
    self.assertAlmostEqual(C.nota_jogo(pos_df), 0.5)

  def test_comparar_da_o_veredito_pelo_intervalo(self):
    real = ['bom', 'ruim']
    certa, errada = posicoes(real, ['bom', 'ruim']), posicoes(real, ['bom', 'bom'])
    amostras = [np.arange(2)] * 3
    self.assertEqual(C.comparar(certa, errada, amostras)['resultado'], 'melhor')
    self.assertEqual(C.comparar(errada, certa, amostras)['resultado'], 'pior')
    self.assertEqual(C.comparar(certa, certa, amostras)['resultado'], 'empate')

  def test_confusao_e_erros_graves(self):
    m, graves = C.confusao(posicoes(['bom', 'ruim', 'degradado'], ['ruim', 'bom', 'degradado']))
    self.assertEqual(list(m.index), list(C.CLASSES))
    self.assertEqual(list(m.columns), list(C.CLASSES))
    self.assertEqual(int(m.loc['degradado', 'degradado']), 1)
    self.assertEqual(graves, 2)

  def test_contra_rotulo_converte_os_cinco_niveis(self):
    real = pd.DataFrame({'_site': ['s1'] * 5, 'classe': ['bom', 'bom', 'degradado', 'ruim', 'ruim']},
                        index=pd.Index(list('abcde'), name='_pos'))
    niveis = {'a': 'Excelente', 'b': 'Bom', 'c': 'Ok', 'd': 'Ruim', 'e': 'Ausente', 'z': 'Bom'}
    acuracia, m = C.contra_rotulo(real, niveis)
    self.assertAlmostEqual(acuracia, 1.0)
    self.assertEqual(int(m.loc['bom', 'bom']), 2)
    self.assertEqual(int(m.values.sum()), 5)


def df_e_prev():
  """2 prédios x 2 posições, 10 linhas sozinhas cada, mais 10 linhas com concorrência em s1-a.

  Verdade: s1-a bom, s1-b ruim (razão 0,2), s2-a bom, s2-b degradado (0,6). A previsão copia
  os valores reais, menos s2-b, que sai com download 100 (bom).
  """
  partes = []
  for s, dn_b in (('s1', 20.0), ('s2', 60.0)):
    partes.append(linhas(f'{s}-a', 10, 100, 100, site=s))
    partes.append(linhas(f'{s}-b', 10, dn_b, 100, site=s))
  partes.append(linhas('s1-a', 10, 1, 1, conc=2.0, site='s1'))
  df = juntas(*partes)
  df['_linha'] = [f'd:{i}' for i in range(len(df))]
  prev = pd.DataFrame({'_linha': df['_linha'], '_site': df['_site'], '_pos': df['_pos'], 'dn': df[C.DN],
                       'up': df[C.UP], 'lat': df[C.LAT], 'jit': df[C.JIT]})
  prev.loc[prev['_pos'] == 's2-b', 'dn'] = 100.0
  return df, prev


META = {'datasets': ['a.csv'], 'ambiente': 'todos'}


class TestBloco(unittest.TestCase):
  def test_de_previsoes_casa_por_linha(self):
    base = pd.DataFrame({'_linha': ['a', 'b', 'c'], '_site': ['s1'] * 3, '_pos': ['p', 'p', 'q']})
    pdn = pd.DataFrame({'_linha': ['a', 'b', 'c'], 'yhat': [1.0, 2.0, 3.0]})
    pup = pd.DataFrame({'_linha': ['c', 'b', 'a'], 'yhat': [30.0, 20.0, 10.0]})
    qlat = pd.DataFrame({'_linha': ['a', 'b'], 'q90': [50.0, 60.0], 'q90_bruto': [5.0, 6.0]})
    qjit = pd.DataFrame({'_linha': ['a', 'b', 'c'], 'q90': [70.0, 80.0, 90.0], 'q90_bruto': [7.0, 8.0, 9.0]})
    p = C.de_previsoes(base, pdn, pup, qlat, qjit).set_index('_linha')
    self.assertEqual(sorted(p.index), ['a', 'b'])
    self.assertEqual(p.loc['b', ['dn', 'up', 'lat', 'jit']].tolist(), [2.0, 20.0, 6.0, 8.0])
    self.assertEqual(p.loc['a', '_pos'], 'p')

  def test_tabela_posicoes_usa_so_linhas_sozinhas(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    self.assertEqual(tab.index.tolist(), ['s1-a', 's1-b', 's2-a', 's2-b'])
    self.assertEqual(tab['real'].tolist(), ['bom', 'ruim', 'bom', 'degradado'])
    # Sem o filtro, as 10 linhas com concorrência puxariam a mediana prevista de s1-a para 50,5.
    self.assertEqual(tab['previsto'].tolist(), ['bom', 'ruim', 'bom', 'bom'])
    self.assertAlmostEqual(tab.loc['s2-b', 'razao_prevista'], 1.0)
    self.assertEqual(set(tab.columns), {'_site', 'real', 'previsto', 'razao_prevista', 'apto_real', 'apto_previsto'})

  def test_bloco_tem_os_campos_e_e_serializavel(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    b = C.bloco(tab, tab.assign(previsto='bom', apto_previsto=False), META)
    self.assertEqual(set(b), {'versao_comodo', 'datasets', 'ambiente', 'nota', 'intervalo', 'piso', 'contra_piso',
                              'jogo', 'por_predio', 'confusao', 'graves', 'posicoes', 'piso_posicoes'})
    json.dumps(b)
    self.assertEqual(set(b['jogo']), {'nota', 'intervalo', 'piso'})
    self.assertEqual(set(b['jogo']['piso']), {'nota', 'intervalo'})
    # Todas as posições são aptas na verdade e na previsão; o piso nunca prevê apto.
    self.assertEqual(b['jogo']['nota'], 1.0)
    self.assertEqual(b['jogo']['piso']['nota'], 0.0)
    self.assertEqual(b['versao_comodo'], C.VERSAO_COMODO)
    self.assertAlmostEqual(b['nota'], 0.6667)
    self.assertAlmostEqual(b['piso']['nota'], 0.3333)
    self.assertEqual(b['posicoes'][3], {'pos': 's2-b', 'site': 's2', 'real': 'degradado', 'previsto': 'bom',
                                        'razao_prevista': 1.0, 'apto_real': True, 'apto_previsto': True})
    self.assertEqual(b['por_predio'], {'s1': [2, 2], 's2': [1, 2]})
    self.assertEqual(b['confusao'], [[2, 0, 0], [1, 0, 0], [0, 0, 1]])

  def test_bloco_recusa_piso_com_outras_posicoes(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    with self.assertRaisesRegex(ValueError, 'posições'):
      C.bloco(tab, tab.iloc[:3], META)

  def test_comparar_blocos_igual_a_comparar_as_tabelas(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    piso = tab.assign(previsto='bom')
    nova, base = C.bloco(tab, piso, META), C.bloco(piso, piso, META)
    r = C.comparar_blocos(nova, base)
    direto = C.comparar(tab, piso, C.amostras_posicoes(tab))
    self.assertEqual((r['diferenca'], r['intervalo'], r['resultado']),
                     (direto['diferenca'], direto['intervalo'], direto['resultado']))
    self.assertEqual((r['nota'], r['nota_base']), (nova['nota'], base['nota']))

  def test_comparar_blocos_recusa_avaliacoes_incompativeis(self):
    df, prev = df_e_prev()
    tab = C.tabela_posicoes(df, prev, LIM)
    b = C.bloco(tab, tab, META)
    for campo, valor in (('versao_comodo', 'velha'), ('datasets', ['b.csv']), ('ambiente', 'domestico')):
      with self.assertRaisesRegex(ValueError, campo):
        C.comparar_blocos(b, dict(b, **{campo: valor}))
    with self.assertRaisesRegex(ValueError, 'posições'):
      C.comparar_blocos(b, dict(b, posicoes=b['posicoes'][:3]))


if __name__ == '__main__':
  unittest.main()

import copy
import json
import os
import sys
import types
import unittest
from unittest import mock

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

  def test_piso_absoluto_quando_o_melhor_comodo_e_fraco(self):
    # Casa cujo melhor cômodo tem 4 Mbps: pela razão tudo seria bom.
    ref_fraca = pd.DataFrame({'dn': [4.0], 'up': [4.0]}, index=pd.Index(['s1'], name='_site'))

    def c(dn, up):
      return C.classificar(est(dn, up), ref_fraca, LIM)['classe'].iloc[0]
    self.assertEqual(c(4.0, 4.0), 'bom')          # acima dos mínimos de Chamada (3,0 / 3,8)
    self.assertEqual(c(3.5, 3.5), 'degradado')    # razão 0,875 (seria bom), mas up < 3,8 (Chamada)
    self.assertEqual(c(1.9, 4.0), 'ruim')         # razão 0,475 (seria degradado), mas dn < 2 (Navegação)

  def test_piso_absoluto_inclui_o_limite(self):
    ref = pd.DataFrame({'dn': [3.8], 'up': [3.8]}, index=pd.Index(['s1'], name='_site'))
    self.assertEqual(C.classificar(est(3.0, 3.8), ref, LIM)['classe'].iloc[0], 'bom')

  def test_apto_jogo_nao_usa_capacidade(self):
    ref = pd.DataFrame({'dn': [4.0], 'up': [4.0]}, index=pd.Index(['s1'], name='_site'))
    t = C.classificar(est(4.0, 4.0, lat=10.0, jit=2.0), ref, LIM)
    self.assertTrue(bool(t['apto_jogo'].iloc[0]))  # dn 4 < 15 do Jogo, mas jogo é só lat/jit


class TestConjuntosSozinhos(unittest.TestCase):
  def test_filtra_cada_alvo_e_preserva_o_resto(self):
    df = juntas(linhas('a', 3, 10, 10), linhas('a', 2, 10, 10, conc=2.0), linhas('b', 1, 10, 10, conc=np.nan))
    conj = types.SimpleNamespace(df=df, datasets=['d.zip'], classes={'x': None})
    out = C.conjuntos_sozinhos({C.DN: conj, C.UP: conj})
    self.assertEqual(len(out[C.DN].df), 3)
    self.assertTrue((out[C.UP].df['concorrentes_mesmo_radio'] == 1).all())
    self.assertEqual(out[C.DN].datasets, ['d.zip'])
    self.assertEqual(len(conj.df), 6)  # o original não muda


def prev_linhas(pos, n, dn, up, lat=10.0, jit=2.0, site='s1'):
  """Previsões no formato de C.prever: uma linha por _linha."""
  return pd.DataFrame({'_linha': [f'{pos}:{i}' for i in range(n)], '_site': [site] * n, '_pos': [pos] * n,
                       'dn': [float(dn)] * n, 'up': [float(up)] * n, 'lat': [lat] * n, 'jit': [jit] * n})


class TestReferenciaPrevista(unittest.TestCase):
  def test_maior_mediana_prevista_por_predio(self):
    prev = juntas(prev_linhas('sala', 10, 400, 380), prev_linhas('quarto', 10, 300, 390),
                  prev_linhas('x', 10, 50, 50, site='s2'))
    ref = C.referencia_prevista(prev)
    self.assertEqual((ref.loc['s1', 'dn'], ref.loc['s1', 'up']), (400.0, 390.0))
    self.assertEqual(ref.loc['s2', 'dn'], 50.0)

  def test_ignora_posicao_com_poucas_linhas(self):
    prev = juntas(prev_linhas('sala', 10, 400, 400), prev_linhas('canto', 9, 900, 900))
    self.assertEqual(C.referencia_prevista(prev).loc['s1', 'dn'], 400.0)

  def test_erro_de_nivel_se_cancela(self):
    # Real: sala 600, quarto 450 (razão 0,75, bom). O modelo previu tudo 1/3 abaixo.
    prev = juntas(prev_linhas('sala', 10, 400, 400), prev_linhas('quarto', 10, 300, 300))
    ref_real = pd.DataFrame({'dn': [600.0], 'up': [600.0]}, index=pd.Index(['s1'], name='_site'))
    com_real = C.classe_prevista(prev, ref_real, LIM)
    com_prevista = C.classe_prevista(prev, C.referencia_prevista(prev), LIM)
    self.assertEqual(com_real.loc['quarto', 'classe'], 'degradado')   # 300 / 600 = 0,50
    self.assertEqual(com_prevista.loc['quarto', 'classe'], 'bom')     # 300 / 400 = 0,75
    self.assertEqual(com_prevista.loc['sala', 'classe'], 'bom')

  def test_estatisticas_previstas_formato(self):
    est = C.estatisticas_previstas(prev_linhas('sala', 4, 100, 50, lat=20.0, jit=3.0))
    self.assertEqual(list(est.columns), ['_site', 'n', 'dn', 'up', 'lat', 'jit'])
    self.assertEqual(est.loc['sala', 'n'], 4)


def linhas_feat(pos, n, tx, sinal, site='s1', conc=1.0, dn=100.0, up=100.0):
  return pd.DataFrame({'_pos': [pos] * n, '_site': [site] * n, 'router_tx_rate_mbps': [float(tx)] * n,
                       'router_signal_dbm': [float(sinal)] * n, 'concorrentes_mesmo_radio': [conc] * n,
                       C.DN: [dn] * n, C.UP: [up] * n})


class TestFeaturesRelativas(unittest.TestCase):
  def test_referencia_e_o_maior_valor_entre_posicoes(self):
    df = juntas(linhas_feat('sala', 10, 800, -45), linhas_feat('quarto', 10, 400, -70),
                linhas_feat('canto', 9, 1200, -30),             # poucas linhas: fora
                linhas_feat('sala', 5, 2000, -10, conc=2.0))    # não sozinha: fora
    ref = C.referencia_features(df, ['router_tx_rate_mbps', 'router_signal_dbm'])
    self.assertEqual(ref.loc['s1', 'router_tx_rate_mbps'], 800.0)
    self.assertEqual(ref.loc['s1', 'router_signal_dbm'], -45.0)

  def test_razao_para_taxa_e_diferenca_para_db(self):
    df = juntas(linhas_feat('sala', 10, 800, -45), linhas_feat('quarto', 10, 400, -70))
    ref = C.referencia_features(df, ['router_tx_rate_mbps', 'router_signal_dbm'])
    rel = C.relativizar(df, ref)
    quarto = rel[rel['_pos'] == 'quarto'].iloc[0]
    self.assertAlmostEqual(quarto['router_tx_rate_mbps_rel'], 0.5)
    self.assertAlmostEqual(quarto['router_signal_dbm_rel'], -25.0)
    self.assertNotIn('router_snr_rel', rel.columns)   # coluna ausente no df: não cria

  def test_mesma_fracao_em_casas_de_nivel_diferente(self):
    # Casa rica e casa pobre: o cômodo com metade da PHY tem o mesmo valor relativo.
    df = juntas(linhas_feat('a1', 10, 1200, -40, site='s1'), linhas_feat('a2', 10, 600, -60, site='s1'),
                linhas_feat('b1', 10, 300, -40, site='s2'), linhas_feat('b2', 10, 150, -60, site='s2'))
    rel = C.relativizar(df, C.referencia_features(df, ['router_tx_rate_mbps', 'router_signal_dbm']))
    por_pos = rel.groupby('_pos')['router_tx_rate_mbps_rel'].first()
    self.assertAlmostEqual(por_pos['a2'], por_pos['b2'])

  def test_alvos_razao(self):
    df = linhas_feat('quarto', 2, 400, -70, dn=50.0, up=20.0)
    ref = pd.DataFrame({'dn': [100.0], 'up': [80.0]}, index=pd.Index(['s1'], name='_site'))
    out = C.alvos_razao(df, ref)
    self.assertAlmostEqual(out[C.RAZAO_DN].iloc[0], 0.5)
    self.assertAlmostEqual(out[C.RAZAO_UP].iloc[0], 0.25)


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


class TestRazaoPrevista(unittest.TestCase):
  def test_classificar_com_razao_dada_ignora_a_referencia(self):
    t = C.classificar(est(100), None, LIM, razao=pd.Series([0.5], index=pd.Index(['p'], name='_pos')))
    self.assertAlmostEqual(t.loc['p', 'razao'], 0.5)
    self.assertEqual(t.loc['p', 'classe'], 'degradado')

  def test_classificar_com_razao_mantem_o_piso_absoluto(self):
    # Razão alta, mas 1,5 Mbps de download previsto: abaixo do mínimo de Navegação.
    t = C.classificar(est(1.5, up=1.5), None, LIM, razao=pd.Series([0.95], index=pd.Index(['p'], name='_pos')))
    self.assertEqual(t.loc['p', 'classe'], 'ruim')

  def test_classe_prevista_razao_usa_o_menor_entre_download_e_upload(self):
    prev = pd.DataFrame({'_linha': ['l1', 'l2'], '_pos': ['a', 'a'], '_site': ['s1', 's1'],
                         'dn': [50.0, 50.0], 'up': [50.0, 50.0], 'lat': [10.0, 10.0], 'jit': [2.0, 2.0]})
    pr = pd.DataFrame({'_linha': ['l1', 'l2'], C.RAZAO_DN: [0.9, 0.9], C.RAZAO_UP: [0.6, 0.6]})
    t = C.classe_prevista_razao(prev, pr, LIM)
    self.assertAlmostEqual(t.loc['a', 'razao'], 0.6)
    self.assertEqual(t.loc['a', 'classe'], 'degradado')

  def test_prever_razao_fora_do_fold(self):
    conjs, _ = conjs_sinteticos()
    ref = pd.DataFrame({'dn': [100.0] * 3, 'up': [55.0] * 3}, index=pd.Index(['s1', 's2', 's3'], name='_site'))
    ref_feat = pd.DataFrame(index=pd.Index(['s1', 's2', 's3'], name='_site'))
    vaz = {a: [] for a in conjs}
    pr = C.prever_razao(conjs, ['x'], vaz, ref, ref_feat)
    self.assertEqual(list(pr.columns), ['_linha', C.RAZAO_DN, C.RAZAO_UP])
    self.assertEqual(len(pr), 90)
    self.assertTrue(pr[C.RAZAO_DN].between(0, 1.2).all())


def linhas_banda(pos, n, tx, radio, site='s1'):
  return pd.DataFrame({'_pos': [pos] * n, '_site': [site] * n, 'radio': [radio] * n,
                       'router_tx_rate_mbps': [float(tx)] * n, 'concorrentes_mesmo_radio': [1.0] * n})


class TestRazaoJusta(unittest.TestCase):
  def test_referencia_por_banda(self):
    df = juntas(linhas_banda('sala', 10, 800, '5ghz'), linhas_banda('sala', 10, 150, '2.4ghz'),
                linhas_banda('quarto', 10, 400, '5ghz'), linhas_banda('quarto', 10, 60, '2.4ghz'))
    ref = C.referencia_features(df, ['router_tx_rate_mbps'], por_banda=True)
    self.assertEqual(ref.loc[('s1', '5ghz'), 'router_tx_rate_mbps'], 800.0)
    self.assertEqual(ref.loc[('s1', '2.4ghz'), 'router_tx_rate_mbps'], 150.0)

  def test_relativizar_por_banda(self):
    df = juntas(linhas_banda('sala', 10, 800, '5ghz'), linhas_banda('sala', 10, 150, '2.4ghz'),
                linhas_banda('quarto', 10, 60, '2.4ghz'))
    ref = C.referencia_features(df, ['router_tx_rate_mbps'], por_banda=True)
    rel = C.relativizar(df, ref, por_banda=True)
    q = rel[(rel['_pos'] == 'quarto')].iloc[0]
    self.assertAlmostEqual(q['router_tx_rate_mbps_rel'], 0.4)   # 60 / 150, não 60 / 800

  def test_referencia_sem_banda_continua_igual(self):
    df = juntas(linhas_banda('sala', 10, 800, '5ghz'), linhas_banda('quarto', 10, 60, '2.4ghz'))
    self.assertEqual(C.referencia_features(df, ['router_tx_rate_mbps']).loc['s1', 'router_tx_rate_mbps'], 800.0)

  def _prev(self, dn):
    return pd.DataFrame({'_linha': ['l1', 'l2'], '_pos': ['a', 'a'], '_site': ['casa', 'casa'],
                         'dn': [dn, dn], 'up': [90.0, 90.0], 'lat': [10.0, 10.0], 'jit': [2.0, 2.0]})

  def test_saturar_wan_leva_a_razao_a_1(self):
    pr = pd.DataFrame({'_linha': ['l1', 'l2'], C.RAZAO_DN: [0.5, 0.5], C.RAZAO_UP: [0.9, 0.9]})
    with mock.patch.object(C, 'teto_wan', lambda s, a: 100.0):
      t = C.classe_prevista_razao(self._prev(90.0), pr, LIM, saturar_wan=True)   # 90 >= 0,85 x 100
    self.assertEqual(t.loc['a', 'classe'], 'bom')
    self.assertAlmostEqual(t.loc['a', 'razao'], 1.0)   # dn (90) e up (90) chegam a 85% do teto: os dois viram 1

  def test_saturar_wan_nao_mexe_abaixo_do_limiar_nem_sem_teto(self):
    pr = pd.DataFrame({'_linha': ['l1', 'l2'], C.RAZAO_DN: [0.5, 0.5], C.RAZAO_UP: [0.9, 0.9]})
    with mock.patch.object(C, 'teto_wan', lambda s, a: 100.0):
      abaixo = C.classe_prevista_razao(self._prev(80.0), pr, LIM, saturar_wan=True)
    with mock.patch.object(C, 'teto_wan', lambda s, a: None):
      sem_teto = C.classe_prevista_razao(self._prev(90.0), pr, LIM, saturar_wan=True)
    self.assertAlmostEqual(abaixo.loc['a', 'razao'], 0.5)
    self.assertAlmostEqual(sem_teto.loc['a', 'razao'], 0.5)

  def test_prever_razao_aceita_por_banda_e_excluir_wan(self):
    conjs, _ = conjs_sinteticos()
    for c in conjs.values():
      c.df['_limitado_wan'] = False
      c.df['radio'] = '5ghz'
    ref = pd.DataFrame({'dn': [100.0] * 3, 'up': [55.0] * 3}, index=pd.Index(['s1', 's2', 's3'], name='_site'))
    ref_feat = pd.DataFrame(index=pd.MultiIndex.from_tuples([], names=['_site', 'radio']))
    pr = C.prever_razao(conjs, ['x'], {a: [] for a in conjs}, ref, ref_feat, por_banda=True, excluir_wan=True)
    self.assertEqual(len(pr), 90)


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

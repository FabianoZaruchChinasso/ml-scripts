import dataclasses
import json
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.core import pacote as P
from ml.core import producao
from ml.core import quantis as Q
from test_studio_features import TABELA, frame

DN, UP, LAT, JIT = P.PREFIXOS
FEATURES = ['router_snr', 'router_signal_dbm', 'radio']
POR_BANDA = {DN: {'coluna': 'router_snr', 'radio': '5ghz'}, UP: {'coluna': 'router_snr', 'radio': '5ghz'}}


def conjuntos():
  """Três prédios (residencia, coworking, hotmilk), sem teto de WAN, com as duas bandas em todos."""
  return {alvo: C.preparar({'a.csv': frame()}, alvo, TABELA) for alvo in P.PREFIXOS}


def sem_predio(conjs, predio):
  return {alvo: dataclasses.replace(c, df=c.df[c.df['_site'] != predio]) for alvo, c in conjs.items()}


class PoucasArvores(unittest.TestCase):
  """25 árvores no modelo da régua: o que se testa é a receita, não a qualidade do modelo."""

  @classmethod
  def setUpClass(cls):
    cls.addClassCleanup(setattr, A, 'ARVORES', A.ARVORES)
    A.ARVORES = 25
    cls.conjs = conjuntos()


class TestTreinarEPrever(PoucasArvores):
  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls.absoluto = P.treinar(cls.conjs, FEATURES)
    cls.eficiencia = P.treinar(cls.conjs, FEATURES, {DN: 'router_snr'})
    cls.por_banda = P.treinar(cls.conjs, FEATURES, POR_BANDA)

  def matriz(self, pacote, alvo, linhas):
    return producao.preparar_entrada(linhas, pacote.receita['alvos'][alvo]['contrato'])[0]

  def test_devolve_as_saidas_com_o_indice_da_entrada(self):
    linhas = self.conjs[DN].df.iloc[[5, 3, 20]]
    saida, avisos = P.prever(self.absoluto, linhas)
    self.assertEqual(list(saida.columns), list(P.SAIDAS))
    self.assertEqual(list(saida.index), list(linhas.index))
    self.assertFalse(saida.isna().any().any())
    self.assertEqual(avisos, [])

  def test_modelos_de_cada_tipo_de_denominador(self):
    quantis = ['jit_q50', 'jit_q90', 'lat_q50', 'lat_q90']
    self.assertEqual(sorted(self.absoluto.modelos), ['down_absoluto'] + quantis + ['up_absoluto'])
    self.assertEqual(sorted(self.eficiencia.modelos), ['down_eficiencia'] + quantis + ['up_absoluto'])
    self.assertEqual(sorted(self.por_banda.modelos),
                     ['down_absoluto', 'down_eficiencia'] + quantis + ['up_absoluto', 'up_eficiencia'])

  def test_receita_vira_json_e_diz_as_colunas_de_entrada(self):
    receita = json.loads(json.dumps(self.por_banda.receita))
    self.assertEqual(receita['entradas'], FEATURES)
    self.assertEqual(receita['saidas'], list(P.SAIDAS))
    self.assertEqual(receita['versao_pacote'], P.VERSAO_PACOTE)
    self.assertEqual(receita['alvos'][DN]['denominador']['radio'], '5ghz')
    self.assertIsNone(self.absoluto.receita['alvos'][DN]['denominador'])
    # Denominador e radio fora das features também são colunas de entrada.
    so_sinal = P.treinar(self.conjs, ['router_signal_dbm'], POR_BANDA)
    self.assertEqual(so_sinal.receita['entradas'], ['router_signal_dbm', 'router_snr', 'radio'])

  def test_eficiencia_multiplica_pelo_denominador(self):
    linhas = self.conjs[DN].df.head(6)
    saida, avisos = P.prever(self.eficiencia, linhas)
    X = self.matriz(self.eficiencia, DN, linhas)
    esperado = self.eficiencia.modelos['down_eficiencia'].predict(X) * linhas['router_snr'].to_numpy()
    np.testing.assert_allclose(saida['download_mbps'].to_numpy(), esperado)
    self.assertEqual(avisos, [])

  def test_denominador_vazio_ou_baixo_usa_a_mediana_e_avisa(self):
    linhas = self.conjs[DN].df.head(6).copy()
    linhas.loc[linhas.index[0], 'router_snr'] = np.nan
    linhas.loc[linhas.index[1], 'router_snr'] = 0.5
    saida, avisos = P.prever(self.eficiencia, linhas)
    den = self.eficiencia.receita['alvos'][DN]['denominador']
    X = self.matriz(self.eficiencia, DN, linhas)
    esperado = self.eficiencia.modelos['down_eficiencia'].predict(X)[:2] * den['mediana_imputacao']
    np.testing.assert_allclose(saida['download_mbps'].to_numpy()[:2], esperado)
    self.assertEqual(len(avisos), 1)
    self.assertIn('2 linha(s)', avisos[0])

  def test_banda_aceita_a_grafia_do_acs_e_radio_vazio_vai_para_o_absoluto(self):
    linhas = self.conjs[DN].df.head(4).copy()
    linhas['radio'] = ['5GHz', ' 5ghz ', '2.4ghz', None]
    saida, avisos = P.prever(self.por_banda, linhas)
    X = self.matriz(self.por_banda, DN, linhas)
    eficiencia = self.por_banda.modelos['down_eficiencia'].predict(X) * linhas['router_snr'].to_numpy()
    absoluto = self.por_banda.modelos['down_absoluto'].predict(X)
    np.testing.assert_allclose(saida['download_mbps'].to_numpy(),
                               [eficiencia[0], eficiencia[1], absoluto[2], absoluto[3]])
    self.assertEqual(avisos, [])

  def test_p90_leva_a_correcao_e_nunca_fica_abaixo_do_p50(self):
    pacote = P.Pacote(self.absoluto.modelos, json.loads(json.dumps(self.absoluto.receita)))
    pacote.receita['alvos'][LAT]['correcao_log_q90'] = 0.5
    linhas = self.conjs[LAT].df.head(10)
    saida, _ = P.prever(pacote, linhas)
    X = self.matriz(pacote, LAT, linhas)
    p50 = np.expm1(pacote.modelos['lat_q50'].predict(X))
    q90_log = pacote.modelos['lat_q90'].predict(X)
    np.testing.assert_allclose(saida['latency_ms_p50'].to_numpy(), p50)
    np.testing.assert_allclose(saida['latency_ms_p90_bruto'].to_numpy(), np.maximum(np.expm1(q90_log), p50))
    np.testing.assert_allclose(saida['latency_ms_p90'].to_numpy(), np.maximum(np.expm1(q90_log + 0.5), p50))
    self.assertTrue((saida['latency_ms_p90'] >= saida['latency_ms_p90_bruto']).all())
    self.assertTrue((saida['latency_ms_p90_bruto'] >= saida['latency_ms_p50']).all())

  def test_entrada_sem_coluna_levanta(self):
    with self.assertRaisesRegex(ValueError, 'router_snr'):
      P.prever(self.absoluto, self.conjs[DN].df.head(3).drop(columns=['router_snr']))

  def test_feature_com_vazamento_nao_entra(self):
    with self.assertRaises(AssertionError):
      P.treinar(self.conjs, FEATURES + ['router_tx_bytes'])

  def test_sem_features_levanta(self):
    with self.assertRaises(ValueError):
      P.treinar(self.conjs, [])

  def test_linhas_limitadas_pela_wan_ficam_fora_do_treino_de_download_e_upload(self):
    marcado, sem = dict(self.conjs), dict(self.conjs)
    for alvo in (DN, UP):
      df = self.conjs[alvo].df.copy()
      df['_limitado_wan'] = df['_site'] == 'hotmilk'
      marcado[alvo] = dataclasses.replace(self.conjs[alvo], df=df)
      sem[alvo] = dataclasses.replace(self.conjs[alvo], df=df[df['_site'] != 'hotmilk'])
    linhas = self.conjs[DN].df.head(10)
    com_marca, sem_linhas = P.prever(P.treinar(marcado, FEATURES), linhas)[0], P.prever(P.treinar(sem, FEATURES), linhas)[0]
    vazao = ['download_mbps', 'upload_mbps']
    np.testing.assert_allclose(com_marca[vazao].to_numpy(), sem_linhas[vazao].to_numpy())
    # Latência e jitter não têm teto: usam todas as linhas.
    todas = P.prever(self.absoluto, linhas)[0]
    np.testing.assert_allclose(com_marca['latency_ms_p50'].to_numpy(), todas['latency_ms_p50'].to_numpy())


class TestIgualAAvaliacao(PoucasArvores):
  """O pacote treinado sem um prédio prevê esse prédio com o mesmo número da avaliação (spec, seção 4.3)."""

  def conferir(self, denominador):
    vazao = {alvo: A.prever_fora_do_fold(self.conjs[alvo].df, FEATURES, alvo, [], denominador=denominador.get(alvo))
             for alvo in (DN, UP)}
    quantis = {alvo: Q.prever_quantis_fora_do_fold(self.conjs[alvo].df, FEATURES, alvo, []) for alvo in (LAT, JIT)}
    for predio in sorted(self.conjs[DN].df['_site'].unique()):
      pacote = P.treinar(sem_predio(self.conjs, predio), FEATURES, denominador)
      for alvo, prev in vazao.items():
        fora = self.conjs[alvo].df[self.conjs[alvo].df['_site'] == predio]
        saida = P.prever(pacote, fora)[0]
        np.testing.assert_allclose(saida[P.SAIDA_VAZAO[alvo]].to_numpy(), prev.loc[fora.index, 'yhat'].to_numpy(),
                                   rtol=1e-9, err_msg=f'{alvo} em {predio}')
      for alvo, prev in quantis.items():
        fora = self.conjs[alvo].df[self.conjs[alvo].df['_site'] == predio]
        saida = P.prever(pacote, fora)[0]
        for coluna, da_avaliacao in ((f'{alvo}_p50', 'q50'), (f'{alvo}_p90', 'q90'), (f'{alvo}_p90_bruto', 'q90_bruto')):
          np.testing.assert_allclose(saida[coluna].to_numpy(), prev.loc[fora.index, da_avaliacao].to_numpy(),
                                     rtol=1e-9, err_msg=f'{coluna} em {predio}')

  def test_eficiencia_no_download_e_absoluto_no_upload(self):
    self.conferir({DN: 'router_snr'})

  def test_eficiencia_por_banda(self):
    self.conferir(POR_BANDA)


if __name__ == '__main__':
  unittest.main()

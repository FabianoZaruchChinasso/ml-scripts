import json
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.pipeline import Pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import percepcao as P

# Um prédio por posições nomeadas (como a residência) e um por prefixo (como o hotmilk).
REGISTRO = {'aliases': {},
            'predios': {'casa': {'ambiente': 'domestico', 'prefixos': [], 'rotulo': 'Casa', 'studio': 'casa',
                                 'posicoes': {'sala': 'res-sala', 'quarto': 'res-quarto'}},
                        'hot': {'ambiente': 'corporativo', 'prefixos': ['hotmilk'], 'rotulo': 'Hot',
                                'studio': 'hot'}}}
CLASSES = {'Excelente': 'excelente', 'Bom': 'media', 'Ok': 'media', 'Ruim': 'ruim', 'Ausente': 'ruim'}


def gravar(dados) -> str:
  arquivo = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
  json.dump(dados, arquivo)
  arquivo.close()
  return arquivo.name


class TestCarregar(unittest.TestCase):
  def test_nivel_vira_classe(self):
    path = gravar({'classes': CLASSES, 'posicoes': {'res-sala': 'Excelente', 'hotmilk-copa': 'Ok',
                                                    'res-quarto': 'Ausente'}})
    self.assertEqual(P.carregar(path, REGISTRO),
                     {'res-sala': 'excelente', 'hotmilk-copa': 'media', 'res-quarto': 'ruim'})

  def test_posicao_desconhecida_levanta(self):
    path = gravar({'classes': CLASSES, 'posicoes': {'res-cozinha': 'Bom'}})
    with self.assertRaisesRegex(ValueError, 'res-cozinha'):
      P.carregar(path, REGISTRO)

  def test_nivel_desconhecido_levanta(self):
    path = gravar({'classes': CLASSES, 'posicoes': {'res-sala': 'Mediano'}})
    with self.assertRaisesRegex(ValueError, 'Mediano'):
      P.carregar(path, REGISTRO)

  def test_classe_desconhecida_levanta(self):
    path = gravar({'classes': {**CLASSES, 'Bom': 'boa'}, 'posicoes': {'res-sala': 'Bom'}})
    with self.assertRaisesRegex(ValueError, 'boa'):
      P.carregar(path, REGISTRO)

  def test_chaves_erradas_levantam(self):
    path = gravar({'classes': CLASSES})
    with self.assertRaisesRegex(ValueError, 'posicoes'):
      P.carregar(path, REGISTRO)

  def test_arquivo_do_repositorio_valida(self):
    rotulos = P.carregar()
    self.assertEqual(len(rotulos), 28)
    self.assertEqual(rotulos['villa_res_cozinha'], 'ruim')


class TestRotular(unittest.TestCase):
  def test_rotula_e_lista_o_que_ficou_fora(self):
    df = pd.DataFrame({'_pos': ['a', 'a', 'b', 'z'], 'x': [1, 2, 3, 4]})
    saida, sem_rotulo, sem_linhas = P.rotular(df, {'a': 'excelente', 'b': 'ruim', 'c': 'media'})
    self.assertEqual(saida['_classe'].tolist(), ['excelente', 'excelente', 'ruim'])
    self.assertEqual(saida.index.tolist(), [0, 1, 2])
    self.assertEqual(sem_rotulo, ['z'])
    self.assertEqual(sem_linhas, ['c'])


class TestPesos(unittest.TestCase):
  def test_posicao_e_classe_somam_igual(self):
    pos = ['a', 'a', 'b', 'c', 'c', 'c']
    classe = ['x', 'x', 'x', 'y', 'y', 'y']
    w = P.pesos(pos, classe)
    # 3 posições, 2 classes: cada classe soma 1,5; dentro da classe x, a e b pesam o mesmo.
    np.testing.assert_allclose(w, [0.375, 0.375, 0.75, 0.5, 0.5, 0.5])

  def test_soma_total_e_o_numero_de_posicoes(self):
    w = P.pesos(['a'] * 180 + ['b'] * 20 + ['c'] * 50, ['x'] * 200 + ['y'] * 50)
    self.assertAlmostEqual(float(w.sum()), 3.0)


class Lembra(BaseEstimator, ClassifierMixin):
  """Guarda o índice e os pesos de cada ajuste; prevê a classe mais frequente do treino com prob. 1."""
  ajustes = []

  def fit(self, X, y, sample_weight=None):
    self.classes_ = np.unique(y)
    self.maioria_ = pd.Series(np.asarray(y)).value_counts().index[0]
    Lembra.ajustes.append((list(X.index), sample_weight))
    return self

  def predict_proba(self, X):
    p = np.zeros((len(X), len(self.classes_)))
    p[:, list(self.classes_).index(self.maioria_)] = 1.0
    return p


def lembra():
  return Pipeline([('clf', Lembra())])


def frame_tres_predios():
  # 3 prédios, 2 posições cada, linhas desiguais; classes nas três.
  pos = ['s1-a'] * 4 + ['s1-b'] * 2 + ['s2-a'] * 3 + ['s2-b'] * 3 + ['s3-a'] * 2 + ['s3-b'] * 2
  site = [p[:2] for p in pos]
  classe = {'s1-a': 'excelente', 's1-b': 'ruim', 's2-a': 'media', 's2-b': 'ruim', 's3-a': 'excelente',
            's3-b': 'media'}
  return pd.DataFrame({'_pos': pos, '_site': site, '_classe': [classe[p] for p in pos],
                       'radio': ['5GHz'] * len(pos), 'sinal': np.arange(len(pos), dtype=float)})


class TestPreverForaDoFold(unittest.TestCase):
  def setUp(self):
    Lembra.ajustes = []

  def test_treino_nunca_ve_o_predio_de_teste(self):
    df = frame_tres_predios()
    P.prever_fora_do_fold(df, ['sinal'], vazadas=[], fabrica=lembra)
    self.assertEqual(len(Lembra.ajustes), 3)
    for indices, _ in Lembra.ajustes:
      self.assertEqual(df.loc[indices, '_site'].nunique(), 2)

  def test_pesos_chegam_ao_estimador(self):
    df = frame_tres_predios()
    P.prever_fora_do_fold(df, ['sinal'], vazadas=[], fabrica=lembra)
    indices, w = Lembra.ajustes[0]
    np.testing.assert_allclose(w, P.pesos(df.loc[indices, '_pos'], df.loc[indices, '_classe']))

  def test_probabilidades_alinhadas_e_somam_um(self):
    df = frame_tres_predios()
    proba = P.prever_fora_do_fold(df, ['sinal', 'radio'], vazadas=[], fabrica=lembra)
    self.assertEqual(list(proba.columns), list(P.CLASSES))
    self.assertEqual(proba.index.tolist(), df.index.tolist())
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)

  def test_coluna_vazada_levanta(self):
    with self.assertRaises(AssertionError):
      P.prever_fora_do_fold(frame_tres_predios(), ['sinal'], vazadas=['sinal'], fabrica=lembra)

  def test_modelo_padrao_nao_usa_class_weight(self):
    self.assertIsNone(P.modelo().named_steps['clf'].class_weight)


class TestPorPosicao(unittest.TestCase):
  def test_media_das_probabilidades_e_argmax(self):
    df = pd.DataFrame({'_pos': ['a', 'a', 'a', 'b'], '_site': ['s1', 's1', 's1', 's2'],
                       '_classe': ['ruim', 'ruim', 'ruim', 'excelente']})
    # Em 'a' a maioria das linhas prevê media, mas a média das probabilidades dá ruim.
    proba = pd.DataFrame([[0.0, 0.6, 0.4], [0.0, 0.6, 0.4], [0.0, 0.0, 1.0], [0.5, 0.5, 0.0]],
                         columns=list(P.CLASSES))
    pos_df = P.por_posicao(df, proba)
    self.assertEqual(pos_df.index.tolist(), ['a', 'b'])
    self.assertEqual(pos_df['previsto'].tolist(), ['ruim', 'excelente'])
    self.assertEqual(pos_df['real'].tolist(), ['ruim', 'excelente'])
    self.assertEqual(pos_df['_site'].tolist(), ['s1', 's2'])


def posicoes(real, previsto, site=None):
  site = site or ['s1'] * len(real)
  return pd.DataFrame({'_site': site, 'real': real, 'previsto': previsto},
                      index=[f'p{i}' for i in range(len(real))])


class TestMetricas(unittest.TestCase):
  def test_acuracia_balanceada(self):
    real = ['excelente', 'excelente', 'media', 'ruim']
    previsto = ['excelente', 'media', 'media', 'media']
    # recall: excelente 0,5; media 1; ruim 0.
    self.assertAlmostEqual(P.acuracia_balanceada(real, previsto), 0.5)

  def test_resumir_sem_reamostra_igual_nota(self):
    pos_df = posicoes(['excelente', 'ruim'], ['excelente', 'ruim'])
    r = P.resumir(pos_df, [np.array([0, 1])] * 3)
    self.assertEqual(r['nota'], 1.0)
    self.assertEqual(r['intervalo'], [1.0, 1.0])

  def test_diferenca_pareada(self):
    nova = posicoes(['excelente', 'ruim'], ['excelente', 'ruim'])
    base = posicoes(['excelente', 'ruim'], ['excelente', 'excelente'])
    d = P.diferenca(nova, base, [np.array([0, 1])] * 3)
    self.assertEqual(d['diferenca'], 0.5)
    self.assertEqual(d['intervalo'], [0.5, 0.5])

  def test_diferenca_exige_mesmas_posicoes(self):
    with self.assertRaises(ValueError):
      P.diferenca(posicoes(['ruim'], ['ruim']), posicoes(['ruim', 'ruim'], ['ruim', 'ruim']), [])

  def test_confusao_e_graves(self):
    pos_df = posicoes(['excelente', 'ruim', 'media'], ['ruim', 'excelente', 'media'])
    m, graves = P.confusao(pos_df)
    self.assertEqual(list(m.index), list(P.CLASSES))
    self.assertEqual(list(m.columns), list(P.CLASSES))
    self.assertEqual(int(m.loc['media', 'media']), 1)
    self.assertEqual(graves, 2)

  def test_por_predio(self):
    pos_df = posicoes(['ruim', 'ruim', 'media'], ['ruim', 'media', 'media'], site=['s1', 's1', 's2'])
    self.assertEqual(P.por_predio(pos_df), {'s1': (1, 2), 's2': (1, 1)})


class TestLeitura(unittest.TestCase):
  def test_aprendivel_por_qualquer_um(self):
    r = P.leitura({'intervalo': [0.30, 0.5]}, {'intervalo': [0.34, 0.6]}, {'intervalo': [-0.1, 0.2]})
    self.assertEqual(r, {'aprendivel': True, 'contra_piso': 'empate'})

  def test_nao_aprendivel(self):
    r = P.leitura({'intervalo': [0.20, 0.5]}, {'intervalo': [1 / 3, 0.6]}, {'intervalo': [0.01, 0.2]})
    self.assertEqual(r, {'aprendivel': False, 'contra_piso': 'melhor'})

  def test_piora(self):
    r = P.leitura({'intervalo': [0.4, 0.5]}, {'intervalo': [0.2, 0.3]}, {'intervalo': [-0.3, -0.01]})
    self.assertEqual(r['contra_piso'], 'piora')

  def test_intervalo_vazio_e_empate(self):
    r = P.leitura({'intervalo': None}, {'intervalo': None}, {'intervalo': None})
    self.assertEqual(r, {'aprendivel': False, 'contra_piso': 'empate'})


if __name__ == '__main__':
  unittest.main()

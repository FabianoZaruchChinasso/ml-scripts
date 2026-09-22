import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import plans as P

SEGMENTOS = np.array([[100, 50, 300, 50], [300, 50, 300, 650], [300, 650, 100, 650],
                      [100, 650, 100, 50], [100, 300, 200, 300]], dtype=float)
W, H = 410.0, 1386.0
COMBOS = list(itertools.product(P.ORIGENS, P.EIXOS))


class TestRegistroParedes(unittest.TestCase):
  def test_origem_vai_para_zero_e_oposto_para_W_H(self):
    cantos = {'superior-esquerdo': (100, 50), 'superior-direito': (300, 50),
              'inferior-esquerdo': (100, 650), 'inferior-direito': (300, 650)}
    opostos = {'superior-esquerdo': (300, 650), 'superior-direito': (100, 650),
               'inferior-esquerdo': (300, 50), 'inferior-direito': (100, 50)}
    for origem, eixo in COMBOS:
      px_para_cm, _ = P.registro_paredes(SEGMENTOS, origem, eixo, W, H)
      np.testing.assert_allclose(px_para_cm(*cantos[origem]), (0, 0), atol=1e-9, err_msg=origem + eixo)
      np.testing.assert_allclose(px_para_cm(*opostos[origem]), (W, H), atol=1e-9, err_msg=origem + eixo)

  def test_ida_e_volta_e_identidade(self):
    for origem, eixo in COMBOS:
      px_para_cm, cm_para_px = P.registro_paredes(SEGMENTOS, origem, eixo, W, H)
      for x, y in [(0, 0), (58, 75), (410, 1386), (200.5, 700.25)]:
        np.testing.assert_allclose(px_para_cm(*cm_para_px(x, y)), (x, y), atol=1e-9)

  def test_casa_real(self):
    _, cm_para_px = P.registro_paredes(np.array([[725, 360, 810, 660]], float),
                                       'inferior-direito', 'horizontal', W, H)
    np.testing.assert_allclose(cm_para_px(58, 75), (810 - 58 * 85 / 410, 660 - 75 * 300 / 1386))

  def test_papel_acompanha_o_registro(self):
    for origem, eixo in COMBOS:
      _, cm_para_px = P.registro_paredes(SEGMENTOS, origem, eixo, W, H)
      papel = P.papel_das_paredes(origem, eixo)
      zero = np.array(cm_para_px(0, 0))
      for coluna, (x, y) in enumerate([(1, 0), (0, 1)]):
        direcao = np.sign(np.array(cm_para_px(x, y)) - zero)
        self.assertEqual(list(direcao), [papel[0][coluna], papel[1][coluna]], origem + eixo)

  def test_valores_invalidos_levantam(self):
    with self.assertRaises(ValueError):
      P.registro_paredes(SEGMENTOS, 'meio', 'horizontal', W, H)
    with self.assertRaises(ValueError):
      P.registro_paredes(SEGMENTOS, 'superior-esquerdo', 'diagonal', W, H)
    with self.assertRaises(ValueError):
      P.registro_paredes(np.array([[1, 1, 1, 5]], float), 'superior-esquerdo', 'horizontal', W, H)


class TestFoto(unittest.TestCase):
  def test_papel_da_foto(self):
    cantos = [[300, 900], [80, 900], [100, 120], [330, 120]]
    self.assertEqual(P.papel_da_foto(cantos), [[-1, 0], [0, -1]])
    self.assertEqual(P.papel_da_foto([[0, 0], [0, 10], [10, 10], [10, 0]]), [[0, 1], [1, 0]])

  def test_papel_degenerado_levanta(self):
    with self.assertRaises(ValueError):
      P.papel_da_foto([[0, 0], [10, 0], [20, 1], [30, 0]])

  def test_validar_cantos(self):
    self.assertEqual(P.validar_cantos([[1, 2], [3, 4], [5, 6], [7, 8]], 10, 10),
                     [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    for ruim in ([[1, 2]] * 3, [[1, 2], [3, 4], [5, 6], [70, 8]], [[1, 2], [3, 4], [5, 6], [True, 8]]):
      with self.assertRaises(ValueError):
        P.validar_cantos(ruim, 10, 10)

  def test_endireitar_leva_os_cantos_aos_cantos_do_envelope(self):
    pasta = tempfile.mkdtemp()
    try:
      marcas = [(40, 30, (255, 0, 0)), (350, 50, (0, 255, 0)), (370, 260, (0, 0, 255)), (20, 280, (255, 0, 255))]
      img = Image.new('RGB', (400, 300), 'white')
      for x, y, cor in marcas:
        for dx in range(-3, 4):
          for dy in range(-3, 4):
            img.putpixel((x + dx, y + dy), cor)
      path = os.path.join(pasta, 'f.png')
      img.save(path)
      png = P.endireitar(path, [[x, y] for x, y, _ in marcas], 200, 100, margem=10)
      saida = Image.open(__import__('io').BytesIO(png)).convert('RGB')
      self.assertEqual(saida.size, (220, 120))
      for (u, v), (_, _, cor) in zip([(10, 10), (210, 10), (210, 110), (10, 110)], marcas):
        self.assertEqual(saida.getpixel((u, v)), cor)
    finally:
      shutil.rmtree(pasta)

  def test_cantos_colineares_levantam(self):
    with self.assertRaises(ValueError):
      P.coeficientes_perspectiva([(0, 0), (1, 0), (1, 1), (0, 1)], [[0, 0], [1, 1], [2, 2], [3, 3]])


class TestArquivos(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    with open(os.path.join(self.pasta, 'paredes.csv'), 'w') as handle:
      handle.write('Elemento,X1_px,Y1_px,X2_px,Y2_px\nP1,725,360,810,360\nP2,810,360,810,660\nP3,725,660,810,660\n')
    Image.new('RGB', (720, 1280), 'white').save(os.path.join(self.pasta, 'foto.jpeg'))
    self.env = {'casa': {'w': W, 'h': H}}

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def _config(self):
    with open(os.path.join(self.pasta, 'plantas.json'), encoding='utf-8') as handle:
      return json.load(handle)

  def test_caminho_recusa_diretorios(self):
    for ruim in ('../x.csv', 'a/b.csv', '', '..'):
      with self.assertRaises(ValueError):
        P.caminho(ruim, self.pasta)

  def test_listar_arquivos(self):
    self.assertEqual(P.listar_arquivos(self.pasta), {'paredes': ['paredes.csv'], 'fotos': ['foto.jpeg']})

  def test_sem_plantas_json_nao_e_erro(self):
    plantas, avisos = P.montar_plantas(self.env, self.pasta)
    self.assertEqual(avisos, [])
    self.assertIsNone(plantas['casa']['paredes'])

  def test_salvar_e_montar(self):
    P.salvar_calibracao('casa', {'arquivo': 'paredes.csv', 'origem': 'inferior-direito', 'eixo_x': 'horizontal'},
                        None, self.pasta)
    P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg',
                                       'cantos': [[307, 935], [76, 935], [97, 124], [328, 124]]}, self.pasta)
    self.assertEqual(set(self._config()['casa']), {'paredes', 'foto'})
    self.assertEqual(sorted(os.listdir(self.pasta)), ['foto.jpeg', 'paredes.csv', 'plantas.json'])
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    casa = plantas['casa']
    self.assertEqual(casa['papel'], [[-1, 0], [0, -1]])
    self.assertEqual(casa['paredes'][1], [0.0, 1386.0, 0.0, 0.0])
    self.assertTrue(casa['foto']['url'].startswith('api/plan/casa/foto.png?v='))

  def test_foto_sem_cantos_fica_so_na_calibracao(self):
    P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg', 'cantos': None}, self.pasta)
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    self.assertIsNone(plantas['casa']['foto'])
    self.assertEqual(plantas['casa']['calibracao']['foto'], {'arquivo': 'foto.jpeg', 'cantos': None})

  def test_salvar_rejeita_invalidos(self):
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa', {'arquivo': 'paredes.csv', 'origem': 'meio', 'eixo_x': 'horizontal'}, None, self.pasta)
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa', None, {'arquivo': '../foto.jpeg', 'cantos': None}, self.pasta)
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg', 'cantos': [[1, 1]] * 4}, self.pasta)
    self.assertFalse(os.path.exists(os.path.join(self.pasta, 'plantas.json')))

  def test_avisos(self):
    with open(os.path.join(self.pasta, 'plantas.json'), 'w') as handle:
      json.dump({'casa': {'foto': {'arquivo': 'sumiu.jpg', 'cantos': None}}, 'galpao': {}}, handle)
    plantas, avisos = P.montar_plantas(self.env, self.pasta)
    self.assertTrue(any('galpao' in a for a in avisos))
    self.assertTrue(any('sumiu.jpg' in a for a in plantas['casa']['avisos']))

  def test_foto_corrompida_nao_derruba_as_paredes(self):
    with open(os.path.join(self.pasta, 'foto.jpeg'), 'wb') as handle:
      handle.write(b'nao e uma imagem de verdade')
    P.salvar_calibracao('casa', {'arquivo': 'paredes.csv', 'origem': 'inferior-direito', 'eixo_x': 'horizontal'},
                        None, self.pasta)
    config, _ = P.carregar_config(self.pasta)
    config['casa']['foto'] = {'arquivo': 'foto.jpeg', 'cantos': [[1, 1], [2, 1], [2, 2], [1, 2]]}
    with open(os.path.join(self.pasta, 'plantas.json'), 'w', encoding='utf-8') as handle:
      json.dump(config, handle)
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    casa = plantas['casa']
    self.assertIsNotNone(casa['paredes'])
    self.assertTrue(any('foto ignorada' in a for a in casa['avisos']))

  def test_cantos_degenerados_nao_deixam_foto_sem_papel(self):
    diamante = [[300, 900], [80, 500], [300, 120], [520, 500]]
    P.salvar_calibracao('casa', None, {'arquivo': 'foto.jpeg', 'cantos': diamante}, self.pasta)
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    casa = plantas['casa']
    self.assertIsNone(casa['foto'])
    self.assertIsNone(casa['papel'])
    self.assertTrue(any('foto ignorada' in a for a in casa['avisos']))


if __name__ == '__main__':
  unittest.main()

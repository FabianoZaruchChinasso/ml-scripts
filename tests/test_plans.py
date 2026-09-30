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

  def test_escala_fixa_leva_a_origem_para_dx_dy(self):
    cantos = {'superior-esquerdo': (100, 50), 'superior-direito': (300, 50),
              'inferior-esquerdo': (100, 650), 'inferior-direito': (300, 650)}
    for origem, eixo in COMBOS:
      px_para_cm, _ = P.registro_paredes(SEGMENTOS, origem, eixo, W, H, escala=1.0, dx=7.0, dy=-3.0)
      np.testing.assert_allclose(px_para_cm(*cantos[origem]), (7, -3), atol=1e-9, err_msg=origem + eixo)

  def test_escala_fixa_nao_estica_no_envelope(self):
    px_para_cm, _ = P.registro_paredes(SEGMENTOS, 'superior-esquerdo', 'horizontal', W, H, escala=2.0)
    np.testing.assert_allclose(px_para_cm(120, 90), (10, 20), atol=1e-9)

  def test_escala_fixa_ida_e_volta(self):
    for origem, eixo in COMBOS:
      px_para_cm, cm_para_px = P.registro_paredes(SEGMENTOS, origem, eixo, W, H, escala=1.0, dx=12.5, dy=-40.0)
      for x, y in [(0, 0), (58, 75), (861, 1448), (-20.5, 700.25)]:
        np.testing.assert_allclose(px_para_cm(*cm_para_px(x, y)), (x, y), atol=1e-9)

  def test_paredes_em_cm_com_escala(self):
    segmentos = np.array([[-101, 0, 760, 0], [760, 0, 760, 1348]], float)
    self.assertEqual(P.paredes_em_cm(segmentos, 'superior-esquerdo', 'horizontal', 861, 1448,
                                     escala=1.0, dx=10, dy=20),
                     [[10.0, 20.0, 871.0, 20.0], [871.0, 20.0, 871.0, 1368.0]])


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


class TestParedesMetros(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def _csv(self, nome, texto):
    path = os.path.join(self.pasta, nome)
    with open(path, 'w', encoding='utf-8') as handle:
      handle.write(texto)
    return path

  def test_so_paredes_em_cm(self):
    path = self._csv('m.csv', 'type,id,x1,y1,x2,y2,label,notes\n'
                              'wall,w1,0.0,0.0,5.12,0.0,,a\n'
                              'dim,c1,0.0,-0.38,2.53,-0.38,"2,53",cota\n'
                              'wall,w2,-1.01,0.0,-1.01,2.75,,"x, y"\n')
    np.testing.assert_allclose(P.ler_paredes_metros(path), [[0, 0, 512, 0], [-101, 0, -101, 275]])

  def test_sem_parede_levanta(self):
    path = self._csv('m.csv', 'type,id,x1,y1,x2,y2\ndim,c1,0,0,1,0\n')
    with self.assertRaises(ValueError):
      P.ler_paredes_metros(path)

  def test_coluna_faltando_levanta(self):
    path = self._csv('m.csv', 'type,id,x1,y1,x2\nwall,w1,0,0,1\n')
    with self.assertRaises(ValueError):
      P.ler_paredes_metros(path)


class TestAndarDe(unittest.TestCase):
  ANDARES = [{'id': 'baixo', 'z_min': None}, {'id': 'cima', 'z_min': 0}]

  def test_pelo_maior_piso_que_nao_passa_do_z(self):
    self.assertEqual(P.andar_de(80.0, self.ANDARES), 'cima')
    self.assertEqual(P.andar_de(0, self.ANDARES), 'cima')
    self.assertEqual(P.andar_de(-165.0, self.ANDARES), 'baixo')

  def test_z_nulo_nao_tem_andar(self):
    self.assertIsNone(P.andar_de(None, self.ANDARES))
    self.assertIsNone(P.andar_de(float('nan'), self.ANDARES))

  def test_abaixo_de_todos_os_pisos_nao_tem_andar(self):
    self.assertIsNone(P.andar_de(-1, [{'id': 'unico', 'z_min': 0}]))


class TestAndares(unittest.TestCase):
  REGISTRO = {'formato': 'metros', 'origem': 'superior-esquerdo', 'eixo_x': 'horizontal'}

  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    with open(os.path.join(self.pasta, 'cima.csv'), 'w', encoding='utf-8') as handle:
      handle.write('type,id,x1,y1,x2,y2,label,notes\n'
                   'wall,w1,-1.01,0.0,7.6,0.0,,topo\n'
                   'wall,w2,7.6,0.0,7.6,13.48,,lateral\n'
                   'dim,d1,-1.01,-0.42,2.64,-0.42,"3,65",cota\n')
    with open(os.path.join(self.pasta, 'baixo.csv'), 'w', encoding='utf-8') as handle:
      handle.write('type,id,x1,y1,x2,y2,label,notes\n'
                   'wall,w1,0.0,0.0,7.35,0.0,,topo\n'
                   'wall,w2,7.35,0.0,7.35,9.14,,lateral\n')
    self.env = {'casa-m': {'w': 861.0, 'h': 1448.0, 'routerZ': 80.0}}

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def _gravar(self, config):
    with open(os.path.join(self.pasta, 'plantas.json'), 'w', encoding='utf-8') as handle:
      json.dump(config, handle)

  def _config(self):
    with open(os.path.join(self.pasta, 'plantas.json'), encoding='utf-8') as handle:
      return json.load(handle)

  def _dois_andares(self, arquivo_baixo='baixo.csv'):
    return {'casa-m': {'andares': [
      {'id': 'baixo', 'z_min': None, 'paredes': dict(self.REGISTRO, arquivo=arquivo_baixo, dx=10, dy=20)},
      {'id': 'cima', 'z_min': 0, 'paredes': dict(self.REGISTRO, arquivo='cima.csv', dx=0, dy=0)},
    ]}}

  def test_um_item_por_andar_do_mais_alto_para_o_mais_baixo(self):
    self._gravar(self._dois_andares())
    plantas, avisos = P.montar_plantas(self.env, self.pasta)
    self.assertEqual(avisos, [])
    andares = plantas['casa-m']['andares']
    self.assertEqual([a['id'] for a in andares], ['cima', 'baixo'])
    cima, baixo = andares
    self.assertEqual(cima['paredes'], [[0.0, 0.0, 861.0, 0.0], [861.0, 0.0, 861.0, 1348.0]])
    self.assertEqual(baixo['paredes'][0], [10.0, 20.0, 745.0, 20.0])
    self.assertEqual(cima['papel'], [[1, 0], [0, 1]])
    self.assertIsNone(cima['foto'])
    self.assertEqual(cima['calibracao']['paredes'],
                     {'arquivo': 'cima.csv', 'origem': 'superior-esquerdo', 'eixo_x': 'horizontal',
                      'formato': 'metros', 'dx': 0.0, 'dy': 0.0})

  def test_roteador_so_no_andar_do_router_z(self):
    self._gravar(self._dois_andares())
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    self.assertEqual([a['roteador'] for a in plantas['casa-m']['andares']], [True, False])

  def test_csv_quebrado_de_um_andar_nao_afeta_o_outro(self):
    self._gravar(self._dois_andares(arquivo_baixo='sumiu.csv'))
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    cima, baixo = plantas['casa-m']['andares']
    self.assertIsNotNone(cima['paredes'])
    self.assertIsNone(baixo['paredes'])
    self.assertTrue(any('paredes ignoradas' in a for a in baixo['avisos']))

  def test_andares_invalidos_viram_aviso_e_planta_simples(self):
    self._gravar({'casa-m': {'andares': 'cima'}})
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    item = plantas['casa-m']
    self.assertNotIn('andares', item)
    self.assertIsNone(item['paredes'])
    self.assertTrue(any('andares ignorados' in a for a in item['avisos']))

  def test_salvar_grava_so_o_andar_pedido(self):
    config = self._dois_andares()
    config['casa'] = {'paredes': {'arquivo': 'x.csv', 'origem': 'inferior-direito', 'eixo_x': 'horizontal'}}
    self._gravar(config)
    P.salvar_calibracao('casa-m', dict(self.REGISTRO, arquivo='baixo.csv', dx=12, dy=-3), None,
                        self.pasta, andar='baixo')
    salvo = self._config()
    baixo = next(a for a in salvo['casa-m']['andares'] if a['id'] == 'baixo')
    cima = next(a for a in salvo['casa-m']['andares'] if a['id'] == 'cima')
    self.assertEqual(baixo['paredes'], {'arquivo': 'baixo.csv', 'origem': 'superior-esquerdo',
                                        'eixo_x': 'horizontal', 'formato': 'metros', 'dx': 12.0, 'dy': -3.0})
    self.assertEqual(cima, config['casa-m']['andares'][1])
    self.assertEqual(salvo['casa'], config['casa'])

  def test_salvar_recusa_andar_inexistente_dx_invalido_e_foto(self):
    self._gravar(self._dois_andares())
    bom = dict(self.REGISTRO, arquivo='baixo.csv', dx=0, dy=0)
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', bom, None, self.pasta, andar='sotao')
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', dict(bom, dx='abc'), None, self.pasta, andar='baixo')
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', dict(bom, formato='polegadas'), None, self.pasta, andar='baixo')
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', None, {'arquivo': 'f.jpeg', 'cantos': None}, self.pasta, andar='baixo')
    self.assertEqual(self._config(), self._dois_andares())

  def test_salvar_sem_andar_em_predio_com_andares_levanta(self):
    self._gravar(self._dois_andares())
    with self.assertRaises(ValueError):
      P.salvar_calibracao('casa-m', dict(self.REGISTRO, arquivo='cima.csv'), None, self.pasta)
    self.assertEqual(self._config(), self._dois_andares())

  def test_paredes_que_nao_e_objeto_vira_aviso_no_andar(self):
    self._gravar({'casa-m': {'andares': [
      {'id': 'cima', 'z_min': 0, 'paredes': 'cima.csv'},
      {'id': 'baixo', 'z_min': None, 'paredes': dict(self.REGISTRO, arquivo='baixo.csv', dx=0, dy=0)},
    ]}})
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    cima, baixo = plantas['casa-m']['andares']
    self.assertIsNone(cima['paredes'])
    self.assertTrue(any('paredes ignoradas' in a for a in cima['avisos']))
    self.assertIsNotNone(baixo['paredes'])

  def test_dx_nao_finito_vira_aviso_no_andar(self):
    self._gravar({'casa-m': {'andares': [
      {'id': 'cima', 'z_min': 0, 'paredes': dict(self.REGISTRO, arquivo='cima.csv', dx=0, dy=0)},
      {'id': 'baixo', 'z_min': None,
       'paredes': dict(self.REGISTRO, arquivo='baixo.csv', dx=float('nan'), dy=0)},
    ]}})
    plantas, _ = P.montar_plantas(self.env, self.pasta)
    cima, baixo = plantas['casa-m']['andares']
    self.assertIsNotNone(cima['paredes'])
    self.assertIsNone(baixo['paredes'])
    self.assertTrue(any('paredes ignoradas' in a for a in baixo['avisos']))
    self.assertIsNone(baixo['calibracao']['paredes'])


if __name__ == '__main__':
  unittest.main()

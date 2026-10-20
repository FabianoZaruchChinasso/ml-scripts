import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import sites as S
from ml.core.sites import BUILDING_ENVIRONMENT

# Todos os valores de `local` em data/ em 2026-10-20 e como o código antigo (regras em
# Python) os resolvia: (posição, prédio). O registro em JSON precisa dar o mesmo.
EQUIVALENCIA = {
  '1.0': ('res-sala', 'residencia'), '2.0': ('res-quarto', 'residencia'), '3.0': ('res-suite', 'residencia'),
  'sala': ('res-sala', 'residencia'), 'quarto': ('res-quarto', 'residencia'), 'suite': ('res-suite', 'residencia'),
  'cwpb-1': ('cwpb-1', 'coworking'), 'cwpb-10m': ('cwpb-10m', 'coworking'),
  'cwpb-10m-2a': ('cwpb-10m-2a', 'coworking'), 'cwpb-13m': ('cwpb-13m', 'coworking'),
  'cwpb-2': ('cwpb-2', 'coworking'), 'cwpb-2m': ('cwpb-2m', 'coworking'),
  'hotmilk-aquario': ('hotmilk-aquario', 'hotmilk'), 'hotmilk-aquario-fora': ('hotmilk-aquario-fora', 'hotmilk'),
  'hotmilk-copa': ('hotmilk-copa', 'hotmilk'), 'quarto-marcelo': ('hotmilk-aquario', 'hotmilk'),
  'marcelo-copa': ('marcelo-copa', 'casa-marcelo'), 'marcelo-copa-split': ('marcelo-copa-split', 'casa-marcelo'),
  'marcelo-inf-ext': ('marcelo-inf-ext', 'casa-marcelo'), 'marcelo-inf-quarto': ('marcelo-inf-quarto', 'casa-marcelo'),
  'marcelo-inf-quarto-split': ('marcelo-inf-quarto-split', 'casa-marcelo'),
  'marcelo-inf-sala': ('marcelo-inf-sala', 'casa-marcelo'), 'marcelo-inf-sala-split': ('marcelo-inf-sala-split', 'casa-marcelo'),
  'marcelo-quarto': ('marcelo-quarto', 'casa-marcelo'), 'marcelo-quarto-split': ('marcelo-quarto-split', 'casa-marcelo'),
  'marcelo-sala-estar': ('marcelo-sala-estar', 'casa-marcelo'),
}


class TestEquivalencia(unittest.TestCase):
  def test_registro_resolve_como_o_codigo_antigo(self):
    valores = pd.Series(list(EQUIVALENCIA))
    posicoes = list(S.resolve_site_id(valores))
    predios = list(S.resolve_site_id(valores, level='building'))
    self.assertEqual(posicoes, [p for p, _ in EQUIVALENCIA.values()])
    self.assertEqual(predios, [b for _, b in EQUIVALENCIA.values()])

  def test_ambientes_e_tetos(self):
    # Os quatro prédios históricos; prédios cadastrados depois pelo Studio podem existir além deles.
    esperado = {'residencia': 'domestico', 'coworking': 'corporativo', 'hotmilk': 'corporativo',
                'casa-marcelo': 'domestico'}
    self.assertEqual({k: BUILDING_ENVIRONMENT[k] for k in esperado}, esperado)
    self.assertEqual(S.teto_wan('residencia', 'speedtest_up_mbps'), 99.0)
    self.assertIsNone(S.teto_wan('hotmilk', 'speedtest_down_mbps'))

  def test_valor_desconhecido_cita_o_registro(self):
    with self.assertRaises(ValueError) as ctx:
      S.resolve_site_id(pd.Series(['zeta-sala']))
    self.assertIn('zeta-sala', str(ctx.exception))
    self.assertIn('predios.json', str(ctx.exception))


class TestValidacao(unittest.TestCase):
  def setUp(self):
    self.reg = S.registro_atual()

  def recusa(self, trecho):
    with self.assertRaises(ValueError) as ctx:
      S.validar_predios(self.reg)
    self.assertIn(trecho, str(ctx.exception))

  def test_registro_atual_e_valido_e_uma_copia(self):
    S.validar_predios(self.reg)
    self.reg['predios'].clear()
    self.assertIn('hotmilk', S.registro_atual()['predios'])

  def test_recusa_prefixo_que_comeca_com_outro(self):
    self.reg['predios']['casa-marcelo']['prefixos'].append('marcelo2')
    self.recusa('marcelo2')

  def test_recusa_prefixo_repetido_entre_predios(self):
    self.reg['predios']['coworking']['prefixos'].append('hotmilk')
    self.recusa('hotmilk')

  def test_recusa_ambiente_invalido(self):
    self.reg['predios']['hotmilk']['ambiente'] = 'industrial'
    self.recusa('industrial')

  def test_recusa_chave_invalida(self):
    self.reg['predios']['Casa Nova'] = copy.deepcopy(self.reg['predios']['hotmilk'])
    self.reg['predios']['Casa Nova']['prefixos'] = ['nova']
    self.reg['predios']['Casa Nova']['studio'] = 'nova'
    self.recusa('Casa Nova')

  def test_recusa_predio_sem_prefixo_e_sem_posicoes(self):
    self.reg['predios']['hotmilk']['prefixos'] = []
    self.recusa('hotmilk')

  def test_recusa_chave_do_studio_repetida(self):
    self.reg['predios']['hotmilk']['studio'] = 'casa'
    self.recusa('casa')

  def test_recusa_posicao_que_comeca_com_prefixo(self):
    self.reg['predios']['residencia']['posicoes']['cwpb-x'] = 'res-sala'
    self.recusa('cwpb-x')


class TestCadastro(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'predios.json')
    shutil.copyfile(S.PREDIOS_PATH, self.path)
    S.recarregar(self.path)

  def tearDown(self):
    S.recarregar(S.PREDIOS_PATH)
    shutil.rmtree(self.pasta)

  def zeta(self, **extra):
    return dict({'chave': 'casa-zeta', 'rotulo': 'Casa Zeta', 'ambiente': 'domestico', 'prefixo': 'zeta'}, **extra)

  def test_cadastra_grava_e_resolve(self):
    S.cadastrar_predios([self.zeta()])
    self.assertEqual(list(S.resolve_site_id(pd.Series(['zeta-sala']), level='building')), ['casa-zeta'])
    with open(self.path, encoding='utf-8') as h:
      gravado = json.load(h)['predios']['casa-zeta']
    self.assertEqual(gravado, {'rotulo': 'Casa Zeta', 'studio': 'casa-zeta', 'ambiente': 'domestico',
                               'prefixos': ['zeta']})

  def test_atualiza_o_dicionario_importado_no_lugar(self):
    antes = BUILDING_ENVIRONMENT
    S.cadastrar_predios([self.zeta()])
    self.assertIs(antes, S.BUILDING_ENVIRONMENT)
    self.assertEqual(BUILDING_ENVIRONMENT['casa-zeta'], 'domestico')

  def test_recusa_chave_existente_sem_gravar(self):
    with open(self.path, encoding='utf-8') as h:
      antes = h.read()
    with self.assertRaises(ValueError):
      S.cadastrar_predios([self.zeta(chave='hotmilk')])
    with open(self.path, encoding='utf-8') as h:
      self.assertEqual(h.read(), antes)

  def test_recusa_prefixo_em_conflito(self):
    with self.assertRaises(ValueError):
      S.cadastrar_predios([self.zeta(prefixo='marcelo2')])
    self.assertNotIn('casa-zeta', BUILDING_ENVIRONMENT)

  def test_recusa_campos_faltando(self):
    with self.assertRaises(ValueError):
      S.cadastrar_predios([{'chave': 'casa-zeta', 'prefixo': 'zeta'}])

  def test_com_novos_nao_toca_no_registro(self):
    reg = S.registro_atual()
    novo = S.com_novos(reg, [self.zeta()])
    self.assertIn('casa-zeta', novo['predios'])
    self.assertNotIn('casa-zeta', reg['predios'])

  def test_resolve_com_registro_explicito(self):
    reg = S.com_novos(S.registro_atual(), [self.zeta()])
    self.assertEqual(list(S.resolve_site_id(pd.Series(['zeta-x']), level='building', registro=reg)), ['casa-zeta'])
    with self.assertRaises(ValueError):
      S.resolve_site_id(pd.Series(['zeta-x']))


class TestStudio(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'predios.json')
    shutil.copyfile(S.PREDIOS_PATH, self.path)
    S.recarregar(self.path)

  def tearDown(self):
    S.recarregar(S.PREDIOS_PATH)
    from ml.studio import data as D
    D.limpar_cache_predios()
    shutil.rmtree(self.pasta)

  def test_predios_do_studio_vem_do_registro(self):
    from ml.studio import data as D
    self.assertEqual(D.predios_studio()['casa'], {'label': 'Casa', 'ambiente': 'domestico'})
    self.assertEqual(D.predio_studio_do_core('residencia'), 'casa')

  def test_predio_cadastrado_aparece_depois_de_limpar_o_cache(self):
    from ml.studio import data as D
    with self.assertRaises(ValueError):
      D._building_of('zeta-sala')
    S.cadastrar_predios([{'chave': 'casa-zeta', 'rotulo': 'Casa Zeta', 'ambiente': 'domestico',
                          'prefixo': 'zeta'}])
    D.limpar_cache_predios()
    self.assertEqual(D._building_of('zeta-sala'), 'casa-zeta')
    self.assertIn('casa-zeta', D.predios_studio())


if __name__ == '__main__':
  unittest.main()

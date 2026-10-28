import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import aplicacoes as AP


def app(**valores):
  base = {'dn': 1, 'up': 1, 'lat': 1, 'jit': 1}
  base.update(valores)
  return base


class TestAplicacoes(unittest.TestCase):
  def test_arquivo_do_repositorio_e_valido_e_igual_ao_studio(self):
    apps = AP.carregar()
    self.assertEqual(list(apps), ['Navegação', 'Chamada de vídeo', 'Streaming 4K', 'Jogo em nuvem'])
    self.assertEqual(apps['Chamada de vídeo'], {'dn': 3.8, 'up': 3.8, 'lat': 150, 'jit': 30})

  def test_chave_raiz_errada_levanta(self):
    with self.assertRaises(ValueError):
      AP.validar({'apps': {'X': app()}})

  def test_sem_aplicacao_levanta(self):
    with self.assertRaises(ValueError):
      AP.validar({'aplicacoes': {}})

  def test_chave_faltando_nomeia_a_aplicacao(self):
    with self.assertRaisesRegex(ValueError, 'Navegação'):
      AP.validar({'aplicacoes': {'Navegação': {'dn': 1, 'up': 1, 'lat': 1}}})

  def test_valor_negativo_nomeia_o_campo(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn"):
      AP.validar({'aplicacoes': {'X': app(dn=-1)}})

  def test_booleano_nao_conta_como_numero(self):
    with self.assertRaises(ValueError):
      AP.validar({'aplicacoes': {'X': app(dn=True)}})


  def test_versao_muda_com_o_conteudo(self):
    with tempfile.TemporaryDirectory() as pasta:
      path = os.path.join(pasta, 'aplicacoes.json')
      with open(path, 'w', encoding='utf-8') as handle:
        handle.write('{"a": 1}')
      antes = AP.versao(path)
      with open(path, 'w', encoding='utf-8') as handle:
        handle.write('{"a": 2}')
      self.assertNotEqual(antes, AP.versao(path))
      self.assertEqual(AP.versao(os.path.join(pasta, 'nao-existe.json')), 'ausente')

  def test_chave_de_cache_do_studio_inclui_as_aplicacoes(self):
    from ml.studio import api
    with mock.patch.object(AP, 'versao', return_value='x1'):
      antes = api._chave_versoes()
    with mock.patch.object(AP, 'versao', return_value='x2'):
      depois = api._chave_versoes()
    self.assertNotEqual(antes, depois)


def norma(**trocas):
  """Arquivo de norma mínimo e válido; `trocas` substitui limiares de 'X'."""
  def item(v):
    return {'valor': v, 'fonte': 'teste', 'url': 'https://exemplo', 'nota': ''}
  limiares = {c: item(1) for c in AP.CHAVES}
  limiares.update(trocas)
  return {'perfil': 'norma', 'aplicacoes': {'X': limiares}}


class TestPerfis(unittest.TestCase):
  def test_atual_continua_igual_ao_carregar(self):
    self.assertEqual(AP.carregar_perfil('atual'), AP.carregar())

  def test_norma_do_repositorio_tem_as_quatro_aplicacoes_e_os_valores_da_spec(self):
    apps = AP.carregar_perfil('norma')
    self.assertEqual(list(apps), ['Navegação', 'Chamada de vídeo', 'Streaming 4K', 'Jogo em nuvem'])
    self.assertEqual(apps['Chamada de vídeo'], {'dn': 3.0, 'up': 3.8, 'lat': 200, 'jit': 50})
    self.assertEqual(apps['Streaming 4K']['dn'], 15)
    self.assertEqual(apps['Jogo em nuvem'], {'dn': 15, 'up': 1, 'lat': 80, 'jit': 10})
    self.assertEqual(apps['Navegação']['lat'], 800)

  def test_toda_norma_tem_fonte(self):
    self.assertTrue(AP.fontes('norma'))
    for nome, chaves in AP.fontes('norma').items():
      for chave, info in chaves.items():
        self.assertTrue(info['fonte'].strip(), f'{nome}.{chave} sem fonte')

  def test_atual_nao_tem_fontes(self):
    self.assertEqual(AP.fontes('atual'), {})

  def test_perfil_desconhecido_levanta(self):
    with self.assertRaisesRegex(ValueError, 'perfil'):
      AP.carregar_perfil('outro')

  def test_norma_sem_fonte_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn: fonte"):
      AP.validar_norma(norma(dn={'valor': 1, 'fonte': ' '}))

  def test_norma_sem_valor_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.up.*valor"):
      AP.validar_norma(norma(up={'fonte': 'x'}))

  def test_norma_valor_negativo_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.lat"):
      AP.validar_norma(norma(lat={'valor': -1, 'fonte': 'x'}))

  def test_norma_chave_raiz_errada_levanta(self):
    with self.assertRaises(ValueError):
      AP.validar_norma({'aplicacoes': norma()['aplicacoes']})

  def test_norma_campo_desconhecido_levanta(self):
    with self.assertRaisesRegex(ValueError, 'campos'):
      AP.validar_norma(norma(jit={'valor': 1, 'fonte': 'x', 'peso': 2}))


  def test_norma_url_nao_texto_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn: url"):
      AP.validar_norma(norma(dn={'valor': 1, 'fonte': 'x', 'url': 5}))

  def test_norma_nota_nao_texto_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn: nota"):
      AP.validar_norma(norma(dn={'valor': 1, 'fonte': 'x', 'nota': 3}))

  def test_norma_valor_booleano_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn"):
      AP.validar_norma(norma(dn={'valor': True, 'fonte': 'x'}))

  def test_norma_item_que_nao_e_dict_levanta(self):
    with self.assertRaisesRegex(ValueError, r"'X'\.dn"):
      AP.validar_norma(norma(dn=5))

  def test_fontes_perfil_desconhecido_levanta(self):
    with self.assertRaisesRegex(ValueError, 'perfil'):
      AP.fontes('outro')

  def test_fontes_sempre_traz_fonte_url_e_nota(self):
    dados = norma(dn={'valor': 1, 'fonte': 'so fonte'})
    with tempfile.TemporaryDirectory() as pasta:
      path = os.path.join(pasta, 'norma.json')
      with open(path, 'w', encoding='utf-8') as handle:
        json.dump(dados, handle)
      info = AP.fontes('norma', path=path)['X']['dn']
    self.assertEqual(info, {'fonte': 'so fonte', 'url': '', 'nota': ''})


if __name__ == '__main__':
  unittest.main()

import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import ativar_mlflow as A
from test_registry_mlflow import ComBanco


class TestAtivar(ComBanco):
  def rodar(self, **env) -> str:
    saida = io.StringIO()
    for chave in ('MODELO', 'VERSAO'):
      os.environ.pop(chave, None)
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(saida):
      A.main()
    return saida.getvalue()

  def test_sem_alias_mostrar_sai_com_mensagem(self):
    with self.assertRaises(SystemExit) as erro:
      self.rodar()
    self.assertIn('nenhuma versão ativa', str(erro.exception))

  def test_ativa_pela_definicao_e_mostra(self):
    self.registrar('v1')
    self.registrar('v5')
    self.registrar('v5')
    self.assertIn('nenhuma -> 3 (v5)', self.rodar(MODELO='v5'))
    self.assertIn('versão 3', self.rodar())
    self.assertIn('definição v5', self.rodar())

  def test_ativa_pelo_numero(self):
    self.registrar('v1')
    self.registrar('v5')
    self.rodar(VERSAO='2')
    self.assertIn('2 (v5) -> 1 (v1)', self.rodar(VERSAO='1'))

  def test_erros(self):
    self.registrar('v5')
    for env, trecho in (({'MODELO': 'v5', 'VERSAO': '1'}, 'não os dois'), ({'VERSAO': 'x'}, 'número'),
                        ({'VERSAO': '7'}, 'versão 7'), ({'MODELO': 'v9'}, "'v9'")):
      with self.subTest(env=env):
        with self.assertRaises(SystemExit) as erro:
          self.rodar(**env)
        self.assertIn(trecho, str(erro.exception))


if __name__ == '__main__':
  unittest.main()

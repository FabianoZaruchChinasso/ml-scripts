import os
import sys
import tempfile
import unittest
from unittest import mock

import mlflow

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import registry_mlflow as G

REGISTRO = {'versoes': {'v1': {'features': ['a']}, 'v5': {'features': ['a', 'b']}}}


class Eco(mlflow.pyfunc.PythonModel):
  def predict(self, context, model_input, params=None):
    return model_input


class ComBanco(unittest.TestCase):
  """Banco SQLite temporário; artefatos dentro da pasta temporária."""

  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    self.tmp = tmp.name
    self.addCleanup(mlflow.set_tracking_uri, mlflow.get_tracking_uri())
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{self.tmp}/mlflow.db'})
    env.start()
    self.addCleanup(env.stop)

  def modelo(self) -> str:
    """Um pyfunc gravado num run; devolve o model_uri (models:/m-...)."""
    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    exp = mlflow.get_experiment_by_name('t')
    exp_id = exp.experiment_id if exp else mlflow.create_experiment('t', artifact_location=os.path.join(self.tmp, 'art'))
    with mlflow.start_run(experiment_id=exp_id):
      return mlflow.pyfunc.log_model(name='pacote', python_model=Eco(), signature=False).model_uri

  def registrar(self, definicao='v5') -> int:
    return G.registrar(self.modelo(), definicao, ['abc', 'def'], 'p1')


class TestSemBanco(unittest.TestCase):
  def test_sem_arquivo_levanta_e_nao_cria_o_banco(self):
    with tempfile.TemporaryDirectory() as tmp:
      caminho = os.path.join(tmp, 'mlflow.db')
      with mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{caminho}'}):
        with self.assertRaisesRegex(G.SemVersaoAtiva, 'não há banco'):
          G.ativa()
        self.assertIsNone(G.definicao_ativa())
      self.assertFalse(os.path.exists(caminho))


class TestRegistrar(ComBanco):
  def test_cria_versoes_com_as_tags(self):
    self.assertEqual(self.registrar('v1'), 1)
    self.assertEqual(self.registrar('v5'), 2)
    v = G.core_registro_mlflow.cliente().get_model_version(G.NOME_MODELO, '2')
    self.assertEqual(v.tags, {'definicao': 'v5', 'fingerprints': 'abc,def', 'versao_pacote': 'p1'})

  def test_versao_da_definicao_e_a_mais_recente(self):
    self.registrar('v5')
    self.registrar('v1')
    self.registrar('v5')
    self.assertEqual(G.versao_da_definicao('v5'), 3)
    self.assertEqual(G.versao_da_definicao('v1'), 2)
    with self.assertRaisesRegex(ValueError, 'v2-tr069'):
      G.versao_da_definicao('v2-tr069')

  def test_registrar_nao_move_o_alias(self):
    self.registrar()
    with self.assertRaises(G.SemVersaoAtiva):
      G.ativa()


class TestAtivar(ComBanco):
  def test_sem_modelo_registrado(self):
    self.modelo()  # cria o banco, sem registrar
    with self.assertRaisesRegex(G.SemVersaoAtiva, 'alias'):
      G.ativa()
    self.assertIsNone(G.definicao_ativa())

  def test_ativar_e_ler(self):
    self.registrar('v1')
    self.registrar('v5')
    self.assertEqual(G.ativar(1), {'anterior': None, 'atual': 1, 'definicao_anterior': None, 'definicao_atual': 'v1'})
    self.assertEqual(G.ativar(2), {'anterior': 1, 'atual': 2, 'definicao_anterior': 'v1', 'definicao_atual': 'v5'})
    a = G.ativa()
    self.assertEqual((a['versao'], a['definicao']), (2, 'v5'))
    self.assertTrue(a['run_id'])
    self.assertEqual(G.definicao_ativa(), 'v5')

  def test_versao_inexistente(self):
    self.registrar()
    with self.assertRaisesRegex(ValueError, 'versão 9'):
      G.ativar(9)


class TestEscolherDefinicao(ComBanco):
  def test_explicita_vence_o_alias(self):
    self.registrar('v5')
    G.ativar(1)
    self.assertEqual(G.escolher_definicao('v1', REGISTRO), 'v1')
    self.assertEqual(G.escolher_definicao(None, REGISTRO), 'v5')
    self.assertEqual(G.escolher_definicao('', REGISTRO), 'v5')

  def test_sem_alias_sai_dizendo_o_que_fazer(self):
    with self.assertRaises(SystemExit) as erro:
      G.escolher_definicao(None, REGISTRO)
    self.assertIn('MODELO=', str(erro.exception))
    self.assertIn('ativar_mlflow.py', str(erro.exception))

  def test_definicao_inexistente(self):
    with self.assertRaises(SystemExit) as erro:
      G.escolher_definicao('v9', REGISTRO)
    self.assertIn("'v9'", str(erro.exception))
    self.assertIn("['v1', 'v5']", str(erro.exception))

  def test_alias_apontando_para_definicao_apagada(self):
    self.registrar('v3-velha')
    G.ativar(1)
    with self.assertRaises(SystemExit) as erro:
      G.escolher_definicao(None, REGISTRO)
    self.assertIn('ativa no Registry', str(erro.exception))


class TestScriptsUsamOAlias(unittest.TestCase):
  SCRIPTS = ('qoe_mlflow.py', 'regression_mlflow.py', 'compare_protocols.py', 'classification_benchmark.py',
             'regression_benchmark.py', 'comodo_benchmark.py', 'versao_mlflow.py')

  def test_nenhum_script_le_o_campo_ativo(self):
    pasta = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'ml'))
    for arq in self.SCRIPTS:
      with open(os.path.join(pasta, arq), encoding='utf-8') as f:
        texto = f.read()
      with self.subTest(arq=arq):
        self.assertNotIn("['ativo']", texto)
        self.assertIn('core_registry', texto)


class TestNinguemLeOCampoAtivo(unittest.TestCase):
  def test_codigo_python_nao_le_o_campo_ativo(self):
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
    achados = []
    for pasta, _, arquivos in os.walk(raiz):
      for arq in arquivos:
        if arq.endswith('.py'):
          with open(os.path.join(pasta, arq), encoding='utf-8') as f:
            for i, linha in enumerate(f, 1):
              if "['ativo']" in linha or 'core_modelos.ativo(' in linha or 'definir_ativo' in linha:
                achados.append(f'{arq}:{i}')
    self.assertEqual(achados, [])

  def test_modelos_json_do_repositorio_nao_tem_ativo(self):
    from ml.core import modelos as M
    self.assertNotIn('ativo', M.carregar())


if __name__ == '__main__':
  unittest.main()

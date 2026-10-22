"""Isolamento do Studio novo: não importa ml.* e não escreve no que é do benchmark."""

import ast
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, conjunto, dados, predios, registro, treino, upload  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PACOTE = os.path.join(REPO, 'src', 'studio')


def modulos_importados(path: str):
  with open(path, encoding='utf-8') as handle:
    arvore = ast.parse(handle.read(), path)
  for no in ast.walk(arvore):
    if isinstance(no, ast.Import):
      for alias in no.names:
        yield alias.name
    elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
      yield no.module


def imports_de_ml(pasta: str) -> list:
  achados = []
  for raiz, _, nomes in os.walk(pasta):
    for nome in nomes:
      if not nome.endswith('.py'):
        continue
      path = os.path.join(raiz, nome)
      for modulo in modulos_importados(path):
        if modulo == 'ml' or modulo.startswith('ml.'):
          achados.append(f'{os.path.relpath(path, REPO)}: {modulo}')
  return achados


class TestImports(unittest.TestCase):
  def test_detector_pega_import_de_ml(self):
    with tempfile.TemporaryDirectory() as pasta:
      with open(os.path.join(pasta, 'x.py'), 'w', encoding='utf-8') as handle:
        handle.write('from ml.core import carga\nimport ml\nimport mlflow\n')
      self.assertEqual(len(imports_de_ml(pasta)), 2)

  def test_pacote_studio_nao_importa_ml(self):
    self.assertTrue(os.path.isdir(PACOTE))
    self.assertEqual(imports_de_ml(PACOTE), [])


PROTEGIDOS = [os.path.join(REPO, 'data'), os.path.join(REPO, 'src', 'ml'),
              os.path.join(REPO, 'mlflow.db'), os.path.join(REPO, 'mlruns')]


def assinatura(caminhos_protegidos) -> dict:
  """{arquivo: (tamanho, mtime_ns)} de tudo sob os caminhos, menos __pycache__.

  Tamanho e mtime em vez de hash: mlruns/ tem mais de 1 GB, e qualquer escrita muda o mtime.
  """
  saida = {}
  for alvo in caminhos_protegidos:
    if os.path.isfile(alvo):
      arquivos = [alvo]
    elif os.path.isdir(alvo):
      arquivos = []
      for raiz, dirs, nomes in os.walk(alvo):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        arquivos += [os.path.join(raiz, n) for n in nomes]
    else:
      arquivos = []
    for path in arquivos:
      st = os.stat(path)
      saida[path] = (st.st_size, st.st_mtime_ns)
  return saida


class TestNaoEscreve(unittest.TestCase):
  def test_upload_conjunto_e_payload_nao_tocam_o_que_e_do_benchmark(self):
    registro_real = predios.carregar(caminhos.PREDIOS_PATH)
    antes = assinatura(PROTEGIDOS)
    with A.pastas_temporarias(registro_real) as p:
      # Lê o data/ de verdade; grava só nas pastas temporárias.
      caminhos.DATA_DIR = os.path.join(REPO, 'data')
      novo = A.frame(['hotmilk-teste-a', 'cwpb-teste-b'], semente=99, deslocamento=0.123)
      token = upload.guardar('studio-teste.csv', novo.to_csv(index=False).encode('utf-8'))
      r = upload.confirmar(token, 'studio-teste.csv')
      self.assertEqual(r['dataset'], 'studio-teste.csv')
      self.assertTrue(os.path.exists(os.path.join(p.uploads, 'studio-teste.csv')))
      from studio import catalogo
      catalogo.esquecer()
      conjunto.gravar(conjunto.ler() + ['studio-teste.csv'])
      payload = dados.montar_payload()
      self.assertIn('studio-teste.csv', [d['id'] for d in payload['datasets']])
    self.assertEqual(assinatura(PROTEGIDOS), antes)

  def test_treino_promocao_e_reavaliacao_nao_tocam_o_mlflow_do_fabiano(self):
    registro_real = predios.carregar(caminhos.PREDIOS_PATH)
    antes = assinatura(PROTEGIDOS)
    with A.pastas_temporarias(registro_real) as p, A.mlflow_temporario():
      novo = A.frame(['hotmilk-teste-a', 'cwpb-teste-b'], semente=98, deslocamento=0.456)
      A.gravar_csv(p.uploads, 'studio-teste.csv', novo)
      pedido = treino.Pedido(alvo='speedtest_down_mbps', datasets=['studio-teste.csv'],
                             features=['router_snr', 'router_signal_dbm'], hiper={'n_estimators': 5})
      r = treino.executar(treino.preparar(pedido))
      registro.promover('speedtest_down_mbps', r['versao'])
      prep = registro.preparar_reavaliacao('speedtest_down_mbps', r['versao'], ['studio-teste.csv'])
      registro.executar_reavaliacao(prep)
    self.assertEqual(assinatura(PROTEGIDOS), antes)


if __name__ == '__main__':
  unittest.main()

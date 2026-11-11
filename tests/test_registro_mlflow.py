import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import registro_mlflow as R

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def versao_sintetica() -> dict:
  return {
    'features': ['a', 'b'],
    'denominador': {'speedtest_down_mbps': {'coluna': 'x', 'radio': '5ghz'}},
    'cobertura': {'nivel': 'parcial'},
    'avaliacao': {
      'perfil': 'residencial',
      'comodo': {'ambiente': 'todos', 'datasets': ['d1.zip', 'd2.csv'], 'nota': 0.7, 'intervalo': [0.6, 0.8],
                 'piso': {'nota': 0.45}, 'contra_piso': {'diferenca': 0.27}, 'graves': 2,
                 'jogo': {'nota': 0.64, 'intervalo': [0.5, 0.78], 'piso': {'nota': 0.55}},
                 'versao_comodo': 'v-c', 'posicoes': [{'pos': 'p1'}], 'piso_posicoes': [{'pos': 'p2'}]},
      'atende_completo': {'media': 0.66}, 'atende_throughput': {'media': 0.65},
      'speedtest_down_mbps': {'pooled': 0.75, 'mae': 59.0, 'mae_log': 0.6, 'versao_regua': 'r1'},
      'latency_ms': {'pooled': -0.1, 'mae': 22.8, 'quantis': {'cobertura': {'q50': 0.5, 'q90': 0.91}}},
    },
  }


class TestUri(unittest.TestCase):
  def test_variavel_de_ambiente_tem_prioridade(self):
    with mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': 'sqlite:////tmp/outro.db'}):
      self.assertEqual(R.uri_rastreamento(), 'sqlite:////tmp/outro.db')

  def test_sem_variavel_usa_o_banco_da_raiz_com_caminho_absoluto(self):
    with mock.patch.dict(os.environ, {}):
      os.environ.pop('MLFLOW_TRACKING_URI', None)
      uri = R.uri_rastreamento()
    self.assertEqual(uri, 'sqlite:///' + os.path.join(RAIZ, 'mlflow.db'))
    self.assertTrue(uri.startswith('sqlite:////'))


class TestParametrosEMetricas(unittest.TestCase):
  def test_parametros(self):
    params, _ = R.parametros_e_metricas('v9', versao_sintetica())
    self.assertEqual(params['modelo'], 'v9')
    self.assertNotIn('ativo', params)  # ativo é tag: parâmetro não muda depois de gravado
    self.assertEqual(params['features'], 'a,b')
    self.assertEqual(params['n_features'], 2)
    self.assertEqual(params['datasets'], 'd1.zip,d2.csv')
    self.assertEqual(params['perfil'], 'residencial')
    self.assertEqual(params['cobertura_tr069'], 'parcial')
    self.assertEqual(params['versao_comodo'], 'v-c')
    self.assertEqual(params['versao_regua'], 'r1')
    self.assertIn('radio', params['denominador'])

  def test_denominador_ausente(self):
    versao = versao_sintetica()
    versao['denominador'] = None
    params, _ = R.parametros_e_metricas('v9', versao)
    self.assertEqual(params['denominador'], 'nenhum')

  def test_metricas_e_ausentes_ignoradas(self):
    _, m = R.parametros_e_metricas('v9', versao_sintetica())
    self.assertEqual(m['comodo_nota'], 0.7)
    self.assertEqual(m['comodo_lo90'], 0.6)
    self.assertEqual(m['comodo_hi90'], 0.8)
    self.assertEqual(m['comodo_piso'], 0.45)
    self.assertEqual(m['comodo_contra_piso'], 0.27)
    self.assertEqual(m['comodo_graves'], 2)
    self.assertEqual(m['jogo_nota'], 0.64)
    self.assertEqual(m['jogo_piso'], 0.55)
    self.assertEqual(m['atende_completo'], 0.66)
    self.assertEqual(m['down_pooled'], 0.75)
    self.assertEqual(m['down_mae_log'], 0.6)
    self.assertEqual(m['lat_cobertura_q90'], 0.91)
    for ausente in ('atende_ajustado', 'up_pooled', 'jit_mae', 'jit_cobertura_q90', 'down_cobertura_q90'):
      self.assertNotIn(ausente, m)
    self.assertNotIn('lat_mae_log', m)

  def test_bloco_comodo_ausente(self):
    versao = versao_sintetica()
    del versao['avaliacao']['comodo']
    params, m = R.parametros_e_metricas('v9', versao)
    self.assertEqual(params['datasets'], '')
    self.assertFalse([k for k in m if k.startswith(('comodo_', 'jogo_'))])

class Base(unittest.TestCase):
  """Cada teste com um mlflow.db próprio numa pasta temporária."""

  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    self.tmp = tmp.name
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{self.tmp}/mlflow.db'})
    env.start()
    self.addCleanup(env.stop)

  def runs(self):
    cli = R.cliente()
    exp = cli.get_experiment_by_name(R.EXPERIMENTO)
    return [] if exp is None else list(cli.search_runs([exp.experiment_id], max_results=1000))

  def tags(self, run_id):
    return R.cliente().get_run(run_id).data.tags


class TestRegistrarAvaliacao(Base):
  def test_cria_run_com_tags_parametros_metricas_e_artefatos(self):
    rid = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar')
    run = R.cliente().get_run(rid)
    self.assertEqual(run.info.run_name, 'v9-studio')
    self.assertEqual(run.info.status, 'FINISHED')
    for chave, valor in {'modelo': 'v9', 'evento': 'salvar', 'atual': 'sim', 'versao_comodo': 'v-c'}.items():
      self.assertEqual(run.data.tags[chave], valor)
    self.assertNotIn('ativo', run.data.tags)   # a ativa é o alias do Model Registry
    self.assertEqual(run.data.params['features'], 'a,b')
    self.assertNotIn('ativo', run.data.params)
    self.assertEqual(run.data.metrics['comodo_nota'], 0.7)
    nomes = {a.path for a in R.cliente().list_artifacts(rid)}
    self.assertEqual(nomes, {'avaliacao.json', 'posicoes.json'})

  def test_artefatos_ficam_ao_lado_do_banco(self):
    R.registrar_avaliacao('v9', versao_sintetica(), 'salvar')
    exp = R.cliente().get_experiment_by_name(R.EXPERIMENTO)
    self.assertIn(self.tmp, exp.artifact_location)

  def test_sem_bloco_comodo_nao_tem_tag_versao_comodo(self):
    versao = versao_sintetica()
    del versao['avaliacao']['comodo']
    rid = R.registrar_avaliacao('v9', versao, 'reavaliar')
    tags = self.tags(rid)
    self.assertNotIn('versao_comodo', tags)

  def test_segundo_registro_vira_o_atual_e_nao_toca_outras_versoes(self):
    primeiro = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar')
    outra = R.registrar_avaliacao('v8', versao_sintetica(), 'salvar')
    segundo = R.registrar_avaliacao('v9', versao_sintetica(), 'reavaliar')
    self.assertEqual(self.tags(primeiro)['atual'], 'nao')
    self.assertEqual(self.tags(segundo)['atual'], 'sim')
    self.assertEqual(self.tags(outra)['atual'], 'sim')
    self.assertEqual(len(self.runs()), 3)  # histórico: nada é apagado

  def test_evento_invalido_levanta_sem_criar_run(self):
    with self.assertRaises(ValueError):
      R.registrar_avaliacao('v9', versao_sintetica(), 'outro')
    self.assertEqual(self.runs(), [])

  def test_falha_no_meio_marca_o_run_como_falho_e_mantem_o_atual_anterior(self):
    anterior = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar')
    with mock.patch('mlflow.MlflowClient.log_dict', side_effect=OSError('disco cheio')):
      with self.assertRaises(OSError):
        R.registrar_avaliacao('v9', versao_sintetica(), 'reavaliar')
    falhos = [r for r in self.runs() if r.info.status == 'FAILED']
    self.assertEqual(len(falhos), 1)
    self.assertEqual(falhos[0].data.tags['atual'], 'nao')
    self.assertEqual(self.tags(anterior)['atual'], 'sim')

class TestRunAntigo(Base):
  def run_antigo(self, nome=None):
    """Run como os gravados antes de 2026-11-09: sem tags, só o parâmetro 'modelo' (ou nem ele)."""
    cli = R.cliente()
    run = cli.create_run(R._experimento(cli), run_name=f'{nome or "sem-nome"}-studio')
    if nome:
      cli.log_param(run.info.run_id, 'modelo', nome)
    cli.set_terminated(run.info.run_id)
    return run.info.run_id

  def test_registro_novo_tira_o_atual_do_run_antigo(self):
    antigo = self.run_antigo('v5')
    R.registrar_avaliacao('v5', versao_sintetica(), 'script')
    self.assertEqual(self.tags(antigo)['atual'], 'nao')

  def test_marcar_ativo_saiu(self):
    self.assertFalse(hasattr(R, 'marcar_ativo'))


class TestConcorrencia(Base):
  def test_dois_registros_simultaneos_da_mesma_versao_deixam_um_atual(self):
    R.registrar_avaliacao('v1', versao_sintetica(), 'salvar')  # cria banco e experimento antes
    original = R._runs

    def devagar(cli, exp_id):
      """Força as duas threads a lerem a lista de anteriores antes de qualquer uma criar o run."""
      runs = original(cli, exp_id)
      time.sleep(0.5)
      return runs

    with mock.patch.object(R, '_runs', side_effect=devagar):
      threads = [threading.Thread(target=R.registrar_avaliacao, args=('v2', versao_sintetica(), 'reavaliar'))
                 for _ in range(2)]
      for t in threads:
        t.start()
      for t in threads:
        t.join()
    runs_v2 = [r for r in self.runs() if r.data.tags.get('modelo') == 'v2']
    self.assertEqual(len(runs_v2), 2)
    self.assertEqual(sorted(r.data.tags['atual'] for r in runs_v2), ['nao', 'sim'])


class TestTagsGit(unittest.TestCase):
  def rodar(self, saidas):
    with mock.patch.object(R.subprocess, 'run', side_effect=saidas):
      return R._tags_git()

  def test_arvore_suja(self):
    tags = self.rodar([subprocess.CompletedProcess([], 0, 'abc123\n', ''),
                       subprocess.CompletedProcess([], 0, ' M src/ml/core/modelos.json\n', '')])
    self.assertEqual(tags, {'mlflow.source.git.commit': 'abc123', 'git_arvore': 'suja'})

  def test_arvore_limpa(self):
    tags = self.rodar([subprocess.CompletedProcess([], 0, 'abc123\n', ''),
                       subprocess.CompletedProcess([], 0, '', '')])
    self.assertEqual(tags, {'mlflow.source.git.commit': 'abc123', 'git_arvore': 'limpa'})

  def test_sem_git_nao_tem_tags(self):
    self.assertEqual(self.rodar(OSError('git não encontrado')), {})

  def test_git_com_erro_nao_tem_tags(self):
    self.assertEqual(self.rodar(subprocess.CalledProcessError(128, ['git'])), {})


class TestRegistroComGit(Base):
  def test_run_tem_commit_e_estado_da_arvore(self):
    with mock.patch.object(R, '_tags_git', return_value={'mlflow.source.git.commit': 'abc', 'git_arvore': 'suja'}):
      rid = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar')
    tags = self.tags(rid)
    self.assertEqual(tags['mlflow.source.git.commit'], 'abc')
    self.assertEqual(tags['git_arvore'], 'suja')


class TestTagsGitPublica(unittest.TestCase):
  def test_devolve_o_mesmo_que_a_interna(self):
    with mock.patch.object(R, '_tags_git', return_value={'git_arvore': 'limpa'}):
      self.assertEqual(R.tags_git(), {'git_arvore': 'limpa'})


class TestIsolamentoDosTestes(unittest.TestCase):
  def test_testes_que_salvam_reavaliam_ou_ativam_trocam_o_mlflow_por_mock(self):
    """Sem o mock, um teste que passa por salvar/reavaliar/ativar grava no mlflow.db da raiz."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    faltam = []
    for arq in sorted(os.listdir(pasta)):
      if not arq.endswith('.py'):
        continue
      with open(os.path.join(pasta, arq), encoding='utf-8') as f:
        texto = f.read()
      if re.search(r'modelos_(salvar|reavaliar)\(', texto) and 'core_registro_mlflow' not in texto:
        faltam.append(arq)
    self.assertEqual(faltam, [])

  def test_testes_do_pipeline_usam_banco_temporario(self):
    """Os testes de pacote_mlflow e versao_mlflow gravam runs de verdade: sem MLFLOW_TRACKING_URI
    temporário, eles iriam para o mlflow.db da raiz."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    faltam = []
    for arq in sorted(os.listdir(pasta)):
      if not arq.endswith('.py') or arq == os.path.basename(__file__):
        continue
      with open(os.path.join(pasta, arq), encoding='utf-8') as f:
        texto = f.read()
      if re.search(r'pacote_mlflow|versao_mlflow', texto) and 'MLFLOW_TRACKING_URI' not in texto:
        faltam.append(arq)
    self.assertEqual(faltam, [])


if __name__ == '__main__':
  unittest.main()

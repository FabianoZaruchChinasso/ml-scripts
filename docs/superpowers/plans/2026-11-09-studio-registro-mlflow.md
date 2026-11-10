# Studio: registro automático no MLflow — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** salvar, reavaliar e ativar uma versão no QoE Studio passam a registrar sozinhos no experimento "MLflow Wifi Studio", sem nunca impedir a gravação em `src/ml/core/modelos.json`.

**Architecture:** módulo novo `src/ml/core/registro_mlflow.py` (com `MlflowClient` direto e import tardio do mlflow) chamado por `src/ml/studio/api.py` depois de cada gravação, dentro de um `_registrar_mlflow` que transforma qualquer falha em aviso. `src/ml/studio_mlflow.py` vira a recuperação manual e usa o mesmo módulo. O front mostra o aviso.

**Tech Stack:** Python 3, mlflow 3.15.1 (sqlite), FastAPI, unittest; JS sem build (`node --test`).

**Spec:** `docs/superpowers/specs/2026-11-09-studio-registro-mlflow-design.md`.

---

## Regras deste repositório (ler antes de começar)

- **Nunca rode `git commit` nem `git push`.** O Lucas commita e sobe à mão. Nos passos "Sugerir commit",
  pare, mostre os arquivos e a mensagem sugerida (só a linha de assunto, sem `Co-Authored-By`, sem citar o
  Claude) e siga para a próxima tarefa.
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py` (congelados).
- Nada de emoji em código, texto de interface ou docs.
- Python do projeto: `venv/bin/python`. Testes: `venv/bin/python -m unittest ...` (não há pytest no venv).
- Indentação Python do projeto: 2 espaços.
- **Nenhum teste pode gravar no `mlflow.db` da raiz.** Testes do módulo novo usam `MLFLOW_TRACKING_URI`
  temporário; testes da API trocam `api.core_registro_mlflow` por um mock.

## Arquivos

| Arquivo | Papel |
|---|---|
| `src/ml/core/registro_mlflow.py` (novo) | destino, parâmetros e métricas, `registrar_avaliacao`, `marcar_ativo` |
| `tests/test_registro_mlflow.py` (novo) | testes do módulo com sqlite temporário + guarda de isolamento |
| `src/ml/studio_mlflow.py` | vira recuperação manual sobre o módulo novo |
| `tests/test_studio_mlflow.py` | reescrito para o script novo |
| `src/ml/studio/api.py` | `_registrar_mlflow` e chamadas em salvar, reavaliar e ativar |
| `tests/test_studio_salvar.py`, `tests/test_studio_reavaliar.py`, `tests/test_studio_assistente.py` | mock do MLflow e testes novos |
| `src/ml/studio/static/logica.js`, `tests/js/logica.test.js` | `avisoMlflow` (texto do aviso) |
| `src/ml/studio/static/modelo.js`, `src/ml/studio/static/index.html` | mostra o aviso; cache das versões dos scripts |
| `README.md`, `CHANGELOG.md` | documentação |

---

### Task 1: destino do registro e parâmetros/métricas

**Files:**
- Create: `src/ml/core/registro_mlflow.py`
- Create: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_registro_mlflow.py`:

```python
import os
import re
import sys
import tempfile
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


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: erro de import (`cannot import name 'registro_mlflow'`).

- [ ] **Step 3: Implementar o começo do módulo**

Criar `src/ml/core/registro_mlflow.py`:

```python
"""Registro da avaliação do Studio no MLflow (experimento "MLflow Wifi Studio").

Chamado pelo Studio ao salvar, reavaliar e ativar uma versão, e por src/ml/studio_mlflow.py para
recuperar o registro à mão. Não treina nada: lê a avaliação que o Studio guardou em
core/modelos.json. Cada avaliação é um run '<nome>-studio'; reavaliar não apaga o run anterior,
só tira dele a tag atual=sim.

Usa MlflowClient direto (sem mlflow.start_run/set_experiment, que guardam estado global por
processo e por thread; os jobs do Studio rodam em threads). O mlflow é importado dentro das
funções: importar o Studio não fica mais lento e, com o pacote quebrado, só o registro falha.
"""

import json
import os
import subprocess
import time
from typing import Optional

EXPERIMENTO = 'MLflow Wifi Studio'
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
EVENTOS = ('salvar', 'reavaliar', 'script')
ALVOS = {'speedtest_down_mbps': 'down', 'speedtest_up_mbps': 'up', 'latency_ms': 'lat', 'jitter_ms': 'jit'}


def uri_rastreamento() -> str:
  """MLFLOW_TRACKING_URI, se definida; senão o mlflow.db da raiz do repositório, com caminho absoluto
  (o padrão do mlflow é relativo à pasta atual, e o Studio pode ser iniciado de qualquer pasta)."""
  return os.environ.get('MLFLOW_TRACKING_URI') or 'sqlite:///' + os.path.join(RAIZ, 'mlflow.db')


def _numero(valor):
  return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def parametros_e_metricas(nome: str, versao: dict) -> tuple:
  """(parâmetros, métricas) de uma versão; métrica ausente na avaliação fica de fora."""
  av = versao.get('avaliacao') or {}
  comodo = av.get('comodo') or {}
  regua = next((av[a]['versao_regua'] for a in ALVOS if (av.get(a) or {}).get('versao_regua')), None)
  denominador = versao.get('denominador')
  params = {
    'modelo': nome,
    'features': ','.join(versao.get('features') or []), 'n_features': len(versao.get('features') or []),
    'denominador': json.dumps(denominador, ensure_ascii=False, sort_keys=True) if denominador else 'nenhum',
    'datasets': ','.join(comodo.get('datasets') or []), 'ambiente': comodo.get('ambiente'),
    'perfil': av.get('perfil'), 'cobertura_tr069': (versao.get('cobertura') or {}).get('nivel'),
    'versao_comodo': comodo.get('versao_comodo'), 'versao_regua': regua,
  }
  jogo = comodo.get('jogo') or {}
  brutas = {
    'comodo_nota': comodo.get('nota'), 'comodo_piso': (comodo.get('piso') or {}).get('nota'),
    'comodo_contra_piso': (comodo.get('contra_piso') or {}).get('diferenca'), 'comodo_graves': comodo.get('graves'),
    'jogo_nota': jogo.get('nota'), 'jogo_piso': (jogo.get('piso') or {}).get('nota'),
  }
  for prefixo, bloco in (('comodo', comodo), ('jogo', jogo)):
    intervalo = bloco.get('intervalo')
    if intervalo:
      brutas[f'{prefixo}_lo90'], brutas[f'{prefixo}_hi90'] = intervalo[0], intervalo[1]
  for chave in ('atende_completo', 'atende_throughput', 'atende_ajustado'):
    brutas[chave] = (av.get(chave) or {}).get('media')
  for alvo, p in ALVOS.items():
    bloco = av.get(alvo) or {}
    brutas[f'{p}_pooled'], brutas[f'{p}_mae'], brutas[f'{p}_mae_log'] = bloco.get('pooled'), bloco.get('mae'), bloco.get('mae_log')
    if p in ('lat', 'jit'):
      brutas[f'{p}_cobertura_q90'] = ((bloco.get('quantis') or {}).get('cobertura') or {}).get('q90')
  metricas = {k: v for k, v in brutas.items() if _numero(v) is not None}
  return params, metricas
```

(`subprocess`, `time` e `Optional` são usados na Task 2.)

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: 6 testes, `OK`.

---

### Task 2: `registrar_avaliacao`

**Files:**
- Modify: `src/ml/core/registro_mlflow.py`
- Modify: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_registro_mlflow.py`, antes de `if __name__ == '__main__':`, acrescentar:

```python
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
    rid = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar', ativo=True)
    run = R.cliente().get_run(rid)
    self.assertEqual(run.info.run_name, 'v9-studio')
    self.assertEqual(run.info.status, 'FINISHED')
    for chave, valor in {'modelo': 'v9', 'evento': 'salvar', 'atual': 'sim', 'ativo': 'sim',
                         'versao_comodo': 'v-c'}.items():
      self.assertEqual(run.data.tags[chave], valor)
    self.assertEqual(run.data.params['features'], 'a,b')
    self.assertNotIn('ativo', run.data.params)
    self.assertEqual(run.data.metrics['comodo_nota'], 0.7)
    nomes = {a.path for a in R.cliente().list_artifacts(rid)}
    self.assertEqual(nomes, {'avaliacao.json', 'posicoes.json'})

  def test_artefatos_ficam_ao_lado_do_banco(self):
    R.registrar_avaliacao('v9', versao_sintetica(), 'salvar', ativo=False)
    exp = R.cliente().get_experiment_by_name(R.EXPERIMENTO)
    self.assertIn(self.tmp, exp.artifact_location)

  def test_sem_bloco_comodo_nao_tem_tag_versao_comodo(self):
    versao = versao_sintetica()
    del versao['avaliacao']['comodo']
    rid = R.registrar_avaliacao('v9', versao, 'reavaliar', ativo=False)
    tags = self.tags(rid)
    self.assertNotIn('versao_comodo', tags)
    self.assertEqual(tags['ativo'], 'nao')

  def test_segundo_registro_vira_o_atual_e_nao_toca_outras_versoes(self):
    primeiro = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar', ativo=False)
    outra = R.registrar_avaliacao('v8', versao_sintetica(), 'salvar', ativo=False)
    segundo = R.registrar_avaliacao('v9', versao_sintetica(), 'reavaliar', ativo=False)
    self.assertEqual(self.tags(primeiro)['atual'], 'nao')
    self.assertEqual(self.tags(segundo)['atual'], 'sim')
    self.assertEqual(self.tags(outra)['atual'], 'sim')
    self.assertEqual(len(self.runs()), 3)  # histórico: nada é apagado

  def test_evento_invalido_levanta_sem_criar_run(self):
    with self.assertRaises(ValueError):
      R.registrar_avaliacao('v9', versao_sintetica(), 'outro', ativo=False)
    self.assertEqual(self.runs(), [])

  def test_falha_no_meio_marca_o_run_como_falho_e_mantem_o_atual_anterior(self):
    anterior = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar', ativo=False)
    with mock.patch('mlflow.MlflowClient.log_dict', side_effect=OSError('disco cheio')):
      with self.assertRaises(OSError):
        R.registrar_avaliacao('v9', versao_sintetica(), 'reavaliar', ativo=False)
    falhos = [r for r in self.runs() if r.info.status == 'FAILED']
    self.assertEqual(len(falhos), 1)
    self.assertEqual(falhos[0].data.tags['atual'], 'nao')
    self.assertEqual(self.tags(anterior)['atual'], 'sim')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: os 6 testes novos falham com `AttributeError: module 'ml.core.registro_mlflow' has no attribute 'cliente'` (ou `registrar_avaliacao`).

- [ ] **Step 3: Implementar**

Acrescentar ao fim de `src/ml/core/registro_mlflow.py`:

```python
def cliente():
  from mlflow import MlflowClient
  return MlflowClient(tracking_uri=uri_rastreamento())


def _local_artefatos() -> Optional[str]:
  """Pasta dos artefatos de um experimento novo: ao lado do banco. Sem isso o mlflow usa ./mlruns
  relativo à pasta atual, e um banco temporário gravaria artefatos no mlruns/ da raiz."""
  uri = uri_rastreamento()
  if uri.startswith('sqlite:///'):
    return os.path.join(os.path.dirname(uri[len('sqlite:///'):]), 'mlruns', 'studio')
  return None


def _experimento(cli) -> str:
  exp = cli.get_experiment_by_name(EXPERIMENTO)
  if exp is not None:
    return exp.experiment_id
  return cli.create_experiment(EXPERIMENTO, artifact_location=_local_artefatos())


def _runs(cli, exp_id: str) -> list:
  runs, token = [], None
  while True:
    pagina = cli.search_runs([exp_id], max_results=1000, page_token=token)
    runs.extend(pagina)
    token = pagina.token
    if not token:
      return runs


def _versao_do_run(run) -> Optional[str]:
  """Tag 'modelo'; os runs antigos (gravados antes de 2026-11-09) só têm o parâmetro 'modelo'."""
  return run.data.tags.get('modelo') or run.data.params.get('modelo')


def _commit_git() -> Optional[str]:
  try:
    saida = subprocess.run(['git', '-C', RAIZ, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                           timeout=5, check=True)
  except (OSError, subprocess.SubprocessError):
    return None
  return saida.stdout.strip() or None


def registrar_avaliacao(nome: str, versao: dict, evento: str, ativo: bool) -> str:
  """Cria o run '<nome>-studio' da avaliação guardada em `versao` e devolve o run_id.

  Tags: modelo, evento, atual=sim, ativo (sim/nao), versao_comodo (se houver) e o commit do git.
  Depois de gravar, os runs anteriores da mesma versão ficam com atual=nao. Se algo falhar no
  meio, o run fica FAILED com atual=nao, os anteriores não mudam e a exceção sobe.
  """
  if evento not in EVENTOS:
    raise ValueError(f'evento {evento!r} inválido; use um de {EVENTOS}')
  from mlflow.entities import Metric, Param
  cli = cliente()
  exp_id = _experimento(cli)
  params, metricas = parametros_e_metricas(nome, versao)
  av = versao.get('avaliacao') or {}
  comodo = av.get('comodo') or {}
  tags = {'modelo': nome, 'evento': evento, 'atual': 'sim', 'ativo': 'sim' if ativo else 'nao'}
  if comodo.get('versao_comodo'):
    tags['versao_comodo'] = str(comodo['versao_comodo'])
  commit = _commit_git()
  if commit:
    tags['mlflow.source.git.commit'] = commit
  anteriores = [r.info.run_id for r in _runs(cli, exp_id) if _versao_do_run(r) == nome]
  rid = cli.create_run(exp_id, run_name=f'{nome}-studio', tags=tags).info.run_id
  try:
    agora = int(time.time() * 1000)
    cli.log_batch(rid, metrics=[Metric(k, float(v), agora, 0) for k, v in metricas.items()],
                  params=[Param(k, str(v)) for k, v in params.items() if v is not None])
    cli.log_dict(rid, av, 'avaliacao.json')
    cli.log_dict(rid, {'posicoes': comodo.get('posicoes') or [], 'piso_posicoes': comodo.get('piso_posicoes') or []},
                 'posicoes.json')
  except Exception:
    cli.set_tag(rid, 'atual', 'nao')
    cli.set_terminated(rid, 'FAILED')
    raise
  cli.set_terminated(rid, 'FINISHED')
  for antigo in anteriores:
    cli.set_tag(antigo, 'atual', 'nao')
  return rid
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: 12 testes, `OK`. Conferir também que `ls -la mlruns | tail -3` não ganhou pasta nova (os
artefatos dos testes vão para a pasta temporária).

---

### Task 3: `marcar_ativo`

**Files:**
- Modify: `src/ml/core/registro_mlflow.py`
- Modify: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_registro_mlflow.py`, antes de `if __name__ == '__main__':`:

```python
class TestMarcarAtivo(Base):
  def run_antigo(self, nome=None):
    """Run como os gravados antes de 2026-11-09: sem tags, só o parâmetro 'modelo' (ou nem ele)."""
    cli = R.cliente()
    run = cli.create_run(R._experimento(cli), run_name=f'{nome or "sem-nome"}-studio')
    if nome:
      cli.log_param(run.info.run_id, 'modelo', nome)
    cli.set_terminated(run.info.run_id)
    return run.info.run_id

  def test_troca_a_versao_ativa(self):
    a = R.registrar_avaliacao('v1', versao_sintetica(), 'salvar', ativo=True)
    b = R.registrar_avaliacao('v2', versao_sintetica(), 'salvar', ativo=False)
    self.assertEqual(R.marcar_ativo('v2'), 1)
    self.assertEqual(self.tags(a)['ativo'], 'nao')
    self.assertEqual(self.tags(b)['ativo'], 'sim')

  def test_todos_os_runs_da_versao_ficam_ativos(self):
    R.registrar_avaliacao('v2', versao_sintetica(), 'salvar', ativo=False)
    R.registrar_avaliacao('v2', versao_sintetica(), 'reavaliar', ativo=False)
    self.assertEqual(R.marcar_ativo('v2'), 2)

  def test_run_antigo_so_com_parametro_entra_e_run_sem_modelo_e_ignorado(self):
    antigo = self.run_antigo('v5')
    sem_modelo = self.run_antigo()
    R.registrar_avaliacao('v1', versao_sintetica(), 'salvar', ativo=True)
    self.assertEqual(R.marcar_ativo('v5'), 1)
    self.assertEqual(self.tags(antigo)['ativo'], 'sim')
    self.assertNotIn('ativo', self.tags(sem_modelo))

  def test_registro_novo_tira_o_atual_do_run_antigo(self):
    antigo = self.run_antigo('v5')
    R.registrar_avaliacao('v5', versao_sintetica(), 'script', ativo=True)
    self.assertEqual(self.tags(antigo)['atual'], 'nao')

  def test_sem_experimento_devolve_zero(self):
    self.assertEqual(R.marcar_ativo('v1'), 0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: `AttributeError: ... has no attribute 'marcar_ativo'` nos testes novos; `test_registro_novo_tira_o_atual_do_run_antigo` já passa (a Task 2 cobre).

- [ ] **Step 3: Implementar**

Acrescentar ao fim de `src/ml/core/registro_mlflow.py`:

```python
def marcar_ativo(nome: str) -> int:
  """ativo=sim nos runs da versão `nome`, ativo=nao nos das outras; devolve quantos ficaram ativos.

  Não cria run. Runs sem tag nem parâmetro 'modelo' ficam como estão.
  """
  cli = cliente()
  exp = cli.get_experiment_by_name(EXPERIMENTO)
  if exp is None:
    return 0
  ativos = 0
  for run in _runs(cli, exp.experiment_id):
    versao = _versao_do_run(run)
    if versao is None:
      continue
    valor = 'sim' if versao == nome else 'nao'
    if run.data.tags.get('ativo') != valor:
      cli.set_tag(run.info.run_id, 'ativo', valor)
    ativos += valor == 'sim'
  return ativos
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: 17 testes, `OK`.

- [ ] **Step 5: Sugerir commit**

Arquivos: `src/ml/core/registro_mlflow.py`, `tests/test_registro_mlflow.py`.
Mensagem: `feat(mlflow): módulo de registro do Studio com tags atual e ativo`

---

### Task 4: `studio_mlflow.py` vira a recuperação manual

**Files:**
- Modify: `src/ml/studio_mlflow.py` (arquivo inteiro)
- Modify: `tests/test_studio_mlflow.py` (arquivo inteiro)

- [ ] **Step 1: Reescrever o teste**

Substituir todo o conteúdo de `tests/test_studio_mlflow.py` por:

```python
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml import studio_mlflow
from ml.core import registro_mlflow as R

REGISTRO = {'ativo': 'v2', 'versoes': {
  'v1': {'features': ['a'], 'avaliacao': {'comodo': {'nota': 0.6}}},
  'v2': {'features': ['a', 'b'], 'avaliacao': {'comodo': {'nota': 0.7}}}}}


class TestScript(unittest.TestCase):
  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    env = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{tmp.name}/mlflow.db'})
    env.start()
    self.addCleanup(env.stop)
    carregar = mock.patch.object(studio_mlflow.core_modelos, 'carregar', return_value=REGISTRO)
    carregar.start()
    self.addCleanup(carregar.stop)

  def runs(self):
    cli = R.cliente()
    return list(cli.search_runs([cli.get_experiment_by_name(R.EXPERIMENTO).experiment_id]))

  def test_registra_todas_com_evento_script_e_marca_a_ativa(self):
    os.environ.pop('MODELO', None)
    studio_mlflow.main()
    tags = {r.data.tags['modelo']: r.data.tags for r in self.runs()}
    self.assertEqual(sorted(tags), ['v1', 'v2'])
    self.assertEqual({t['evento'] for t in tags.values()}, {'script'})
    self.assertEqual(tags['v2']['ativo'], 'sim')
    self.assertEqual(tags['v1']['ativo'], 'nao')

  def test_modelo_limita_a_uma_versao(self):
    with mock.patch.dict(os.environ, {'MODELO': 'v1'}):
      studio_mlflow.main()
    self.assertEqual([r.data.tags['modelo'] for r in self.runs()], ['v1'])

  def test_modelo_inexistente_para_com_mensagem(self):
    with mock.patch.dict(os.environ, {'MODELO': 'v9'}):
      with self.assertRaises(SystemExit) as ctx:
        studio_mlflow.main()
    self.assertIn('v9', str(ctx.exception))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Não rodar contra o script antigo**

Exceção ao "ver falhar": o script antigo usa `mlflow.set_experiment`, que cria o experimento com artefatos
em `./mlruns` relativo à pasta atual, ou seja, no `mlruns/` da raiz. O teste novo falharia (sem tags
`evento`/`ativo`), mas sujaria a pasta. Vá direto ao Step 3.

- [ ] **Step 3: Reescrever o script**

Substituir todo o conteúdo de `src/ml/studio_mlflow.py` por:

```python
"""Recupera à mão o registro do Studio no MLflow (experimento "MLflow Wifi Studio").

O Studio já registra sozinho ao salvar, reavaliar e ativar (core/registro_mlflow.py). Este script
serve quando esse registro falhou (o Studio mostra o aviso) ou para registrar todas as versões de uma
vez. MODELO=<nome> limita a uma versão (padrão: todas de core/modelos.json). Não treina nada: cria um
run '<nome>-studio' com evento=script a partir da avaliação guardada e, no fim, marca a versão ativa.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import modelos as core_modelos
from ml.core import registro_mlflow


def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO')
  if nome and nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  nomes = [nome] if nome else list(registro['versoes'])
  ativa = registro['ativo']
  for n in nomes:
    registro_mlflow.registrar_avaliacao(n, registro['versoes'][n], 'script', ativo=n == ativa)
    print(f'registrado: {n}-studio')
  print(f'ativa: {ativa} ({registro_mlflow.marcar_ativo(ativa)} runs marcados)')


if __name__ == '__main__':
  main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_mlflow.py tests/test_registro_mlflow.py -v`
Expected: 20 testes, `OK`.

- [ ] **Step 5: Conferir que ninguém mais usava as funções removidas**

Run: `grep -rn "studio_mlflow\.\(parametros_e_metricas\|registrar_versao\)" src tests`
Expected: nenhuma linha.

- [ ] **Step 6: Sugerir commit**

Arquivos: `src/ml/studio_mlflow.py`, `tests/test_studio_mlflow.py`.
Mensagem: `refactor(mlflow): studio_mlflow.py vira a recuperação manual sobre o módulo de registro`

---

### Task 5: Studio registra ao salvar

**Files:**
- Modify: `src/ml/studio/api.py` (imports; `modelos_salvar`, perto da linha 816)
- Modify: `tests/test_studio_salvar.py`
- Modify: `tests/test_studio_assistente.py:405-407`

- [ ] **Step 1: Isolar os testes existentes e escrever os novos**

Em `tests/test_studio_salvar.py`:

1. Depois de `AVAL = {'atende_completo': {'media': 0.6}}`, acrescentar:

```python
GRAVADO = {'ativo': 'v1', 'versoes': {'v2': {'features': ['router_snr'], 'descricao': 'teste', 'avaliacao': AVAL}}}
```

2. Em `TestSalvarRota.setUp`, logo antes de `self.addCleanup(mock.patch.stopall)`, acrescentar:

```python
    self.mlflow = mock.patch.object(api, 'core_registro_mlflow').start()
```

3. No método `salvar`, trocar

```python
         mock.patch.object(api.core_modelos, 'salvar_versao') as s, \
```

por

```python
         mock.patch.object(api.core_modelos, 'salvar_versao', return_value=GRAVADO) as s, \
```

4. Em `test_salva_dentro_do_job_com_progresso`, trocar

```python
    self.assertEqual(r['resultado'], {'nome': 'v2', 'ativa': False, 'erro_ativar': None})
```

por

```python
    self.assertEqual(r['resultado'], {'nome': 'v2', 'ativa': False, 'erro_ativar': None, 'aviso_mlflow': None})
```

5. Ao fim de `TestSalvarRota` (depois de `test_falha_na_avaliacao_nao_grava`), acrescentar:

```python
  def test_registra_no_mlflow_a_versao_gravada(self):
    r, _, _, _ = self.salvar()
    self.mlflow.registrar_avaliacao.assert_called_once_with('v2', GRAVADO['versoes']['v2'], 'salvar', ativo=False)
    self.mlflow.marcar_ativo.assert_not_called()
    self.assertIsNone(r['resultado']['aviso_mlflow'])

  def test_ativar_marca_a_ativa_no_mlflow(self):
    self.salvar(ativar=True)
    self.mlflow.registrar_avaliacao.assert_called_once_with('v2', GRAVADO['versoes']['v2'], 'salvar', ativo=True)
    self.mlflow.marcar_ativo.assert_called_once_with('v2')

  def test_ativacao_que_falha_nao_marca_no_mlflow(self):
    self.salvar(ativar=True, ativar_falha=ValueError('registro travado'))
    self.assertFalse(self.mlflow.registrar_avaliacao.call_args.kwargs['ativo'])
    self.mlflow.marcar_ativo.assert_not_called()

  def test_falha_do_mlflow_vira_aviso_e_a_versao_fica_salva(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('database is locked')
    r, _, salvar, _ = self.salvar()
    salvar.assert_called_once()
    self.assertEqual(r['resultado']['aviso_mlflow'], 'não registrou no MLflow: database is locked')
    self.assertIsNone(r['resultado']['erro_ativar'])

  def test_falha_na_avaliacao_nao_registra(self):
    self.salvar(aval=[RuntimeError('sem memória')])
    self.mlflow.registrar_avaliacao.assert_not_called()
```

6. Em `TestReavaliarProgresso.test_reavaliar_repassa_a_etapa_com_o_nome_da_versao`, no bloco `with`,
trocar

```python
         mock.patch.object(api.core_modelos, 'reavaliar'):
```

por

```python
         mock.patch.object(api.core_modelos, 'reavaliar'), \
         mock.patch.object(api, 'core_registro_mlflow'):
```

Em `tests/test_studio_assistente.py`, no `test_salvar_copia_o_denominador_da_base` (linhas 405-407), trocar

```python
    with mock.patch.object(api.core_modelos, 'salvar_versao') as salvar, \
         mock.patch.object(api, 'avaliacao_completa', return_value={}), \
         mock.patch.object(api, '_iniciar_job', side_effect=sincrono):
```

por

```python
    with mock.patch.object(api.core_modelos, 'salvar_versao') as salvar, \
         mock.patch.object(api, 'avaliacao_completa', return_value={}), \
         mock.patch.object(api, '_iniciar_job', side_effect=sincrono), \
         mock.patch.object(api, 'core_registro_mlflow'):
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: `AttributeError: <module 'ml.studio.api'> does not have the attribute 'core_registro_mlflow'`.

- [ ] **Step 3: Implementar em `api.py`**

1. Nos imports, depois de `from ml.core import quantis as core_quantis`:

```python
from ml.core import registro_mlflow as core_registro_mlflow
```

2. Logo antes de `class NovaVersao(BaseModel):`, acrescentar:

```python
def _registrar_mlflow(acao) -> Optional[str]:
  """Roda o registro no MLflow; devolve None ou o aviso para a tela.

  O modelos.json é a fonte da verdade: uma falha aqui (MLflow fora do ar, banco travado, pacote
  quebrado) nunca desfaz nem impede a gravação. Recuperação: src/ml/studio_mlflow.py.
  """
  try:
    acao()
    return None
  except Exception as erro:
    return f'não registrou no MLflow: {erro}'
```

3. Em `modelos_salvar`, dentro de `tarefa`, trocar

```python
    try:
      core_modelos.salvar_versao(corpo.nome, corpo.features, corpo.descricao, conhecidas,
```

por

```python
    try:
      gravado = core_modelos.salvar_versao(corpo.nome, corpo.features, corpo.descricao, conhecidas,
```

(as linhas de continuação dos argumentos ganham 10 espaços a mais para ficarem alinhadas com o `(`).

4. Ainda em `tarefa`, trocar

```python
    return {'nome': corpo.nome, 'ativa': corpo.ativar and erro_ativar is None, 'erro_ativar': erro_ativar}
```

por

```python
    ativa = corpo.ativar and erro_ativar is None

    def registrar():
      core_registro_mlflow.registrar_avaliacao(corpo.nome, gravado['versoes'][corpo.nome], 'salvar', ativo=ativa)
      if ativa:
        core_registro_mlflow.marcar_ativo(corpo.nome)
    return {'nome': corpo.nome, 'ativa': ativa, 'erro_ativar': erro_ativar,
            'aviso_mlflow': _registrar_mlflow(registrar)}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py tests/test_studio_assistente.py -v`
Expected: todos `OK`.

---

### Task 6: Studio registra ao reavaliar

**Files:**
- Modify: `src/ml/studio/api.py` (`modelos_reavaliar`, perto da linha 904)
- Modify: `tests/test_studio_reavaliar.py`

- [ ] **Step 1: Isolar e escrever os testes**

Em `tests/test_studio_reavaliar.py`:

1. Depois do dicionário `REGISTRO`, acrescentar:

```python
REGRAVADO = {'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'avaliacao': NOVA},
                                        'v2': {'features': ['router_snr', 'router_noise'], 'avaliacao': NOVA}}}
```

2. Em `setUp`, depois do laço `for p in self.patches: p.start()`, acrescentar:

```python
    self.mlflow_patch = mock.patch.object(api, 'core_registro_mlflow')
    self.mlflow = self.mlflow_patch.start()
    self.addCleanup(self.mlflow_patch.stop)
```

3. Em `rodar`, trocar

```python
         mock.patch.object(api.core_modelos, 'reavaliar') as reav:
```

por

```python
         mock.patch.object(api.core_modelos, 'reavaliar', return_value=REGRAVADO) as reav:
```

4. Em `test_reavalia_em_ordem_com_o_denominador_da_versao`, trocar

```python
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2']})
```

por

```python
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2'], 'avisos_mlflow': []})
```

5. Antes de `if __name__ == '__main__':`, dentro da classe `TestReavaliarRota`, acrescentar:

```python
  def test_registra_cada_versao_reavaliada_com_a_ativa_marcada(self):
    self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(self.mlflow.registrar_avaliacao.call_args_list, [
      mock.call('v1', REGRAVADO['versoes']['v1'], 'reavaliar', ativo=True),
      mock.call('v2', REGRAVADO['versoes']['v2'], 'reavaliar', ativo=False)])

  def test_falha_do_mlflow_vira_aviso_e_nao_para_o_lote(self):
    self.mlflow.registrar_avaliacao.side_effect = [OSError('database is locked'), None]
    r, _, reav = self.rodar(['v1', 'v2'], [NOVA, NOVA])
    self.assertEqual(reav.call_count, 2)
    self.assertEqual(r['resultado'], {'reavaliadas': ['v1', 'v2'], 'avisos_mlflow': [
      {'nome': 'v1', 'aviso': 'não registrou no MLflow: database is locked'}]})

  def test_falha_na_avaliacao_registra_so_as_que_terminaram(self):
    self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertEqual([c.args[0] for c in self.mlflow.registrar_avaliacao.call_args_list], ['v1'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_reavaliar.py -v`
Expected: falham `test_reavalia_em_ordem...` (sem `avisos_mlflow`) e os três novos.

- [ ] **Step 3: Implementar**

Em `modelos_reavaliar`, substituir a função interna `tarefa` inteira por:

```python
  def tarefa(progresso):
    feitas, avisos = [], []
    for i, nome in enumerate(nomes):
      progresso({'nome': nome, 'i': i, 'total': len(nomes)})
      versao = registro['versoes'][nome]
      try:
        etapa = lambda evento, nome=nome, i=i: progresso({'nome': nome, 'i': i, 'total': len(nomes), **evento})
        avaliacao = avaliacao_completa(corpo.ds, corpo.ambiente, versao['features'], versao.get('denominador'),
                                       progresso=etapa, perfil_qoe=core_modelos.perfil_de(registro, nome))
        nota = core_modelos.nota_reavaliacao(versao.get('avaliacao'), avaliacao, date.today().isoformat())
        regravado = core_modelos.reavaliar(nome, avaliacao, core_features.cobertura_tr069(versao['features'], tabela),
                                           nota)
      except Exception as falha:
        detalhe = falha.detail if isinstance(falha, HTTPException) else str(falha)
        raise RuntimeError(f'parou em {nome}: {detalhe}; já reavaliadas: {feitas}') from falha
      finally:
        _ajustes.clear()
        _modelos_cache.clear()
      feitas.append(nome)
      aviso = _registrar_mlflow(lambda nome=nome, regravado=regravado: core_registro_mlflow.registrar_avaliacao(
        nome, regravado['versoes'][nome], 'reavaliar', ativo=nome == regravado['ativo']))
      if aviso:
        avisos.append({'nome': nome, 'aviso': aviso})
    return {'reavaliadas': feitas, 'avisos_mlflow': avisos}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_reavaliar.py tests/test_studio_salvar.py -v`
Expected: todos `OK`.

---

### Task 7: Studio marca a ativa ao ativar

**Files:**
- Modify: `src/ml/studio/api.py` (`modelos_ativo`, perto da linha 880)
- Modify: `tests/test_studio_salvar.py`

- [ ] **Step 1: Escrever os testes**

Em `tests/test_studio_salvar.py`, antes de `if __name__ == '__main__':`:

```python
class TestAtivarRota(unittest.TestCase):
  def setUp(self):
    self.mlflow = mock.patch.object(api, 'core_registro_mlflow').start()
    mock.patch.object(api, 'modelos_listar', return_value={'ativo': 'v2', 'versoes': []}).start()
    self.addCleanup(mock.patch.stopall)

  def test_ativar_marca_no_mlflow(self):
    with mock.patch.object(api.core_modelos, 'definir_ativo') as definir:
      r = api.modelos_ativo(api.Ativo(nome='v2'), PEDIDO)
    definir.assert_called_once_with('v2')
    self.mlflow.marcar_ativo.assert_called_once_with('v2')
    self.assertEqual(r, {'ativo': 'v2', 'versoes': [], 'aviso_mlflow': None})

  def test_falha_do_mlflow_vira_aviso_e_a_ativacao_fica(self):
    self.mlflow.marcar_ativo.side_effect = OSError('database is locked')
    with mock.patch.object(api.core_modelos, 'definir_ativo') as definir:
      r = api.modelos_ativo(api.Ativo(nome='v2'), PEDIDO)
    definir.assert_called_once_with('v2')
    self.assertEqual(r['aviso_mlflow'], 'não registrou no MLflow: database is locked')

  def test_ativacao_recusada_nao_mexe_no_mlflow(self):
    with mock.patch.object(api.core_modelos, 'definir_ativo', side_effect=ValueError('não existe')):
      with self.assertRaises(api.HTTPException):
        api.modelos_ativo(api.Ativo(nome='v9'), PEDIDO)
    self.mlflow.marcar_ativo.assert_not_called()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: falham `test_ativar_marca_no_mlflow` e `test_falha_do_mlflow_vira_aviso_e_a_ativacao_fica`.

- [ ] **Step 3: Implementar**

Em `modelos_ativo`, trocar

```python
  _ajustes.clear()
  _modelos_cache.clear()
  return modelos_listar()
```

por

```python
  _ajustes.clear()
  _modelos_cache.clear()
  aviso = _registrar_mlflow(lambda: core_registro_mlflow.marcar_ativo(corpo.nome))
  return {**modelos_listar(), 'aviso_mlflow': aviso}
```

(Esse trecho aparece só uma vez em `modelos_ativo`; confira com
`grep -n "return modelos_listar()" src/ml/studio/api.py` antes de editar.)

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py tests/test_studio_reavaliar.py tests/test_studio_assistente.py -v`
Expected: todos `OK`.

- [ ] **Step 5: Sugerir commit**

Arquivos: `src/ml/studio/api.py`, `tests/test_studio_salvar.py`, `tests/test_studio_reavaliar.py`, `tests/test_studio_assistente.py`.
Mensagem: `feat(studio): registra no MLflow ao salvar, reavaliar e ativar, com aviso quando falha`

---

### Task 8: guarda de isolamento dos testes

**Files:**
- Modify: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever o teste**

Em `tests/test_registro_mlflow.py`, antes de `if __name__ == '__main__':`:

```python
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
      if re.search(r'modelos_(salvar|reavaliar|ativo)\(', texto) and 'core_registro_mlflow' not in texto:
        faltam.append(arq)
    self.assertEqual(faltam, [])
```

- [ ] **Step 2: Rodar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: 18 testes, `OK`. Para ver que a guarda conta os arquivos certos, rode
`grep -lE "modelos_(salvar|reavaliar|ativo)\(" tests/*.py` (deve listar `test_studio_assistente.py`,
`test_studio_reavaliar.py` e `test_studio_salvar.py`) e
`grep -lE "modelos_(salvar|reavaliar|ativo)\(" tests/*.py | xargs grep -L core_registro_mlflow` (deve sair vazio).

---

### Task 9: aviso na tela

**Files:**
- Modify: `src/ml/studio/static/logica.js` (nova função + export)
- Modify: `tests/js/logica.test.js`
- Modify: `src/ml/studio/static/modelo.js` (linhas 23, 223, 252, 268-270, 281, 298-299, 440, 814)
- Modify: `src/ml/studio/static/index.html:145,153`

- [ ] **Step 1: Escrever o teste JS**

Ao fim de `tests/js/logica.test.js`:

```js
test('avisoMlflow junta o aviso do salvar/ativar e os do reavaliar, ou devolve null', () => {
  const dica = '. Rode venv/bin/python src/ml/studio_mlflow.py para registrar de novo.';
  assert.equal(L.avisoMlflow(null), null);
  assert.equal(L.avisoMlflow({ aviso_mlflow: null }), null);
  assert.equal(L.avisoMlflow({ reavaliadas: ['v1'], avisos_mlflow: [] }), null);
  assert.equal(L.avisoMlflow({ aviso_mlflow: 'não registrou no MLflow: locked' }),
    'não registrou no MLflow: locked' + dica);
  assert.equal(L.avisoMlflow({ avisos_mlflow: [{ nome: 'v1', aviso: 'a' }, { nome: 'v2', aviso: 'b' }] }),
    'v1: a; v2: b' + dica);
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `node --test tests/js/logica.test.js`
Expected: falha `L.avisoMlflow is not a function`.

- [ ] **Step 3: Implementar em `logica.js`**

Antes da linha `  return { METRICAS, MIN_AMOSTRAS, ...` (fim do arquivo), acrescentar:

```js
  // Aviso do MLflow depois de salvar, ativar (aviso_mlflow) ou reavaliar (avisos_mlflow). O modelos.json
  // já foi gravado; o aviso só diz que o MLflow ficou para trás e como recuperar.
  function avisoMlflow(r) {
    if (!r) return null;
    const itens = [];
    if (r.aviso_mlflow) itens.push(r.aviso_mlflow);
    for (const a of r.avisos_mlflow || []) itens.push(`${a.nome}: ${a.aviso}`);
    return itens.length ? `${itens.join('; ')}. Rode venv/bin/python src/ml/studio_mlflow.py para registrar de novo.` : null;
  }
```

e, no `return { ... }` final, trocar `acertosPorPredio, linhasComodo };` por
`acertosPorPredio, linhasComodo, avisoMlflow };`.

- [ ] **Step 4: Rodar e ver passar**

Run: `node --test tests/js/logica.test.js`
Expected: todos os testes passam (`# fail 0`).

- [ ] **Step 5: Mostrar o aviso em `modelo.js`**

1. Estado (linha 23): trocar `msg: null, erro: null, menu: null,` por `msg: null, erro: null, aviso: null, menu: null,`.

2. Limpar junto com a mensagem: trocar todas as ocorrências de `st.msg = null; st.erro = null;` por
`st.msg = null; st.erro = null; st.aviso = null;` (Edit com `replace_all: true`; são 4, nas linhas 223,
268, 281 e 814).

3. Salvar (`acompanharSalvar`, linha 252): logo depois de `const r = job.resultado;`, acrescentar a linha
`      st.aviso = L.avisoMlflow(r);`.

4. Ativar (`ativarManual`, linha 270): trocar

```js
      .then((reg) => { st.reg = reg; st.msg = `${nome} agora é a versão ativa. Revise src/ml/core/modelos.json no git diff antes do commit.`; })
```

por

```js
      .then((reg) => { st.reg = reg; st.aviso = L.avisoMlflow(reg); st.msg = `${nome} agora é a versão ativa. Revise src/ml/core/modelos.json no git diff antes do commit.`; })
```

5. Reavaliar (`acompanharReav`, linha 298): logo depois de `const n = job.resultado.reavaliadas.length;`,
acrescentar `        st.aviso = L.avisoMlflow(job.resultado);`.

6. Mostrar (`secaoVersoes`, linha 440): trocar

```js
      ${st.msg ? U.gate('good', 'Feito', esc(st.msg)) : ''}${st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : ''}
```

por

```js
      ${st.msg ? U.gate('good', 'Feito', esc(st.msg)) : ''}${st.aviso ? U.gate('warning', 'MLflow ficou para trás', esc(st.aviso)) : ''}${st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : ''}
```

7. Em `index.html`, subir a versão de cache dos dois scripts: `logica.js?v=5` -> `logica.js?v=6` e
`modelo.js?v=4` -> `modelo.js?v=5`.

- [ ] **Step 6: Conferir a tela**

Run: `tests/studio_screenshots.sh /tmp/qoe-studio-telas`
Expected: termina sem erro de console. Abrir uma das telas da área de modelos para ver que nada quebrou (o
aviso só aparece depois de uma falha do MLflow, então não aparece nas telas).

- [ ] **Step 7: Sugerir commit**

Arquivos: `src/ml/studio/static/logica.js`, `src/ml/studio/static/modelo.js`, `src/ml/studio/static/index.html`, `tests/js/logica.test.js`.
Mensagem: `feat(studio): mostra quando o registro no MLflow falhou`

---

### Task 10: documentação

**Files:**
- Modify: `README.md` (linha 139 e seção MLflow, linhas 144-157)
- Modify: `CHANGELOG.md` (entrada nova no topo)

- [ ] **Step 1: README**

1. Trocar

```
venv/bin/python src/ml/studio_mlflow.py                            # logs the Studio evaluation
```

por

```
venv/bin/python src/ml/studio_mlflow.py                            # re-logs the Studio evaluation (the Studio logs on its own)
```

2. Na seção `### MLflow`, depois do item `- The working MLflow at the root (...) is in `.gitignore`.`, acrescentar:

```markdown
- The Studio logs to the working MLflow by itself ("MLflow Wifi Studio"): saving or re-evaluating a version creates a run `<version>-studio`, and activating a version only updates tags. Useful filters: `tags.atual = 'sim'` (latest run of each version) and `tags.ativo = 'sim'` (runs of the active version). If logging fails, the version is still saved and the Studio shows a warning; run `venv/bin/python src/ml/studio_mlflow.py` to log again. Set `MLFLOW_TRACKING_URI` to log somewhere else.
```

- [ ] **Step 2: CHANGELOG**

No topo de `CHANGELOG.md` (antes da primeira linha `# Changelog — ...`), acrescentar:

```markdown
# Changelog — Studio registra no MLflow sozinho

**Data:** 2026-11-09

## Por quê

Tarefa da reunião de 2026-11-04 ("migrar ou ajustar o Studio para o MLflow"). Até aqui o Studio gravava só
em `core/modelos.json`, e o experimento "MLflow Wifi Studio" só recebia os números quando alguém rodava
`studio_mlflow.py` à mão. Rodar duas vezes duplicava os runs (eram 10 para 5 versões) e o parâmetro `ativo`
ficava errado depois de trocar a versão ativa, porque parâmetro do MLflow não muda depois de gravado.

## Mudanças

- `core/registro_mlflow.py` (novo): `registrar_avaliacao` cria o run `<nome>-studio` com tags `modelo`,
  `evento` (salvar, reavaliar ou script), `atual`, `ativo`, `versao_comodo` e o commit do git;
  `marcar_ativo` troca a tag `ativo` sem criar run. O destino é `MLFLOW_TRACKING_URI` ou o `mlflow.db` da
  raiz com caminho absoluto. `ativo` deixou de ser parâmetro.
- `studio/api.py`: salvar, reavaliar e ativar registram no MLflow. Uma falha do MLflow não impede gravar no
  `modelos.json`; a resposta traz `aviso_mlflow` (ou `avisos_mlflow` no reavaliar) e a tela mostra o aviso.
- `studio_mlflow.py`: virou a recuperação manual, sobre o mesmo módulo (`evento=script`).
- Testes: `tests/test_registro_mlflow.py` (novo, com sqlite temporário e uma guarda que exige mock do MLflow
  em todo teste que passa por salvar, reavaliar ou ativar); `test_studio_mlflow.py` reescrito; testes de
  salvar, reavaliar e ativar com o MLflow em mock.
- Benchmarks congelados, `modelos.json` e a régua não mudaram.

## Como conferir

No MLflow da raiz, experimento "MLflow Wifi Studio": filtro `tags.atual = 'sim'` mostra um run por versão;
`tags.ativo = 'sim'` mostra só os runs da versão ativa. Os 10 runs antigos ficaram com `atual=nao` depois da
rodada de `studio_mlflow.py` feita nesta entrega.

```

- [ ] **Step 3: Sugerir commit**

Arquivos: `README.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-11-09-studio-registro-mlflow-design.md`, `docs/superpowers/plans/2026-11-09-studio-registro-mlflow.md`.
Mensagem: `docs: changelog, README e plano do registro do Studio no MLflow`

---

### Task 11: verificação final e recuperação dos runs antigos

- [ ] **Step 1: Anotar o estado do banco da raiz**

Run: `stat -c '%s %Y' mlflow.db`
Anotar a saída (tamanho e data de modificação).

- [ ] **Step 2: Suíte inteira**

Run (leva cerca de 30 min; rodar em segundo plano): `venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5`
e `node --test tests/js/logica.test.js 2>&1 | tail -5`
Expected: `OK` e `# fail 0`. Se algo falhar, pare e mostre a saída; não "conserte" testes sem entender.

- [ ] **Step 3: Conferir que a suíte não tocou no banco da raiz**

Run: `stat -c '%s %Y' mlflow.db`
Expected: igual ao Step 1. Se mudou, algum teste gravou no banco real: pare e avise.

- [ ] **Step 4: Recuperar os runs antigos (grava no MLflow da raiz, de propósito)**

Run: `venv/bin/python src/ml/studio_mlflow.py`
Expected: `registrado: v1-studio` ... `registrado: v5-studio` e `ativa: v5 (N runs marcados)` com N = 3 (os 2
runs antigos da v5 e o novo).

- [ ] **Step 5: Conferir os critérios da spec**

Run:

```bash
venv/bin/python - <<'EOF'
import collections, sys
sys.path.insert(0, 'src')
from ml.core import registro_mlflow as R
cli = R.cliente()
exp = cli.get_experiment_by_name(R.EXPERIMENTO)
runs = list(cli.search_runs([exp.experiment_id], max_results=1000))
atuais = collections.Counter(R._versao_do_run(r) for r in runs if r.data.tags.get('atual') == 'sim')
ativos = {R._versao_do_run(r) for r in runs if r.data.tags.get('ativo') == 'sim'}
print('runs', len(runs), 'atual=sim por versão', dict(atuais), 'versões com ativo=sim', ativos)
EOF
```

Expected: `runs 15`, cada versão (v1, v2-tr069, v3-tr069, v4, v5) com exatamente 1 `atual=sim`, e
`versões com ativo=sim {'v5'}`.

- [ ] **Step 6: Relatar**

Relatar ao Lucas: resultado da suíte (com a saída), o Step 3, a saída do Step 5 e a lista de commits
sugeridos que ainda não foram feitos. Lembrar que `res/mlflow/` (snapshot versionado) não foi atualizado,
por estar fora do escopo.

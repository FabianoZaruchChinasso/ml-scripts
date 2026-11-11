# Model Registry e alias do modelo ativo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a versão ativa passa a ser o alias `ativo` do modelo registrado `qoe-wifi` no Model Registry do MLflow; todo run de `versao_mlflow.py` vira uma versão registrada e leva as entradas do treino como referência para o monitoramento.

**Architecture:** um módulo novo, `src/ml/core/registry_mlflow.py`, é a única porta para o Registry (registrar, ativar, ler a ativa, escolher a definição de um script). `versao_mlflow.py` registra o pacote e grava `referencia_entradas.parquet`; `ativar_mlflow.py` move o alias à mão até o portão existir. Os 8 scripts e o Studio deixam de ler o campo `ativo` de `modelos.json`, que sai no fim.

**Tech Stack:** Python 3.12, mlflow 3.15.1 (sqlite), pandas + pyarrow 25, FastAPI (Studio), JS puro (Studio), unittest, node --test.

**Spec:** `docs/superpowers/specs/2026-11-11-model-registry-alias-design.md`.

---

## Regras deste repositório (ler antes de começar)

- **Commits:** pode commitar ao fim de cada tarefa, com a mensagem indicada. Só a linha de assunto, **sem `Co-Authored-By` e sem citar o Claude**, nunca. **Push: nunca sem perguntar ao Lucas.**
- Trabalhe na branch `model-registry` (já criada; contém a spec).
- Nada de emoji em código, texto ou docs.
- Python do projeto: `venv/bin/python`. Testes: `venv/bin/python -m unittest discover -s tests -p '<arquivo>'` a partir da raiz (não há pytest; os testes importam uns aos outros). JS: `node --test tests/js/logica.test.js`.
- Indentação Python: 2 espaços. Aspas simples. Comentários e docstrings em português.
- **Nenhum teste pode ler ou gravar o `mlflow.db` da raiz.** Teste que grava usa `MLFLOW_TRACKING_URI` temporário. Teste que importa o Studio aponta o MLflow para um banco inexistente (Tarefa 6).
- Os benchmarks (`regression_benchmark.py`, `classification_benchmark.py`) **podem** ser editados neste plano (liberado em 2026-11-11).
- A suíte inteira leva cerca de 5 min. Se for morta com exit 137 (falta de memória), rode de novo sozinha.

## O que já foi conferido (protótipo de 2026-11-11, mlflow 3.15.1)

- `mlflow.register_model('models:/m-<id>', 'qoe-wifi', tags={...})` cria o modelo na primeira vez e uma versão nova nas seguintes; devolve `version` e `run_id`.
- `MlflowClient.get_model_version_by_alias`: sem modelo registrado levanta `MlflowException` com `error_code == 'RESOURCE_DOES_NOT_EXIST'`; com modelo e sem alias, `'INVALID_PARAMETER_VALUE'`.
- `search_model_versions("name='qoe-wifi' and tag.definicao='v5'")` filtra por tag, mas volta com `aliases` vazio: o alias se lê de `get_registered_model(...).aliases`.
- `mlflow.pyfunc.load_model('models:/qoe-wifi@ativo')` carrega.
- Parquet com coluna numérica com `None` e coluna de texto com `None` grava e volta pelo `mlflow.artifacts.download_artifacts`.

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/registry_mlflow.py` | novo: registrar, versao_da_definicao, ativa, definicao_ativa, ativar, escolher_definicao |
| `src/ml/versao_mlflow.py` | referência das entradas, registro da versão, definição pelo alias |
| `src/ml/ativar_mlflow.py` | novo: mostra ou move o alias |
| `src/ml/qoe_mlflow.py`, `regression_mlflow.py`, `compare_protocols.py`, `classification_benchmark.py`, `regression_benchmark.py`, `comodo_benchmark.py` | definição pelo alias |
| `src/ml/core/registro_mlflow.py`, `src/ml/studio_mlflow.py` | sem tag `ativo`, sem `marcar_ativo` |
| `src/ml/studio/api.py` | lê o alias; sem rota de ativar; salvar sem `ativar` |
| `src/ml/studio/static/modelo.js`, `logica.js`, `desenho.js`, `paralelos.js` | sem botões de ativar; `ativo` pode ser `null` |
| `src/ml/core/modelos.py`, `src/ml/core/modelos.json` | sem `ativo`; `features_de` |
| `tests/isolamento_mlflow.py` | novo: banco inexistente para os testes do Studio |
| `tests/test_registry_mlflow.py`, `tests/test_ativar_mlflow.py`, `tests/test_studio_ativa.py` | novos |
| README, CHANGELOG, inventário, docstrings | documentação |

---

### Task 1: `core/registry_mlflow.py`

**Files:**
- Create: `src/ml/core/registry_mlflow.py`
- Test: `tests/test_registry_mlflow.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_registry_mlflow.py`:

```python
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
    exp = mlflow.get_experiment_by_name('t') or None
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


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registry_mlflow.py'`
Expected: erro de import (`cannot import name 'registry_mlflow'`).

- [ ] **Step 3: Implementar**

`src/ml/core/registry_mlflow.py`:

```python
"""Model Registry do MLflow: o modelo registrado 'qoe-wifi' e o alias 'ativo'.

"Definição" é uma entrada de core/modelos.json (v1, ..., v5): features, denominador e perfil.
"Versão registrada" é o número do Registry (1, 2, 3...): o pacote treinado com uma definição sobre um
conjunto de dados. Cada versão registrada leva a tag 'definicao'. O alias 'ativo' é a única fonte da
versão ativa; o campo 'ativo' de modelos.json saiu em 2026-11-11.
"""

import os
from typing import Optional

import mlflow
from mlflow.exceptions import MlflowException

from ml.core import registro_mlflow as core_registro_mlflow

NOME_MODELO = 'qoe-wifi'
ALIAS = 'ativo'
# Modelo inexistente: RESOURCE_DOES_NOT_EXIST; alias ou versão inexistente: INVALID_PARAMETER_VALUE (mlflow 3.15.1).
_AUSENTE = ('RESOURCE_DOES_NOT_EXIST', 'INVALID_PARAMETER_VALUE')
_COMO_RESOLVER = ('Passe a definição (MODELO=<definição> ou --modelo <definição>) '
                  'ou ative uma com src/ml/ativar_mlflow.py')


class SemVersaoAtiva(RuntimeError):
  """Não há banco do MLflow, modelo registrado ou alias 'ativo'."""


def _cliente_de_leitura():
  """Cliente do MLflow que não cria o banco: na máquina de outra pessoa, ler não pode deixar um mlflow.db vazio."""
  uri = core_registro_mlflow.uri_rastreamento()
  if uri.startswith('sqlite:///') and not os.path.exists(uri[len('sqlite:///'):]):
    raise SemVersaoAtiva(f'não há banco do MLflow em {uri}')
  return core_registro_mlflow.cliente()


def registrar(model_uri: str, definicao: str, fingerprints: list, versao_pacote: str) -> int:
  """Cria uma versão de NOME_MODELO a partir do modelo em `model_uri` e devolve o número. Não move o alias."""
  mlflow.set_tracking_uri(core_registro_mlflow.uri_rastreamento())
  versao = mlflow.register_model(model_uri, NOME_MODELO, tags={
    'definicao': definicao, 'fingerprints': ','.join(fingerprints), 'versao_pacote': versao_pacote})
  return int(versao.version)


def versao_da_definicao(definicao: str) -> int:
  """A versão registrada mais recente da definição. ValueError se ela nunca foi registrada."""
  achadas = core_registro_mlflow.cliente().search_model_versions(
    f"name='{NOME_MODELO}' and tag.definicao='{definicao}'")
  if not achadas:
    raise ValueError(f'a definição {definicao!r} não tem versão registrada em {NOME_MODELO!r}; '
                     f'rode MODELO={definicao} venv/bin/python src/ml/versao_mlflow.py')
  return max(int(v.version) for v in achadas)


def ativa() -> dict:
  """{'versao', 'definicao', 'run_id'} da versão apontada pelo alias. SemVersaoAtiva se faltar algo."""
  cli = _cliente_de_leitura()
  try:
    v = cli.get_model_version_by_alias(NOME_MODELO, ALIAS)
  except MlflowException as erro:
    if erro.error_code in _AUSENTE:
      raise SemVersaoAtiva(f'o modelo {NOME_MODELO!r} não tem o alias {ALIAS!r} '
                           f'em {core_registro_mlflow.uri_rastreamento()}') from erro
    raise
  return {'versao': int(v.version), 'definicao': v.tags.get('definicao'), 'run_id': v.run_id}


def definicao_ativa() -> Optional[str]:
  """A definição da versão ativa, ou None sem banco, sem modelo ou sem alias."""
  try:
    return ativa()['definicao']
  except SemVersaoAtiva:
    return None


def ativar(versao: int) -> dict:
  """Move o alias para `versao`. ValueError se ela não existir."""
  cli = core_registro_mlflow.cliente()
  try:
    nova = cli.get_model_version(NOME_MODELO, str(versao))
  except MlflowException as erro:
    if erro.error_code in _AUSENTE:
      raise ValueError(f'{NOME_MODELO!r} não tem a versão {versao}') from erro
    raise
  anterior = cli.get_registered_model(NOME_MODELO).aliases.get(ALIAS)
  definicao_anterior = None
  if anterior is not None:
    definicao_anterior = cli.get_model_version(NOME_MODELO, str(anterior)).tags.get('definicao')
  cli.set_registered_model_alias(NOME_MODELO, ALIAS, str(versao))
  return {'anterior': None if anterior is None else int(anterior), 'atual': int(versao),
          'definicao_anterior': definicao_anterior, 'definicao_atual': nova.tags.get('definicao')}


def escolher_definicao(explicita: Optional[str], registro: dict) -> str:
  """A definição que um script deve usar: `explicita` se vier; senão a do alias.

  Sai com SystemExit (mensagem para quem rodou o script) sem alias ou com uma definição que não existe
  em core/modelos.json.
  """
  if explicita:
    nome, origem = explicita, 'pedida'
  else:
    try:
      nome = ativa()['definicao']
    except SemVersaoAtiva as erro:
      raise SystemExit(f'nenhuma versão ativa no Model Registry ({erro}). {_COMO_RESOLVER}') from erro
    origem = f'ativa no Registry ({NOME_MODELO}@{ALIAS})'
  if nome not in registro['versoes']:
    raise SystemExit(f'a definição {origem} {nome!r} não existe em core/modelos.json; '
                     f'definições: {sorted(registro["versoes"])}')
  return nome
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registry_mlflow.py'`
Expected: `OK` (12 testes). Se `test_versao_inexistente` falhar porque o `error_code` de `get_model_version` com versão inexistente for outro, imprima `erro.error_code` e acrescente-o a `_AUSENTE`, com o comentário atualizado.

- [ ] **Step 5: Commit**

```bash
git add src/ml/core/registry_mlflow.py tests/test_registry_mlflow.py
git commit -m "feat(core): porta única para o Model Registry e o alias ativo"
```

---

### Task 2: `versao_mlflow.py` registra a versão e grava a referência das entradas

**Files:**
- Modify: `src/ml/versao_mlflow.py`
- Test: `tests/test_versao_mlflow.py`

- [ ] **Step 1: Atualizar e acrescentar testes**

Em `tests/test_versao_mlflow.py`:

1. Imports: acrescentar `import pandas as pd` e `from ml.core import registry_mlflow as G`.
2. `REGISTRO`: tirar a chave `'ativo'` (fica `REGISTRO = {'versoes': {'v1': {...}}}`).
3. Em `ComBancoTemporario`, trocar o helper `registrar` por estes dois:

```python
  def registrar_tudo(self, conjs=None):
    versao = {'features': FEATURES, 'denominador': POR_BANDA, 'cobertura': {'nivel': 'proxy'}}
    return V.registrar('v9', versao, conjs or self.conjs, avaliacao(), self.pacote, ['abc123', 'def456'])

  def registrar(self):
    return self.registrar_tudo()[0]
```

4. Em `test_run_tem_parametros_tags_dado_e_arquivos`, a lista de artefatos passa a ser:

```python
    self.assertEqual(sorted(a.path for a in cli.list_artifacts(run.info.run_id)),
                     ['avaliacao.json', 'cobertura_tr069.json', 'posicoes.json', 'receita.json',
                      'referencia_entradas.parquet'])
```

5. Acrescentar à classe `TestRegistrar`:

```python
  def test_referencia_tem_as_entradas_do_treino(self):
    run_id = self.registrar()
    caminho = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path='referencia_entradas.parquet',
                                                  dst_path=self.tmp)
    ref = pd.read_parquet(caminho)
    self.assertEqual(list(ref.columns), self.pacote.receita['entradas'])
    self.assertEqual(len(ref), len(self.conjs[DN].df))

  def test_registra_a_versao_sem_mover_o_alias(self):
    run_id, versao = self.registrar_tudo()
    self.assertEqual(versao, 1)
    cli = R.cliente()
    self.assertEqual(cli.get_run(run_id).data.tags['versao_registrada'], '1')
    v = cli.get_model_version(G.NOME_MODELO, '1')
    self.assertEqual((v.run_id, v.tags['definicao'], v.tags['fingerprints']), (run_id, 'v9', 'abc123,def456'))
    self.assertEqual(v.tags['versao_pacote'], P.VERSAO_PACOTE)
    self.assertIsNone(G.definicao_ativa())

  def test_falha_ao_registrar_deixa_o_run_failed(self):
    with mock.patch.object(V.core_registry, 'registrar', side_effect=RuntimeError('banco travado')):
      with self.assertRaisesRegex(RuntimeError, 'banco travado'):
        self.registrar()
    cli = R.cliente()
    runs = cli.search_runs([cli.get_experiment_by_name(V.EXPERIMENTO).experiment_id])
    self.assertEqual([r.info.status for r in runs], ['FAILED'])
```

E uma classe nova, sem banco (precisa de `import io` nos imports):

```python
class TestReferenciaEntradas(unittest.TestCase):
  def test_texto_misturado_vira_texto_e_ausente_fica_ausente(self):
    df = pd.DataFrame({'radio': ['5ghz', 2, None, float('nan')], 'snr': [1.0, None, 3.0, 4.0],
                       'alvo': [1, 2, 3, 4]}, index=[7, 8, 9, 10])
    ref = V.referencia_entradas(df, ['radio', 'snr'])
    self.assertEqual(list(ref.columns), ['radio', 'snr'])
    self.assertEqual(list(ref.index), [0, 1, 2, 3])
    self.assertEqual(ref['radio'].tolist(), ['5ghz', '2', None, None])
    ref.to_parquet(io.BytesIO(), index=False)   # tipos misturados quebrariam aqui
```

6. Em `TestMain.setUp`, trocar `('registrar', (V, 'registrar'), {'return_value': 'run-1'})` por `('registrar', (V, 'registrar'), {'return_value': ('run-1', 3)})` e acrescentar à tupla de patches:

```python
        ('ativa', (V.core_registry, 'ativa'), {'return_value': {'versao': 3, 'definicao': 'v1', 'run_id': 'r'}}),
```

7. Acrescentar à classe `TestMain`:

```python
  def test_sem_modelo_usa_a_definicao_do_alias(self):
    V.main()
    self.assertEqual(self.m['registrar'].call_args.args[0], 'v1')

  def test_sem_modelo_e_sem_alias_sai_antes_de_carregar_dados(self):
    self.m['ativa'].side_effect = G.SemVersaoAtiva('não há banco do MLflow em sqlite:////nao/usado.db')
    with self.assertRaises(SystemExit) as erro:
      V.main()
    self.assertIn('MODELO=', str(erro.exception))
    self.m['carregar'].assert_not_called()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py'`
Expected: falhas em artefatos (sem `referencia_entradas.parquet`), em `registrar_tudo` (desempacota uma string), em `V.core_registry` (atributo inexistente).

- [ ] **Step 3: Implementar**

Em `src/ml/versao_mlflow.py`:

1. Docstring do módulo: trocar `Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json)` por `Definição: MODELO=<nome> (padrão: a da versão ativa, alias 'ativo' do Model Registry)` e acrescentar ao fim do parágrafo: `Cada run vira uma versão registrada de 'qoe-wifi' (sem mover o alias) e leva as entradas do treino em referencia_entradas.parquet, a referência do monitoramento.`
2. Imports: acrescentar `import tempfile` e `from ml.core import registry_mlflow as core_registry`.
3. Constante: `ARQUIVO_REFERENCIA = 'referencia_entradas.parquet'`.
4. Acrescentar a função:

```python
def referencia_entradas(df, entradas: list):
  """As entradas do treino, sem alvos e sem índice. Coluna de objeto vira texto: o parquet recusa tipos misturados."""
  ref = df[entradas].reset_index(drop=True)
  for coluna in ref.columns:
    if ref[coluna].dtype == object:
      ref[coluna] = ref[coluna].map(lambda v: None if v is None or v != v else str(v))
  return ref
```

5. `registrar`: a assinatura e a docstring passam a ser

```python
def registrar(nome: str, versao: dict, conjs: dict, avaliacao: dict, pacote, fingerprints: list) -> tuple:
  """Grava o run '<nome>-pipeline', registra o pacote como versão de 'qoe-wifi' e devolve (run_id, versão registrada).

  `versao`: features, denominador e cobertura da versão avaliada. Se gravar, carregar ou registrar o pacote
  falhar, o run termina FAILED e a exceção sobe. Não move o alias 'ativo'.
  """
```

e o fim do bloco `with mlflow.start_run(...)` (a partir de `core_pacote_mlflow.gravar(pacote, exemplo)`) passa a ser:

```python
    with tempfile.TemporaryDirectory() as tmp:
      caminho = os.path.join(tmp, ARQUIVO_REFERENCIA)
      referencia_entradas(base.df, entradas).to_parquet(caminho, index=False)
      mlflow.log_artifact(caminho)
    info = core_pacote_mlflow.gravar(pacote, exemplo)
    mlflow.pyfunc.load_model(f'runs:/{run.info.run_id}/{core_pacote_mlflow.NOME}').predict(exemplo)
    versao_registrada = core_registry.registrar(info.model_uri, nome, fingerprints, pacote.receita['versao_pacote'])
    mlflow.set_tag('versao_registrada', str(versao_registrada))
  return run.info.run_id, versao_registrada
```

6. `main`: trocar as quatro linhas iniciais

```python
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO') or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(...)
```

por

```python
  registro = core_modelos.carregar()
  nome = core_registry.escolher_definicao(os.environ.get('MODELO'), registro)
```

trocar `(' (ativa)' if nome == registro['ativo'] else '')` por `(' (ativa)' if nome == core_registry.definicao_ativa() else '')`, trocar `run_id = registrar(...)` por `run_id, versao_registrada = registrar(...)` e acrescentar ao fim:

```python
  print(f'versão registrada {versao_registrada} de "{core_registry.NOME_MODELO}" (o alias não mudou); '
        f'para ativar: VERSAO={versao_registrada} venv/bin/python src/ml/ativar_mlflow.py')
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_versao_mlflow.py'`
Expected: `OK`. Também `venv/bin/python -m unittest discover -s tests -p 'test_pacote_mlflow.py'` (não muda, mas usa o mesmo banco temporário).

- [ ] **Step 5: Commit**

```bash
git add src/ml/versao_mlflow.py tests/test_versao_mlflow.py
git commit -m "feat(pipeline): versao_mlflow registra a versão e grava a referência das entradas"
```

---

### Task 3: comando `ativar_mlflow.py`

**Files:**
- Create: `src/ml/ativar_mlflow.py`
- Test: `tests/test_ativar_mlflow.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_ativar_mlflow.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_ativar_mlflow.py'`
Expected: erro de import (`No module named 'ml.ativar_mlflow'`).

- [ ] **Step 3: Implementar**

`src/ml/ativar_mlflow.py`:

```python
"""Mostra ou troca a versão ativa: o alias 'ativo' do modelo 'qoe-wifi' no Model Registry.

Sem variáveis, mostra a ativa. MODELO=<definição> ativa a versão registrada mais recente dessa definição;
VERSAO=<n> ativa a versão registrada n. É a promoção manual até o portão de promoção existir.

  venv/bin/python src/ml/ativar_mlflow.py
  MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py
  VERSAO=3 venv/bin/python src/ml/ativar_mlflow.py
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import registry_mlflow as core_registry


def _rotulo(versao, definicao) -> str:
  return 'nenhuma' if versao is None else f'{versao} ({definicao})'


def main():
  definicao, numero = os.environ.get('MODELO'), os.environ.get('VERSAO')
  if definicao and numero:
    raise SystemExit('use MODELO ou VERSAO, não os dois')
  if not definicao and not numero:
    try:
      a = core_registry.ativa()
    except core_registry.SemVersaoAtiva as erro:
      raise SystemExit(f'nenhuma versão ativa: {erro}') from erro
    print(f"ativa: versão {a['versao']} de {core_registry.NOME_MODELO} "
          f"(definição {a['definicao']}, run {a['run_id']})")
    return
  if numero:
    if not numero.isdigit():
      raise SystemExit(f'VERSAO={numero!r}: use o número da versão registrada')
    versao = int(numero)
  else:
    try:
      versao = core_registry.versao_da_definicao(definicao)
    except ValueError as erro:
      raise SystemExit(str(erro)) from erro
  try:
    r = core_registry.ativar(versao)
  except ValueError as erro:
    raise SystemExit(str(erro)) from erro
  print(f"{core_registry.NOME_MODELO}@{core_registry.ALIAS}: {_rotulo(r['anterior'], r['definicao_anterior'])}"
        f" -> {_rotulo(r['atual'], r['definicao_atual'])}")


if __name__ == '__main__':
  main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_ativar_mlflow.py'`
Expected: `OK` (4 testes).

- [ ] **Step 5: Commit**

```bash
git add src/ml/ativar_mlflow.py tests/test_ativar_mlflow.py
git commit -m "feat(pipeline): comando ativar_mlflow mostra e move o alias do modelo ativo"
```

---

### Task 4: os seis scripts de treino e benchmark leem a definição pelo alias

**Files:**
- Modify: `src/ml/qoe_mlflow.py:38-41`, `src/ml/regression_mlflow.py:138-143` e `:164`, `src/ml/compare_protocols.py:38-41`, `src/ml/classification_benchmark.py:266-269`, `src/ml/regression_benchmark.py:294-297`, `src/ml/comodo_benchmark.py:66-73` e `:137`
- Test: `tests/test_registry_mlflow.py` (teste de fonte)

- [ ] **Step 1: Teste que olha o código-fonte**

Acrescentar a `tests/test_registry_mlflow.py`:

```python
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
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registry_mlflow.py'`
Expected: FAIL em 6 subtestes (todos menos `versao_mlflow.py`).

- [ ] **Step 2: Trocar a leitura em cada script**

Em cada um dos seis, acrescentar o import ao bloco `from ml.core import ...`, em ordem alfabética:

```python
from ml.core import registry_mlflow as core_registry
```

`qoe_mlflow.py`: trocar

```python
  nome = os.environ.get('MODELO') or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
```

por

```python
  nome = core_registry.escolher_definicao(os.environ.get('MODELO'), registro)
```

`regression_mlflow.py`: trocar

```python
  nome_modelo = os.environ.get('MODELO') or registro['ativo']
  if nome_modelo not in registro['versoes']:
    raise SystemExit(
      f"MODELO={nome_modelo!r} não existe em core/modelos.json; "
      f"versões disponíveis: {sorted(registro['versoes'])}")
```

por

```python
  nome_modelo = core_registry.escolher_definicao(os.environ.get('MODELO'), registro)
```

e, na linha do `print(f"Modelo: {nome_modelo}" ...`, trocar `nome_modelo == registro['ativo']` por `nome_modelo == core_registry.definicao_ativa()`.

`compare_protocols.py`, `classification_benchmark.py` e `regression_benchmark.py`: trocar

```python
  nome = args.modelo or registro['ativo']
  if nome not in registro['versoes']:
    raise SystemExit(f'--modelo {nome!r} não existe; versões: {sorted(registro["versoes"])}')
```

por

```python
  nome = core_registry.escolher_definicao(args.modelo, registro)
```

Se o texto de ajuda do `--modelo` nesses três disser "padrão: a ativa", trocar por "padrão: a ativa no Model Registry (alias 'ativo')".

`comodo_benchmark.py`: trocar

```python
  pedido = os.environ.get('MODELO')
  if pedido and pedido not in registro['versoes']:
    raise SystemExit(f'MODELO={pedido!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  ativa = registro['ativo']
  nomes = [pedido] if pedido else list(registro['versoes'])
  if ativa not in nomes:
    nomes.append(ativa)
```

por

```python
  pedido = os.environ.get('MODELO')
  if pedido:
    core_registry.escolher_definicao(pedido, registro)   # só valida o nome
  ativa = core_registry.definicao_ativa()
  if ativa not in registro['versoes']:
    ativa = None   # sem alias (ou alias para definição apagada): roda sem a comparação com a ativa
  nomes = [pedido] if pedido else list(registro['versoes'])
  if ativa and ativa not in nomes:
    nomes.append(ativa)
```

Depois, `grep -n "ativa" src/ml/comodo_benchmark.py` e conferir cada uso de `ativa` depois desse trecho: onde ele calcula `vs_ativa` ou compara com a ativa, o código precisa aceitar `ativa is None` (pular a comparação e gravar `vs_ativa` como `None` não serve: `metricas_mlflow` grava métrica, então omita a chave quando não houver ativa). Na linha do `print(... ativa = {ativa})`, usar `{ativa or 'nenhuma (sem alias no Model Registry)'}`. A docstring do módulo (linha 3: "a ativa entra sempre") passa a dizer "a ativa no Model Registry entra sempre, se houver alias".

- [ ] **Step 3: Rodar os testes**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_registry_mlflow.py'` e `venv/bin/python -m unittest discover -s tests -p 'test_comodo_benchmark.py'`
Expected: `OK` nos dois. Se `test_comodo_benchmark.py` montar um registro com `'ativo'` e esperar a ativa na lista, acrescente no `setUp` um `mock.patch.object(comodo_benchmark.core_registry, 'definicao_ativa', return_value=<o valor antigo de 'ativo'>)` (use o nome com que o teste importa o módulo).

Também: `for s in qoe_mlflow regression_mlflow compare_protocols classification_benchmark regression_benchmark comodo_benchmark; do venv/bin/python -c "import sys; sys.path.insert(0, 'src'); import ml.$s" || echo FALHOU $s; done`
Expected: nenhum `FALHOU`.

- [ ] **Step 4: Commit**

```bash
git add src/ml/qoe_mlflow.py src/ml/regression_mlflow.py src/ml/compare_protocols.py src/ml/classification_benchmark.py src/ml/regression_benchmark.py src/ml/comodo_benchmark.py tests/test_registry_mlflow.py tests/test_comodo_benchmark.py
git commit -m "refactor(pipeline): scripts de treino e benchmark leem a definição pelo alias"
```

(Tire `tests/test_comodo_benchmark.py` do `git add` se ele não mudou.)

---

### Task 5: runs do Studio sem tag `ativo`; Studio sem rota de ativar

**Files:**
- Modify: `src/ml/core/registro_mlflow.py:143-200`, `src/ml/studio_mlflow.py`, `src/ml/studio/api.py` (classe `NovaVersao`, `modelos_salvar`, classe `Ativo`, `modelos_ativo`, `modelos_reavaliar`)
- Test: `tests/test_registro_mlflow.py`, `tests/test_studio_mlflow.py`, `tests/test_studio_salvar.py`, `tests/test_studio_reavaliar.py`

- [ ] **Step 1: Atualizar os testes**

`tests/test_registro_mlflow.py`:
- Em toda chamada `R.registrar_avaliacao(..., ativo=True)` ou `ativo=False)`, tirar o argumento: `sed -i "s/, ativo=True)/)/; s/, ativo=False)/)/" tests/test_registro_mlflow.py` e conferir com `grep -n "ativo" tests/test_registro_mlflow.py`.
- No dicionário de tags esperadas (perto da linha 120), tirar `'ativo': 'sim'`, e logo depois acrescentar `self.assertNotIn('ativo', run.data.tags)`.
- Tirar `self.assertEqual(tags['ativo'], 'nao')` (perto da linha 140).
- Apagar os testes de `marcar_ativo` (a classe ou os métodos que chamam `R.marcar_ativo`, perto das linhas 170-205).
- `kwargs={'ativo': False}` (perto da linha 218) vira `kwargs={}`.
- No teste `test_testes_que_salvam_reavaliam_ou_ativam_trocam_o_mlflow_por_mock`, a regex passa a ser `r'modelos_(salvar|reavaliar)\('`.
- Acrescentar:

```python
  def test_marcar_ativo_saiu(self):
    self.assertFalse(hasattr(R, 'marcar_ativo'))
```

(dentro de qualquer classe de `unittest.TestCase` do arquivo que não precise de banco).

`tests/test_studio_mlflow.py`: `REGISTRO` sem `'ativo'`; no teste `test_registra_todas_com_evento_script_e_marca_a_ativa`, renomear para `test_registra_todas_com_evento_script` e trocar as duas asserções de `ativo` por `self.assertNotIn('ativo', tags['v2'])`. Se outro teste do arquivo verificar `marcar_ativo` ou a linha impressa "ativa:", apagar essa verificação.

`tests/test_studio_reavaliar.py` (linhas 85-86): tirar `, ativo=True` e `, ativo=False` das duas `mock.call(...)`.

`tests/test_studio_salvar.py`:
- O helper `salvar` perde o parâmetro `ativar_falha` e o patch de `definir_ativo`; passa a devolver `r, a, s`:

```python
  def salvar(self, aval=AVAL, **campos):
    corpo = api.NovaVersao(**{'nome': 'v2', 'features': ['router_snr'], 'descricao': 'teste', **campos})
    with mock.patch.object(api, 'avaliacao_completa', side_effect=[aval] if isinstance(aval, dict) else aval) as a, \
         mock.patch.object(api.core_modelos, 'salvar_versao', return_value=GRAVADO) as s:
      try:
        r = api.modelos_salvar(corpo, PEDIDO)
      except Exception as erro:  # 422 e falhas do job voltam para o teste examinar
        r = erro
    return r, a, s
```

- Todo `r, a, s, d = self.salvar(...)` / `r, _, _, _ = ...` / `r, aval, salvar, ativar = ...` perde o quarto elemento; `ativar.assert_not_called()` sai.
- `test_salva_dentro_do_job_com_progresso`: resultado esperado `{'nome': 'v2', 'aviso_mlflow': None}`.
- `test_registra_no_mlflow_a_versao_gravada`: `assert_called_once_with('v2', GRAVADO['versoes']['v2'], 'salvar')` e sem `marcar_ativo`.
- `test_falha_do_mlflow_vira_aviso_e_a_versao_fica_salva`: tirar a linha do `erro_ativar`.
- Apagar `test_ativar_marca_a_ativa_no_mlflow`, `test_ativacao_que_falha_nao_marca_no_mlflow`, `test_falha_no_registro_ainda_marca_a_ativa`, `test_duas_falhas_juntam_os_avisos` e a classe `TestAtivarRota` inteira.
- Acrescentar à `TestSalvarRota`:

```python
  def test_studio_nao_ativa_mais(self):
    self.assertNotIn('ativar', api.NovaVersao.model_fields)
    self.assertFalse(hasattr(api, 'Ativo'))
    self.assertNotIn('/api/modelos/ativo', [getattr(r, 'path', None) for r in api.app.routes])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `for p in test_registro_mlflow.py test_studio_mlflow.py test_studio_salvar.py test_studio_reavaliar.py; do venv/bin/python -m unittest discover -s tests -p $p 2>&1 | tail -3; done`
Expected: falhas (argumento `ativo` ainda exigido, rota ainda existe).

- [ ] **Step 3: Implementar**

`src/ml/core/registro_mlflow.py`:
- `registrar_avaliacao(nome: str, versao: dict, evento: str) -> str`: tirar o parâmetro `ativo`; na docstring, a lista de tags passa a ser "modelo, evento, atual=sim, versao_comodo (se houver), o commit do git e git_arvore (limpa/suja)"; o dicionário vira `tags = {'modelo': nome, 'evento': evento, 'atual': 'sim'}`.
- Apagar a função `marcar_ativo` inteira.
- Se a docstring do módulo citar a tag `ativo`, trocar por: "A versão ativa não é marcada aqui: é o alias 'ativo' do Model Registry (core/registry_mlflow.py)."

`src/ml/studio_mlflow.py`, `main` passa a ser:

```python
def main():
  registro = core_modelos.carregar()
  nome = os.environ.get('MODELO')
  if nome and nome not in registro['versoes']:
    raise SystemExit(f'MODELO={nome!r} não existe em core/modelos.json; versões: {sorted(registro["versoes"])}')
  nomes = [nome] if nome else list(registro['versoes'])
  for n in nomes:
    registro_mlflow.registrar_avaliacao(n, registro['versoes'][n], 'script')
    print(f'registrado: {n}-studio')
```

(e tirar da docstring do módulo qualquer menção a marcar a ativa).

`src/ml/studio/api.py`:
- `NovaVersao`: apagar `ativar: bool = False`.
- `modelos_salvar`: docstring "Valida na hora (422 com o motivo); avaliação e gravação rodam num job." Dentro de `tarefa`, depois do `try/finally` do `salvar_versao`, todo o bloco de `erro_ativar`/`ativa` sai e o fim fica:

```python
    aviso = _registrar_mlflow(lambda: core_registro_mlflow.registrar_avaliacao(
      corpo.nome, gravado['versoes'][corpo.nome], 'salvar'))
    return {'nome': corpo.nome, 'aviso_mlflow': aviso}
```

- Apagar a classe `Ativo` e a função `modelos_ativo` com o decorador `@app.post('/api/modelos/ativo')`.
- `modelos_reavaliar`: a chamada vira `core_registro_mlflow.registrar_avaliacao(nome, regravado['versoes'][nome], 'reavaliar')`.

- [ ] **Step 4: Rodar e ver passar**

Run: o mesmo laço do Step 2.
Expected: `OK` nos quatro.

- [ ] **Step 5: Commit**

```bash
git add src/ml/core/registro_mlflow.py src/ml/studio_mlflow.py src/ml/studio/api.py tests/test_registro_mlflow.py tests/test_studio_mlflow.py tests/test_studio_salvar.py tests/test_studio_reavaliar.py
git commit -m "refactor(studio): sem tag ativo nos runs e sem rota de ativar versão"
```

---

### Task 6: o Studio lê a versão ativa do alias

**Files:**
- Create: `tests/isolamento_mlflow.py`, `tests/test_studio_ativa.py`
- Modify: `src/ml/core/modelos.py` (acrescenta `features_de`), `src/ml/studio/api.py`
- Modify (testes): os 8 arquivos que importam o Studio (`test_studio_comodo.py`, `test_aplicacoes.py`, `test_studio_reavaliar.py`, `test_studio_salvar.py`, `test_studio_data_mudou.py`, `test_studio_upload.py`, `test_studio_assistente.py`, `test_studio_qoe.py`) e `tests/test_registro_mlflow.py`

- [ ] **Step 1: Isolamento dos testes do Studio**

`tests/isolamento_mlflow.py`:

```python
"""Aponta o MLflow para um banco que não existe, durante um módulo de testes inteiro.

Os testes que importam o Studio usam no módulo:

  from isolamento_mlflow import isolar as setUpModule, restaurar as tearDownModule

Sem isso, o Studio leria o alias 'ativo' do mlflow.db da raiz, e o resultado dos testes dependeria da
máquina. Com o banco inexistente, registry_mlflow.definicao_ativa() devolve None sem criar o arquivo;
o teste que precisa de uma ativa faz mock de api.core_registry.definicao_ativa.
"""

import os
import tempfile
from unittest import mock

_estado = {}


def isolar():
  pasta = tempfile.TemporaryDirectory()
  patch = mock.patch.dict(os.environ, {'MLFLOW_TRACKING_URI': f'sqlite:///{pasta.name}/nao-existe.db'})
  patch.start()
  _estado.update(pasta=pasta, patch=patch)


def restaurar():
  _estado.pop('patch').stop()
  _estado.pop('pasta').cleanup()
```

Em cada um dos 8 arquivos que importam o Studio, logo depois dos imports:

```python
from isolamento_mlflow import isolar as setUpModule, restaurar as tearDownModule  # noqa: E402,F401
```

Em `tests/test_registro_mlflow.py`, classe `TestIsolamentoDosTestes`, acrescentar:

```python
  def test_testes_que_importam_o_studio_isolam_o_registry(self):
    """Sem o isolamento, o Studio leria o alias do mlflow.db da raiz."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    faltam = []
    for arq in sorted(os.listdir(pasta)):
      if not arq.endswith('.py') or arq == 'test_registro_mlflow.py':
        continue
      with open(os.path.join(pasta, arq), encoding='utf-8') as f:
        texto = f.read()
      if 'from ml.studio import api' in texto and 'isolamento_mlflow' not in texto:
        faltam.append(arq)
    self.assertEqual(faltam, [])
```

(Se algum arquivo importar o Studio de outro jeito, por exemplo `from ml.studio import api as A`, ajuste a condição para `re.search(r'from ml\.studio import api\b', texto)`.)

- [ ] **Step 2: Testes de `_ativa`, `_base` e `features_de`**

`tests/test_studio_ativa.py`:

```python
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import modelos as M
from ml.studio import api
from isolamento_mlflow import isolar as setUpModule, restaurar as tearDownModule  # noqa: E402,F401

REGISTRO = {'versoes': {'v1': {'features': ['a']}, 'v5': {'features': ['a', 'b']}}}


class TestAtivaNoStudio(unittest.TestCase):
  def test_sem_alias(self):
    self.assertIsNone(api._ativa(REGISTRO))
    with self.assertRaises(api.HTTPException) as erro:
      api._base(None, REGISTRO)
    self.assertEqual(erro.exception.status_code, 409)
    self.assertIn('ativar_mlflow.py', erro.exception.detail)
    self.assertEqual(api._base('v1', REGISTRO), 'v1')

  def test_com_alias(self):
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v5'):
      self.assertEqual(api._ativa(REGISTRO), 'v5')
      self.assertEqual(api._base(None, REGISTRO), 'v5')
      self.assertEqual(api._base('v1', REGISTRO), 'v1')
      self.assertEqual(api._features_ativa(REGISTRO), ['a', 'b'])

  def test_alias_para_definicao_apagada_conta_como_sem_ativa(self):
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v3-velha'):
      self.assertIsNone(api._ativa(REGISTRO))

  def test_troca_do_alias_muda_a_chave_dos_caches(self):
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v1'):
      antes = api._chave_versoes()
    with mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v5'):
      self.assertNotEqual(api._chave_versoes(), antes)

  def test_features_de(self):
    self.assertEqual(M.features_de(REGISTRO, 'v5'), ['a', 'b'])
    with self.assertRaises(KeyError):
      M.features_de(REGISTRO, 'v9')


if __name__ == '__main__':
  unittest.main()
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_studio_ativa.py'`
Expected: erros (`_ativa` e `features_de` não existem).

- [ ] **Step 3: Implementar**

`src/ml/core/modelos.py`, logo depois de `def ativo(registro)` (que sai na Tarefa 8):

```python
def features_de(registro: dict, nome: str) -> list:
  """Features da definição `nome`. KeyError se ela não existir."""
  return list(registro['versoes'][nome]['features'])
```

`src/ml/studio/api.py`:

1. Import: `from ml.core import registry_mlflow as core_registry` (no bloco `from ml.core import ...`, em ordem alfabética, depois de `registro_mlflow`).
2. `_chave_versoes`: acrescentar `core_registry.definicao_ativa()` ao fim da tupla.
3. `_registro`: a reserva perde `'ativo': 'v1', ` (fica `{'versoes': {'v1': {...}}}`).
4. Logo depois de `_registro`, acrescentar:

```python
def _ativa(registro) -> Optional[str]:
  """Definição da versão ativa (alias 'ativo' do Model Registry), ou None sem alias ou com alias para
  uma definição que não está em modelos.json."""
  nome = core_registry.definicao_ativa()
  return nome if nome in registro['versoes'] else None


def _base(base, registro) -> str:
  """A versão base pedida; sem ela, a ativa; sem as duas, 409."""
  nome = base or _ativa(registro)
  if not nome:
    raise HTTPException(409, 'sem versão ativa no Model Registry: escolha a versão base '
                             '(ou ative uma com src/ml/ativar_mlflow.py)')
  return nome


def _features_ativa(registro) -> list:
  return core_modelos.features_de(registro, _base(None, registro))
```

5. Trocas (conferir cada uma com `grep -n "'ativo'\]\|core_modelos.ativo(" src/ml/studio/api.py` até não sobrar nenhuma):
   - `core_modelos.ativo(registro)` (7 lugares) -> `_features_ativa(registro)`.
   - `features_inventario`: `inv['modelo_ativo'] = registro['ativo']` -> `inv['modelo_ativo'] = _ativa(registro)`.
   - `modelos_listar`: antes do laço, `ativa = _ativa(registro)`; `ativo=nome == registro['ativo']` -> `ativo=nome == ativa`; o retorno passa a começar com `{'ativo': ativa, 'versoes': versoes, 'erro': erro or (None if ativa else 'sem versão ativa no Model Registry: ative uma com src/ml/ativar_mlflow.py'), ...`.
   - `modelos_comparar`: `registro['ativo']` -> `_ativa(registro)`.
   - `modelos_avaliar` (perto da linha 306): `registro['versoes'][base or registro['ativo']]` -> `registro['versoes'][_base(base, registro)]`.
   - `modelos_avaliar_comodo` (perto da linha 356): idem.
   - `_features_base`: `nome = base or registro['ativo']` -> `nome = _base(base, registro)`.
   - `paralelos_iniciar`: `resultado['versao_base'] = base or registro['ativo']` -> `resultado['versao_base'] = _base(base, registro)`.
   - `derivadas_salvar`: `'base': corpo.base or _registro()[0]['ativo']` -> `'base': _base(corpo.base, _registro()[0])`.
   - `assistente_sugestoes`: `'base': base or registro['ativo']` -> `'base': _base(base, registro)`.
   - `modelos_salvar` (perto da linha 799): `registro['versoes'][corpo.base or registro['ativo']]` -> `registro['versoes'][_base(corpo.base, registro)]`. A chamada `core_modelos.validar_registro({'ativo': corpo.nome, 'versoes': ...})` fica como está nesta tarefa (muda na Tarefa 8).

- [ ] **Step 4: Testes que precisam de uma ativa**

Run: `for p in test_studio_ativa.py test_studio_comodo.py test_aplicacoes.py test_studio_reavaliar.py test_studio_salvar.py test_studio_data_mudou.py test_studio_upload.py test_studio_assistente.py test_studio_qoe.py test_registro_mlflow.py; do echo "== $p"; venv/bin/python -m unittest discover -s tests -p $p 2>&1 | tail -3; done`

Onde um teste falhar com 409 "sem versão ativa no Model Registry" (ou com `modelo_ativo`/`ativo` igual a `None` onde esperava um nome), acrescentar no `setUp` da classe:

```python
    ativa = mock.patch.object(api.core_registry, 'definicao_ativa', return_value='v1')
    ativa.start()
    self.addCleanup(ativa.stop)
```

com o valor que o `'ativo'` do `REGISTRO` daquele arquivo tinha. Depois, tirar `'ativo': ...` de todos os dicionários de registro dos testes do Studio (`grep -n "'ativo':" tests/test_studio_*.py`), para eles terem a forma nova de `modelos.json`.

Expected no fim: `OK` em todos.

- [ ] **Step 5: Commit**

```bash
git add tests/isolamento_mlflow.py tests/test_studio_ativa.py src/ml/core/modelos.py src/ml/studio/api.py tests/test_studio_*.py tests/test_aplicacoes.py tests/test_registro_mlflow.py
git commit -m "feat(studio): versão ativa lida do alias do Model Registry"
```

---

### Task 7: tela do Studio sem botões de ativar e com ativa opcional

**Files:**
- Modify: `src/ml/studio/static/modelo.js`, `src/ml/studio/static/logica.js`, `src/ml/studio/static/desenho.js:69-79`, `src/ml/studio/static/paralelos.js:51-57`
- Test: `tests/js/logica.test.js`

- [ ] **Step 1: Testes de JS**

Em `tests/js/logica.test.js`:
- Apagar o teste `'podeAtivar segue o veredito por cômodo e exige cobertura implantável'` (linhas 102 em diante, até o fim desse `test(...)`).
- Acrescentar:

```js
test('sugerirNome sem versão ativa parte da última versão', () => {
  assert.equal(L.sugerirNome(null, ['v1', 'v5']), 'v6');
  assert.equal(L.sugerirNome(null, []), 'v1');
});

test('podeAtivar saiu: promover é do portão (src/ml/ativar_mlflow.py)', () => {
  assert.equal(L.podeAtivar, undefined);
});
```

Run: `node --test tests/js/logica.test.js`
Expected: FAIL nos dois testes novos.

- [ ] **Step 2: `logica.js`**

- Apagar a função `podeAtivar` (e o comentário acima dela) e tirá-la do objeto exportado no fim do arquivo.
- `sugerirNome` passa a ser:

```js
  // Próximo nome livre a partir da ativa (ou da última versão, sem ativa): v3-tr069 -> v4-tr069.
  function sugerirNome(ativo, nomes) {
    const ref = ativo || nomes[nomes.length - 1] || 'v0';
    const m = ref.match(/^(\D*)(\d+)(.*)$/);
    const gerar = m ? (i) => m[1] + i + m[3] : (i) => `${ref}-${i}`;
    let i = m ? Number(m[2]) + 1 : 2;
    while (nomes.includes(gerar(i))) i += 1;
    return gerar(i);
  }
```

- No comentário perto da linha 306 ("Aviso do MLflow depois de salvar, ativar (aviso_mlflow) ou reavaliar"), tirar "ativar".

Run: `node --test tests/js/logica.test.js`
Expected: `pass` em todos.

- [ ] **Step 3: `modelo.js`**

1. Ativa opcional:
   - `const ativa = () => versao(st.reg.ativo);` fica; `igualAtiva` vira `const igualAtiva = () => !!ativa() && L.mesmasFeatures(ativa().features, selLista());`.
   - Acrescentar, perto de `ativa`: `const ultima = () => (st.reg && st.reg.versoes.length ? st.reg.versoes[st.reg.versoes.length - 1].nome : null);`
   - `aplicarRascunho`: `usarBase(st.reg.ativo);` -> `usarBase(st.reg.ativo || st.base || ultima());`
   - `carregarRegistro`: `usarBase(reg.ativo);` -> `usarBase(reg.ativo || ultima());`
   - Nos textos que mostram `${st.reg.ativo}` ou `${esc(st.reg.ativo)}` (linhas ~212, 654, 678, 682, 687, 691, 704), usar `${esc(st.reg.ativo || '–')}`.
   - Nas duas URLs com `'&contra=' + encodeURIComponent(st.reg.ativo)` (linhas ~129 e ~135), usar `encodeURIComponent(st.reg.ativo || '')` (o servidor compara com a própria base quando `contra` vem vazio).
2. Saem os botões de ativar:
   - No menu do cartão de versão, apagar a linha `${v.ativo ? '' : `<button role="menuitem" data-acao="ativar" ...>Tornar ativa</button>`}` (mantendo o `</div>` que fecha o menu).
   - No `dock()`, apagar o botão `abrir-ativar` ("Salvar e tornar ativa"), a linha `const pode = L.podeAtivar(...)` e o parágrafo `${pode.ok ? '' : `<p class="dock-motivo" ...>`}`. Apagar a função `motivoDock` inteira e o comentário acima dela.
   - No `switch` de ações, apagar `case 'ativar': ativarManual(b.dataset.nome); break;` e `case 'abrir-ativar': abrirForm(true); break;`.
   - Apagar a função `ativarManual` inteira.
   - `abrirForm(ativar)` vira `abrirForm()`, e `st.form = { ativar, nome: ...` vira `st.form = { nome: L.sugerirNome(st.reg.ativo, st.reg.versoes.map((v) => v.nome)), ...`. Conferir que `case 'abrir-salvar'` chama `abrirForm()` (sem argumento).
   - `formSalvar`: o rótulo do botão vira `${st.salvando ? textoSalvando() : 'Salvar versão'}`.
   - `publicar`: o corpo do `U.post('api/modelos', ...)` perde `, ativar: !!f.ativar`.
   - `acompanharSalvar`: as duas linhas do `erro_ativar`/`st.msg` viram uma só:
     `st.msg = `Versão ${nome} salva em src/ml/core/modelos.json. Revise no git diff antes do commit; para ativá-la, registre e ative pelo MLflow (versao_mlflow.py e ativar_mlflow.py).`;`
   - O título da seção `/* ---------------- salvar e ativar ---------------- */` vira `/* ---------------- salvar ---------------- */`.
   - Os textos "(decide a ativação)" e "não entra na ativação" (linhas ~685 e ~691) viram "(referência)" e "informativo".
   - Os comentários de `chaveVered` que citam o "Tornar ativa" do cartão: trocar por "Último veredito por cômodo de cada versão contra a ativa; independe do alvo."
3. Aviso de onde a ativa vem: na `secaoVersoes()`, logo depois do `<h2>Versões</h2>`, acrescentar `<p class="hint">A versão ativa é o alias do Model Registry; para trocar: <code>MODELO=&lt;versão&gt; venv/bin/python src/ml/ativar_mlflow.py</code>.</p>`.

Run: `grep -n "ativar\|podeAtivar\|erro_ativar" src/ml/studio/static/*.js`
Expected: nenhuma ocorrência (fora o texto de ajuda com `ativar_mlflow.py`).

- [ ] **Step 4: `desenho.js` e `paralelos.js`**

- `desenho.js`, linha ~79: `${esc(st.reg.ativo)}` -> `${esc(st.reg.ativo || '–')}`.
- `paralelos.js`, linha ~57: `(puras.length ? puras[puras.length - 1] : reg.versoes.find((v) => v.ativo)).nome` -> `(puras.length ? puras[puras.length - 1] : reg.versoes.find((v) => v.ativo) || reg.versoes[reg.versoes.length - 1]).nome`.

- [ ] **Step 5: Conferir no navegador**

Subir o Studio como o README manda (procure "studio" no README; em geral `venv/bin/python src/ml/studio.py` a partir da raiz) **com `MLFLOW_TRACKING_URI=sqlite:////tmp/nao-existe.db`**, para ver a tela sem ativa. Abrir a aba Modelo: a lista de versões aparece, a base inicial é a última versão, o aviso "sem versão ativa" aparece, o menu do cartão só tem "Reavaliar" e o dock só tem "Descartar" e "Salvar…". Sem erro no console do navegador. Parar o servidor.

Run: `node --test tests/js/logica.test.js`
Expected: `pass` em todos.

- [ ] **Step 6: Commit**

```bash
git add src/ml/studio/static/modelo.js src/ml/studio/static/logica.js src/ml/studio/static/desenho.js src/ml/studio/static/paralelos.js tests/js/logica.test.js
git commit -m "feat(studio): tela sem botões de ativar e com versão ativa opcional"
```

---

### Task 8: `modelos.json` sem o campo `ativo`

**Files:**
- Modify: `src/ml/core/modelos.py:50-98` e `:180-187`, `src/ml/core/modelos.json`, `src/ml/studio/api.py` (chamada de `validar_registro` em `modelos_salvar`)
- Test: `tests/test_modelos_core.py`, `tests/test_registry_mlflow.py`

- [ ] **Step 1: Testes**

`tests/test_modelos_core.py`:
- Toda fixture `{'ativo': 'v1', 'versoes': ...}` vira `{'versoes': ...}`: `sed -i "s/{'ativo': 'v1', 'versoes'/{'versoes'/" tests/test_modelos_core.py`.
- Em `test_salva_e_le_de_volta`, tirar `self.assertEqual(reg['ativo'], 'v1')`.
- Apagar `test_definir_ativo`.
- Em `TestSemente`, tirar as duas `self.assertEqual(reg['ativo'], 'v5')`.
- Acrescentar à `TestRegistro`:

```python
  def test_campo_ativo_e_recusado(self):
    with self.assertRaisesRegex(ValueError, 'alias'):
      M.validar_registro({'ativo': 'v1', 'versoes': {'v1': {'features': ['router_snr'], 'descricao': 'x'}}})
    with self.assertRaises(ValueError):
      M.validar_registro({'versoes': {}, 'outro': 1})

  def test_ativo_e_definir_ativo_sairam(self):
    self.assertFalse(hasattr(M, 'ativo'))
    self.assertFalse(hasattr(M, 'definir_ativo'))
```

`tests/test_registry_mlflow.py`, acrescentar:

```python
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
```

Run: `venv/bin/python -m unittest discover -s tests -p 'test_modelos_core.py'` e `-p 'test_registry_mlflow.py'`
Expected: FAIL (o validador ainda exige `ativo`; `modelos.json` ainda tem o campo).

- [ ] **Step 2: Implementar**

`src/ml/core/modelos.py`:
- Em `validar_registro`, trocar

```python
  if not isinstance(registro, dict) or set(registro) != {'ativo', 'versoes'}:
    raise ValueError("o registro precisa ter exatamente as chaves 'ativo' e 'versoes'")
```

por

```python
  if isinstance(registro, dict) and 'ativo' in registro:
    raise ValueError("o campo ativo saiu do modelos.json em 2026-11-11: a versão ativa é o alias 'ativo' "
                     "do Model Registry (src/ml/ativar_mlflow.py)")
  if not isinstance(registro, dict) or set(registro) != {'versoes'}:
    raise ValueError("o registro precisa ter exatamente a chave 'versoes'")
```

- Apagar as duas linhas do fim de `validar_registro` (`if registro['ativo'] not in versoes: raise ...`).
- Apagar `def ativo(registro)` e `def definir_ativo(...)`.

`src/ml/core/modelos.json`: apagar a linha `"ativo": "v5",` (a primeira chave). Conferir que o arquivo continua JSON válido: `venv/bin/python -c "import json; json.load(open('src/ml/core/modelos.json'))"`.

`src/ml/studio/api.py`, em `modelos_salvar`: `core_modelos.validar_registro({'ativo': corpo.nome, 'versoes': {corpo.nome: {` -> `core_modelos.validar_registro({'versoes': {corpo.nome: {`.

- [ ] **Step 3: Rodar e ver passar**

Run: `venv/bin/python -m unittest discover -s tests -p 'test_modelos_core.py'`, `-p 'test_registry_mlflow.py'` e `-p 'test_studio_salvar.py'`
Expected: `OK` nos três.

- [ ] **Step 4: Commit**

```bash
git add src/ml/core/modelos.py src/ml/core/modelos.json src/ml/studio/api.py tests/test_modelos_core.py tests/test_registry_mlflow.py
git commit -m "refactor(core): modelos.json só com as definições; a ativa é o alias do Registry"
```

---

### Task 9: documentação

**Files:**
- Modify: `README.md` (seção "MLflow", perto das linhas 139-160), `CHANGELOG.md`, `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`

- [ ] **Step 1: README (em inglês, como o resto do arquivo)**

- Na lista de comandos (perto da linha 139), depois da linha do `versao_mlflow.py`, acrescentar:

```
venv/bin/python src/ml/ativar_mlflow.py                            # show the active version (alias "ativo")
MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py                  # activate the latest registered version of v5
```

- No parágrafo "In the scripts, `MODELO` is the version (default: the active one)", trocar "(default: the active one)" por "(default: the definition of the active version, alias `ativo` of the registered model `qoe-wifi` in the working MLflow; on a machine without that MLflow, pass `MODELO=` or `--modelo`, or the script stops)".
- Na seção "MLflow", trocar o item do Studio ("activating a version only updates tags. Useful filters: ... `tags.ativo = 'sim'` ...") por: "Useful filter: `tags.atual = 'sim'` (latest run of each version). The Studio no longer activates versions."
- No item do `versao_mlflow.py`, acrescentar ao fim: "Each run is also registered as a new version of the model `qoe-wifi` in the Model Registry (tags `definicao`, `fingerprints`, `versao_pacote`; run tag `versao_registrada`) and carries the training inputs in `referencia_entradas.parquet`, the reference for input-drift monitoring. Registering does not change the active version."
- Acrescentar um item novo:

```
- The active version is the alias `ativo` of `qoe-wifi` (`models:/qoe-wifi@ativo`), the only source: `src/ml/core/modelos.json` keeps only the definitions (features, denominator, profile). A *definition* is an entry of `modelos.json` (v1 ... v5); a *registered version* is a Model Registry number, the package trained from a definition on a given dataset. `src/ml/ativar_mlflow.py` moves the alias by hand until the promotion gate exists. The Registry lives in the working MLflow, which is not in git: other machines see no active version.
```

- No item "Runs logged before 2026-11-09 still carry an `ativo` parameter ... use the `ativo` tag", trocar o fim por: "...may be stale (MLflow parameters cannot change). The `ativo` tag was removed from the Studio runs on 2026-11-11; the active version is the Registry alias."

- [ ] **Step 2: CHANGELOG**

Seguir o formato das entradas existentes (ver as primeiras linhas de `CHANGELOG.md`) e acrescentar, para 2026-11-11:

- Model Registry: cada run de `versao_mlflow.py` vira uma versão de `qoe-wifi`, com `referencia_entradas.parquet` para o monitoramento.
- A versão ativa é o alias `ativo` do Registry; o campo `ativo` saiu de `modelos.json`. Comando novo `ativar_mlflow.py`.
- Os oito scripts (benchmarks incluídos) leem a definição pelo alias; sem Registry, pedem `MODELO=`/`--modelo`.
- O Studio lê o alias e não ativa mais versões; a tag `ativo` saiu dos runs do Studio.

- [ ] **Step 3: Inventário**

Em `docs/pipeline/2026-11-10-inventario-studio-mlflow.md`, na "Ordem proposta", o passo 4 ganha: "Feito em 2026-11-11: `core/registry_mlflow.py`, `ativar_mlflow.py`; o Studio lê o alias e não ativa mais (spec `docs/superpowers/specs/2026-11-11-model-registry-alias-design.md`)." Em "O que falta no MLflow", o item 1 ganha "(feito em 2026-11-11)".

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md docs/pipeline/2026-11-10-inventario-studio-mlflow.md
git commit -m "docs: Model Registry, alias ativo e ativar_mlflow"
```

---

### Task 10: migração com o dado real

Cerca de 35 min de máquina. Grava no MLflow da raiz (é o objetivo desta tarefa).

- [ ] **Step 1: Registrar as cinco definições**

```bash
for d in v1 v2-tr069 v3-tr069 v4 v5; do MODELO=$d venv/bin/python src/ml/versao_mlflow.py 2>&1 | tail -4; done
```

Expected: cada uma termina com `versão registrada N de "qoe-wifi" (o alias não mudou)`, com N de 1 a 5 nessa ordem.

- [ ] **Step 2: Ativar a v5**

```bash
MODELO=v5 venv/bin/python src/ml/ativar_mlflow.py
venv/bin/python src/ml/ativar_mlflow.py
```

Expected: `qoe-wifi@ativo: nenhuma -> 5 (v5)` e depois `ativa: versão 5 de qoe-wifi (definição v5, run ...)`.

- [ ] **Step 3: Tirar a tag `ativo` dos runs antigos do Studio**

```bash
venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, 'src')
from ml.core import registro_mlflow as R
cli = R.cliente()
exp = cli.get_experiment_by_name(R.EXPERIMENTO)
n = 0
for run in cli.search_runs([exp.experiment_id], max_results=5000):
  if 'ativo' in run.data.tags:
    cli.delete_tag(run.info.run_id, 'ativo'); n += 1
print('tags apagadas:', n)
EOF
```

- [ ] **Step 4: Conferências**

1. Métricas do run novo da v5 contra o run do item anterior (mesmo código de avaliação, mesmo dado):

```bash
venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, 'src')
from ml.core import registro_mlflow as R, registry_mlflow as G
cli = R.cliente()
antigo = cli.get_run('9b7a4ece25884f3bb164fd7f06986923').data.metrics
novo = cli.get_run(G.ativa()['run_id']).data.metrics
diferentes = {k: (antigo[k], novo.get(k)) for k in antigo if novo.get(k) != antigo[k]}
print('métricas:', len(antigo), 'diferentes:', diferentes)
EOF
```

Expected: `diferentes: {}`. Se houver diferença, parar e investigar antes de seguir (o código de avaliação não mudou neste plano).

2. O modelo do alias carrega e prevê:

```bash
venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, 'src')
import mlflow
from ml.core import registro_mlflow as R
mlflow.set_tracking_uri(R.uri_rastreamento())
m = mlflow.pyfunc.load_model('models:/qoe-wifi@ativo')
print(m.predict(m.input_example))
EOF
```

Expected: tabela com 5 linhas e as colunas de `pacote.SAIDAS`. (Se `m.input_example` não existir nessa versão do MLflow, ler o exemplo do run com `mlflow.models.Model.load(...)` ou passar `pd.read_parquet` da referência com `.head(5)`.)

3. A referência existe e tem as entradas:

```bash
venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, 'src')
import mlflow, pandas as pd
from ml.core import registro_mlflow as R, registry_mlflow as G
mlflow.set_tracking_uri(R.uri_rastreamento())
ref = pd.read_parquet(mlflow.artifacts.download_artifacts(run_id=G.ativa()['run_id'], artifact_path='referencia_entradas.parquet'))
print(ref.shape); print(ref.dtypes)
EOF
```

Expected: cerca de 1.708 linhas e as colunas de entrada da v5.

4. Studio: subir como o README manda (sem `MLFLOW_TRACKING_URI`), abrir a aba Modelo e conferir que a v5 aparece como ativa, e que `curl -s http://127.0.0.1:<porta>/api/modelos | venv/bin/python -c "import json,sys; print(json.load(sys.stdin)['ativo'])"` imprime `v5`. Parar o servidor.

5. Um script com o alias, sem `MODELO`: `venv/bin/python src/ml/compare_protocols.py --help` (só confere o import) e, para a resolução do nome, `venv/bin/python -c "import sys; sys.path.insert(0,'src'); from ml.core import modelos as M, registry_mlflow as G; print(G.escolher_definicao(None, M.carregar()))"`.
Expected: `v5`.

Nada a commitar nesta tarefa: o MLflow da raiz está no `.gitignore`.

---

### Task 11: suíte inteira e fechamento

- [ ] **Step 1: Suíte Python e JS**

Run: `venv/bin/python -m unittest discover -s tests 2>&1 | tail -5` e `node --test tests/js/logica.test.js 2>&1 | tail -5`
Expected: `OK` e todos `pass`. Exit 137 é falta de memória: rodar de novo sozinha.

- [ ] **Step 2: O mlflow.db da raiz não foi tocado pelos testes**

Run: antes da suíte, `stat -c %Y mlflow.db`; depois, de novo.
Expected: o mesmo valor. Se mudou, algum teste escapou do isolamento: achar com `grep -L "isolamento_mlflow\|MLFLOW_TRACKING_URI" tests/test_*.py` entre os que importam o Studio ou o Registry.

- [ ] **Step 3: Revisão final**

`git diff master --stat` e conferir que:
- não sobrou `['ativo']`, `definir_ativo`, `marcar_ativo` nem `podeAtivar` no código;
- nenhum commit tem `Co-Authored-By` (`git log master..HEAD --format=%B | grep -i co-authored` não imprime nada).

- [ ] **Step 4: Avisar o Lucas**

Relatório final: o que foi feito, as decisões tomadas sem perguntar (lista da seção 2 da spec e qualquer ajuste feito durante a execução), o resultado das conferências da Tarefa 10, e o lembrete de que o Fabiano precisa passar `--modelo` nos benchmarks enquanto o MLflow for só local. **Perguntar antes de qualquer push ou merge.**

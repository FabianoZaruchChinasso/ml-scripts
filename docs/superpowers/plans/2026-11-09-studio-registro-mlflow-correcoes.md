# Studio no MLflow: correções da revisão — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** corrigir os problemas achados na revisão crítica do registro do Studio no MLflow (plano `2026-11-09-studio-registro-mlflow.md`, já implementado no branch `studio-registro-mlflow`, sem commit).

**Architecture:** mudanças pequenas e localizadas em `src/ml/core/registro_mlflow.py` (trava do processo, tags do git) e em `src/ml/studio/api.py` (texto do aviso, marcação da ativa à parte, avisos no erro do reavaliar), mais README e CHANGELOG.

**Tech Stack:** Python 3, mlflow 3.15.1 (sqlite), FastAPI, unittest.

**Spec:** `docs/superpowers/specs/2026-11-09-studio-registro-mlflow-design.md` (seções 4.2 e 4.3 já atualizadas com estas correções).

---

## Regras deste repositório (ler antes de começar)

- **Nunca rode `git commit` nem `git push`.** O Lucas commita à mão. Nos passos "Sugerir commit", só relate
  arquivos e a mensagem (linha de assunto, sem `Co-Authored-By`, sem citar o Claude).
- Não edite `src/ml/regression_benchmark.py` nem `src/ml/classification_benchmark.py`.
- Sem emoji. Python: `venv/bin/python -m unittest` (não há pytest). Indentação de 2 espaços.
- Nenhum teste pode gravar no `mlflow.db` nem no `mlruns/` da raiz. Antes de começar, anote
  `stat -c '%s %Y' mlflow.db` e `ls mlruns`; no fim, confira que não mudaram.
- `tests/test_studio_assistente.py` importa `test_studio_features`: rode-o com
  `venv/bin/python -m unittest discover -s tests -p 'test_studio_assistente.py'`.

## O que foi medido na revisão (contexto)

| Caso | Hoje |
|---|---|
| Banco travado | aviso só depois de 20 s (o MLflow força `PRAGMA busy_timeout = 20000`; `?timeout=` na URI não muda nada) e o texto traz a consulta SQL inteira, em 6 linhas |
| Dois registros simultâneos da mesma versão | os dois runs ficam `atual=sim` |
| Salvar + ativar com o registro falhando | `marcar_ativo` não roda; a versão anterior continua `ativo=sim` no MLflow |
| Reavaliação que para no meio | os avisos do MLflow das versões já terminadas se perdem |
| Tag `mlflow.source.git.commit` | aponta para o `HEAD`, que não contém a versão recém-salva (o `modelos.json` está sujo) |

O atraso de 20 s fica como está (é o pior caso, com outro processo segurando o banco; não vale trocar o
ativar por um job). Só o texto do aviso é corrigido.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `src/ml/studio/api.py` | `_registrar_mlflow` com primeira linha cortada; salvar marca a ativa à parte; erro do reavaliar com avisos |
| `src/ml/core/registro_mlflow.py` | trava do processo; `_tags_git` no lugar de `_commit_git` |
| `tests/test_studio_salvar.py`, `tests/test_studio_reavaliar.py`, `tests/test_registro_mlflow.py` | testes novos |
| `README.md`, `CHANGELOG.md` | documentação |

---

### Task 1: aviso legível

**Files:**
- Modify: `src/ml/studio/api.py` (`_registrar_mlflow`)
- Modify: `tests/test_studio_salvar.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_studio_salvar.py`, antes de `if __name__ == '__main__':`:

```python
class TestRegistrarMlflow(unittest.TestCase):
  def test_aviso_usa_so_a_primeira_linha_do_erro(self):
    def falha():
      raise OSError('(sqlite3.OperationalError) database is locked\n[SQL: SELECT experiments.experiment_id]\n'
                    '(Background on this error at: https://sqlalche.me/e/20/e3q8)')
    self.assertEqual(api._registrar_mlflow(falha),
                     'não registrou no MLflow: (sqlite3.OperationalError) database is locked')

  def test_aviso_longo_e_cortado(self):
    def falha():
      raise OSError('x' * 500)
    aviso = api._registrar_mlflow(falha)
    self.assertEqual(aviso, 'não registrou no MLflow: ' + 'x' * 200 + '...')

  def test_erro_sem_mensagem_usa_o_nome_da_excecao(self):
    def falha():
      raise OSError()
    self.assertEqual(api._registrar_mlflow(falha), 'não registrou no MLflow: OSError')

  def test_sem_erro_devolve_none(self):
    self.assertIsNone(api._registrar_mlflow(lambda: None))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: falham os três primeiros (a mensagem vem inteira; o erro vazio vira `'não registrou no MLflow: '`).

- [ ] **Step 3: Implementar**

Em `src/ml/studio/api.py`, substituir a função `_registrar_mlflow` inteira por:

```python
AVISO_MLFLOW_MAX = 200


def _registrar_mlflow(acao) -> Optional[str]:
  """Roda o registro no MLflow; devolve None ou o aviso para a tela.

  O modelos.json é a fonte da verdade: uma falha aqui (MLflow fora do ar, banco travado, pacote
  quebrado) nunca desfaz nem impede a gravação. Recuperação: src/ml/studio_mlflow.py.
  O aviso leva só a primeira linha do erro, cortada: o erro de banco travado do SQLAlchemy traz a
  consulta SQL inteira. Com o banco travado, o aviso só chega depois de 20 s (o MLflow força
  PRAGMA busy_timeout = 20000 em toda sessão).
  """
  try:
    acao()
    return None
  except Exception as erro:
    linhas = str(erro).strip().splitlines()
    motivo = linhas[0] if linhas else type(erro).__name__
    if len(motivo) > AVISO_MLFLOW_MAX:
      motivo = motivo[:AVISO_MLFLOW_MAX] + '...'
    return f'não registrou no MLflow: {motivo}'
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py tests/test_studio_reavaliar.py -v`
Expected: todos `OK`.

---

### Task 2: salvar marca a ativa mesmo se o registro falhar

**Files:**
- Modify: `src/ml/studio/api.py` (`modelos_salvar`, função interna `tarefa`)
- Modify: `tests/test_studio_salvar.py` (classe `TestSalvarRota`)

- [ ] **Step 1: Escrever os testes que falham**

Em `TestSalvarRota`, depois de `test_falha_do_mlflow_vira_aviso_e_a_versao_fica_salva`:

```python
  def test_falha_no_registro_ainda_marca_a_ativa(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('database is locked')
    r, _, _, _ = self.salvar(ativar=True)
    self.mlflow.marcar_ativo.assert_called_once_with('v2')
    self.assertEqual(r['resultado']['aviso_mlflow'], 'não registrou no MLflow: database is locked')

  def test_duas_falhas_juntam_os_avisos(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('a')
    self.mlflow.marcar_ativo.side_effect = OSError('b')
    r, _, _, _ = self.salvar(ativar=True)
    self.assertEqual(r['resultado']['aviso_mlflow'], 'não registrou no MLflow: a; não registrou no MLflow: b')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: falham os dois novos (`marcar_ativo` não é chamado quando o registro falha).

- [ ] **Step 3: Implementar**

Em `modelos_salvar`, dentro de `tarefa`, substituir

```python
    ativa = corpo.ativar and erro_ativar is None

    def registrar():
      core_registro_mlflow.registrar_avaliacao(corpo.nome, gravado['versoes'][corpo.nome], 'salvar', ativo=ativa)
      if ativa:
        core_registro_mlflow.marcar_ativo(corpo.nome)
    return {'nome': corpo.nome, 'ativa': ativa, 'erro_ativar': erro_ativar,
            'aviso_mlflow': _registrar_mlflow(registrar)}
```

por

```python
    ativa = corpo.ativar and erro_ativar is None
    avisos = [_registrar_mlflow(lambda: core_registro_mlflow.registrar_avaliacao(
      corpo.nome, gravado['versoes'][corpo.nome], 'salvar', ativo=ativa))]
    if ativa:
      # À parte: mesmo sem o run novo, a tag ativo precisa sair dos runs da versão anterior.
      avisos.append(_registrar_mlflow(lambda: core_registro_mlflow.marcar_ativo(corpo.nome)))
    return {'nome': corpo.nome, 'ativa': ativa, 'erro_ativar': erro_ativar,
            'aviso_mlflow': '; '.join(a for a in avisos if a) or None}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_salvar.py -v`
Expected: todos `OK` (inclusive `test_ativar_marca_a_ativa_no_mlflow` e `test_ativacao_que_falha_nao_marca_no_mlflow`, que já existiam).

---

### Task 3: reavaliação que para no meio leva os avisos do MLflow

**Files:**
- Modify: `src/ml/studio/api.py` (`modelos_reavaliar`, bloco `except` da função interna `tarefa`)
- Modify: `tests/test_studio_reavaliar.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `TestReavaliarRota`, depois de `test_falha_na_avaliacao_registra_so_as_que_terminaram`:

```python
  def test_falha_na_avaliacao_leva_os_avisos_do_mlflow_das_que_terminaram(self):
    self.mlflow.registrar_avaliacao.side_effect = OSError('database is locked')
    r, _, _ = self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertIn('parou em v2', str(r))
    self.assertIn('MLflow: v1: não registrou no MLflow: database is locked', str(r))

  def test_falha_na_avaliacao_sem_aviso_nao_cita_o_mlflow(self):
    r, _, _ = self.rodar(['v1', 'v2'], [NOVA, RuntimeError('sem memória')])
    self.assertNotIn('MLflow', str(r))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_studio_reavaliar.py -v`
Expected: falha o primeiro (a mensagem de erro não cita o MLflow); o segundo já passa.

- [ ] **Step 3: Implementar**

Em `modelos_reavaliar`, dentro de `tarefa`, substituir

```python
      except Exception as falha:
        detalhe = falha.detail if isinstance(falha, HTTPException) else str(falha)
        raise RuntimeError(f'parou em {nome}: {detalhe}; já reavaliadas: {feitas}') from falha
```

por

```python
      except Exception as falha:
        detalhe = falha.detail if isinstance(falha, HTTPException) else str(falha)
        # As que terminaram já foram gravadas; se o MLflow ficou para trás nelas, o erro precisa dizer.
        mlflow = '; MLflow: ' + '; '.join(f"{a['nome']}: {a['aviso']}" for a in avisos) if avisos else ''
        raise RuntimeError(f'parou em {nome}: {detalhe}; já reavaliadas: {feitas}{mlflow}') from falha
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_studio_reavaliar.py -v`
Expected: todos `OK` (inclusive `test_falha_no_meio_mantem_as_anteriores_e_cita_a_versao`).

- [ ] **Step 5: Sugerir commit**

Arquivos: `src/ml/studio/api.py`, `tests/test_studio_salvar.py`, `tests/test_studio_reavaliar.py`.
Mensagem: `fix(studio): aviso do MLflow legível, ativa marcada à parte e avisos no erro do reavaliar`

---

### Task 4: trava contra registros simultâneos

**Files:**
- Modify: `src/ml/core/registro_mlflow.py`
- Modify: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_registro_mlflow.py`, acrescentar `import threading` e `import time` aos imports do topo
(em ordem alfabética, depois de `import tempfile`), e antes de `class TestIsolamentoDosTestes`:

```python
class TestConcorrencia(Base):
  def test_dois_registros_simultaneos_da_mesma_versao_deixam_um_atual(self):
    R.registrar_avaliacao('v1', versao_sintetica(), 'salvar', ativo=False)  # cria banco e experimento antes
    original = R._runs

    def devagar(cli, exp_id):
      """Força as duas threads a lerem a lista de anteriores antes de qualquer uma criar o run."""
      runs = original(cli, exp_id)
      time.sleep(0.5)
      return runs

    with mock.patch.object(R, '_runs', side_effect=devagar):
      threads = [threading.Thread(target=R.registrar_avaliacao, args=('v2', versao_sintetica(), 'reavaliar'),
                                  kwargs={'ativo': False}) for _ in range(2)]
      for t in threads:
        t.start()
      for t in threads:
        t.join()
    runs_v2 = [r for r in self.runs() if r.data.tags.get('modelo') == 'v2']
    self.assertEqual(len(runs_v2), 2)
    self.assertEqual(sorted(r.data.tags['atual'] for r in runs_v2), ['nao', 'sim'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: `test_dois_registros_simultaneos_da_mesma_versao_deixam_um_atual` falha com `['sim', 'sim'] != ['nao', 'sim']`.

- [ ] **Step 3: Implementar**

Em `src/ml/core/registro_mlflow.py`:

1. Nos imports, acrescentar `import functools` (depois de `import json`) e `import threading` (depois de
   `import subprocess`).

2. Depois da linha `ALVOS = {...}`, acrescentar:

```python
# registrar_avaliacao lê os runs anteriores e só depois cria o novo: duas chamadas ao mesmo tempo para a
# mesma versão deixariam os dois runs com atual=sim. A trava vale para o processo (as threads do Studio);
# outro processo ao mesmo tempo (o script junto com o Studio) não é coberto: rodar o script de novo conserta.
_trava = threading.Lock()


def _exclusivo(funcao):
  @functools.wraps(funcao)
  def envolta(*args, **kwargs):
    with _trava:
      return funcao(*args, **kwargs)
  return envolta
```

3. Pôr `@_exclusivo` na linha de cima de `def registrar_avaliacao(` e na linha de cima de `def marcar_ativo(`.
   (`registrar_avaliacao` não chama `marcar_ativo` nem o contrário, então a trava não se trava sozinha.)

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py tests/test_studio_mlflow.py -v`
Expected: todos `OK`.

---

### Task 5: tag de árvore suja no lugar do commit sozinho

**Files:**
- Modify: `src/ml/core/registro_mlflow.py` (`_commit_git` vira `_tags_git`; uso em `registrar_avaliacao`)
- Modify: `tests/test_registro_mlflow.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_registro_mlflow.py`, acrescentar `import subprocess` aos imports do topo (depois de `import re`),
e antes de `class TestIsolamentoDosTestes`:

```python
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
      rid = R.registrar_avaliacao('v9', versao_sintetica(), 'salvar', ativo=False)
    tags = self.tags(rid)
    self.assertEqual(tags['mlflow.source.git.commit'], 'abc')
    self.assertEqual(tags['git_arvore'], 'suja')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py -v`
Expected: `AttributeError: ... has no attribute '_tags_git'` nos testes novos.

- [ ] **Step 3: Implementar**

Em `src/ml/core/registro_mlflow.py`, substituir a função `_commit_git` inteira por:

```python
def _tags_git() -> dict:
  """Commit do HEAD e se a árvore (arquivos rastreados) tinha mudanças. Logo depois de salvar, é sempre
  'suja': a versão nova só existe no modelos.json ainda não commitado, então o commit sozinho não
  reproduz o run. Sem git, ou com erro do git, não há tags."""
  try:
    commit = subprocess.run(['git', '-C', RAIZ, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                            timeout=5, check=True).stdout.strip()
    mudancas = subprocess.run(['git', '-C', RAIZ, 'status', '--porcelain', '--untracked-files=no'],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
  except (OSError, subprocess.SubprocessError):
    return {}
  if not commit:
    return {}
  return {'mlflow.source.git.commit': commit, 'git_arvore': 'suja' if mudancas else 'limpa'}
```

E, em `registrar_avaliacao`, substituir

```python
  commit = _commit_git()
  if commit:
    tags['mlflow.source.git.commit'] = commit
```

por

```python
  tags.update(_tags_git())
```

Atualizar a docstring de `registrar_avaliacao`: trocar `versao_comodo (se houver) e o commit do git.` por
`versao_comodo (se houver), o commit do git e git_arvore (limpa/suja).`

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m unittest tests/test_registro_mlflow.py tests/test_studio_mlflow.py -v`
Expected: todos `OK`. Conferir que não sobrou referência: `grep -rn "_commit_git" src tests` sem saída.

- [ ] **Step 5: Sugerir commit**

Arquivos: `src/ml/core/registro_mlflow.py`, `tests/test_registro_mlflow.py`.
Mensagem: `fix(mlflow): trava contra registros simultâneos e tag de árvore suja no registro do Studio`

---

### Task 6: documentação

**Files:**
- Modify: `README.md` (seção `### MLflow`)
- Modify: `CHANGELOG.md` (entrada "Studio registra no MLflow sozinho", no topo)

- [ ] **Step 1: README**

Na seção `### MLflow`, logo depois do item que começa com `- The Studio logs to the working MLflow by itself`,
acrescentar:

```markdown
- Runs logged before 2026-11-09 still carry an `ativo` parameter that may be stale (MLflow parameters cannot change); use the `ativo` tag. The `git_arvore` tag says whether tracked files had uncommitted changes when the run was logged: right after saving it is always `suja`, because the new version only exists in the uncommitted `modelos.json`.
```

- [ ] **Step 2: CHANGELOG**

Na entrada `# Changelog — Studio registra no MLflow sozinho` (a primeira do arquivo), logo antes de `## Como conferir`,
acrescentar:

```markdown
## Correções da revisão

Medido num banco temporário antes de corrigir:

- Banco travado: o aviso vinha com a consulta SQL inteira (6 linhas). Agora leva só a primeira linha,
  cortada em 200 caracteres. A espera de 20 s continua: o MLflow força `PRAGMA busy_timeout = 20000` em toda
  sessão e um `timeout` na URI não muda isso. É o pior caso (outro processo segurando o banco).
- Dois registros simultâneos da mesma versão deixavam os dois runs com `atual=sim`. Agora
  `registrar_avaliacao` e `marcar_ativo` rodam sob uma trava do processo (não cobre outro processo ao
  mesmo tempo).
- Salvar e ativar com o registro falhando deixava a versão anterior com `ativo=sim`. Agora `marcar_ativo`
  roda à parte e os dois avisos aparecem juntos.
- Uma reavaliação que parava no meio perdia os avisos do MLflow das versões já gravadas. Agora a mensagem de
  erro os inclui.
- A tag `mlflow.source.git.commit` sugeria que o commit reproduzia o run, mas logo depois de salvar a versão
  nova só existe no `modelos.json` não commitado. Agora o run também leva `git_arvore` (`limpa` ou `suja`).
- Os runs antigos ainda têm o parâmetro `ativo` desatualizado (parâmetro não muda); vale a tag.

```

- [ ] **Step 3: Sugerir commit**

Arquivos: `README.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-11-09-studio-registro-mlflow-design.md`,
`docs/superpowers/plans/2026-11-09-studio-registro-mlflow-correcoes.md`.
Mensagem: `docs: correções da revisão do registro do Studio no MLflow`

---

### Task 7: verificação final

- [ ] **Step 1:** `stat -c '%s %Y' mlflow.db` e `ls mlruns`: anotar.
- [ ] **Step 2:** suíte inteira (cerca de 3 a 30 min; em segundo plano):
  `venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | grep -E "^Ran |^OK|^FAILED"` e
  `node --test tests/js/logica.test.js 2>&1 | grep -E "^# (pass|fail)"`.
  Expected: `OK` e `# fail 0`. Se algo falhar, pare e mostre a saída.
- [ ] **Step 3:** repetir o Step 1; os valores precisam ser iguais.
- [ ] **Step 4:** relatar ao Lucas: saída da suíte, Steps 1 e 3, commits sugeridos ainda não feitos. Não rodar
  `studio_mlflow.py` de novo (o MLflow da raiz já foi recuperado; rodar criaria mais 5 runs sem necessidade).

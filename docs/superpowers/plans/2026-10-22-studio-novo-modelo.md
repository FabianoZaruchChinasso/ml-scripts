# Studio novo, parte 2: Modelo com MLflow próprio (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acrescentar ao Studio novo a área Modelo: treinar (LOGO por prédio), registrar versões, promover `@ativo` e reavaliar sem retreinar, tudo num MLflow do Studio (`.studio/mlflow.db`), que o Studio sobe como processo filho e abre por link.

**Architecture:** `run.py` sobe `mlflow server` em `127.0.0.1:5100` com o backend e os artefatos em `.studio/`. O módulo `rastreio` é a única porta para o MLflow e recusa o `mlflow.db` da raiz, que é do Fabiano. `avaliacao` é a avaliação própria do Studio (LOGO, MAE/RMSE/R², "atende"). `treino` e `registro` fazem o trabalho, e `fila` roda os jobs fora da requisição. A tela Modelo (`modelo.js`) mostra a `@ativo`, o formulário de treino, a promoção, a reavaliação e os jobs. Listas e comparações de runs ficam na UI do MLflow.

**Tech Stack:** MLflow 3.15.1 (já no venv), scikit-learn 1.9, XGBoost 3.4, FastAPI, JS puro, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-22-studio-mlflow-design.md` (seções 5, 6, 7, 8).
**Depende de:** `docs/superpowers/plans/2026-10-22-studio-novo-dados.md` concluído (pacote `src/studio/`, `tests/apoio_studio_novo.py`, `web/`).

**Regras do projeto para quem executa:**
- Indentação de 2 espaços no Python.
- Rodar testes com `./venv/bin/python -m unittest <arquivo>` a partir da raiz.
- **Não rodar `git commit` nem `git push`.** Nos pontos marcados "Ponto de commit", pare, liste os arquivos e sugira a mensagem (sem linha `Co-Authored-By`).
- Não editar `src/ml/`, `data/`, `mlflow.db`, `mlruns/`. Nunca apontar o MLflow para o `mlflow.db` ou o `mlruns/` da raiz.

**Fato verificado (2026-10-22, MLflow 3.15.1):** num store sqlite temporário, `mlflow.sklearn.log_model(pipe, name='modelo', signature=..., registered_model_name='studio-x', serialization_format='cloudpickle')` com Pipeline + XGBRegressor registra a versão 1, devolve `info.registered_model_version == 1` e `info.run_id`. `set_registered_model_alias` e `get_model_version_by_alias` funcionam, `mlflow.sklearn.load_model('models:/studio-x@ativo')` recarrega, e nada é escrito fora do sqlite e da pasta de artefatos. `get_model_version_by_alias` levanta `MlflowException` quando o modelo não existe.

---

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/studio/caminhos.py` (modificar) | URI, porta, banco e artefatos do MLflow do Studio |
| `src/studio/rastreio.py` | Cliente MLflow, experimento, nomes, links, guarda contra o store da raiz |
| `src/studio/avaliacao.py` | Regras de descarte, LOGO, métricas, "atende" |
| `src/studio/colunas.py` | Colunas oferecidas no formulário, com marca de vazamento |
| `src/studio/catalogo.py` (modificar) | `usaveis_por_id`, `sobreposicoes` |
| `src/studio/treino.py` | Modelos, pedido, preparação (recusa rápida) e execução (run + versão) |
| `src/studio/fila.py` | Fila de um worker para treinos e reavaliações |
| `src/studio/registro.py` | `@ativo`, versões, comparação, promoção, reavaliação |
| `src/studio/mlflow_servidor.py` | Processo filho `mlflow server` |
| `src/studio/api.py` (modificar) | Rotas de Modelo |
| `src/studio/run.py` (modificar) | Sobe o MLflow junto |
| `src/studio/web/modelo.js` | Tela Modelo |
| `src/studio/web/index.html`, `studio.js`, `styles.css` (modificar) | Aba Modelo |
| `tests/apoio_studio_novo.py` (modificar) | `mlflow_temporario`, `esperar_job` |
| `tests/test_studio_novo_*.py` | Testes |

---

### Task 1: Caminhos do MLflow e módulo `rastreio`

**Files:**
- Modify: `src/studio/caminhos.py`
- Create: `src/studio/rastreio.py`
- Modify: `tests/apoio_studio_novo.py`
- Create: `tests/test_studio_novo_rastreio.py`

- [ ] **Step 1: Acrescentar o apoio de MLflow temporário**

Em `tests/apoio_studio_novo.py`, acrescentar `import time` aos imports do topo e, no fim do arquivo:

```python
@contextlib.contextmanager
def mlflow_temporario():
  """MLflow do Studio num sqlite temporário, sem servidor. Restaura a URI global ao sair."""
  import mlflow
  raiz = tempfile.mkdtemp(prefix='studio-mlflow-')
  anterior = mlflow.get_tracking_uri()
  troca = {'MLFLOW_URI': 'sqlite:///' + os.path.join(raiz, 'mlflow.db'),
           'ARTEFATOS_URI': 'file://' + os.path.join(raiz, 'artefatos'),
           'MLFLOW_UI': 'http://127.0.0.1:5100'}
  with mock.patch.multiple(caminhos, **troca):
    try:
      yield raiz
    finally:
      mlflow.set_tracking_uri(anterior)
      mlflow.set_registry_uri(anterior)
      shutil.rmtree(raiz, ignore_errors=True)


def esperar_job(job_id: str, limite_s: float = 180.0) -> dict:
  from studio import fila
  fim = time.time() + limite_s
  while time.time() < fim:
    job = fila.job(job_id)
    if job['status'] in ('concluído', 'falhou'):
      return job
    time.sleep(0.05)
  raise AssertionError(f'job {job_id} não terminou em {limite_s} s')
```

- [ ] **Step 2: Escrever os testes**

`tests/test_studio_novo_rastreio.py`:

```python
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, rastreio  # noqa: E402


class TestRastreio(unittest.TestCase):
  def test_recusa_o_mlflow_da_raiz(self):
    for uri in ('sqlite:///' + os.path.join(caminhos.REPO, 'mlflow.db'),
                'file://' + os.path.join(caminhos.REPO, 'mlruns'), '', 'http://example.com:5000'):
      with mock.patch.object(caminhos, 'MLFLOW_URI', uri):
        with self.assertRaises(RuntimeError, msg=uri):
          rastreio.uri()

  def test_aceita_o_servidor_do_studio_e_sqlite_fora_da_raiz(self):
    with mock.patch.object(caminhos, 'MLFLOW_URI', 'http://127.0.0.1:5100'):
      self.assertEqual(rastreio.uri(), 'http://127.0.0.1:5100')
    with A.mlflow_temporario():
      self.assertTrue(rastreio.uri().startswith('sqlite:///'))

  def test_experimento_criado_uma_vez(self):
    with A.mlflow_temporario():
      cli = rastreio.cliente()
      self.assertEqual(rastreio.experimento_id(cli), rastreio.experimento_id(cli))
      self.assertEqual(cli.get_experiment_by_name('QoE Studio').name, 'QoE Studio')

  def test_nomes_e_links(self):
    self.assertEqual(rastreio.nome_modelo('latency_ms'), 'studio-latency_ms')
    with self.assertRaises(ValueError):
      rastreio.nome_modelo('qoe_dw_score')
    with mock.patch.object(caminhos, 'MLFLOW_UI', 'http://127.0.0.1:5100'):
      self.assertEqual(rastreio.link_run('3', 'abc'), 'http://127.0.0.1:5100/#/experiments/3/runs/abc')
      self.assertEqual(rastreio.link_versao('studio-jitter_ms', '2'),
                       'http://127.0.0.1:5100/#/models/studio-jitter_ms/versions/2')


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_rastreio.py -v`
Expected: ERROR `ImportError: cannot import name 'rastreio' from 'studio'`.

- [ ] **Step 4: Acrescentar os caminhos do MLflow**

No fim de `src/studio/caminhos.py`:

```python

# MLflow do Studio. Nunca o mlflow.db/mlruns da raiz, que são do Fabiano.
MLFLOW_PORTA = 5100
MLFLOW_URI = f'http://127.0.0.1:{MLFLOW_PORTA}'
MLFLOW_UI = MLFLOW_URI
MLFLOW_DB = os.path.join(ESTADO_DIR, 'mlflow.db')
ARTEFATOS_DIR = os.path.join(ESTADO_DIR, 'artefatos')
# Só nos testes (sqlite sem servidor). Com o servidor, ele decide (mlflow-artifacts:/).
ARTEFATOS_URI = None
```

- [ ] **Step 5: Implementar `rastreio.py`**

`src/studio/rastreio.py`:

```python
"""Única porta do Studio para o MLflow: URI, cliente, experimento, nomes e links.

Recusa apontar para o MLflow da raiz do repositório (mlflow.db, mlruns/): é do
Fabiano, e o benchmark e o regression_mlflow.py gravam lá.
"""

import math
import os

import mlflow
from mlflow import MlflowClient

from studio import caminhos

EXPERIMENTO = 'QoE Studio'
ALVOS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')
ALIAS_ATIVO = 'ativo'


def uri() -> str:
  """A URI em uso, se for o servidor local do Studio ou um sqlite fora do mlflow.db da raiz."""
  u = caminhos.MLFLOW_URI or ''
  if u.startswith(('http://127.0.0.1:', 'http://localhost:')):
    return u
  if u.startswith('sqlite:///'):
    path = os.path.abspath(u[len('sqlite:///'):])
    if path != os.path.join(caminhos.REPO, 'mlflow.db'):
      return u
  raise RuntimeError(f'URI do MLflow recusada: {u!r}. O Studio só usa o próprio servidor local '
                     'ou um sqlite fora do mlflow.db da raiz.')


def cliente() -> MlflowClient:
  """Cliente apontado para o MLflow do Studio. Ajusta também a URI global (start_run, load_model)."""
  u = uri()
  mlflow.set_tracking_uri(u)
  mlflow.set_registry_uri(u)
  return MlflowClient(tracking_uri=u, registry_uri=u)


def experimento_id(cli: MlflowClient) -> str:
  exp = cli.get_experiment_by_name(EXPERIMENTO)
  if exp is not None:
    return exp.experiment_id
  return cli.create_experiment(EXPERIMENTO, artifact_location=caminhos.ARTEFATOS_URI)


def nome_modelo(alvo: str) -> str:
  if alvo not in ALVOS:
    raise ValueError(f'alvo {alvo!r} desconhecido; esperado um de {list(ALVOS)}')
  return f'studio-{alvo}'


def link_run(experimento: str, run_id: str) -> str:
  return f'{caminhos.MLFLOW_UI}/#/experiments/{experimento}/runs/{run_id}'


def link_versao(nome: str, versao) -> str:
  return f'{caminhos.MLFLOW_UI}/#/models/{nome}/versions/{versao}'


def registrar_metricas(metricas: dict) -> None:
  """log_metrics só com números finitos: NaN (R² de prédio com 1 linha) fica de fora."""
  mlflow.log_metrics({k: float(v) for k, v in metricas.items()
                      if isinstance(v, (int, float)) and math.isfinite(v)})
```

- [ ] **Step 6: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_rastreio.py tests/test_studio_novo_isolamento.py -v`
Expected: OK (4 + 3 testes).

- [ ] **Step 7: Ponto de commit**

Arquivos: `src/studio/caminhos.py`, `src/studio/rastreio.py`, `tests/apoio_studio_novo.py`, `tests/test_studio_novo_rastreio.py`.
Mensagem sugerida: `feat(studio-novo): acesso ao MLflow do Studio, recusando o store da raiz`

---

### Task 2: Avaliação própria do Studio

**Files:**
- Create: `src/studio/avaliacao.py`
- Create: `tests/test_studio_novo_avaliacao.py`

- [ ] **Step 1: Escrever os testes (números calculados à mão)**

`tests/test_studio_novo_avaliacao.py`:

```python
import math
import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from studio import avaliacao  # noqa: E402

ALVO = 'speedtest_down_mbps'
ZERO = {'up': 0, 'lat': 0, 'jit': 0}


class TestMetricas(unittest.TestCase):
  # erros: +2, -2, +3, 0
  y = [10.0, 20.0, 30.0, 40.0]
  pred = [12.0, 18.0, 33.0, 40.0]
  grupos = ['a', 'a', 'b', 'b']
  apps = {'X': {'dn': 25, **ZERO}, 'Y': {'dn': 19, **ZERO}, 'Tudo Passa': {'dn': 0, **ZERO}}

  def test_regressao_global_e_por_predio(self):
    m = avaliacao.metricas(self.y, self.pred, self.grupos, ALVO, self.apps)
    self.assertAlmostEqual(m['mae'], 1.75)
    self.assertAlmostEqual(m['rmse'], math.sqrt(17 / 4))
    self.assertAlmostEqual(m['r2'], 1 - 17 / 500)
    self.assertAlmostEqual(m['mae__a'], 2.0)
    self.assertAlmostEqual(m['mae__b'], 1.5)
    self.assertEqual((m['linhas'], m['predios']), (4, 2))

  def test_atende_acuracia_balanceada(self):
    m = avaliacao.metricas(self.y, self.pred, self.grupos, ALVO, self.apps)
    # limiar 25: real [F,F,T,T], previsto [F,F,T,T]
    self.assertAlmostEqual(m['atende_bacc__x'], 1.0)
    # limiar 19: real [F,T,T,T], previsto [F,F,T,T] -> (1 + 2/3) / 2
    self.assertAlmostEqual(m['atende_bacc__y'], (1 + 2 / 3) / 2)
    # limiar 0: todas atendem, acurácia balanceada indefinida
    self.assertNotIn('atende_bacc__tudo_passa', m)

  def test_latencia_atende_com_menor_ou_igual(self):
    self.assertEqual(list(avaliacao.atende(np.array([50.0, 100.0, 150.0]), 'latency_ms', 100)), [True, True, False])
    self.assertEqual(list(avaliacao.atende(np.array([5.0, 25.0]), ALVO, 25)), [False, True])

  def test_slug_de_aplicacao(self):
    self.assertEqual(avaliacao.slug('Chamada de vídeo'), 'chamada_de_video')
    self.assertEqual(avaliacao.slug('Streaming 4K'), 'streaming_4k')


class TestLogo(unittest.TestCase):
  def test_cada_predio_e_previsto_sem_ele_no_treino(self):
    X = pd.DataFrame({'f': [1.0, 2.0, 3.0, 4.0]})
    y = pd.Series([10.0, 20.0, 30.0, 40.0])
    grupos = pd.Series(['a', 'a', 'b', 'b'])
    pred = avaliacao.fora_do_fold(DummyRegressor(), X, y, grupos)
    self.assertEqual(list(pred), [35.0, 35.0, 15.0, 15.0])


class TestRegras(unittest.TestCase):
  def setUp(self):
    self.df = pd.DataFrame({
      '_predio': ['alfa', 'alfa', 'alfa', 'alfa', 'beta', 'alfa'],
      ALVO: [0.0, 50.0, 95.0, 90.0, 95.0, np.nan],
      'router_expected_throughput_mbps': [200.0, 200.0, 200.0, 80.0, 200.0, 200.0],
    })
    self.tetos = {'alfa': 100.0}

  def test_padrao_tira_vazio_e_zero(self):
    df, removidas = avaliacao.aplicar_regras(self.df, ALVO, avaliacao.REGRAS_PADRAO, self.tetos)
    self.assertEqual(list(df[ALVO]), [50.0, 95.0, 90.0, 95.0])
    self.assertEqual(removidas, {'alvo_vazio': 1, 'descartar_alvo_zero': 1})

  def test_teto_wan_tira_so_quem_esta_no_teto_e_podia_mais(self):
    regras = {'descartar_alvo_zero': True, 'teto_wan': True}
    df, removidas = avaliacao.aplicar_regras(self.df, ALVO, regras, self.tetos)
    # 95 >= 0,85 x 100 e esperado 200 > 100: sai. 90 com esperado 80: fica. beta não tem teto: fica.
    self.assertEqual(list(df[ALVO]), [50.0, 90.0, 95.0])
    self.assertEqual(removidas['teto_wan'], 1)

  def test_sem_regras_so_tira_vazio(self):
    df, removidas = avaliacao.aplicar_regras(self.df, ALVO, {'descartar_alvo_zero': False, 'teto_wan': False}, {})
    self.assertEqual(len(df), 5)
    self.assertEqual(removidas, {'alvo_vazio': 1})


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_avaliacao.py -v`
Expected: ERROR `ImportError: cannot import name 'avaliacao' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/avaliacao.py`:

```python
"""Avaliação do Studio: LOGO por prédio, MAE/RMSE/R² e "atende" por aplicação.

Própria do Studio, sem relação com a régua de ml/core/avaliacao.py. As regras de
descarte são parâmetros explícitos, e a contagem de linhas que cada uma tirou
volta para ser logada no run.
"""

import re
import unicodedata

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import balanced_accuracy_score, mean_absolute_error, mean_squared_error, r2_score

COLUNA_PREDIO = '_predio'
# Chave do limiar em config/aplicacoes.json e sentido do "atende" de cada alvo.
LIMIAR = {'speedtest_down_mbps': ('dn', 'min'), 'speedtest_up_mbps': ('up', 'min'),
          'latency_ms': ('lat', 'max'), 'jitter_ms': ('jit', 'max')}
REGRAS_PADRAO = {'descartar_alvo_zero': True, 'teto_wan': False}
# Fração do teto de WAN a partir da qual o speedtest pode estar medindo a internet.
FRACAO_TETO = 0.85


def slug(texto: str) -> str:
  """Nome de aplicação como pedaço de nome de métrica: 'Chamada de vídeo' -> 'chamada_de_video'."""
  base = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
  return re.sub(r'[^a-z0-9]+', '_', base.lower()).strip('_')


def aplicar_regras(df: pd.DataFrame, alvo: str, regras: dict, tetos: dict) -> tuple:
  """(df filtrado com índice refeito, {regra: linhas removidas}).

  `tetos` = {prédio: Mbps} para este alvo. Alvo vazio sai sempre.
  """
  removidas = {}
  y = pd.to_numeric(df[alvo], errors='coerce')
  vazio = y.isna()
  removidas['alvo_vazio'] = int(vazio.sum())
  df, y = df[~vazio], y[~vazio]
  if regras.get('descartar_alvo_zero'):
    zero = y == 0
    removidas['descartar_alvo_zero'] = int(zero.sum())
    df, y = df[~zero], y[~zero]
  if regras.get('teto_wan'):
    teto = df[COLUNA_PREDIO].map(tetos).astype(float)
    if 'router_expected_throughput_mbps' in df.columns:
      esperado = pd.to_numeric(df['router_expected_throughput_mbps'], errors='coerce')
    else:
      esperado = pd.Series(np.nan, index=df.index)
    no_teto = (teto.notna() & (y >= FRACAO_TETO * teto) & (esperado > teto)).fillna(False).astype(bool)
    removidas['teto_wan'] = int(no_teto.sum())
    df = df[~no_teto]
  return df.reset_index(drop=True), removidas


def fora_do_fold(modelo, X: pd.DataFrame, y: pd.Series, grupos: pd.Series) -> np.ndarray:
  """Previsão de cada linha pelo modelo treinado sem o prédio dela (LOGO)."""
  pred = np.full(len(y), np.nan)
  grupos = np.asarray(grupos)
  for predio in sorted(set(grupos)):
    teste = grupos == predio
    ajustado = clone(modelo).fit(X[~teste], y[~teste])
    pred[teste] = ajustado.predict(X[teste])
  return pred


def _regressao(y: np.ndarray, pred: np.ndarray) -> dict:
  return {'mae': float(mean_absolute_error(y, pred)),
          'rmse': float(np.sqrt(mean_squared_error(y, pred))),
          'r2': float(r2_score(y, pred)) if len(y) > 1 else float('nan')}


def atende(valores: np.ndarray, alvo: str, limiar: float) -> np.ndarray:
  _, sentido = LIMIAR[alvo]
  return valores >= limiar if sentido == 'min' else valores <= limiar


def metricas(y, pred, grupos, alvo: str, aplicacoes: dict) -> dict:
  y = np.asarray(y, dtype=float)
  pred = np.asarray(pred, dtype=float)
  grupos = np.asarray(grupos)
  saida = dict(_regressao(y, pred))
  for predio in sorted(set(grupos)):
    m = grupos == predio
    for nome, valor in _regressao(y[m], pred[m]).items():
      saida[f'{nome}__{predio}'] = valor
  chave, _ = LIMIAR[alvo]
  for app, limiares in aplicacoes.items():
    real, previsto = atende(y, alvo, limiares[chave]), atende(pred, alvo, limiares[chave])
    if len(set(real.tolist())) < 2:
      continue  # todas as amostras do mesmo lado do limiar: acurácia balanceada indefinida
    saida[f'atende_bacc__{slug(app)}'] = float(balanced_accuracy_score(real, previsto))
  saida['linhas'] = int(len(y))
  saida['predios'] = int(len(set(grupos)))
  return saida


def tabela_por_predio(y, pred, grupos) -> pd.DataFrame:
  y, pred, grupos = np.asarray(y, dtype=float), np.asarray(pred, dtype=float), np.asarray(grupos)
  linhas = []
  for predio in sorted(set(grupos)):
    m = grupos == predio
    linhas.append({'predio': predio, 'linhas': int(m.sum()), **_regressao(y[m], pred[m])})
  return pd.DataFrame(linhas)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_avaliacao.py -v`
Expected: 8 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/avaliacao.py`, `tests/test_studio_novo_avaliacao.py`.
Mensagem sugerida: `feat(studio-novo): avaliação própria (LOGO por prédio, MAE/RMSE/R², atende)`

---

### Task 3: Colunas do formulário e seleção de datasets

**Files:**
- Modify: `src/studio/catalogo.py`
- Create: `src/studio/colunas.py`
- Create: `tests/test_studio_novo_colunas.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_colunas.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import catalogo, colunas  # noqa: E402


class TestColunas(unittest.TestCase):
  def test_numericas_comuns_sem_alvos_nem_excluidas(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], n=3, semente=2).drop(columns=['router_signal_dbm']))
      nomes = {c['coluna']: c for c in colunas.disponiveis(['a.csv', 'b.csv'])}
      self.assertIn('router_snr', nomes)
      self.assertNotIn('router_signal_dbm', nomes)
      self.assertNotIn('speedtest_down_mbps', nomes)
      self.assertNotIn('combo', nomes)
      self.assertTrue(nomes['router_tx_retries']['vazamento'])
      self.assertFalse(nomes['router_snr']['vazamento'])
      self.assertEqual(nomes['router_snr']['preenchimento'], 1.0)

  def test_prefixo_de_vazamento(self):
    cfg = colunas.carregar()
    self.assertTrue(colunas.com_vazamento('download_bytes', cfg))
    self.assertFalse(colunas.com_vazamento('router_snr', cfg))


class TestSelecao(unittest.TestCase):
  def test_usaveis_por_id_recusa_desconhecido(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      self.assertEqual([d['id'] for d in catalogo.usaveis_por_id(['a.csv'])], ['a.csv'])
      with self.assertRaises(ValueError):
        catalogo.usaveis_por_id(['a.csv', 'x.csv'])

  def test_sobreposicoes(self):
    with A.pastas_temporarias() as p:
      base = A.frame(['alfa-1', 'beta-1'], semente=1)
      A.gravar_csv(p.data, 'a.csv', base)
      A.gravar_csv(p.data, 'copia.csv', base)
      A.gravar_csv(p.data, 'parte.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'outro.csv', A.frame(['gama-1'], semente=9))
      self.assertEqual(catalogo.sobreposicoes(['a.csv', 'outro.csv']), [])
      self.assertEqual(catalogo.sobreposicoes(['a.csv', 'copia.csv']), ['a.csv e copia.csv têm os mesmos alvos'])
      self.assertEqual(catalogo.sobreposicoes(['parte.csv', 'a.csv']), ['parte.csv está contido em a.csv'])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_colunas.py -v`
Expected: ERROR `ImportError: cannot import name 'colunas' from 'studio'`.

- [ ] **Step 3: Acrescentar a seleção ao catálogo**

No fim de `src/studio/catalogo.py`:

```python


def usaveis_por_id(ids, itens: list = None) -> list:
  """Os descritores utilizáveis dos ids, na ordem pedida. ValueError lista os que faltam."""
  itens = descobertos() if itens is None else itens
  por_id = {d['id']: d for d in itens if d.get('usable')}
  faltam = [i for i in ids if i not in por_id]
  if faltam:
    raise ValueError(f'datasets desconhecidos ou inutilizáveis: {faltam}')
  return [por_id[i] for i in ids]


def sobreposicoes(ids, itens: list = None) -> list:
  """Pares entre os escolhidos com os mesmos alvos ou um contido no outro: as amostras contariam duas vezes."""
  chaves = {d['id']: chaves_alvos(d['_frame']) for d in usaveis_por_id(ids, itens)}
  saida = []
  for a in sorted(chaves):
    for b in sorted(chaves):
      if a < b and chaves[a] == chaves[b]:
        saida.append(f'{a} e {b} têm os mesmos alvos')
      elif a != b and chaves[a] and chaves[a] < chaves[b]:
        saida.append(f'{a} está contido em {b}')
  return saida
```

- [ ] **Step 4: Implementar `colunas.py`**

`src/studio/colunas.py`:

```python
"""Colunas que o formulário de treino oferece, com a marca de vazamento.

A lista de vazamento vem de config/colunas.json (semeado de column_provenance.json):
os contadores router_* são deltas da janela do speedtest e carregam o próprio alvo.
"""

import json

import pandas as pd

from studio import caminhos, catalogo

CHAVES = {'vazamento', 'vazamento_prefixos', 'excluir'}


def carregar(path: str = None) -> dict:
  with open(path or caminhos.COLUNAS_PATH, encoding='utf-8') as handle:
    cfg = json.load(handle)
  if not isinstance(cfg, dict) or set(cfg) != CHAVES or not all(isinstance(cfg[k], list) for k in CHAVES):
    raise ValueError(f'colunas.json precisa ter exatamente as listas {sorted(CHAVES)}')
  return cfg


def com_vazamento(coluna: str, cfg: dict) -> bool:
  return coluna in cfg['vazamento'] or any(coluna.startswith(p) for p in cfg['vazamento_prefixos'])


def disponiveis(ids, itens: list = None) -> list:
  """Colunas numéricas presentes em todos os datasets escolhidos, sem alvos nem identificadores."""
  escolhidos = catalogo.usaveis_por_id(ids, itens)
  if not escolhidos:
    return []
  cfg = carregar()
  numericas = [{c for c in d['_frame'].columns if pd.api.types.is_numeric_dtype(d['_frame'][c])} for d in escolhidos]
  comuns = set.intersection(*numericas) - set(cfg['excluir']) - set(catalogo.TARGETS)
  junto = pd.concat([d['_frame'][sorted(comuns)] for d in escolhidos], ignore_index=True)
  return [{'coluna': c, 'vazamento': com_vazamento(c, cfg), 'preenchimento': round(float(junto[c].notna().mean()), 4)}
          for c in sorted(comuns)]
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_colunas.py tests/test_studio_novo_catalogo.py -v`
Expected: 4 + 3 testes, OK.

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/studio/catalogo.py`, `src/studio/colunas.py`, `tests/test_studio_novo_colunas.py`.
Mensagem sugerida: `feat(studio-novo): colunas do formulário com marca de vazamento e checagem de sobreposição`

---

### Task 4: Treino

**Files:**
- Create: `src/studio/treino.py`
- Create: `tests/test_studio_novo_treino.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_treino.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import rastreio, treino  # noqa: E402

ALVO = 'speedtest_down_mbps'
FEATURES = ['router_snr', 'router_signal_dbm']


def pedido(datasets, features=FEATURES, **extra):
  return treino.Pedido(alvo=ALVO, datasets=list(datasets), features=list(features),
                       hiper=extra.pop('hiper', {'n_estimators': 5}), **extra)


class TestPreparar(unittest.TestCase):
  def test_um_predio_so_e_recusado(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'alfa-2'], semente=1))
      with self.assertRaisesRegex(ValueError, 'prédio'):
        treino.preparar(pedido(['a.csv']))

  def test_feature_ausente_e_recusada(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      with self.assertRaisesRegex(ValueError, 'nao_existe'):
        treino.preparar(pedido(['a.csv'], ['router_snr', 'nao_existe']))

  def test_datasets_sobrepostos_sao_recusados(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      A.gravar_csv(p.data, 'parte.csv', A.frame(['alfa-1'], semente=1))
      with self.assertRaisesRegex(ValueError, 'sobrepostos'):
        treino.preparar(pedido(['a.csv', 'parte.csv']))

  def test_alvo_como_feature_e_hiper_desconhecido_sao_recusados(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      with self.assertRaises(ValueError):
        treino.preparar(pedido(['a.csv'], ['router_snr', 'speedtest_up_mbps']))
      with self.assertRaises(ValueError):
        treino.preparar(pedido(['a.csv'], hiper={'nao_existe': 1}))

  def test_vazamento_marcado_e_regras_completas(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      prep = treino.preparar(pedido(['a.csv'], ['router_snr', 'router_tx_retries']))
      self.assertTrue(prep.contem_vazamento)
      self.assertEqual(prep.pedido.regras, {'descartar_alvo_zero': True, 'teto_wan': False})
      self.assertFalse(treino.preparar(pedido(['a.csv'])).contem_vazamento)


class TestExecutar(unittest.TestCase):
  def test_treino_registra_run_metricas_artefatos_e_versao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1', 'gama-1'], n=15, semente=1))
      etapas = []
      r = treino.executar(treino.preparar(pedido(['a.csv'])), etapas.append)
      self.assertTrue(etapas)
      cli = rastreio.cliente()
      run = cli.get_run(r['run_id'])
      self.assertEqual(run.info.status, 'FINISHED')
      self.assertEqual(run.data.tags['tipo'], 'treino')
      self.assertNotIn('contem_vazamento', run.data.tags)
      self.assertEqual(run.data.params['features'], 'router_snr,router_signal_dbm')
      self.assertEqual(run.data.params['hiper__n_estimators'], '5')
      self.assertEqual(run.data.params['regra__descartar_alvo_zero'], 'True')
      self.assertTrue(run.data.params['fingerprints'].startswith('a.csv:'))
      for k in ('mae', 'rmse', 'r2', 'mae__alfa', 'mae__beta', 'mae__gama', 'linhas', 'predios'):
        self.assertIn(k, run.data.metrics)
      self.assertEqual(run.data.metrics['predios'], 3)
      artefatos = {a.path for a in cli.list_artifacts(r['run_id'])}
      self.assertTrue({'por_predio.csv', 'previsoes_fora_do_fold.csv', 'features.json'} <= artefatos)
      self.assertEqual(r['versao'], '1')
      self.assertEqual(cli.get_model_version('studio-speedtest_down_mbps', '1').run_id, r['run_id'])
      self.assertTrue(r['link_run'].startswith('http://127.0.0.1:5100/#/experiments/'))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_treino.py -v`
Expected: ERROR `ImportError: cannot import name 'treino' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/treino.py`:

```python
"""Treino pelo Studio: valida o pedido, avalia por LOGO, treina o final e registra no MLflow do Studio.

preparar() roda dentro da requisição (recusa rápida, com o motivo); executar() roda
na fila, fora dela.
"""

import json
import traceback
from dataclasses import dataclass, field

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from studio import aplicacoes, avaliacao, catalogo, colunas, predios, rastreio

SEMENTE = 42
MIN_PREDIOS = 2
# Padrões de build_models em src/ml/regression_benchmark.py, copiados em 2026-10-22 (sem importar).
MODELOS = {
  'RandomForest': (RandomForestRegressor, {'n_estimators': 600, 'min_samples_leaf': 2}),
  'ExtraTrees': (ExtraTreesRegressor, {'n_estimators': 600, 'min_samples_leaf': 2}),
  'HistGradientBoosting': (HistGradientBoostingRegressor,
                           {'learning_rate': 0.05, 'max_depth': 8, 'max_iter': 400, 'min_samples_leaf': 20}),
  'XGBoost': (XGBRegressor, {'n_estimators': 1000, 'learning_rate': 0.03, 'max_depth': 6, 'min_child_weight': 3,
                             'subsample': 0.8, 'colsample_bytree': 0.8, 'reg_alpha': 0.01, 'reg_lambda': 1.0}),
}
# Fixos por modelo: não aparecem no formulário.
FIXOS = {
  'RandomForest': {'n_jobs': -1, 'random_state': SEMENTE},
  'ExtraTrees': {'n_jobs': -1, 'random_state': SEMENTE},
  'HistGradientBoosting': {'random_state': SEMENTE},
  'XGBoost': {'objective': 'reg:squarederror', 'random_state': SEMENTE},
}


def hiper_efetivo(modelo: str, hiper: dict) -> dict:
  if modelo not in MODELOS:
    raise ValueError(f'modelo {modelo!r} desconhecido; esperado um de {list(MODELOS)}')
  padrao = MODELOS[modelo][1]
  desconhecidos = sorted(set(hiper or {}) - set(padrao))
  if desconhecidos:
    raise ValueError(f'hiperparâmetros desconhecidos para {modelo}: {desconhecidos}')
  return {**padrao, **(hiper or {})}


def montar(modelo: str, hiper: dict = None) -> Pipeline:
  efetivo = hiper_efetivo(modelo, hiper)
  classe = MODELOS[modelo][0]
  return Pipeline([('imputer', SimpleImputer(strategy='median')),
                   ('reg', classe(**efetivo, **FIXOS[modelo]))])


@dataclass
class Pedido:
  alvo: str
  datasets: list
  features: list
  modelo: str = 'RandomForest'
  hiper: dict = field(default_factory=dict)
  regras: dict = field(default_factory=lambda: dict(avaliacao.REGRAS_PADRAO))


@dataclass
class Preparado:
  pedido: Pedido
  df: pd.DataFrame
  removidas: dict
  fingerprints: dict
  contem_vazamento: bool


def carregar(ids, itens: list = None, registro: dict = None) -> pd.DataFrame:
  """Linhas dos datasets escolhidos, com `_ds` e o prédio de cada linha em avaliacao.COLUNA_PREDIO."""
  registro = registro if registro is not None else predios.atual()
  frames = []
  for item in catalogo.usaveis_por_id(ids, itens):
    frame = item['_frame'].copy()
    frame['_ds'] = item['id']
    try:
      frame[avaliacao.COLUNA_PREDIO] = predios.resolver(frame['local'], 'predio', registro).to_numpy()
    except ValueError as erro:
      raise ValueError(f"{item['id']}: {erro}") from None
    frames.append(frame)
  return pd.concat(frames, ignore_index=True, sort=False)


def tetos(df: pd.DataFrame, alvo: str, registro: dict) -> dict:
  saida = {}
  for predio in df[avaliacao.COLUNA_PREDIO].unique():
    teto = predios.teto_wan(predio, alvo, registro)
    if teto is not None:
      saida[predio] = teto
  return saida


def faltando(ids, features, itens: list = None) -> dict:
  """{dataset: [features ausentes]}; vazio quando todas existem em todos."""
  saida = {}
  for item in catalogo.usaveis_por_id(ids, itens):
    ausentes = [f for f in features if f not in item['_frame'].columns]
    if ausentes:
      saida[item['id']] = ausentes
  return saida


def matriz(df: pd.DataFrame, features: list) -> pd.DataFrame:
  return df[list(features)].apply(pd.to_numeric, errors='coerce')


def preparar(pedido: Pedido, itens: list = None) -> Preparado:
  """Valida tudo o que dá para validar antes da fila. ValueError com o motivo."""
  if pedido.alvo not in rastreio.ALVOS:
    raise ValueError(f'alvo {pedido.alvo!r} desconhecido; esperado um de {list(rastreio.ALVOS)}')
  if not pedido.datasets:
    raise ValueError('escolha pelo menos um dataset')
  if not pedido.features:
    raise ValueError('escolha pelo menos uma feature')
  alvos = [f for f in pedido.features if f in catalogo.TARGETS]
  if alvos:
    raise ValueError(f'alvo não pode ser feature: {alvos}')
  desconhecidas = sorted(set(pedido.regras) - set(avaliacao.REGRAS_PADRAO))
  if desconhecidas:
    raise ValueError(f'regras desconhecidas: {desconhecidas}')
  hiper_efetivo(pedido.modelo, pedido.hiper)
  itens = catalogo.descobertos() if itens is None else itens
  sobre = catalogo.sobreposicoes(pedido.datasets, itens)
  if sobre:
    raise ValueError('datasets sobrepostos (as mesmas amostras contariam duas vezes): ' + '; '.join(sobre))
  falta = faltando(pedido.datasets, pedido.features, itens)
  if falta:
    raise ValueError(f'features ausentes: {falta}')
  registro = predios.atual()
  regras = {**avaliacao.REGRAS_PADRAO, **pedido.regras}
  df = carregar(pedido.datasets, itens, registro)
  df, removidas = avaliacao.aplicar_regras(df, pedido.alvo, regras, tetos(df, pedido.alvo, registro))
  n = int(df[avaliacao.COLUNA_PREDIO].nunique())
  if n < MIN_PREDIOS:
    raise ValueError(f'só {n} prédio depois das regras: a avaliação deixa um prédio de fora por vez '
                     f'e precisa de pelo menos {MIN_PREDIOS}')
  cfg = colunas.carregar()
  fingerprints = {d['id']: d['fingerprint'] for d in catalogo.usaveis_por_id(pedido.datasets, itens)}
  normalizado = Pedido(pedido.alvo, list(pedido.datasets), list(pedido.features), pedido.modelo,
                       dict(pedido.hiper), regras)
  return Preparado(normalizado, df, removidas, fingerprints,
                   any(colunas.com_vazamento(f, cfg) for f in pedido.features))


def params(prep: Preparado) -> dict:
  p = prep.pedido
  saida = {'alvo': p.alvo, 'datasets': ','.join(p.datasets),
           'fingerprints': ','.join(f'{k}:{v}' for k, v in sorted(prep.fingerprints.items())),
           'features': ','.join(p.features), 'modelo': p.modelo}
  saida.update({f'hiper__{k}': v for k, v in hiper_efetivo(p.modelo, p.hiper).items()})
  saida.update({f'regra__{k}': v for k, v in p.regras.items()})
  saida.update({f'removidas__{k}': v for k, v in prep.removidas.items()})
  return saida


def registrar_artefatos(df: pd.DataFrame, alvo: str, pred, grupos, nome_previsoes: str) -> None:
  """por_predio.csv e as previsões linha a linha, no run ativo."""
  mlflow.log_text(avaliacao.tabela_por_predio(df[alvo], pred, grupos).to_csv(index=False), 'por_predio.csv')
  previsoes = pd.DataFrame({'dataset': df['_ds'], 'local': df['local'], 'predio': grupos,
                            'real': df[alvo], 'previsto': pred})
  mlflow.log_text(previsoes.to_csv(index=False), nome_previsoes)


def executar(prep: Preparado, progresso=None) -> dict:
  """Avalia por LOGO, treina o final, registra run + versão nova em studio-<alvo>."""
  progresso = progresso or (lambda texto: None)
  p = prep.pedido
  cli = rastreio.cliente()
  exp_id = rastreio.experimento_id(cli)
  nome = rastreio.nome_modelo(p.alvo)
  modelo = montar(p.modelo, p.hiper)
  X = matriz(prep.df, p.features)
  y = pd.to_numeric(prep.df[p.alvo])
  grupos = prep.df[avaliacao.COLUNA_PREDIO]
  tags = {'tipo': 'treino', 'alvo': p.alvo}
  if prep.contem_vazamento:
    tags['contem_vazamento'] = 'true'
  # Uma exceção dentro do `with` deixa o run como FAILED.
  with mlflow.start_run(experiment_id=exp_id) as run:
    mlflow.set_tags(tags)
    mlflow.log_params(params(prep))
    mlflow.log_text(json.dumps(p.features, ensure_ascii=False, indent=2), 'features.json')
    try:
      progresso('avaliando: um prédio fora por vez')
      pred = avaliacao.fora_do_fold(modelo, X, y, grupos)
      met = avaliacao.metricas(y, pred, grupos, p.alvo, aplicacoes.carregar())
      rastreio.registrar_metricas(met)
      registrar_artefatos(prep.df, p.alvo, pred, grupos, 'previsoes_fora_do_fold.csv')
      progresso('treinando o modelo final com todas as linhas')
      final = clone(modelo).fit(X, y)
      progresso('registrando a versão')
      info = mlflow.sklearn.log_model(final, name='modelo', signature=infer_signature(X, final.predict(X)),
                                      serialization_format='cloudpickle', registered_model_name=nome)
    except Exception:
      mlflow.log_text(traceback.format_exc(), 'erro.txt')
      raise
  versao = str(info.registered_model_version)
  return {'run_id': run.info.run_id, 'versao': versao,
          'link_run': rastreio.link_run(exp_id, run.info.run_id), 'link_versao': rastreio.link_versao(nome, versao),
          'metricas': {k: met[k] for k in ('mae', 'rmse', 'r2', 'linhas', 'predios')}}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_treino.py -v`
Expected: 6 testes, OK.

Run: `git status --short mlruns mlflow.db`
Expected: vazio (nada foi escrito no MLflow da raiz).

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/treino.py`, `tests/test_studio_novo_treino.py`.
Mensagem sugerida: `feat(studio-novo): treino com LOGO, run e versão no MLflow do Studio`

---

### Task 5: Fila de jobs

**Files:**
- Create: `src/studio/fila.py`
- Create: `tests/test_studio_novo_fila.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_fila.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import fila  # noqa: E402


class TestFila(unittest.TestCase):
  def test_conclui_com_resultado_e_etapa(self):
    def tarefa(progresso):
      progresso('somando')
      return 1 + 1
    job = fila.enfileirar('teste', 'soma', tarefa)
    self.assertIn(job['status'], ('na fila', 'rodando', 'concluído'))
    final = A.esperar_job(job['id'], 10)
    self.assertEqual((final['status'], final['resultado'], final['etapa']), ('concluído', 2, 'somando'))

  def test_falha_guarda_o_erro(self):
    def tarefa(progresso):
      raise ValueError('quebrou')
    final = A.esperar_job(fila.enfileirar('teste', 'falha', tarefa)['id'], 10)
    self.assertEqual(final['status'], 'falhou')
    self.assertIn('quebrou', final['erro'])

  def test_job_desconhecido(self):
    with self.assertRaises(KeyError):
      fila.job('nao-existe')

  def test_listar_mais_recente_primeiro(self):
    a = fila.enfileirar('teste', 'a', lambda p: None)
    b = fila.enfileirar('teste', 'b', lambda p: None)
    A.esperar_job(b['id'], 10)
    ids = [j['id'] for j in fila.listar()]
    self.assertLess(ids.index(b['id']), ids.index(a['id']))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_fila.py -v`
Expected: ERROR `ImportError: cannot import name 'fila' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/fila.py`:

```python
"""Fila de jobs com um worker só: treinos e reavaliações rodam um por vez, fora da requisição."""

import itertools
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

MAX_LISTADOS = 20

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio-job')
_jobs = {}
_lock = threading.Lock()
_ordem = itertools.count()


def enfileirar(tipo: str, descricao: str, tarefa) -> dict:
  """`tarefa(progresso)` roda no worker; `progresso(texto)` atualiza a etapa mostrada na tela."""
  job = {'id': uuid.uuid4().hex[:12], 'tipo': tipo, 'descricao': descricao, 'status': 'na fila',
         'etapa': None, 'resultado': None, 'erro': None, 'criado': time.time(), '_ordem': next(_ordem)}
  with _lock:
    _jobs[job['id']] = job

  def progresso(texto: str) -> None:
    with _lock:
      job['etapa'] = texto

  def rodar() -> None:
    with _lock:
      job['status'] = 'rodando'
    try:
      resultado = tarefa(progresso)
    except Exception as erro:  # o motivo vai para a tela
      with _lock:
        job.update(status='falhou', erro=f'{type(erro).__name__}: {erro}')
      return
    with _lock:
      job.update(status='concluído', resultado=resultado)

  _executor.submit(rodar)
  return _publico(job)


def _publico(job: dict) -> dict:
  return {k: v for k, v in job.items() if not k.startswith('_')}


def job(job_id: str) -> dict:
  with _lock:
    if job_id not in _jobs:
      raise KeyError(f'job {job_id!r} desconhecido')
    return _publico(_jobs[job_id])


def listar() -> list:
  with _lock:
    recentes = sorted(_jobs.values(), key=lambda j: j['_ordem'], reverse=True)[:MAX_LISTADOS]
    return [_publico(j) for j in recentes]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_fila.py -v`
Expected: 4 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/fila.py`, `tests/test_studio_novo_fila.py`.
Mensagem sugerida: `feat(studio-novo): fila de jobs com um worker`

---

### Task 6: Registro (`@ativo`, promoção, reavaliação)

**Files:**
- Create: `src/studio/registro.py`
- Create: `tests/test_studio_novo_registro.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_registro.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import rastreio, registro, treino  # noqa: E402

ALVO = 'speedtest_down_mbps'


def treinar(datasets=('a.csv',), features=('router_snr', 'router_signal_dbm')):
  pedido = treino.Pedido(alvo=ALVO, datasets=list(datasets), features=list(features), hiper={'n_estimators': 5})
  return treino.executar(treino.preparar(pedido))


class TestRegistro(unittest.TestCase):
  def test_promover_move_o_alias(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      self.assertIsNone(registro.ativo(ALVO))
      self.assertEqual(registro.versoes(ALVO), [])
      treinar()
      treinar()
      self.assertEqual(registro.promover(ALVO, '1')['versao'], '1')
      self.assertEqual(registro.promover(ALVO, '2')['versao'], '2')
      self.assertEqual(registro.ativo(ALVO)['features'], ['router_snr', 'router_signal_dbm'])
      self.assertEqual([v['versao'] for v in registro.versoes(ALVO)], ['2', '1'])
      with self.assertRaises(KeyError):
        registro.promover(ALVO, '9')

  def test_comparar_avisa_vazamento_e_mesma_versao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      treinar(features=('router_snr', 'router_tx_retries'))
      comp = registro.comparar(ALVO, '1')
      self.assertIsNone(comp['ativo'])
      self.assertTrue(any('vazamento' in a for a in comp['avisos']))
      registro.promover(ALVO, '1')
      self.assertTrue(any('já é a @ativo' in a for a in registro.comparar(ALVO, '1')['avisos']))

  def test_reavaliar_cria_run_sem_versao_nova_e_avisa_sobreposicao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['gama-1'], semente=4))
      treinar()
      prep = registro.preparar_reavaliacao(ALVO, '1', ['a.csv', 'b.csv'])
      self.assertEqual(len(prep['avisos']), 1)
      self.assertIn('a.csv', prep['avisos'][0])
      r = registro.executar_reavaliacao(prep)
      run = rastreio.cliente().get_run(r['run_id'])
      self.assertEqual(run.data.tags['tipo'], 'reavaliacao')
      self.assertEqual(run.data.tags['modelo_versao'], 'studio-speedtest_down_mbps/1')
      self.assertIn('mae__gama', run.data.metrics)
      self.assertEqual([v['versao'] for v in registro.versoes(ALVO)], ['1'])

  def test_reavaliar_recusa_feature_ausente(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['gama-1'], semente=4).drop(columns=['router_signal_dbm']))
      treinar()
      with self.assertRaisesRegex(ValueError, 'router_signal_dbm'):
        registro.preparar_reavaliacao(ALVO, '1', ['b.csv'])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_registro.py -v`
Expected: ERROR `ImportError: cannot import name 'registro' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/registro.py`:

```python
"""Versões registradas no MLflow do Studio: @ativo, comparação, promoção e reavaliação."""

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.exceptions import MlflowException

from studio import aplicacoes, avaliacao, catalogo, predios, rastreio, treino


def _versao(cli, nome: str, versao):
  try:
    return cli.get_model_version(nome, str(versao))
  except MlflowException:
    raise KeyError(f'versão {versao} de {nome} não existe') from None


def _lista(texto: str) -> list:
  return [x for x in (texto or '').split(',') if x]


def resumo(cli, nome: str, mv) -> dict:
  run = cli.get_run(mv.run_id)
  m, params, tags = run.data.metrics, run.data.params, run.data.tags
  return {'versao': str(mv.version), 'run_id': mv.run_id, 'modelo': params.get('modelo'),
          'features': _lista(params.get('features')), 'datasets': _lista(params.get('datasets')),
          'mae': m.get('mae'), 'rmse': m.get('rmse'), 'r2': m.get('r2'),
          'predios': int(m['predios']) if 'predios' in m else None,
          'linhas': int(m['linhas']) if 'linhas' in m else None,
          'contem_vazamento': tags.get('contem_vazamento') == 'true',
          'link': rastreio.link_versao(nome, mv.version),
          'link_run': rastreio.link_run(run.info.experiment_id, mv.run_id)}


def ativo(alvo: str):
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  try:
    mv = cli.get_model_version_by_alias(nome, rastreio.ALIAS_ATIVO)
  except MlflowException:
    return None
  return resumo(cli, nome, mv)


def versoes(alvo: str) -> list:
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  try:
    mvs = cli.search_model_versions(f"name='{nome}'")
  except MlflowException:
    return []
  return [resumo(cli, nome, mv) for mv in sorted(mvs, key=lambda v: int(v.version), reverse=True)]


def comparar(alvo: str, versao) -> dict:
  """Candidata ao lado da @ativo, com avisos que não bloqueiam a promoção."""
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  candidata = resumo(cli, nome, _versao(cli, nome, versao))
  atual = ativo(alvo)
  avisos = []
  if candidata['contem_vazamento']:
    avisos.append('o treino desta versão usou colunas com vazamento (contadores da janela do speedtest): '
                  'o erro medido é otimista')
  if atual and atual['versao'] == candidata['versao']:
    avisos.append('esta versão já é a @ativo')
  elif atual and (candidata['predios'] or 0) < (atual['predios'] or 0):
    avisos.append(f"avaliada em {candidata['predios']} prédios; a @ativo foi avaliada em {atual['predios']}")
  return {'candidata': candidata, 'ativo': atual, 'avisos': avisos}


def promover(alvo: str, versao) -> dict:
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  _versao(cli, nome, versao)
  cli.set_registered_model_alias(nome, rastreio.ALIAS_ATIVO, str(versao))
  return ativo(alvo)


def preparar_reavaliacao(alvo: str, versao, ids, itens: list = None) -> dict:
  """Valida antes da fila: versão existe, features presentes, sem sobreposição; aplica as regras da versão."""
  cli, nome = rastreio.cliente(), rastreio.nome_modelo(alvo)
  mv = _versao(cli, nome, versao)
  params = cli.get_run(mv.run_id).data.params
  features = _lista(params.get('features'))
  regras = {k[len('regra__'):]: v == 'True' for k, v in params.items() if k.startswith('regra__')}
  if not ids:
    raise ValueError('escolha pelo menos um dataset')
  itens = catalogo.descobertos() if itens is None else itens
  sobre = catalogo.sobreposicoes(ids, itens)
  if sobre:
    raise ValueError('datasets sobrepostos (as mesmas amostras contariam duas vezes): ' + '; '.join(sobre))
  falta = treino.faltando(ids, features, itens)
  if falta:
    raise ValueError(f'a versão {versao} usa features ausentes nestes datasets: {falta}')
  reg = predios.atual()
  df = treino.carregar(ids, itens, reg)
  df, removidas = avaliacao.aplicar_regras(df, alvo, regras, treino.tetos(df, alvo, reg))
  if df.empty:
    raise ValueError('nenhuma linha sobrou depois das regras da versão')
  de_treino = {fp.split(':', 1)[1] for fp in _lista(params.get('fingerprints')) if ':' in fp}
  escolhidos = catalogo.usaveis_por_id(ids, itens)
  avisos = [f"{d['id']} estava no treino desta versão: a medida é otimista"
            for d in escolhidos if d['fingerprint'] in de_treino]
  return {'alvo': alvo, 'nome': nome, 'versao': str(versao), 'run_treino': mv.run_id, 'features': features,
          'regras': regras, 'ids': list(ids), 'fingerprints': {d['id']: d['fingerprint'] for d in escolhidos},
          'df': df, 'removidas': removidas, 'avisos': avisos}


def executar_reavaliacao(prep: dict, progresso=None) -> dict:
  """Prevê com a versão registrada, sem retreinar, e grava um run tipo=reavaliacao."""
  progresso = progresso or (lambda texto: None)
  cli = rastreio.cliente()
  exp_id = rastreio.experimento_id(cli)
  progresso('carregando o modelo registrado')
  modelo = mlflow.sklearn.load_model(f"models:/{prep['nome']}/{prep['versao']}")
  df, alvo = prep['df'], prep['alvo']
  X = treino.matriz(df, prep['features'])
  y = pd.to_numeric(df[alvo])
  grupos = df[avaliacao.COLUNA_PREDIO]
  progresso('prevendo sem retreinar')
  pred = modelo.predict(X)
  met = avaliacao.metricas(y, pred, grupos, alvo, aplicacoes.carregar())
  with mlflow.start_run(experiment_id=exp_id) as run:
    mlflow.set_tags({'tipo': 'reavaliacao', 'alvo': alvo, 'modelo_versao': f"{prep['nome']}/{prep['versao']}",
                     'run_treino': prep['run_treino']})
    mlflow.log_params({'datasets': ','.join(prep['ids']),
                       'fingerprints': ','.join(f'{k}:{v}' for k, v in sorted(prep['fingerprints'].items())),
                       **{f'regra__{k}': v for k, v in prep['regras'].items()},
                       **{f'removidas__{k}': v for k, v in prep['removidas'].items()}})
    rastreio.registrar_metricas(met)
    treino.registrar_artefatos(df, alvo, pred, grupos, 'previsoes.csv')
    if prep['avisos']:
      mlflow.log_text('\n'.join(prep['avisos']) + '\n', 'avisos.txt')
  return {'run_id': run.info.run_id, 'link_run': rastreio.link_run(exp_id, run.info.run_id),
          'avisos': prep['avisos'], 'metricas': {k: met[k] for k in ('mae', 'rmse', 'r2', 'linhas', 'predios')}}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_registro.py -v`
Expected: 4 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/registro.py`, `tests/test_studio_novo_registro.py`.
Mensagem sugerida: `feat(studio-novo): @ativo, promoção e reavaliação sem retreinar`

---

### Task 7: Processo do MLflow

**Files:**
- Create: `src/studio/mlflow_servidor.py`
- Modify: `src/studio/rastreio.py` (função `disponivel`)
- Create: `tests/test_studio_novo_mlflow_servidor.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_mlflow_servidor.py`:

```python
import os
import socket
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, mlflow_servidor, portas, rastreio  # noqa: E402


class TestServidor(unittest.TestCase):
  def test_comando_usa_o_store_do_studio_e_so_loopback(self):
    cmd = mlflow_servidor.comando(5100)
    self.assertEqual(cmd[cmd.index('--backend-store-uri') + 1],
                     'sqlite:///' + os.path.join(caminhos.REPO, '.studio', 'mlflow.db'))
    self.assertEqual(cmd[cmd.index('--artifacts-destination') + 1], os.path.join(caminhos.REPO, '.studio', 'artefatos'))
    self.assertEqual(cmd[cmd.index('--host') + 1], '127.0.0.1')
    self.assertEqual(cmd[cmd.index('--port') + 1], '5100')

  def test_porta_ocupada_recusa_sem_subir_nada(self):
    with socket.socket() as s:
      s.bind(('127.0.0.1', 0))
      s.listen()
      porta = s.getsockname()[1]
      with mock.patch('subprocess.Popen') as popen:
        with self.assertRaisesRegex(RuntimeError, 'ocupada'):
          mlflow_servidor.iniciar(porta)
        popen.assert_not_called()

  def test_saudavel_falso_sem_servidor(self):
    with socket.socket() as s:
      s.bind(('127.0.0.1', 0))
      porta = s.getsockname()[1]
    self.assertTrue(portas.livre(porta))
    self.assertFalse(mlflow_servidor.saudavel(f'http://127.0.0.1:{porta}', timeout=0.3))

  def test_disponivel_com_sqlite_dispensa_servidor(self):
    with A.mlflow_temporario():
      self.assertTrue(rastreio.disponivel())


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_mlflow_servidor.py -v`
Expected: ERROR `ImportError: cannot import name 'mlflow_servidor' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/mlflow_servidor.py`:

```python
"""Processo filho `mlflow server` do Studio: backend e artefatos em .studio/, só em 127.0.0.1.

Nunca se conecta a um MLflow que já esteja rodando (pode ser o de outra pessoa):
com a porta ocupada, recusa.
"""

import os
import subprocess
import sys
import time
import urllib.request

from studio import caminhos, portas

ESPERA_S = 90

_estado = {'proc': None, 'log': None}


def comando(porta: int) -> list:
  return [sys.executable, '-m', 'mlflow', 'server',
          '--backend-store-uri', 'sqlite:///' + caminhos.MLFLOW_DB,
          '--artifacts-destination', caminhos.ARTEFATOS_DIR,
          '--host', '127.0.0.1', '--port', str(porta)]


def saudavel(url: str = None, timeout: float = 1.0) -> bool:
  try:
    with urllib.request.urlopen((url or caminhos.MLFLOW_URI) + '/health', timeout=timeout) as resposta:
      return resposta.status == 200
  except OSError:
    return False


def iniciar(porta: int = None) -> subprocess.Popen:
  porta = porta or caminhos.MLFLOW_PORTA
  if not portas.livre(porta):
    raise RuntimeError(f'porta {porta} ocupada: o Studio não se conecta a um MLflow que já está rodando')
  os.makedirs(caminhos.ARTEFATOS_DIR, exist_ok=True)
  log = open(os.path.join(caminhos.ESTADO_DIR, 'mlflow.log'), 'ab')
  # cwd em .studio/: qualquer arquivo solto que o servidor crie fica lá, nunca na raiz.
  proc = subprocess.Popen(comando(porta), stdout=log, stderr=subprocess.STDOUT, cwd=caminhos.ESTADO_DIR)
  _estado.update(proc=proc, log=log)
  limite = time.time() + ESPERA_S
  while time.time() < limite:
    if proc.poll() is not None:
      parar()
      raise RuntimeError(f'mlflow server saiu com código {proc.returncode}; veja .studio/mlflow.log')
    if saudavel(f'http://127.0.0.1:{porta}'):
      return proc
    time.sleep(0.5)
  parar()
  raise RuntimeError(f'mlflow server não respondeu em {ESPERA_S} s; veja .studio/mlflow.log')


def parar() -> None:
  proc, log = _estado['proc'], _estado['log']
  if proc is not None and proc.poll() is None:
    proc.terminate()
    try:
      proc.wait(10)
    except subprocess.TimeoutExpired:
      proc.kill()
  if log is not None:
    log.close()
  _estado.update(proc=None, log=None)


def reiniciar() -> subprocess.Popen:
  parar()
  return iniciar(caminhos.MLFLOW_PORTA)
```

No fim de `src/studio/rastreio.py`:

```python


def disponivel() -> bool:
  """sqlite (testes) está sempre disponível; o servidor do Studio, quando responde ao /health."""
  u = uri()
  if u.startswith('sqlite:///'):
    return True
  from studio import mlflow_servidor
  return mlflow_servidor.saudavel(u)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_mlflow_servidor.py tests/test_studio_novo_isolamento.py -v`
Expected: 4 + 3 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/mlflow_servidor.py`, `src/studio/rastreio.py`, `tests/test_studio_novo_mlflow_servidor.py`.
Mensagem sugerida: `feat(studio-novo): processo mlflow server do Studio em .studio/`

---

### Task 8: Rotas de Modelo e `run.py` com MLflow

**Files:**
- Modify: `src/studio/api.py`
- Modify: `src/studio/run.py`
- Create: `tests/test_studio_novo_api_modelo.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_api_modelo.py`:

```python
import os
import sys
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import api  # noqa: E402

LOCAL = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))
ALVO = 'speedtest_down_mbps'


class TestApiModelo(unittest.TestCase):
  def setUp(self):
    api.dados_mudaram()

  def tearDown(self):
    api.dados_mudaram()

  def test_treino_vira_job_versao_e_promocao(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], semente=1))
      api.dados_mudaram()
      self.assertTrue(api.mlflow_status()['ok'])
      corpo = api.PedidoTreino(alvo=ALVO, datasets=['a.csv'], features=['router_snr'], hiper={'n_estimators': 5})
      final = A.esperar_job(api.treinos_iniciar(corpo, LOCAL)['id'])
      self.assertEqual(final['status'], 'concluído', final.get('erro'))
      self.assertEqual(final['resultado']['versao'], '1')
      self.assertEqual(api.modelos_alvo(ALVO)['versoes'][0]['versao'], '1')
      self.assertEqual(api.modelos_promover_comparar(ALVO, '1')['candidata']['versao'], '1')
      api.modelos_promover(ALVO, api.Promocao(versao='1'), LOCAL)
      self.assertEqual(api.modelos_alvo(ALVO)['ativo']['versao'], '1')
      self.assertEqual(api.job(final['id'])['status'], 'concluído')
      api.dados_mudaram()

  def test_treino_com_um_predio_da_422_sem_job(self):
    with A.pastas_temporarias() as p, A.mlflow_temporario():
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      api.dados_mudaram()
      antes = len(api.jobs()['jobs'])
      with self.assertRaises(HTTPException) as ctx:
        api.treinos_iniciar(api.PedidoTreino(alvo=ALVO, datasets=['a.csv'], features=['router_snr']), LOCAL)
      self.assertEqual(ctx.exception.status_code, 422)
      self.assertEqual(len(api.jobs()['jobs']), antes)
      api.dados_mudaram()

  def test_alvo_e_versao_desconhecidos(self):
    with A.pastas_temporarias(), A.mlflow_temporario():
      with self.assertRaises(HTTPException) as ctx:
        api.modelos_alvo('qoe_dw_score')
      self.assertEqual(ctx.exception.status_code, 404)
      with self.assertRaises(HTTPException) as ctx:
        api.modelos_promover(ALVO, api.Promocao(versao='7'), LOCAL)
      self.assertEqual(ctx.exception.status_code, 404)

  def test_padroes_do_formulario(self):
    padroes = api.modelos_padroes()
    self.assertEqual(padroes['modelos']['RandomForest']['n_estimators'], 600)
    self.assertEqual(padroes['regras'], {'descartar_alvo_zero': True, 'teto_wan': False})


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_api_modelo.py -v`
Expected: ERROR `AttributeError: module 'studio.api' has no attribute 'mlflow_status'` (ou `PedidoTreino`).

- [ ] **Step 3: Acrescentar as rotas**

Em `src/studio/api.py`, trocar a linha de import do pacote por:

```python
from mlflow.exceptions import MlflowException

from studio import (avaliacao, caminhos, catalogo, colunas, conjunto, dados, fila, mlflow_servidor, plantas,
                    predios, rastreio, registro, treino, upload)
```

E acrescentar, **antes** da linha `app.mount('/', ...)`:

```python
# ---------------- Modelo (MLflow do Studio) ----------------

def _alvo(alvo: str) -> None:
  if alvo not in rastreio.ALVOS:
    raise HTTPException(404, f'alvo {alvo!r} desconhecido')


def _com_mlflow(funcao, *args):
  """KeyError -> 404, ValueError -> 422, falha do MLflow -> 503, sempre com o motivo."""
  try:
    return funcao(*args)
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  except MlflowException as erro:
    raise HTTPException(503, f'MLflow: {erro.message}')


def _lista(texto: str) -> list:
  return [x.strip() for x in (texto or '').split(',') if x.strip()]


@app.get('/api/mlflow/status')
def mlflow_status():
  return {'ok': rastreio.disponivel(), 'ui': caminhos.MLFLOW_UI}


@app.post('/api/mlflow/reiniciar')
def mlflow_reiniciar(request: Request):
  _so_local(request)
  try:
    mlflow_servidor.reiniciar()
  except RuntimeError as erro:
    raise HTTPException(503, str(erro))
  return {'ok': True}


@app.get('/api/colunas')
def colunas_disponiveis(ds: str = ''):
  ids = _lista(ds) or conjunto.ler()
  try:
    return {'datasets': ids, 'colunas': colunas.disponiveis(ids)}
  except ValueError as erro:
    raise HTTPException(422, str(erro))


@app.get('/api/modelos/padroes')
def modelos_padroes():
  return {'modelos': {nome: padrao for nome, (_, padrao) in treino.MODELOS.items()},
          'regras': dict(avaliacao.REGRAS_PADRAO), 'alvos': list(rastreio.ALVOS)}


@app.get('/api/modelos/{alvo}')
def modelos_alvo(alvo: str):
  _alvo(alvo)
  return {'nome': rastreio.nome_modelo(alvo), 'ativo': _com_mlflow(registro.ativo, alvo),
          'versoes': _com_mlflow(registro.versoes, alvo)}


@app.get('/api/modelos/{alvo}/promover')
def modelos_promover_comparar(alvo: str, versao: str):
  _alvo(alvo)
  return _com_mlflow(registro.comparar, alvo, versao)


class Promocao(BaseModel):
  versao: str


@app.post('/api/modelos/{alvo}/promover')
def modelos_promover(alvo: str, corpo: Promocao, request: Request):
  _so_local(request)
  _alvo(alvo)
  return {'ativo': _com_mlflow(registro.promover, alvo, corpo.versao)}


class PedidoTreino(BaseModel):
  alvo: str
  datasets: list[str]
  features: list[str]
  modelo: str = 'RandomForest'
  hiper: dict = {}
  regras: dict = {}


@app.post('/api/treinos')
def treinos_iniciar(corpo: PedidoTreino, request: Request):
  """Valida na requisição (422 com o motivo); só um pedido válido entra na fila."""
  _so_local(request)
  pedido = treino.Pedido(alvo=corpo.alvo, datasets=corpo.datasets, features=corpo.features,
                         modelo=corpo.modelo, hiper=dict(corpo.hiper),
                         regras={**avaliacao.REGRAS_PADRAO, **corpo.regras})
  prep = _com_mlflow(treino.preparar, pedido)
  if not rastreio.disponivel():
    raise HTTPException(503, 'MLflow indisponível: reinicie pela aba Modelo')
  descricao = f'treino {corpo.modelo} · {corpo.alvo} · {len(corpo.features)} features'
  return fila.enfileirar('treino', descricao, lambda progresso: treino.executar(prep, progresso))


class PedidoReavaliacao(BaseModel):
  versao: str
  datasets: list[str]


@app.post('/api/modelos/{alvo}/reavaliar')
def modelos_reavaliar(alvo: str, corpo: PedidoReavaliacao, request: Request):
  _so_local(request)
  _alvo(alvo)
  prep = _com_mlflow(registro.preparar_reavaliacao, alvo, corpo.versao, corpo.datasets)
  descricao = f'reavaliação v{corpo.versao} · {alvo} · {len(corpo.datasets)} datasets'
  return fila.enfileirar('reavaliacao', descricao, lambda progresso: registro.executar_reavaliacao(prep, progresso))


@app.get('/api/jobs')
def jobs():
  return {'jobs': fila.listar()}


@app.get('/api/jobs/{job_id}')
def job(job_id: str):
  try:
    return fila.job(job_id)
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
```

A rota `/api/modelos/padroes` precisa ficar declarada antes de `/api/modelos/{alvo}`, como acima, ou o FastAPI a trataria como alvo `padroes`.

- [ ] **Step 4: `run.py` sobe o MLflow junto**

Substituir a função `main` de `src/studio/run.py` por:

```python
def main():
  parser = argparse.ArgumentParser(description='QoE Studio (novo)')
  parser.add_argument('--port', type=int, default=8100)
  parser.add_argument('--mlflow-port', type=int, default=5100)
  args = parser.parse_args()

  # Antes de importar o mlflow: sem servidor, falhar rápido em vez de ~2 min de novas tentativas.
  os.environ.setdefault('MLFLOW_HTTP_REQUEST_MAX_RETRIES', '0')
  os.environ.setdefault('MLFLOW_HTTP_REQUEST_TIMEOUT', '120')

  from studio import caminhos, mlflow_servidor, portas
  for porta in (args.port, args.mlflow_port):
    if not portas.livre(porta):
      raise SystemExit(f'porta {porta} ocupada: feche o que está nela ou escolha outra (--port, --mlflow-port)')
  caminhos.MLFLOW_PORTA = args.mlflow_port
  caminhos.MLFLOW_URI = caminhos.MLFLOW_UI = f'http://127.0.0.1:{args.mlflow_port}'
  os.makedirs(caminhos.ESTADO_DIR, exist_ok=True)

  print('Subindo o MLflow do Studio (.studio/mlflow.db)...')
  try:
    mlflow_servidor.iniciar(args.mlflow_port)
  except RuntimeError as erro:
    raise SystemExit(str(erro))
  try:
    import uvicorn
    from studio.api import app
    print(f'QoE Studio  ->  http://127.0.0.1:{args.port}')
    print(f'MLflow      ->  {caminhos.MLFLOW_UI}')
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
  finally:
    mlflow_servidor.parar()
```

E atualizar a docstring do topo para:

```python
"""Sobe o QoE Studio novo e o MLflow do Studio em localhost.

  ./venv/bin/python src/studio/run.py [--port 8100] [--mlflow-port 5100]
"""
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_api_modelo.py tests/test_studio_novo_api.py -v`
Expected: 4 + 4 testes, OK.

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/studio/api.py`, `src/studio/run.py`, `tests/test_studio_novo_api_modelo.py`.
Mensagem sugerida: `feat(studio-novo): rotas de Modelo e MLflow subindo com o Studio`

---

### Task 9: Tela Modelo

**Files:**
- Create: `src/studio/web/modelo.js`
- Modify: `src/studio/web/index.html`
- Modify: `src/studio/web/studio.js`
- Modify: `src/studio/web/styles.css`

- [ ] **Step 1: `index.html`: ícones, aba e área**

Em `src/studio/web/index.html`:

1. Antes de `</defs></svg>`, acrescentar:

```html
  <symbol id="i-external" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></symbol>
  <symbol id="i-play" viewBox="0 0 24 24"><polygon points="6 4 20 12 6 20 6 4"/></symbol>
```

2. Trocar

```html
    <a href="#dados" data-area="dados">Dados</a>
```

por

```html
    <a href="#dados" data-area="dados">Dados</a>
    <a href="#modelo" data-area="modelo">Modelo</a>
```

3. Logo depois do `</section>` da área Dados (antes de `</main>`), acrescentar:

```html
  <section id="area-modelo" class="area hide">
    <div class="area-cab">
      <div><h1>Modelo</h1>
        <p class="sub">Treine, promova e reavalie versões no MLflow do Studio. Comparar runs e ver gráficos: abra no MLflow.</p></div>
      <div class="seg" role="group" aria-label="O que o modelo prevê" id="mAlvos"></div>
    </div>
    <div id="mCorpo"></div>
  </section>
```

4. Trocar

```html
<script src="studio.js?v=1"></script>
```

por

```html
<script src="modelo.js?v=1"></script>
<script src="studio.js?v=2"></script>
```

- [ ] **Step 2: `studio.js`: registrar a área**

Em `src/studio/web/studio.js`, trocar `const AREAS = ['dados'];` por `const AREAS = ['dados', 'modelo'];`.

- [ ] **Step 3: `styles.css`: três regras**

No fim de `src/studio/web/styles.css`:

```css
/* ---------- área Modelo (Studio novo) ---------- */
a.btn { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.lista-colunas { max-height: 320px; overflow: auto; border: 1px solid var(--border); border-radius: 8px; padding: 4px 8px; }
.jobs { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
```

- [ ] **Step 4: Escrever `modelo.js`**

`src/studio/web/modelo.js`:

```js
/* modelo.js — área Modelo: versões no MLflow do Studio por alvo, treino, promoção e
   reavaliação. Listas de runs, comparações e gráficos ficam na UI do MLflow, aberta
   por link. Estado próprio; studio.js chama render(ctx) a cada mudança. */
(function () {
  'use strict';
  const V = window.VENKO;
  const U = V.util;
  const { esc, num, icone } = U;
  const $ = (s) => document.querySelector(s);

  const ATIVOS = ['na fila', 'rodando'];
  const st = { ctx: null, alvo: 'speedtest_down_mbps', status: null, padroes: null, modelos: {}, painel: null,
               form: null, colunas: null, colunasChave: null, filtro: '', jobs: [], poll: null,
               promo: null, reav: null, erro: null, ocupado: false };

  const nomeAlvo = (a) => U.ALVO[a].rotulo;
  const unidade = (a) => U.ALVO[a].unidade;
  const link = (href, texto) => `<a class="btn" href="${esc(href)}" target="_blank" rel="noopener">${icone('i-external')} ${esc(texto)}</a>`;
  const modelos = () => st.modelos[st.alvo] || { nome: 'studio-' + st.alvo, versoes: [], ativo: null };
  const ativo = () => modelos().ativo;
  const listaHtml = (itens) => '<ul>' + itens.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>';

  function alternar(lista, id, ligado) {
    const i = lista.indexOf(id);
    if (ligado && i < 0) lista.push(id);
    if (!ligado && i >= 0) lista.splice(i, 1);
  }

  /* ---------------- carregamento ---------------- */
  function carregarStatus() {
    return U.pedir('api/mlflow/status').then((s) => { st.status = s; })
      .catch((e) => { st.status = { ok: false, erro: e.message }; });
  }

  function carregarModelos(alvo) {
    return U.pedir('api/modelos/' + alvo).then((m) => { st.modelos[alvo] = m; st.erro = null; })
      .catch((e) => { st.erro = e.message; });
  }

  function iniciar() {
    if (st.status) return;
    st.status = { carregando: true };
    Promise.all([carregarStatus(), U.pedir('api/modelos/padroes').then((p) => { st.padroes = p; })])
      .then(() => (st.status.ok ? carregarModelos(st.alvo) : null))
      .catch((e) => { st.erro = e.message; })
      .then(() => { desenhar(); return atualizarJobs(); });
  }

  /* ---------------- jobs ---------------- */
  function agendar() {
    clearTimeout(st.poll);
    if (st.jobs.some((j) => ATIVOS.includes(j.status))) st.poll = setTimeout(atualizarJobs, 2000);
  }

  function atualizarJobs() {
    return U.pedir('api/jobs').then((r) => {
      const antes = new Set(st.jobs.filter((j) => ATIVOS.includes(j.status)).map((j) => j.id));
      st.jobs = r.jobs;
      if (st.jobs.some((j) => antes.has(j.id) && !ATIVOS.includes(j.status))) carregarModelos(st.alvo).then(desenhar);
      agendar();
      desenhar();
    }).catch(agendar);
  }

  /* ---------------- treino ---------------- */
  function abrirTreino() {
    if (!st.padroes) return;
    const modelo = 'RandomForest';
    st.form = { datasets: st.ctx.enabledIds.slice(), features: new Set(), modelo,
                hiper: { ...st.padroes.modelos[modelo] }, regras: { ...st.padroes.regras } };
    st.painel = 'treino';
    st.erro = null;
    carregarColunas();
  }

  function carregarColunas() {
    const chave = st.form.datasets.slice().sort().join(',');
    if (st.colunasChave === chave && st.colunas) { desenhar(); return; }
    st.colunasChave = chave;
    st.colunas = null;
    desenhar();
    if (!st.form.datasets.length) return;
    U.pedir('api/colunas?ds=' + encodeURIComponent(chave))
      .then((r) => { if (st.colunasChave === chave) st.colunas = r.colunas; })
      .catch((e) => { if (st.colunasChave === chave) st.colunas = { erro: e.message }; })
      .finally(desenhar);
  }

  function enviarTreino() {
    const f = st.form;
    const hiper = {};
    Object.entries(f.hiper).forEach(([k, v]) => {
      const n = Number(v);
      hiper[k] = String(v).trim() !== '' && Number.isFinite(n) ? n : v;
    });
    st.ocupado = true; st.erro = null; desenhar();
    U.post('api/treinos', { alvo: st.alvo, datasets: f.datasets, features: [...f.features],
                            modelo: f.modelo, hiper, regras: f.regras })
      .then((job) => { st.jobs = [job].concat(st.jobs); st.painel = null; agendar(); })
      .catch((e) => { st.erro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- promover ---------------- */
  function abrirPromover() {
    st.painel = 'promover';
    st.promo = { versao: '', comp: null };
    st.erro = null;
    desenhar();
  }

  function compararPromo(versao) {
    st.promo = { versao, comp: null };
    desenhar();
    if (!versao) return;
    U.pedir(`api/modelos/${st.alvo}/promover?versao=${encodeURIComponent(versao)}`)
      .then((c) => { if (st.promo && st.promo.versao === versao) st.promo.comp = c; })
      .catch((e) => { st.erro = e.message; })
      .finally(desenhar);
  }

  function confirmarPromo() {
    st.ocupado = true; desenhar();
    U.post(`api/modelos/${st.alvo}/promover`, { versao: st.promo.versao })
      .then(() => { st.painel = null; return carregarModelos(st.alvo); })
      .catch((e) => { st.erro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- reavaliar ---------------- */
  function abrirReavaliar() {
    st.painel = 'reavaliar';
    st.reav = { versao: (ativo() || {}).versao || '', datasets: st.ctx.enabledIds.slice() };
    st.erro = null;
    desenhar();
  }

  function enviarReav() {
    st.ocupado = true; st.erro = null; desenhar();
    U.post(`api/modelos/${st.alvo}/reavaliar`, st.reav)
      .then((job) => { st.jobs = [job].concat(st.jobs); st.painel = null; agendar(); })
      .catch((e) => { st.erro = e.message; })
      .finally(() => { st.ocupado = false; desenhar(); });
  }

  /* ---------------- desenho ---------------- */
  function cartaoAtivo() {
    const a = ativo();
    if (!a) {
      return `<div class="card"><h2>Versão @ativo</h2>
        <p class="gate-msg">Nenhuma versão promovida para ${esc(nomeAlvo(st.alvo))} ainda. Treine e promova uma.</p></div>`;
    }
    return `<div class="card"><h2>Versão @ativo · v${esc(a.versao)}</h2>
      <p class="resumo">MAE <b>${num(a.mae, 2)}</b> ${esc(unidade(st.alvo))} · R² <b>${num(a.r2, 3)}</b> ·
        ${a.predios} prédios · ${a.linhas} linhas · ${esc(a.modelo || '')}</p>
      ${a.contem_vazamento ? U.gate('warning', 'Treinada com vazamento', 'Usou contadores da janela do speedtest: o erro medido é otimista.') : ''}
      <div class="controls">${link(a.link, 'Abrir versão no MLflow')}${link(a.link_run, 'Abrir run')}</div></div>`;
  }

  function linhaDataset(d, marcado, atributo) {
    return `<label class="ds"><input type="checkbox" ${atributo}="${esc(d.id)}" data-k="${atributo}-${esc(d.id)}"${marcado ? ' checked' : ''}>
      <code>${esc(d.id)}</code>${d.origem === 'upload' ? ' <span class="tag">upload</span>' : ''}
      <span class="gate-msg num">${d.rows.toLocaleString('pt-BR')} linhas</span><span></span></label>`;
  }

  function painelTreino() {
    const f = st.form;
    const ds = st.ctx.data.datasets.map((d) => linhaDataset(d, f.datasets.includes(d.id), 'data-fds')).join('');
    let cols;
    if (!f.datasets.length) cols = '<p class="gate-msg">Escolha pelo menos um dataset.</p>';
    else if (!st.colunas) cols = '<p class="gate-msg">Carregando colunas…</p>';
    else if (st.colunas.erro) cols = U.gate('critical', 'Colunas indisponíveis', esc(st.colunas.erro));
    else {
      const filtro = st.filtro.toLowerCase();
      cols = st.colunas.filter((c) => !filtro || c.coluna.toLowerCase().includes(filtro)).map((c) =>
        `<label class="ds"><input type="checkbox" data-fcol="${esc(c.coluna)}" data-k="fcol-${esc(c.coluna)}"${f.features.has(c.coluna) ? ' checked' : ''}>
          <code>${esc(c.coluna)}</code>${c.vazamento ? ' <span class="tag leak">vazamento</span>' : ''}
          <span class="gate-msg num">${U.pct(c.preenchimento)} preenchido</span><span></span></label>`).join('');
    }
    const a = ativo();
    const hiper = Object.entries(f.hiper).map(([k, v]) =>
      `<label>${esc(k)}<input type="text" data-hiper="${esc(k)}" data-k="hiper-${esc(k)}" value="${esc(v)}"></label>`).join('');
    const regras = Object.keys(st.padroes.regras).map((k) =>
      `<label class="ds"><input type="checkbox" data-regra="${esc(k)}" data-k="regra-${esc(k)}"${f.regras[k] ? ' checked' : ''}>
        <code>${esc(k)}</code><span></span><span></span></label>`).join('');
    const pode = !st.ocupado && f.datasets.length && f.features.size;
    return `<div class="card"><h2>Novo treino · ${esc(nomeAlvo(st.alvo))}</h2>
      <h3>Datasets</h3>${ds}
      <h3>Features (${f.features.size})</h3>
      <div class="controls">
        <input type="search" placeholder="filtrar colunas" data-filtro="1" data-k="filtro" value="${esc(st.filtro)}" aria-label="Filtrar colunas">
        ${a && a.features.length ? '<button class="btn" data-acao="copiar-ativo" data-k="copiar-ativo">Copiar features da @ativo</button>' : ''}
        <button class="btn" data-acao="limpar-features" data-k="limpar-features">Limpar</button></div>
      <div class="lista-colunas">${cols}</div>
      <h3>Modelo</h3>
      <div class="controls"><select data-modelo="1" data-k="modelo" aria-label="Modelo">${Object.keys(st.padroes.modelos).map((m) =>
        `<option${m === f.modelo ? ' selected' : ''}>${esc(m)}</option>`).join('')}</select></div>
      <div class="upload-campos">${hiper}</div>
      <h3>Regras</h3>${regras}
      <div class="controls"><button class="btn" data-acao="fechar-painel" data-k="fechar-painel">Cancelar</button>
        <button class="btn-pri" data-acao="enviar-treino" data-k="enviar-treino"${pode ? '' : ' disabled'}>${icone('i-play')} Treinar</button></div></div>`;
  }

  function opcoesVersoes(selecionada) {
    return modelos().versoes.map((v) => `<option value="${esc(v.versao)}"${v.versao === selecionada ? ' selected' : ''}>
      v${esc(v.versao)} · ${esc(v.modelo || '')} · MAE ${num(v.mae, 2)}</option>`).join('');
  }

  function painelPromover() {
    const pr = st.promo;
    const c = pr.comp;
    const celula = (r, k, d) => (!r || r[k] == null ? '–' : num(r[k], d));
    const linha = (rotulo, k, d) => `<tr><th>${rotulo}</th><td class="num">${celula(c.candidata, k, d)}</td>
      <td class="num">${celula(c.ativo, k, d)}</td></tr>`;
    const tabela = c ? `<table><thead><tr><th></th><th>v${esc(c.candidata.versao)}</th>
        <th>@ativo${c.ativo ? ' v' + esc(c.ativo.versao) : ''}</th></tr></thead><tbody>
        ${linha('MAE', 'mae', 2)}${linha('RMSE', 'rmse', 2)}${linha('R²', 'r2', 3)}${linha('Prédios', 'predios', 0)}${linha('Linhas', 'linhas', 0)}
      </tbody></table>${c.avisos.length ? U.gate('warning', 'Avisos', listaHtml(c.avisos)) : ''}` : '';
    return `<div class="card"><h2>Promover para @ativo · ${esc(nomeAlvo(st.alvo))}</h2>
      <div class="controls"><select data-promo="1" data-k="promo" aria-label="Versão">
        <option value="">Escolha uma versão</option>${opcoesVersoes(pr.versao)}</select></div>
      ${tabela}
      <div class="controls"><button class="btn" data-acao="fechar-painel" data-k="fechar-painel">Cancelar</button>
        <button class="btn-pri" data-acao="confirmar-promo" data-k="confirmar-promo"${c && !st.ocupado ? '' : ' disabled'}>Promover</button></div></div>`;
  }

  function painelReavaliar() {
    const r = st.reav;
    const ds = st.ctx.data.datasets.map((d) => linhaDataset(d, r.datasets.includes(d.id), 'data-rds')).join('');
    return `<div class="card"><h2>Reavaliar sem retreinar · ${esc(nomeAlvo(st.alvo))}</h2>
      <p class="gate-msg">Prevê com a versão escolhida nos datasets marcados e registra um run de reavaliação.
        Datasets que estavam no treino da versão deixam a medida otimista: o Studio avisa.</p>
      <div class="controls"><select data-reav="1" data-k="reav" aria-label="Versão">
        <option value="">Escolha uma versão</option>${opcoesVersoes(r.versao)}</select></div>
      ${ds}
      <div class="controls"><button class="btn" data-acao="fechar-painel" data-k="fechar-painel">Cancelar</button>
        <button class="btn-pri" data-acao="enviar-reav" data-k="enviar-reav"${r.versao && r.datasets.length && !st.ocupado ? '' : ' disabled'}>
          ${icone('i-play')} Reavaliar</button></div></div>`;
  }

  function secaoJobs() {
    if (!st.jobs.length) return '';
    return `<div class="card"><h2>Jobs</h2><ul class="jobs">${st.jobs.map((j) => {
      const r = j.resultado || {};
      let extra;
      if (j.status === 'falhou') extra = U.gate('critical', 'Falhou', esc(j.erro || ''));
      else if (j.status === 'concluído') {
        extra = `<div class="controls">${r.versao ? `<span class="tag ok">v${esc(r.versao)}</span>` : ''}
            ${r.metricas ? `<span class="gate-msg">MAE ${num(r.metricas.mae, 2)} · R² ${num(r.metricas.r2, 3)}</span>` : ''}
            ${r.link_run ? link(r.link_run, 'Abrir run') : ''}</div>
          ${(r.avisos || []).length ? U.gate('warning', 'Avisos', listaHtml(r.avisos)) : ''}`;
      } else extra = `<span class="gate-msg">${esc(j.etapa || '')}</span>`;
      return `<li><b>${esc(j.descricao)}</b> <span class="tag">${esc(j.status)}</span>${extra}</li>`;
    }).join('')}</ul></div>`;
  }

  function desenhar() {
    const host = $('#mCorpo');
    if (!st.ctx || !host || $('#area-modelo').classList.contains('hide')) return;
    $('#mAlvos').innerHTML = U.ALVOS.map(([k, r]) =>
      `<button data-alvo="${k}" aria-pressed="${k === st.alvo}">${esc(r)}</button>`).join('');
    if (!st.status || st.status.carregando) {
      U.redesenhar(host, '<p class="gate-msg">Conectando ao MLflow do Studio…</p>');
      return;
    }
    if (!st.status.ok) {
      U.redesenhar(host, U.gate('critical', 'MLflow indisponível',
        'O processo do MLflow do Studio não responde. A aba Dados continua funcionando.',
        `<div class="controls"><button class="btn" data-acao="reiniciar" data-k="reiniciar"${st.ocupado ? ' disabled' : ''}>
          ${icone('i-refresh')} Reiniciar MLflow</button></div>`) + (st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : ''));
      return;
    }
    const temVersoes = modelos().versoes.length > 0;
    const botoes = `<div class="controls">
      <button class="btn-pri" data-acao="novo-treino" data-k="novo-treino">${icone('i-play')} Novo treino</button>
      <button class="btn" data-acao="reavaliar" data-k="reavaliar"${temVersoes ? '' : ' disabled'}>Reavaliar</button>
      <button class="btn" data-acao="promover" data-k="promover"${temVersoes ? '' : ' disabled'}>Promover</button>
      ${link(`${st.status.ui}/#/models/${encodeURIComponent(modelos().nome)}`, 'Abrir no MLflow')}</div>`;
    const painel = st.painel === 'treino' ? painelTreino()
      : st.painel === 'promover' ? painelPromover()
        : st.painel === 'reavaliar' ? painelReavaliar() : '';
    U.redesenhar(host, (st.erro ? U.gate('critical', 'Algo deu errado', esc(st.erro)) : '') +
      cartaoAtivo() + botoes + painel + secaoJobs());
  }

  /* ---------------- eventos ---------------- */
  document.addEventListener('click', (ev) => {
    if ($('#area-modelo').classList.contains('hide')) return;
    const alvo = ev.target.closest('#mAlvos [data-alvo]');
    if (alvo) {
      st.alvo = alvo.dataset.alvo; st.painel = null; st.erro = null;
      desenhar();
      carregarModelos(st.alvo).then(desenhar);
      return;
    }
    const b = ev.target.closest('#mCorpo [data-acao]');
    if (!b || b.disabled) return;
    const acao = b.dataset.acao;
    if (acao === 'novo-treino') abrirTreino();
    if (acao === 'promover') abrirPromover();
    if (acao === 'reavaliar') abrirReavaliar();
    if (acao === 'fechar-painel') { st.painel = null; desenhar(); }
    if (acao === 'enviar-treino') enviarTreino();
    if (acao === 'confirmar-promo') confirmarPromo();
    if (acao === 'enviar-reav') enviarReav();
    if (acao === 'copiar-ativo') { st.form.features = new Set(ativo().features); desenhar(); }
    if (acao === 'limpar-features') { st.form.features = new Set(); desenhar(); }
    if (acao === 'reiniciar') {
      st.ocupado = true; st.erro = null; desenhar();
      U.post('api/mlflow/reiniciar', {})
        .catch((e) => { st.erro = e.message; })
        .then(carregarStatus)
        .then(() => (st.status.ok ? carregarModelos(st.alvo) : null))
        .finally(() => { st.ocupado = false; desenhar(); });
    }
  });

  document.addEventListener('change', (ev) => {
    const t = ev.target;
    if (!t.closest || !t.closest('#mCorpo')) return;
    if (t.dataset.fds) { alternar(st.form.datasets, t.dataset.fds, t.checked); carregarColunas(); }
    else if (t.dataset.fcol) {
      if (t.checked) st.form.features.add(t.dataset.fcol); else st.form.features.delete(t.dataset.fcol);
      desenhar();
    } else if (t.dataset.modelo) {
      st.form.modelo = t.value; st.form.hiper = { ...st.padroes.modelos[t.value] }; desenhar();
    } else if (t.dataset.regra) st.form.regras[t.dataset.regra] = t.checked;
    else if (t.dataset.promo !== undefined) compararPromo(t.value);
    else if (t.dataset.reav !== undefined) { st.reav.versao = t.value; desenhar(); }
    else if (t.dataset.rds) { alternar(st.reav.datasets, t.dataset.rds, t.checked); desenhar(); }
  });

  document.addEventListener('input', (ev) => {
    const t = ev.target;
    if (!t.closest || !t.closest('#mCorpo')) return;
    if (t.dataset.hiper) st.form.hiper[t.dataset.hiper] = t.value;
    if (t.dataset.filtro) { st.filtro = t.value; desenhar(); }
  });

  V.areas = V.areas || {};
  V.areas.modelo = { render(ctx) { st.ctx = ctx; iniciar(); desenhar(); } };
})();
```

- [ ] **Step 5: Conferir as rotas usadas pelo front**

Run: `grep -no "api/[a-z/]*" src/studio/web/modelo.js | sort -u`
Expected: só `api/colunas`, `api/jobs`, `api/mlflow/reiniciar`, `api/mlflow/status`, `api/modelos/` e `api/treinos`. Todas existem em `api.py` (Task 8).

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/studio/web/modelo.js`, `src/studio/web/index.html`, `src/studio/web/studio.js`, `src/studio/web/styles.css`.
Mensagem sugerida: `feat(studio-novo): tela Modelo (treino, promoção, reavaliação, jobs)`

---

### Task 10: Não escrita com o ciclo completo, verificação manual e CHANGELOG

**Files:**
- Modify: `tests/test_studio_novo_isolamento.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Estender o teste de não escrita**

Em `tests/test_studio_novo_isolamento.py`, trocar a linha de import do pacote por:

```python
from studio import caminhos, conjunto, dados, predios, registro, treino, upload  # noqa: E402
```

E acrescentar dentro de `class TestNaoEscreve`:

```python
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
```

- [ ] **Step 2: Rodar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_isolamento.py -v`
Expected: 4 testes, OK.

- [ ] **Step 3: Suíte inteira**

Run: `./venv/bin/python -m unittest discover -s tests -q 2>&1 | tail -4`
Expected: `OK`.

Run: `node --test tests/js/ 2>&1 | grep -E "^# (pass|fail)"`
Expected: `# fail 0`.

Run: `git status --short mlruns mlflow.db data src/ml`
Expected: vazio.

- [ ] **Step 4: Verificação manual no navegador**

Run: `./venv/bin/python src/studio/run.py --port 8200 --mlflow-port 5200`
Expected: `Subindo o MLflow do Studio...`, depois as duas URLs. A primeira subida cria `.studio/mlflow.db` e pode levar uns 10 a 20 s.

Portas 8200/5200, para não colidir com o Studio antigo nem com um MLflow que o Fabiano tenha aberto (5000 é o padrão do MLflow). No navegador (Playwright, se disponível):
1. Abrir `http://127.0.0.1:8200/#modelo`. Aparece "Nenhuma versão promovida" e o botão Novo treino.
2. Novo treino: alvo Download, datasets do conjunto padrão, features `router_snr`, `router_signal_dbm`, `router_noise`, modelo RandomForest com `n_estimators` = 50. Clicar Treinar. O job aparece como "na fila" ou "rodando", depois como "concluído" com v1, MAE e o link "Abrir run".
3. Abrir o link do run. A UI do MLflow (porta 5200) mostra o run no experimento "QoE Studio", com params, métricas por prédio e os artefatos.
4. Promover: escolher v1. A tabela mostra v1 sem @ativo. Promover. O card "Versão @ativo · v1" aparece.
5. Novo treino marcando `router_tx_retries`: a coluna aparece com a tag "vazamento". Ao promover essa versão, o aviso de vazamento aparece.
6. Reavaliar v1 com um dataset de `.studio/uploads/` (se houver) ou com o conjunto atual: o job termina e avisa que os datasets estavam no treino.
7. Parar o servidor com Ctrl+C e conferir que o processo do MLflow também parou: `ss -ltnp | grep 5200` vazio.
8. Subir de novo com o MLflow ocupado (`./venv/bin/python -m http.server 5200 &`, depois `run.py --port 8200 --mlflow-port 5200`): o Studio recusa com "porta 5200 ocupada". Matar o `http.server`.
9. `git status --short mlruns mlflow.db data src/ml` vazio.

- [ ] **Step 5: CHANGELOG**

Acrescentar no topo de `CHANGELOG.md`:

```markdown
# Changelog — Studio novo, parte 2: Modelo com MLflow próprio

**Data:** 2026-10-22

## Mudanças

- `src/studio/run.py` sobe também um `mlflow server` do Studio (backend `.studio/mlflow.db`, artefatos `.studio/artefatos/`, só em 127.0.0.1). Com a porta ocupada, recusa: nunca se conecta a outro MLflow. O `mlflow.db` e o `mlruns/` da raiz, do Fabiano, não são lidos nem escritos (teste automático).
- Área Modelo: por alvo (download, upload, latência, jitter), card da versão `@ativo`, **Novo treino** (datasets, features com marca de vazamento, RandomForest/ExtraTrees/HistGradientBoosting/XGBoost com hiperparâmetros editáveis, regras `descartar_alvo_zero` e `teto_wan`), **Promover** (comparação com a `@ativo` e avisos) e **Reavaliar** (prevê sem retreinar, avisa quando o dataset estava no treino).
- Avaliação própria do Studio: LOGO por prédio, MAE/RMSE/R² globais e por prédio, acurácia balanceada do "atende" por aplicação. Sem relação com a régua de `src/ml/core/avaliacao.py`.
- Cada treino é um run no experimento "QoE Studio" e uma versão nova em `studio-<alvo>`. Listar, comparar e ver gráficos de runs: link "Abrir no MLflow".

---
```

- [ ] **Step 6: Ponto de commit**

Arquivos: `tests/test_studio_novo_isolamento.py`, `CHANGELOG.md`.
Mensagem sugerida: `test(studio-novo): treino, promoção e reavaliação não tocam o MLflow do Fabiano`

# Régua única, carga canônica e concorrência — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Studio, `regression_mlflow.py` e `regression_benchmark.py` passam a medir com uma carga e uma régua únicas no `core` (LOGO por prédio, intervalo por bootstrap de posições, métrica "atende em throughput"), e a `v3-tr069` (v2 + concorrência) é avaliada nessa régua.

**Architecture:** `core/carga.py` absorve a descoberta de datasets e o `preparar` do Studio e acrescenta concorrência, descarte de linhas sem stats de estação e marcação de teto de WAN. `core/avaliacao.py` absorve o `_logo`/`_resumo`/`avaliar` do Studio, devolve previsões fora do fold com chave estável (`_linha`) e calcula MAE log, intervalos, "atende" e o veredito de promoção. `studio/features.py` e `studio/data.py` reexportam os nomes movidos para que `paralelos.py`, `selecao.py`, `api.py` e os testes continuem funcionando.

**Tech Stack:** Python 3.12, pandas, numpy, scikit-learn, MLflow, FastAPI (Studio), JavaScript sem framework (Studio). Testes com `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-05-regua-unica-concorrencia-design.md`

---

## Regras para quem executa

- **Nunca rode `git commit` nem `git push`.** O usuário faz os dois à mão. Onde o plano diz "Checkpoint", pare, mostre `git status --short` e peça ao usuário para revisar e commitar.
- **Não altere nada em `data/`, `src/get-metrics.py`, `src/get-all.py` nem `src/medium_use.py`.**
- Indentação de 2 espaços em Python, como no resto do repositório. Comentários e mensagens em português.
- Rode os comandos a partir da raiz do repositório (`/home/venko/ml/TR069/ml-scripts`). O `python3` do PATH é o do `venv/`.
- Suíte completa: `python3 -m unittest discover -s tests -q`. Antes deste plano: `Ran 278 tests ... OK (skipped=1)`.

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `src/ml/core/aplicacoes.json` | Novo. Limiares por aplicação (saem de `studio.js`) |
| `src/ml/core/aplicacoes.py` | Novo. Carrega e valida o JSON |
| `src/ml/core/sites.py` | `TETOS_WAN` e `teto_wan()` |
| `src/ml/core/carga.py` | Novo. Descoberta, duplicatas, concorrência, descartes, teto, `Conjunto`, `preparar`, `carregar` |
| `src/ml/core/avaliacao.py` | Novo. Régua: previsões fora do fold, métricas, intervalos, atende, promoção |
| `src/ml/core/column_provenance.json` | `n_clients` e `concorrentes_mesmo_radio` como `tr069` |
| `src/ml/core/modelos.json` | Nova versão `v3-tr069` (gravada por `salvar_versao`) |
| `src/ml/studio/data.py` | Importa a descoberta de `carga`; payload ganha `aplicacoes` |
| `src/ml/studio/features.py` | Importa `Conjunto`/`preparar` de `carga` e a régua de `avaliacao` |
| `src/ml/studio/selecao.py` | Usa `avaliacao.modelo_regua()` |
| `src/ml/studio/api.py` | `versao_regua`, `atende_throughput`, `promocao`, colunas calculadas |
| `src/ml/studio/static/studio.js` | `PROFILES` vem do payload |
| `src/ml/studio/static/modelos.js` | Motivo "régua de avaliação mudou" |
| `src/ml/studio/static/assistente.js` | Intervalo do R² e cartão de promoção |
| `src/ml/regression_mlflow.py` | Reescrito sobre `carga` + `avaliacao` |
| `src/ml/regression_benchmark.py` | Carga e folds pela régua |
| `tests/test_aplicacoes.py`, `tests/test_carga.py`, `tests/test_avaliacao.py` | Novos |
| `tests/test_studio_features.py`, `tests/test_selecao.py`, `tests/test_formulas_paralelos.py`, `tests/test_studio_assistente.py` | Pontos de patch movidos para `carga`/`avaliacao`; asserções novas |
| `CHANGELOG.md` | Entrada nova no topo |

---

### Task 1: Limiares de aplicação em JSON

**Files:**
- Create: `src/ml/core/aplicacoes.json`
- Create: `src/ml/core/aplicacoes.py`
- Test: `tests/test_aplicacoes.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_aplicacoes.py`:

```python
import os
import sys
import unittest

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


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_aplicacoes -v`
Expected: `ModuleNotFoundError: No module named 'ml.core.aplicacoes'`

- [ ] **Step 3: Criar o JSON e o módulo**

`src/ml/core/aplicacoes.json` (mesmos valores de `PROFILES` em `src/ml/studio/static/studio.js:15-20`):

```json
{
  "aplicacoes": {
    "Navegação": {"dn": 2, "up": 0.5, "lat": 300, "jit": 100},
    "Chamada de vídeo": {"dn": 3.8, "up": 3.8, "lat": 150, "jit": 30},
    "Streaming 4K": {"dn": 25, "up": 0, "lat": 500, "jit": 100},
    "Jogo em nuvem": {"dn": 15, "up": 1, "lat": 40, "jit": 10}
  }
}
```

`src/ml/core/aplicacoes.py`:

```python
"""Limiares de QoE por aplicação: o que cada uma precisa de download, upload, latência e jitter.

Vive em aplicacoes.json, versionado. O Studio lê pelo payload e a régua usa
download e upload para a métrica "atende em throughput".
"""

import json
import os

APLICACOES_PATH = os.path.join(os.path.dirname(__file__), 'aplicacoes.json')
# dn/up em Mbps (mínimo), lat/jit em ms (máximo). Os nomes curtos são os do studio.js.
CHAVES = ('dn', 'up', 'lat', 'jit')


def validar(dados) -> None:
  if not isinstance(dados, dict) or set(dados) != {'aplicacoes'}:
    raise ValueError("aplicacoes.json precisa ter exatamente a chave 'aplicacoes'")
  apps = dados['aplicacoes']
  if not isinstance(apps, dict) or not apps:
    raise ValueError('aplicacoes.json precisa de pelo menos uma aplicação')
  for nome, limiares in apps.items():
    if not isinstance(limiares, dict) or set(limiares) != set(CHAVES):
      raise ValueError(f'{nome!r}: esperado exatamente as chaves {list(CHAVES)}')
    for chave in CHAVES:
      valor = limiares[chave]
      if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
        raise ValueError(f'{nome!r}.{chave}: precisa ser número não negativo, veio {valor!r}')


def carregar(path: str = APLICACOES_PATH) -> dict:
  with open(path, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar(dados)
  return dados['aplicacoes']
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_aplicacoes -v`
Expected: `Ran 6 tests ... OK`

---

### Task 2: Teto de WAN por prédio

**Files:**
- Modify: `src/ml/core/sites.py` (depois de `BUILDING_ENVIRONMENT`)
- Test: `tests/test_carga.py` (arquivo novo; as próximas tasks acrescentam classes nele)

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_carga.py`:

```python
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core.sites import teto_wan


class TestTetoWan(unittest.TestCase):
  def test_teto_da_residencia(self):
    self.assertEqual(teto_wan('residencia', 'speedtest_down_mbps'), 154.0)
    self.assertEqual(teto_wan('residencia', 'speedtest_up_mbps'), 99.0)

  def test_sem_teto_conhecido(self):
    self.assertIsNone(teto_wan('hotmilk', 'speedtest_down_mbps'))
    self.assertIsNone(teto_wan('residencia', 'latency_ms'))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga -v`
Expected: `ImportError: cannot import name 'teto_wan'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/sites.py`, logo depois do bloco `BUILDING_ENVIRONMENT = {...}`:

```python
# Teto do plano de WAN por local de coleta e por alvo (Mbps): acima disto o
# speedtest mede a internet, não o Wi-Fi. Inferido pelo p99 em 2026-10-05
# (download 154, upload 99,8 na residência). Prédio ausente = sem teto conhecido.
TETOS_WAN = {
  RESIDENCE_BUILDING: {'speedtest_down_mbps': 154.0, 'speedtest_up_mbps': 99.0},
}


def teto_wan(predio: str, alvo: str):
  """Teto de WAN do prédio para o alvo, ou None quando não há teto conhecido."""
  return TETOS_WAN.get(predio, {}).get(alvo)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_carga -v`
Expected: `Ran 2 tests ... OK`

- [ ] **Step 5: Checkpoint.** Peça ao usuário para revisar e commitar (Tasks 1 e 2).

---

### Task 3: Descoberta de datasets vai para `core/carga.py`

**Files:**
- Create: `src/ml/core/carga.py`
- Modify: `src/ml/studio/data.py` (imports no topo, remoção das funções movidas, bloco de duplicatas em `build_payload`)
- Modify: `tests/test_studio_features.py` (patch de `DATA_DIR`/`_descobertos` passa a ser em `carga`)
- Test: `tests/test_carga.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescente em `tests/test_carga.py`, depois dos imports existentes:

```python
from ml.core import carga as C

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']


def alvos(n, inicio=0.0):
  valores = np.arange(n, dtype=float) + inicio + 1
  return pd.DataFrame({'local': ['sala'] * n, **{a: valores for a in ALVOS}})
```

E a classe:

```python
class TestDescoberta(unittest.TestCase):
  def test_ids_padrao_exclui_legacy_duplicata_e_substituido(self):
    b = alvos(4)
    datasets = [
      {'id': 'a-fix.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f1', '_frame': alvos(3, 100)},
      {'id': 'a.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f1', '_frame': alvos(3, 100)},
      {'id': 'b.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f2', '_frame': b},
      {'id': 'parte.csv', 'usable': True, 'generation': 'current', 'fingerprint': 'f3', '_frame': b.iloc[:2]},
      {'id': 'velho.csv', 'usable': True, 'generation': 'legacy', 'fingerprint': 'f4', '_frame': alvos(2, 500)},
      {'id': 'quebrado.csv', 'usable': False, 'error': 'x'},
    ]
    self.assertEqual(C.duplicatas(datasets), {'a.csv': 'a-fix.csv'})
    self.assertEqual(C._superseded(datasets), {'parte.csv': 'b.csv'})
    self.assertEqual(C.ids_padrao(datasets), ['a-fix.csv', 'b.csv'])

  def test_discover_le_zip_e_csv_da_pasta(self):
    with tempfile.TemporaryDirectory() as pasta:
      alvos(2).to_csv(os.path.join(pasta, 'x.csv'), index=False)
      antes = C.DATA_DIR
      C.DATA_DIR = pasta
      try:
        achados = {d['id']: d for d in C.discover()}
      finally:
        C.DATA_DIR = antes
    self.assertEqual(achados['x.csv']['rows'], 2)
    self.assertEqual(achados['x.csv']['generation'], 'legacy')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga -v`
Expected: `ImportError: cannot import name 'carga'`

- [ ] **Step 3: Criar `src/ml/core/carga.py`**

O corpo de `_read_any`, `_generation`, `discover`, `descobertos` e `_superseded` é o de `src/ml/studio/data.py`, sem mudar a lógica. A única diferença é indexar com `list(TARGETS)`, porque aqui `TARGETS` é tupla:

```python
"""Carga canônica dos datasets do QoE: descoberta, duplicatas, concorrência, descartes e teto de WAN.

Só lê: nada aqui grava em data/. Toda correção é regra aplicada em memória, para
que o QoE Studio e os scripts de treino vejam exatamente o mesmo conjunto.
"""

import hashlib
import io
import os
import zipfile

import pandas as pd

TARGETS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')

# A geracao de esquema e o que separa `legacy_` do modelo de colunas atual.
# `combo`/`n_clients` (o eixo de contencao) so existem na geracao atual.
CURRENT_MARKERS = ['combo', 'n_clients', 'station_x', 'house_x0']

DATA_DIR = 'data'

# Casas decimais do fingerprint. As versoes -fix/-distcalc recalculam os alvos
# e diferem da original em ~1e-14: sem arredondar, o dedupe nao as reconhece.
FINGERPRINT_DECIMALS = 6


def _read_any(path: str) -> pd.DataFrame:
  """Le CSV ou o unico CSV dentro de um zip, sem gravar nada em disco."""
  if path.endswith('.zip'):
    with zipfile.ZipFile(path) as archive:
      names = [n for n in archive.namelist() if n.endswith('.csv')]
      if len(names) != 1:
        raise ValueError(f'{path}: esperado exatamente 1 CSV no zip, achei {len(names)}')
      with archive.open(names[0]) as handle:
        return pd.read_csv(io.BytesIO(handle.read()), low_memory=False)
  return pd.read_csv(path, low_memory=False)


def _generation(columns) -> str:
  return 'current' if all(m in columns for m in CURRENT_MARKERS) else 'legacy'


def discover() -> list:
  """Varre data/ e devolve um descritor por dataset utilizavel."""
  found = []
  for name in sorted(os.listdir(DATA_DIR)):
    if not (name.endswith('.csv') or name.endswith('.zip')):
      continue
    # Os -qoe.csv carregam qoe_dw_score, cuja formula se perdeu e cujas duas
    # versoes diferem por ~3200x. Ficam de fora ate serem recalculados.
    if '-qoe' in name or 'filllast' in name:
      continue
    path = os.path.join(DATA_DIR, name)
    try:
      frame = _read_any(path)
    except Exception as error:
      found.append({'id': name, 'path': path, 'error': str(error), 'usable': False})
      continue
    if 'local' not in frame.columns or not all(t in frame.columns for t in TARGETS):
      continue
    alvos = frame[list(TARGETS)].round(FINGERPRINT_DECIMALS)
    digest = hashlib.sha256(pd.util.hash_pandas_object(alvos, index=False).values.tobytes())
    found.append({
      'id': name,
      'path': path,
      'usable': True,
      'rows': int(len(frame)),
      'columns': int(len(frame.columns)),
      'generation': _generation(frame.columns),
      'fingerprint': digest.hexdigest()[:12],
      '_frame': frame,
    })
  return found


_descobertos = None


def descobertos() -> list:
  """discover() uma vez por processo: reler o zip de 52 MB a cada requisicao travaria as views."""
  global _descobertos
  if _descobertos is None:
    _descobertos = discover()
  return _descobertos


def _superseded(datasets: list) -> dict:
  """Marca datasets cujas linhas estao inteiras dentro de outro (0817 dentro de 0827)."""
  verdict = {}
  keyed = {}
  for item in datasets:
    if not item.get('usable'):
      continue
    frame = item['_frame']
    keys = set(map(tuple, frame[list(TARGETS)].round(FINGERPRINT_DECIMALS).astype(str).values))
    keyed[item['id']] = keys
  for a, keys_a in keyed.items():
    for b, keys_b in keyed.items():
      if a == b or not keys_a:
        continue
      if keys_a <= keys_b and len(keys_a) < len(keys_b):
        verdict[a] = b
  return verdict


def duplicatas(datasets: list) -> dict:
  """Fingerprint igual = os mesmos alvos ate a 6a casa: o segundo e duplicata do primeiro.

  Manter os dois ligados duplica o peso de cada amostra sem avisar.
  """
  vistos, duplicata_de = {}, {}
  for item in datasets:
    if not item.get('usable'):
      continue
    primeiro = vistos.setdefault(item['fingerprint'], item['id'])
    if primeiro != item['id']:
      duplicata_de[item['id']] = primeiro
  return duplicata_de


def ids_padrao(datasets: list) -> list:
  """O conjunto canônico: geração atual, nem substituído nem duplicado."""
  substituidos, duplicados = _superseded(datasets), duplicatas(datasets)
  return [d['id'] for d in datasets
          if d.get('usable') and d['generation'] == 'current'
          and d['id'] not in substituidos and d['id'] not in duplicados]
```

- [ ] **Step 4: Fazer `studio/data.py` usar `carga`**

Em `src/ml/studio/data.py`:

1. Troque os imports do topo (`import hashlib`, `import io`, `from collections import Counter`, `import os`, `import zipfile`, `import pandas as pd`, `from ml.core.sites import ...`, `from ml.studio.plans import ...`) por:

```python
from collections import Counter

import pandas as pd

from ml.core import aplicacoes as core_aplicacoes
from ml.core.carga import TARGETS as _TARGETS
from ml.core.carga import _superseded, descobertos, discover, duplicatas
from ml.core.sites import CORPORATE, DOMESTIC
from ml.studio.plans import andar_de, montar_plantas

TARGETS = list(_TARGETS)
```

2. Apague de `data.py`: a linha `TARGETS = [...]`, o comentário e a constante `CURRENT_MARKERS`, `DATA_DIR = 'data'`, o comentário e a constante `FINGERPRINT_DECIMALS`, e as funções `_read_any`, `_generation`, `discover`, a variável `_descobertos`, `descobertos` e `_superseded`. Ficam `BUILDINGS`, `AMBIENTES`, `POSITION_LABELS`, `_canonical_local`, `_building_of` e `build_payload`.

3. Em `build_payload`, troque o bloco que monta `seen_fingerprints`/`duplicate_of`:

```python
  # Fingerprint igual = os mesmos alvos ate a 6a casa. Manter os dois ligados
  # duplica o peso de cada amostra sem avisar.
  seen_fingerprints = {}
  duplicate_of = {}
  for item in datasets:
    if not item.get('usable'):
      continue
    first = seen_fingerprints.setdefault(item['fingerprint'], item['id'])
    if first != item['id']:
      duplicate_of[item['id']] = first
```

por:

```python
  duplicate_of = duplicatas(datasets)
```

4. No `return` de `build_payload`, acrescente a chave `'aplicacoes': core_aplicacoes.carregar(),` depois de `'ambientes': AMBIENTES,`.

- [ ] **Step 5: Mover os pontos de patch dos testes do Studio**

Em `tests/test_studio_features.py`:

- Acrescente `from ml.core import carga as C` junto dos outros imports de `ml.core`.
- Em `test_versoes_com_ruido_de_float_sao_duplicatas`: troque `antes = SD.DATA_DIR` / `SD.DATA_DIR = pasta` / `achados = {d['id']: d for d in SD.discover()}` / `SD.DATA_DIR = antes` por `antes = C.DATA_DIR` / `C.DATA_DIR = pasta` / `achados = {d['id']: d for d in C.discover()}` / `C.DATA_DIR = antes`.
- Em `test_payload_traz_router_z_e_andar_por_linha` e `test_envelope_e_o_mais_frequente_e_nao_o_da_primeira_linha`, troque os três trechos de patch:

```python
      antes = (SD.DATA_DIR, SP.PLANTA_DIR)
      SD.DATA_DIR, SP.PLANTA_DIR, SD._descobertos = dados, planta, None
      try:
        payload = SD.build_payload()
      finally:
        (SD.DATA_DIR, SP.PLANTA_DIR), SD._descobertos = antes, None
```

por:

```python
      antes = (C.DATA_DIR, SP.PLANTA_DIR)
      C.DATA_DIR, SP.PLANTA_DIR, C._descobertos = dados, planta, None
      try:
        payload = SD.build_payload()
      finally:
        (C.DATA_DIR, SP.PLANTA_DIR), C._descobertos = antes, None
```

- Em `test_payload_traz_router_z_e_andar_por_linha`, acrescente no fim:

```python
    self.assertEqual(payload['aplicacoes']['Jogo em nuvem']['lat'], 40)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python3 -m unittest tests.test_carga tests.test_studio_features -v 2>&1 | tail -5`
Expected: `OK`

Run: `grep -rn "SD\.DATA_DIR\|SD\._descobertos\|SD\.discover" tests src`
Expected: nenhuma linha.

Run: `python3 -c "import sys; sys.path.insert(0,'src'); from ml.core import carga as C; print(C.ids_padrao(C.descobertos()))"`
Expected: `['20260827-metrics.zip', '20260917-metrics-fix.zip', '20260921-metrics-distcalc.zip', '20260925-metrics.zip', '20260928-metrics.zip']`

---

### Task 4: Concorrência no mesmo rádio

**Files:**
- Modify: `src/ml/core/carga.py`
- Test: `tests/test_carga.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_carga.py`:

```python
T0 = pd.Timestamp('2026-09-17T19:00:00Z')


def simultaneos(linhas):
  """linhas: (ds, run_id, combo, n_clients, bssid, segundos depois de T0)."""
  return pd.DataFrame([{'_ds': ds, 'session_id': 1, 'run_id': run, 'combo': combo, 'n_clients': n,
                        'bssid': bssid, '_time': (T0 + pd.Timedelta(seconds=s)).isoformat()}
                       for ds, run, combo, n, bssid, s in linhas])


class TestConcorrencia(unittest.TestCase):
  def test_dois_bssid_no_mesmo_grupo_contam_separado(self):
    df = simultaneos([('a', 1, 'ABC', 3, 'x', 0), ('a', 1, 'ABC', 3, 'x', 5), ('a', 1, 'ABC', 3, 'y', 9)])
    self.assertEqual(C.concorrentes_mesmo_radio(df).tolist(), [2.0, 2.0, 1.0])

  def test_grupo_incompleto_vira_nan(self):
    df = simultaneos([('a', 2, 'AB', 2, 'x', 0)])
    self.assertTrue(C.concorrentes_mesmo_radio(df).isna().all())

  def test_grupo_maior_que_n_clients_vira_nan(self):
    df = simultaneos([('a', 3, 'A', 1, 'x', 0), ('a', 3, 'A', 1, 'x', 5)])
    self.assertTrue(C.concorrentes_mesmo_radio(df).isna().all())

  def test_run_id_repetido_depois_da_janela_e_outro_grupo(self):
    df = simultaneos([('a', 4, 'C', 1, 'x', 0), ('a', 4, 'C', 1, 'x', 600)])
    self.assertEqual(C.concorrentes_mesmo_radio(df).tolist(), [1.0, 1.0])

  def test_sem_bssid_vira_nan_so_na_linha(self):
    df = simultaneos([('a', 5, 'AB', 2, 'x', 0), ('a', 5, 'AB', 2, None, 4)])
    r = C.concorrentes_mesmo_radio(df)
    self.assertEqual(r.iloc[0], 1.0)
    self.assertTrue(np.isnan(r.iloc[1]))

  def test_datasets_diferentes_nao_se_misturam(self):
    df = simultaneos([('a', 6, 'A', 1, 'x', 0), ('b', 6, 'A', 1, 'x', 1)])
    self.assertEqual(C.concorrentes_mesmo_radio(df).tolist(), [1.0, 1.0])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga.TestConcorrencia -v`
Expected: `AttributeError: module 'ml.core.carga' has no attribute 'concorrentes_mesmo_radio'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/carga.py`, acrescente `import numpy as np` aos imports e, ao fim do arquivo:

```python
# Testes simultâneos: mesma rodada (`run_id`) da mesma sessão e do mesmo `combo`.
# `run_id` se repete mais tarde na mesma sessão (hotmilk), então o grupo também é
# cortado no tempo: linhas a mais de JANELA_SIMULTANEO_S da primeira abrem outro.
JANELA_SIMULTANEO_S = 60
CHAVE_SIMULTANEO = ('_ds', 'session_id', 'run_id', 'combo')
COLUNAS_CONCORRENCIA = CHAVE_SIMULTANEO + ('_time', 'n_clients', 'bssid')
# Colunas que a carga sempre produz quando os insumos existem: entram em
# `colunas_conhecidas` para poderem ser classificadas e usadas em versões.
COLUNAS_CALCULADAS = ('concorrentes_mesmo_radio',)


def _blocos_no_tempo(tempos: pd.Series) -> list:
  """Corta um grupo em blocos de até JANELA_SIMULTANEO_S a partir da primeira linha de cada bloco."""
  blocos, inicio, atual = [], None, []
  for indice, instante in tempos.sort_values().items():
    if inicio is None or (instante - inicio).total_seconds() > JANELA_SIMULTANEO_S:
      if atual:
        blocos.append(atual)
      inicio, atual = instante, []
    atual.append(indice)
  if atual:
    blocos.append(atual)
  return blocos


def concorrentes_mesmo_radio(df: pd.DataFrame) -> pd.Series:
  """Clientes em teste simultâneo no mesmo `bssid` (a própria linha incluída).

  Mesmo `bssid` = mesmo rádio do mesmo roteador: é onde há disputa de ar. NaN quando
  o tamanho do grupo difere de `n_clients` (faltou a linha de um cliente, ou duas
  rodadas caíram na mesma janela), ou quando falta `bssid` na linha.
  """
  saida = pd.Series(np.nan, index=df.index, dtype=float)
  tempo = pd.to_datetime(df['_time'], utc=True, errors='coerce')
  chave = list(CHAVE_SIMULTANEO)
  validas = df[chave].notna().all(axis=1) & tempo.notna() & df['n_clients'].notna()
  for indices in df[validas].groupby(chave, sort=False).groups.values():
    for bloco in _blocos_no_tempo(tempo.loc[indices]):
      sub = df.loc[bloco]
      if len(sub) != int(sub['n_clients'].iloc[0]):
        continue
      contagem = sub['bssid'].map(sub['bssid'].value_counts())
      saida.loc[bloco] = contagem.where(sub['bssid'].notna()).astype(float)
  return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_carga -v 2>&1 | tail -3`
Expected: `OK`

---

### Task 5: Descarte sem stats de estação e marca de teto de WAN

**Files:**
- Modify: `src/ml/core/carga.py`
- Test: `tests/test_carga.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_carga.py`:

```python
class TestSemEnlace(unittest.TestCase):
  def test_linha_sem_os_quatro_campos_sai_e_com_um_fica(self):
    df = pd.DataFrame({'router_tx_rate_mbps': [np.nan, np.nan], 'router_rx_rate_mbps': [np.nan, np.nan],
                       'router_snr': [np.nan, 30.0], 'router_signal_dbm': [np.nan, np.nan]})
    saida, n = C.descartar_sem_enlace(df)
    self.assertEqual(n, 1)
    self.assertEqual(saida['router_snr'].tolist(), [30.0])

  def test_so_as_colunas_presentes_contam(self):
    df = pd.DataFrame({'router_snr': [np.nan, 20.0]})
    saida, n = C.descartar_sem_enlace(df)
    self.assertEqual((n, len(saida)), (1, 1))

  def test_sem_nenhuma_coluna_de_enlace_nao_descarta(self):
    df = pd.DataFrame({'outra': [1.0, 2.0]})
    saida, n = C.descartar_sem_enlace(df)
    self.assertEqual((n, len(saida)), (0, 2))


class TestLimitadoWan(unittest.TestCase):
  def setUp(self):
    self.df = pd.DataFrame({
      '_site': ['residencia'] * 4 + ['hotmilk'],
      'speedtest_down_mbps': [150.0, 150.0, 100.0, 150.0, 600.0],
      'latency_ms': [5.0] * 5,
      'router_expected_throughput_mbps': [300.0, 100.0, 300.0, np.nan, 900.0],
    })

  def test_so_marca_com_as_duas_condicoes(self):
    # 1: no teto e Wi-Fi acima dele. 2: Wi-Fi abaixo do teto. 3: abaixo de 85% do teto.
    # 4: sem expected_throughput. 5: prédio sem teto.
    self.assertEqual(C.marcar_limitado_wan(self.df, 'speedtest_down_mbps').tolist(),
                     [True, False, False, False, False])

  def test_latencia_nunca_marca(self):
    self.assertFalse(C.marcar_limitado_wan(self.df, 'latency_ms').any())

  def test_sem_expected_throughput_nao_marca(self):
    df = self.df.drop(columns=['router_expected_throughput_mbps'])
    self.assertFalse(C.marcar_limitado_wan(df, 'speedtest_down_mbps').any())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga.TestSemEnlace tests.test_carga.TestLimitadoWan -v`
Expected: `AttributeError: ... 'descartar_sem_enlace'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/carga.py`, acrescente `from ml.core.sites import teto_wan` aos imports e, ao fim:

```python
# Campos de enlace do TR-069. Sem nenhum deles a linha não tem o que o modelo lê
# em produção (AX3000 da casa-marcelo e o 20260925 não trazem stats de estação).
ENLACE = ('router_tx_rate_mbps', 'router_rx_rate_mbps', 'router_snr', 'router_signal_dbm')
# Fração do teto a partir da qual o speedtest pode estar medindo a WAN.
LIMIAR_TETO = 0.85


def descartar_sem_enlace(df: pd.DataFrame):
  """Remove linhas em que todos os campos de ENLACE presentes estão vazios.

  Se nenhum deles existe no conjunto, a regra não se aplica. Devolve (df, quantas saíram).
  """
  presentes = [c for c in ENLACE if c in df.columns]
  if not presentes:
    return df, 0
  vazias = df[presentes].isna().all(axis=1)
  return df[~vazias].reset_index(drop=True), int(vazias.sum())


def marcar_limitado_wan(df: pd.DataFrame, alvo: str) -> pd.Series:
  """Verdadeiro quando o alvo está no teto de WAN do prédio e o Wi-Fi podia entregar mais.

  Condições: o prédio tem teto para o alvo, alvo >= LIMIAR_TETO * teto e
  router_expected_throughput_mbps > teto. Latência e jitter nunca marcam.
  """
  marca = pd.Series(False, index=df.index)
  if 'router_expected_throughput_mbps' not in df.columns:
    return marca
  tetos = df['_site'].map(lambda predio: teto_wan(predio, alvo)).astype(float)
  esperado = pd.to_numeric(df['router_expected_throughput_mbps'], errors='coerce')
  y = pd.to_numeric(df[alvo], errors='coerce')
  return (tetos.notna() & (y >= LIMIAR_TETO * tetos) & (esperado > tetos)).fillna(False).astype(bool)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_carga -v 2>&1 | tail -3`
Expected: `OK`

- [ ] **Step 5: Checkpoint.** Peça ao usuário para revisar e commitar (Tasks 3 a 5).

---

### Task 6: `Conjunto` e `preparar` vão para `carga`, com as regras novas

**Files:**
- Modify: `src/ml/core/carga.py`
- Modify: `src/ml/studio/features.py:6-118` (imports, `TARGETS`, `_INTERNAS`, `Conjunto`, `preparar`)
- Test: `tests/test_carga.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_carga.py`, acrescente `from ml.studio import features as SF` aos imports e:

```python
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {a: {'classe': 'alvo'} for a in ALVOS}}


def rodada(n_por_local=4):
  """Uma linha por teste, todos individuais (combo de 1), em 3 prédios."""
  locais = ['sala', 'cwpb-1', 'hotmilk-copa']
  linhas = []
  for i, local in enumerate(np.repeat(locais, n_por_local)):
    linhas.append({'local': local, 'session_id': 1, 'run_id': i, 'combo': 'A', 'n_clients': 1,
                   'bssid': f'b{i}', '_time': (T0 + pd.Timedelta(minutes=i)).isoformat(),
                   'speedtest_down_mbps': 50.0 + i, 'speedtest_up_mbps': 20.0 + i,
                   'latency_ms': 10.0, 'jitter_ms': 1.0, 'router_snr': 30.0,
                   'router_expected_throughput_mbps': 100.0})
  return pd.DataFrame(linhas)


class TestPreparar(unittest.TestCase):
  def test_studio_usa_o_mesmo_preparar(self):
    self.assertIs(SF.preparar, C.preparar)
    self.assertIs(SF.Conjunto, C.Conjunto)

  def test_concorrencia_e_calculada_antes_de_descartar_alvo_zero(self):
    f = rodada()
    f.loc[1, ['run_id', 'combo', 'n_clients', 'bssid', '_time']] = [0, 'AB', 2, 'b0', f.loc[0, '_time']]
    f.loc[0, ['combo', 'n_clients']] = ['AB', 2]
    f.loc[1, 'speedtest_down_mbps'] = 0.0
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(conj.df.loc[conj.df['_linha'] == 'a.csv:0', 'concorrentes_mesmo_radio'].tolist(), [2.0])

  def test_sem_colunas_de_concorrencia_avisa_e_omite(self):
    f = rodada().drop(columns=['bssid'])
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertNotIn('concorrentes_mesmo_radio', conj.df.columns)
    self.assertTrue(any('concorrentes_mesmo_radio omitida' in a for a in conj.avisos))

  def test_descarta_sem_enlace_e_avisa(self):
    f = rodada()
    f.loc[0, 'router_snr'] = np.nan
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(len(conj.df), len(f) - 1)
    self.assertTrue(any('1 linhas sem stats de estação' in a for a in conj.avisos))

  def test_marca_limitado_wan_e_avisa(self):
    f = rodada()
    f.loc[0, ['speedtest_down_mbps', 'router_expected_throughput_mbps']] = [150.0, 300.0]
    conj = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(conj.df.loc[conj.df['_limitado_wan'], '_linha'].tolist(), ['a.csv:0'])
    self.assertTrue(any('1 linhas no teto de WAN' in a for a in conj.avisos))

  def test_linha_estavel_entre_alvos(self):
    f = rodada()
    f.loc[2, 'speedtest_down_mbps'] = np.nan
    dn = C.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    up = C.preparar({'a.csv': f}, 'speedtest_up_mbps', TABELA)
    self.assertNotIn('a.csv:2', dn.df['_linha'].tolist())
    self.assertIn('a.csv:2', up.df['_linha'].tolist())
    self.assertEqual(set(dn.df['_linha']) - set(up.df['_linha']), set())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga.TestPreparar -v`
Expected: `AttributeError: module 'ml.core.carga' has no attribute 'preparar'`

- [ ] **Step 3: Mover `Conjunto` e `preparar` para `carga`**

Em `src/ml/core/carga.py`, acrescente aos imports:

```python
from dataclasses import dataclass, field

from ml.core import features as F
from ml.core.data import descartar_testes_falhos
from ml.core.sites import BUILDING_ENVIRONMENT, ENVIRONMENTS, resolve_site_id, teto_wan
```

(a linha `from ml.core.sites import teto_wan` da Task 5 é substituída por esta).

Ao fim do arquivo:

```python
# `_site` é o grupo dos folds: o local de coleta (prédio). Deixar só um cômodo
# de fora mantinha os outros cômodos do mesmo prédio no treino — mesmo roteador,
# mesmo ambiente, mesmo dia — e inflava o R² (ver CHANGELOG).
# `_pos` é o cômodo; `_amb` é doméstico/corporativo; `_linha` é a chave estável
# da linha ('<dataset>:<linha no arquivo>'), igual para todos os alvos;
# `_limitado_wan` marca o alvo no teto do plano de internet.
_INTERNAS = ('_ds', '_site', '_pos', '_amb', '_limitado_wan', '_linha')


@dataclass
class Conjunto:
  df: pd.DataFrame
  alvo: str
  datasets: list
  classes: dict
  tabela: dict
  avisos: list = field(default_factory=list)
  catalogo: tuple = F.CATALOGO


def preparar(frames: dict, alvo: str, tabela: dict, ambiente: str = None, catalogo=None) -> Conjunto:
  """Junta os frames, calcula a concorrência, aplica os descartes e marca o teto de WAN.

  `ambiente` ('domestico' ou 'corporativo') restringe o conjunto a esse tipo de
  local de coleta; None mantém todos. `catalogo` é o de derivadas (padrão: o curado
  mais as desenhadas no Studio, F.catalogo_completo()).
  """
  catalogo = F.catalogo_completo() if catalogo is None else tuple(catalogo)
  if alvo not in TARGETS:
    raise ValueError(f'alvo {alvo!r} desconhecido; esperado um de {list(TARGETS)}')
  if ambiente is not None and ambiente not in ENVIRONMENTS:
    raise ValueError(f'ambiente {ambiente!r} desconhecido; esperado um de {list(ENVIRONMENTS)}')
  if not frames:
    raise ValueError('nenhum dataset não-legacy ativo')
  avisos = []
  df = pd.concat([f.assign(_ds=ds, _linha=[f'{ds}:{i}' for i in range(len(f))])
                  for ds, f in frames.items()], ignore_index=True)
  if alvo not in df.columns:
    raise ValueError(f'o alvo {alvo!r} não existe nos datasets ativos')

  # Antes de qualquer descarte: um teste que falhou também disputava o ar.
  faltam = [c for c in COLUNAS_CONCORRENCIA if c not in df.columns]
  if faltam:
    avisos.append(f'concorrentes_mesmo_radio omitida: faltam {faltam}')
  else:
    df['concorrentes_mesmo_radio'] = concorrentes_mesmo_radio(df)

  sem_alvo = int(df[alvo].isna().sum())
  if sem_alvo:
    avisos.append(f'{sem_alvo} linhas sem {alvo} descartadas')
  df = df[df[alvo].notna()]
  df, falhos = descartar_testes_falhos(df, alvo)
  if falhos:
    avisos.append(f'{falhos} testes que falharam ({alvo} = 0) descartados')

  posicoes, predios = {}, {}
  desconhecidos = []
  for valor in df['local'].dropna().unique():
    try:
      posicoes[valor] = resolve_site_id(pd.Series([valor])).iloc[0]
      predios[valor] = resolve_site_id(pd.Series([valor]), level='building').iloc[0]
    except ValueError:
      desconhecidos.append(str(valor))
  fora = int((~df['local'].isin(list(posicoes))).sum())
  if fora:
    avisos.append(f'{fora} linhas com local desconhecido em core/sites.py descartadas: '
                  f'{sorted(desconhecidos)}')
  df = df[df['local'].isin(list(posicoes))].reset_index(drop=True)
  df = df.assign(_site=df['local'].map(predios), _pos=df['local'].map(posicoes))
  df['_amb'] = df['_site'].map(BUILDING_ENVIRONMENT)
  if ambiente is not None:
    df = df[df['_amb'] == ambiente].reset_index(drop=True)
    if df.empty:
      raise ValueError(f'nenhuma linha de ambiente {ambiente!r} nos datasets ativos')

  df, sem_enlace = descartar_sem_enlace(df)
  if sem_enlace:
    avisos.append(f'{sem_enlace} linhas sem stats de estação (taxa PHY, SNR e sinal vazios) descartadas')
  df['_limitado_wan'] = marcar_limitado_wan(df, alvo)
  limitadas = int(df['_limitado_wan'].sum())
  if limitadas:
    avisos.append(f'{limitadas} linhas no teto de WAN: fora do treino, previsão cortada no teto')
  if 'concorrentes_mesmo_radio' in df.columns:
    sem_grupo = int(df['concorrentes_mesmo_radio'].isna().sum())
    if sem_grupo:
      avisos.append(f'{sem_grupo} linhas sem concorrentes_mesmo_radio '
                    '(grupo simultâneo incompleto ou sem bssid)')

  df, avisos_derivadas = F.aplicar_derivadas(df, catalogo)
  avisos += avisos_derivadas

  derivadas = {d.nome: d for d in catalogo}
  classes = {}
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    if coluna in derivadas:
      classes[coluna] = F.classificar_derivada(derivadas[coluna], tabela)
    else:
      classes[coluna] = F.classificar(coluna, tabela)
  return Conjunto(df, alvo, sorted(frames), classes, tabela, avisos, catalogo)
```

- [ ] **Step 4: `studio/features.py` reexporta de `carga`**

Em `src/ml/studio/features.py`:

1. Apague a constante `TARGETS = (...)`, o comentário e a tupla `_INTERNAS = (...)`, o `@dataclass class Conjunto` e a função `preparar` inteira.
2. Troque `from dataclasses import dataclass, field` por nada (remova a linha), troque `from ml.core.data import descartar_testes_falhos` e `from ml.core.sites import BUILDING_ENVIRONMENT, ENVIRONMENTS, resolve_site_id` por:

```python
from ml.core.carga import _INTERNAS, TARGETS, Conjunto, preparar
```

O restante de `features.py` (inventário, ajuste, comparar…) continua usando `Conjunto`, `preparar`, `TARGETS` e `_INTERNAS` pelos mesmos nomes.

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m unittest tests.test_carga tests.test_studio_features tests.test_studio_assistente tests.test_selecao tests.test_formulas_paralelos 2>&1 | tail -3`
Expected: `OK`

---

### Task 7: `carregar` para os scripts

**Files:**
- Modify: `src/ml/core/carga.py`
- Test: `tests/test_carga.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_carga.py`:

```python
class TestCarregar(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.TemporaryDirectory()
    atual = rodada().assign(station_x=1.0, house_x0=1.0)
    atual.to_csv(os.path.join(self.pasta.name, 'novo.csv'), index=False)
    alvos(3).to_csv(os.path.join(self.pasta.name, 'velho.csv'), index=False)
    self.antes = (C.DATA_DIR, C._descobertos)
    C.DATA_DIR, C._descobertos = self.pasta.name, None

  def tearDown(self):
    C.DATA_DIR, C._descobertos = self.antes
    self.pasta.cleanup()

  def test_padrao_e_o_conjunto_canonico(self):
    conj = C.carregar('speedtest_down_mbps', tabela=TABELA)
    self.assertEqual(conj.datasets, ['novo.csv'])
    self.assertEqual(len(conj.df), 12)

  def test_id_desconhecido_levanta(self):
    with self.assertRaisesRegex(ValueError, 'nao_existe.csv'):
      C.carregar('speedtest_down_mbps', ids=['nao_existe.csv'], tabela=TABELA)

  def test_legacy_nao_entra_na_regua(self):
    with self.assertRaisesRegex(ValueError, 'velho.csv'):
      C.carregar('speedtest_down_mbps', ids=['velho.csv'], tabela=TABELA)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga.TestCarregar -v`
Expected: `AttributeError: ... 'carregar'`

- [ ] **Step 3: Implementar**

Ao fim de `src/ml/core/carga.py`:

```python
def carregar(alvo: str, ids=None, tabela: dict = None, ambiente: str = None, catalogo=None) -> Conjunto:
  """Conjunto canônico para os scripts de treino: os mesmos datasets e regras do Studio.

  `ids` são nomes de arquivo em DATA_DIR; vazio = ids_padrao(). `tabela` padrão é
  column_provenance.json.
  """
  datasets = descobertos()
  por_id = {d['id']: d for d in datasets if d.get('usable')}
  ids = list(ids) if ids else ids_padrao(datasets)
  desconhecidos = [i for i in ids if i not in por_id]
  if desconhecidos:
    raise ValueError(f'datasets desconhecidos em {DATA_DIR}: {desconhecidos}')
  legacy = [i for i in ids if por_id[i]['generation'] != 'current']
  if legacy:
    raise ValueError(f'datasets da geração antiga não entram na régua: {legacy}')
  tabela = F.carregar_tabela() if tabela is None else tabela
  return preparar({i: por_id[i]['_frame'] for i in ids}, alvo, tabela, ambiente, catalogo)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_carga -v 2>&1 | tail -3`
Expected: `OK`

---

### Task 8: Classificar `n_clients` e `concorrentes_mesmo_radio`

**Files:**
- Modify: `src/ml/core/column_provenance.json` (via `gravar_classificacao`)
- Modify: `src/ml/studio/api.py` (`_colunas_conhecidas`)
- Test: `tests/test_carga.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_carga.py`, acrescente `from ml.core import features as F` aos imports e:

```python
class TestClassificacao(unittest.TestCase):
  def test_concorrencia_e_tr069_no_repositorio(self):
    tabela = F.carregar_tabela()
    for coluna in ('n_clients', 'concorrentes_mesmo_radio'):
      c = F.classificar(coluna, tabela)
      self.assertEqual((c.classe, c.vazamento), ('tr069', False), coluna)
      self.assertIn('depende do coletor', c.parametro)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_carga.TestClassificacao -v`
Expected: `FAIL` (`n_clients` vem como `identificador`)

- [ ] **Step 3: Gravar a classificação pela função do core** (mantém o formato do JSON)

Run:

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, 'src')
from ml.core import features as F
conhecidas = {'n_clients', 'concorrentes_mesmo_radio'}
F.gravar_classificacao('n_clients', 'tr069', False,
  'substituto de estações ativas no rádio; em produção depende do coletor', conhecidas)
F.gravar_classificacao('concorrentes_mesmo_radio', 'tr069', False,
  'clientes em teste simultâneo no mesmo bssid; em produção depende do coletor', conhecidas)
EOF
git diff --stat src/ml/core/column_provenance.json
```

Expected: `1 file changed`, com `n_clients` alterado e `concorrentes_mesmo_radio` novo.

- [ ] **Step 4: Colunas calculadas entram em `_colunas_conhecidas`**

Em `src/ml/studio/api.py`, acrescente `from ml.core import carga as core_carga` aos imports de `ml.core` e, em `_colunas_conhecidas`, troque a primeira linha:

```python
  conhecidas = {d.nome for d in core_features.catalogo_completo()}
```

por:

```python
  conhecidas = {d.nome for d in core_features.catalogo_completo()} | set(core_carga.COLUNAS_CALCULADAS)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `OK (skipped=1)`

- [ ] **Step 6: Checkpoint.** Peça ao usuário para revisar e commitar (Tasks 6 a 8).

---

### Task 9: Régua — previsões fora do fold em `core/avaliacao.py`

**Files:**
- Create: `src/ml/core/avaliacao.py`
- Modify: `src/ml/studio/features.py` (remove `_modelo`, `_logo`, `r2_por_local`, `_resumo`, `assert_sem_vazamento`, `avaliar_versao`, `avaliar`; importa de `avaliacao`)
- Modify: `src/ml/studio/selecao.py:96`
- Modify: `tests/test_studio_features.py`, `tests/test_selecao.py`, `tests/test_formulas_paralelos.py` (patch de `ARVORES`)
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_avaliacao.py`:

```python
import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import avaliacao as A
from ml.core import carga as C
from ml.studio import features as SF

ALVOS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']
TABELA = {'prefixos': {'router_': {'classe': 'tr069'}},
          'colunas': {**{a: {'classe': 'alvo'} for a in ALVOS},
                      'router_tx_bytes': {'classe': 'tr069', 'vazamento': True}}}
LOCAIS = ['sala', 'quarto', 'cwpb-1', 'cwpb-2', 'hotmilk-copa', 'hotmilk-aquario']


class Constante(BaseEstimator, RegressorMixin):
  """Prevê sempre `valor` e guarda o índice das linhas de treino."""

  def __init__(self, valor=1000.0):
    self.valor = valor

  def fit(self, X, y):
    self.indices_ = list(X.index)
    return self

  def predict(self, X):
    return np.full(len(X), self.valor)


def frame(n_por_local=10, seed=0):
  rng = np.random.default_rng(seed)
  n = len(LOCAIS) * n_por_local
  snr = rng.uniform(10, 40, n)
  return pd.DataFrame({
    'local': np.repeat(LOCAIS, n_por_local),
    'speedtest_down_mbps': 3 * snr + rng.normal(0, 1, n),
    'speedtest_up_mbps': snr + rng.normal(0, 1, n),
    'latency_ms': rng.normal(20, 2, n), 'jitter_ms': rng.normal(3, 1, n),
    'router_snr': snr, 'router_tx_bytes': snr * 1000,
  })


def conjunto(alvo='speedtest_down_mbps', f=None):
  return C.preparar({'a.csv': frame() if f is None else f}, alvo, TABELA, catalogo=())


class Base(unittest.TestCase):
  def setUp(self):
    self._arvores = A.ARVORES
    A.ARVORES = 15

  def tearDown(self):
    A.ARVORES = self._arvores


class TestPrevisoes(Base):
  def test_cada_linha_e_prevista_sem_o_proprio_predio(self):
    conj = conjunto()
    vistos = []
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [],
                                 ao_ajustar=lambda fold, m: vistos.append((fold.test_site, fold.train_sites)))
    self.assertEqual(sorted(prev['_site'].unique()), ['coworking', 'hotmilk', 'residencia'])
    for teste, treino in vistos:
      self.assertNotIn(teste, treino)
    self.assertEqual(sorted(prev['_linha']), sorted(conj.df['_linha']))

  def test_linha_limitada_sai_do_treino_e_fica_no_teste(self):
    conj = conjunto()
    limitadas = conj.df.index[conj.df['_site'] == 'residencia'][:3]
    conj.df.loc[limitadas, '_limitado_wan'] = True
    treinos = []
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(),
                                 ao_ajustar=lambda fold, m: treinos.append(set(m.indices_)))
    for treino in treinos:
      self.assertFalse(set(limitadas) & treino)
    self.assertTrue(set(limitadas) <= set(prev.index))

  def test_previsao_cortada_no_teto_do_predio(self):
    conj = conjunto()
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(1000.0))
    por_site = prev.groupby('_site')['yhat'].unique().map(list).to_dict()
    self.assertEqual(por_site['residencia'], [154.0])
    self.assertEqual(por_site['hotmilk'], [1000.0])

  def test_latencia_nao_tem_teto(self):
    conj = conjunto('latency_ms')
    prev = A.prever_fora_do_fold(conj.df, ['router_snr'], conj.alvo, [], estimador=Constante(1000.0))
    self.assertEqual(prev['yhat'].unique().tolist(), [1000.0])

  def test_vazamento_levanta(self):
    conj = conjunto()
    with self.assertRaises(AssertionError):
      A.prever_fora_do_fold(conj.df, ['router_tx_bytes'], conj.alvo, ['router_tx_bytes'])

  def test_formato_antigo_do_logo(self):
    conj = conjunto()
    por_local, reais, previstos, mae = A._logo(conj.df, ['router_snr'], conj.alvo, [])
    self.assertEqual(sorted(por_local), ['coworking', 'hotmilk', 'residencia'])
    self.assertEqual(len(reais), len(conj.df))
    self.assertEqual(sorted(mae), sorted(por_local))

  def test_studio_reexporta_a_regua(self):
    self.assertIs(SF.avaliar, A.avaliar)
    self.assertIs(SF._logo, A._logo)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao -v`
Expected: `ImportError: cannot import name 'avaliacao'`

- [ ] **Step 3: Criar `src/ml/core/avaliacao.py`**

`_resumo` é o mesmo de `src/ml/studio/features.py`:

```python
"""Régua única do modelo: LOGO por prédio, métricas, intervalos e veredito de promoção.

O QoE Studio, regression_mlflow.py e regression_benchmark.py medem por aqui, para
que uma versão tenha um número só, venha de onde vier.
"""

from statistics import mean

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline

from ml.core.features import matriz
from ml.core.sites import teto_wan
from ml.core.splits import outer_logo_folds

# Muda quando a régua muda: avaliações guardadas com outra versão ficam "desatualizadas".
VERSAO_REGUA = '2026-10-05.1'
ARVORES = 200
ALVOS_COM_TETO = ('speedtest_down_mbps', 'speedtest_up_mbps')
_COLUNAS_PREVISAO = ['_linha', 'y', 'yhat', '_site', '_pos']


def modelo_regua(arvores: int = None) -> Pipeline:
  """O modelo que compara versões: fixo, para que a diferença venha das features."""
  return Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('reg', RandomForestRegressor(n_estimators=arvores or ARVORES, min_samples_leaf=2,
                                  n_jobs=-1, random_state=42)),
  ])


_modelo = modelo_regua  # nome antigo, usado pelo Studio


def assert_sem_vazamento(colunas, vazadas) -> None:
  proibidas = sorted(set(colunas) & set(vazadas))
  if proibidas:
    raise AssertionError(f'colunas com vazamento chegaram a um ajuste: {proibidas}')


def prever_fora_do_fold(df: pd.DataFrame, colunas, y_col: str, vazadas, arvores: int = None,
                        min_teste: int = 1, min_treino: int = 1, estimador=None,
                        ao_ajustar=None) -> pd.DataFrame:
  """Previsão de cada linha pelo modelo treinado sem o prédio dela (LOGO por `_site`).

  Para download e upload, linhas `_limitado_wan` saem do treino e a previsão é
  cortada no teto de WAN do prédio de teste. `estimador` troca o modelo da régua
  (é clonado a cada fold); `ao_ajustar(fold, modelo)` é chamado depois de cada ajuste.
  Devolve colunas _linha, y, yhat, _site, _pos, indexadas como `df`.
  """
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return pd.DataFrame(columns=_COLUNAS_PREVISAO)
  sub = df[df[y_col].notna()]
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  com_teto = y_col in ALVOS_COM_TETO
  limitado = pd.Series(False, index=sub.index)
  if com_teto and '_limitado_wan' in sub.columns:
    limitado = sub['_limitado_wan'].astype(bool)
  linha = sub['_linha'] if '_linha' in sub.columns else pd.Series(sub.index.astype(str), index=sub.index)
  posicao = sub['_pos'] if '_pos' in sub.columns else sub['_site']
  partes = []
  for fold in outer_logo_folds(X, y, sub['_site']):
    treino = ~limitado.loc[fold.X_train.index].to_numpy()
    if len(fold.y_test) < min_teste or int(treino.sum()) < min_treino:
      continue
    modelo = clone(estimador) if estimador is not None else modelo_regua(arvores)
    modelo.fit(fold.X_train[treino], fold.y_train[treino])
    previsto = np.asarray(modelo.predict(fold.X_test), dtype=float)
    teto = teto_wan(fold.test_site, y_col) if com_teto else None
    if teto is not None:
      previsto = np.minimum(previsto, teto)
    if ao_ajustar is not None:
      ao_ajustar(fold, modelo)
    indice = fold.X_test.index
    partes.append(pd.DataFrame({'_linha': linha.loc[indice].to_numpy(), 'y': fold.y_test.to_numpy(),
                                'yhat': previsto, '_site': fold.test_site,
                                '_pos': posicao.loc[indice].to_numpy()}, index=indice))
  if not partes:
    return pd.DataFrame(columns=_COLUNAS_PREVISAO)
  return pd.concat(partes)


def _tupla(prev: pd.DataFrame):
  """Previsões no formato antigo do Studio: (R² por local, y real, y previsto, MAE por local)."""
  if prev.empty:
    return {}, [], [], {}
  grupos = prev.groupby('_site', sort=False)
  por_local = {s: float(r2_score(g['y'], g['yhat'])) for s, g in grupos}
  mae_local = {s: float(mean_absolute_error(g['y'], g['yhat'])) for s, g in grupos}
  return por_local, prev['y'].astype(float).tolist(), prev['yhat'].astype(float).tolist(), mae_local


def _logo(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1):
  """LOGO por local de coleta. Devolve (R² por local, y real, y previsto, MAE por local)."""
  return _tupla(prever_fora_do_fold(df, colunas, y_col, vazadas, arvores, min_teste, min_treino))


def r2_por_local(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1) -> dict:
  return _logo(df, colunas, y_col, vazadas, arvores, min_teste, min_treino)[0]


def _resumo(logo, n: int) -> dict:
  """Média por local, mais R² e MAE sobre todas as previsões fora do fold.

  Com poucos locais a média dos R² por fold é dominada pelo local de menor
  variância do alvo; o R² pooled e o MAE não têm esse problema.
  """
  por_local, reais, previstos, mae_local = logo
  return {'n': n, 'media': round(mean(por_local.values()), 4) if por_local else None,
          'pooled': round(float(r2_score(reais, previstos)), 4) if len(reais) > 1 else None,
          'mae': round(float(mean_absolute_error(reais, previstos)), 4) if reais else None,
          'por_local': {s: round(v, 4) for s, v in sorted(por_local.items())},
          'mae_por_local': {s: round(v, 4) for s, v in sorted(mae_local.items())}}


def resumir(prev: pd.DataFrame, n: int) -> dict:
  """Resumo da régua: o do Studio mais a versão da régua."""
  resumo = _resumo(_tupla(prev), n)
  resumo['versao_regua'] = VERSAO_REGUA
  return resumo


def avaliar(conj, features, vazadas, com_previsoes: bool = False):
  """LOGO por local de coleta de uma lista de features, como está.

  Feature ausente do conjunto sai da conta e é listada; feature com vazamento
  levanta (assert_sem_vazamento), nunca é descartada em silêncio. Com
  `com_previsoes`, devolve (resumo, previsões fora do fold).
  """
  presentes = [f for f in features if f in conj.df.columns]
  prev = prever_fora_do_fold(conj.df, presentes, conj.alvo, vazadas)
  resumo = resumir(prev, len(presentes))
  resumo['ausentes'] = [f for f in features if f not in conj.df.columns]
  return (resumo, prev) if com_previsoes else resumo


def avaliar_versao(conj, features, vazadas, com_previsoes: bool = False):
  """Como avaliar, mas uma versão salva que usa coluna hoje marcada como vazamento é
  avaliada sem ela, e a lista sai em `removidas_por_vazamento`. Assim a comparação
  continua de pé quando alguém confirma um vazamento depois de a versão existir."""
  removidas = [f for f in features if f in vazadas]
  saida = avaliar(conj, [f for f in features if f not in vazadas], vazadas, com_previsoes)
  resumo = saida[0] if com_previsoes else saida
  resumo['removidas_por_vazamento'] = removidas
  return saida
```

- [ ] **Step 4: `studio/features.py` passa a importar a régua**

Em `src/ml/studio/features.py`:

1. Apague as funções `assert_sem_vazamento`, `_modelo`, `_logo`, `r2_por_local`, `_resumo`, `avaliar_versao` e `avaliar`, e a constante `ARVORES = 200`. `ARVORES_PROXY` fica.
2. Troque os imports de `sklearn` (`RandomForestRegressor`, `SimpleImputer`, `mean_absolute_error`, `r2_score`, `Pipeline`) e `from ml.core.splits import COMFORTABLE_SITES, outer_logo_folds` por:

```python
from ml.core.avaliacao import (_logo, _modelo, _resumo, assert_sem_vazamento, avaliar,
                               avaliar_versao, r2_por_local)
from ml.core.splits import COMFORTABLE_SITES
```

3. Confira que nada mais em `features.py` usa nomes removidos:

Run: `grep -n "RandomForestRegressor\|SimpleImputer\|r2_score\|mean_absolute_error\|Pipeline\|outer_logo_folds\|ARVORES\b" src/ml/studio/features.py`
Expected: nenhuma linha (só `ARVORES_PROXY` pode aparecer, e não casa com `ARVORES\b`).

- [ ] **Step 5: `selecao.py` usa o modelo da régua**

Em `src/ml/studio/selecao.py`, acrescente `from ml.core import avaliacao as A` aos imports e troque, na linha 96:

```python
    p = SF._modelo(SF.ARVORES).fit(X_tr, treino[alvo].astype(float)).predict(X_te)
```

por:

```python
    p = A.modelo_regua().fit(X_tr, treino[alvo].astype(float)).predict(X_te)
```

- [ ] **Step 6: Os testes passam a reduzir `A.ARVORES`**

- `tests/test_studio_features.py`: acrescente `from ml.core import avaliacao as A`. Em `Base.setUp`/`tearDown`, troque `(SF.ARVORES, SF.ARVORES_PROXY)` por `(A.ARVORES, SF.ARVORES_PROXY)` nas três linhas (guardar, reduzir para 25, restaurar).
- `tests/test_selecao.py`: acrescente `from ml.core import avaliacao as A`. Em `Base`, troque `SF.ARVORES` por `A.ARVORES` nas três linhas.
- `tests/test_formulas_paralelos.py`: acrescente `from ml.core import avaliacao as A`. Em `TestParalelos.setUp`/`tearDown`, troque `SF.ARVORES` por `A.ARVORES` nas três linhas.

Run: `grep -rn "SF\.ARVORES\b" tests src`
Expected: nenhuma linha.

- [ ] **Step 7: Rodar e ver passar**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `OK (skipped=1)`

- [ ] **Step 8: Checkpoint.** Peça ao usuário para revisar e commitar (Task 9).

---

### Task 10: MAE em escala log

**Files:**
- Modify: `src/ml/core/avaliacao.py`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
class TestMaeLog(Base):
  def test_previsao_negativa_conta_como_zero(self):
    self.assertAlmostEqual(A.mae_log([0.0, 9.0], [-5.0, 9.0]), 0.0)

  def test_valor_conhecido(self):
    self.assertAlmostEqual(A.mae_log([np.e - 1], [0.0]), 1.0)

  def test_resumo_traz_mae_log_e_versao(self):
    conj = conjunto()
    r = A.avaliar(conj, ['router_snr'], [])
    self.assertEqual(r['versao_regua'], A.VERSAO_REGUA)
    self.assertGreater(r['mae_log'], 0)
    self.assertEqual(sorted(r['mae_log_por_local']), ['coworking', 'hotmilk', 'residencia'])

  def test_resumo_vazio_nao_quebra(self):
    r = A.resumir(pd.DataFrame(columns=['_linha', 'y', 'yhat', '_site', '_pos']), 0)
    self.assertIsNone(r['mae_log'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao.TestMaeLog -v`
Expected: `AttributeError: ... 'mae_log'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/avaliacao.py`, antes de `_tupla`:

```python
def mae_log(y, yhat) -> float:
  """Média de |log1p(y) - log1p(ŷ)|: erro relativo, para os prédios rápidos não dominarem.

  Previsão negativa é cortada em 0 (throughput e tempo não são negativos).
  """
  y = np.asarray(y, dtype=float)
  yhat = np.clip(np.asarray(yhat, dtype=float), 0, None)
  return float(np.mean(np.abs(np.log1p(y) - np.log1p(yhat))))
```

E troque `resumir` por:

```python
def resumir(prev: pd.DataFrame, n: int) -> dict:
  """Resumo da régua: o do Studio mais MAE log e a versão da régua."""
  resumo = _resumo(_tupla(prev), n)
  vazio = prev.empty
  resumo['mae_log'] = None if vazio else round(mae_log(prev['y'], prev['yhat']), 4)
  resumo['mae_log_por_local'] = {} if vazio else {
    s: round(mae_log(g['y'], g['yhat']), 4) for s, g in sorted(prev.groupby('_site'), key=lambda kv: kv[0])}
  resumo['versao_regua'] = VERSAO_REGUA
  return resumo
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -3`
Expected: `OK`

---

### Task 11: Intervalos por bootstrap de posições

**Files:**
- Modify: `src/ml/core/avaliacao.py`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
class TestBootstrap(Base):
  def setUp(self):
    super().setUp()
    self.site = pd.Series(['a'] * 4 + ['b'] * 6)
    self.pos = pd.Series(['a1', 'a1', 'a2', 'a2', 'b1', 'b1', 'b1', 'b2', 'b3', 'b3'])

  def test_deterministico(self):
    r1 = A.reamostras(self.pos, self.site, n=20)
    r2 = A.reamostras(self.pos, self.site, n=20)
    self.assertTrue(all(np.array_equal(x, y) for x, y in zip(r1, r2)))

  def test_todo_predio_em_toda_reamostragem(self):
    for idx in A.reamostras(self.pos, self.site, n=50):
      self.assertEqual(set(self.site.iloc[idx]), {'a', 'b'})

  def test_posicao_entra_inteira(self):
    tamanho = self.pos.value_counts()
    for idx in A.reamostras(self.pos, self.site, n=50):
      contagem = self.pos.iloc[idx].value_counts()
      for p, c in contagem.items():
        self.assertEqual(c % tamanho[p], 0)

  def test_resumo_traz_intervalos(self):
    r = A.avaliar(conjunto(), ['router_snr'], [])
    for chave in ('pooled', 'mae', 'mae_log'):
      lo, hi = r['intervalos'][chave]
      self.assertLessEqual(lo, hi)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao.TestBootstrap -v`
Expected: `AttributeError: ... 'reamostras'`

- [ ] **Step 3: Implementar**

Em `src/ml/core/avaliacao.py`, junto das constantes do topo:

```python
N_BOOTSTRAP = 1000
SEMENTE = 42
# Intervalo de 90%.
PERCENTIS = (5, 95)
```

Antes de `_tupla`:

```python
def reamostras(pos, site, n: int = None, semente: int = SEMENTE) -> list:
  """Índices posicionais de cada reamostragem bootstrap.

  Sorteia com reposição as posições de medição de cada prédio, levando todas as
  linhas de cada posição sorteada: linhas da mesma posição não são independentes.
  Estratificado por prédio, então todo prédio aparece em toda reamostragem.
  """
  n = N_BOOTSTRAP if n is None else n
  rng = np.random.default_rng(semente)
  blocos = {}
  for i, (s, p) in enumerate(zip(np.asarray(site), np.asarray(pos))):
    blocos.setdefault(str(s), {}).setdefault(str(p), []).append(i)
  por_site = [[np.array(blocos[s][p]) for p in sorted(blocos[s])] for s in sorted(blocos)]
  saida = []
  for _ in range(n):
    partes = []
    for posicoes in por_site:
      partes.extend(posicoes[i] for i in rng.integers(0, len(posicoes), size=len(posicoes)))
    saida.append(np.concatenate(partes))
  return saida


def _r2(y: np.ndarray, p: np.ndarray) -> float:
  soma = float(np.sum((y - y.mean()) ** 2))
  return float('nan') if soma == 0 else 1 - float(np.sum((y - p) ** 2)) / soma


def _intervalo(valores):
  """Percentis PERCENTIS dos valores que não são NaN; None se não sobra nenhum."""
  v = np.asarray(valores, dtype=float)
  v = v[~np.isnan(v)]
  if not len(v):
    return None
  lo, hi = np.percentile(v, PERCENTIS)
  return [round(float(lo), 4), round(float(hi), 4)]


def intervalos(prev: pd.DataFrame, amostras=None) -> dict:
  """Intervalo de 90% de R² pooled, MAE e MAE log sobre as previsões fora do fold (não retreina)."""
  if len(prev) < 2:
    return {}
  amostras = reamostras(prev['_pos'], prev['_site']) if amostras is None else amostras
  y, p = prev['y'].to_numpy(dtype=float), prev['yhat'].to_numpy(dtype=float)
  r2s, maes, logs = [], [], []
  for idx in amostras:
    yy, pp = y[idx], p[idx]
    r2s.append(_r2(yy, pp))
    maes.append(float(np.mean(np.abs(yy - pp))))
    logs.append(mae_log(yy, pp))
  return {'pooled': _intervalo(r2s), 'mae': _intervalo(maes), 'mae_log': _intervalo(logs)}
```

Em `resumir`, antes de `resumo['versao_regua'] = VERSAO_REGUA`:

```python
  resumo['intervalos'] = intervalos(prev)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -3`
Expected: `OK`

---

### Task 12: Métrica "atende em throughput"

**Files:**
- Modify: `src/ml/core/avaliacao.py`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
def previsoes(linhas, y, yhat, sites=None, pos=None):
  n = len(linhas)
  return pd.DataFrame({'_linha': linhas, 'y': y, 'yhat': yhat,
                       '_site': sites or ['s1', 's1', 's2', 's2', 's2'][:n],
                       '_pos': pos or ['p1', 'p2', 'p3', 'p4', 'p5'][:n]})


APPS = {'Video': {'dn': 10, 'up': 5, 'lat': 150, 'jit': 30},
        'Tudo': {'dn': 0, 'up': 0, 'lat': 500, 'jit': 100}}


class TestAtende(Base):
  def test_acuracia_balanceada_e_aplicacao_de_classe_unica_fora(self):
    dn = previsoes(['a:0', 'a:1', 'a:2', 'a:3', 'a:9'], [30, 1, 30, 1, 30], [30, 1, 1, 30, 30])
    up = previsoes(['a:0', 'a:1', 'a:2', 'a:3'], [10, 10, 10, 10], [10, 10, 10, 10])
    r = A.atende(dn, up, APPS)
    # Video: real [T, F, T, F], previsto [T, F, F, T] -> (1/2 + 1/2) / 2 = 0,5
    self.assertEqual(r['por_aplicacao'], {'Video': 0.5})
    self.assertEqual(r['media'], 0.5)
    self.assertEqual(r['n'], 4)
    self.assertTrue(any('Tudo' in a for a in r['avisos']))

  def test_previsao_perfeita_da_1(self):
    dn = previsoes(['a:0', 'a:1', 'a:2', 'a:3'], [30, 1, 30, 1], [30, 1, 30, 1])
    up = previsoes(['a:0', 'a:1', 'a:2', 'a:3'], [10, 10, 10, 10], [10, 10, 10, 10])
    self.assertEqual(A.atende(dn, up, APPS)['media'], 1.0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao.TestAtende -v`
Expected: `AttributeError: ... 'atende'`

- [ ] **Step 3: Implementar**

Ao fim de `src/ml/core/avaliacao.py`:

```python
def _acuracia_balanceada(real, previsto) -> float:
  """Média de sensibilidade e especificidade; NaN se o real tem uma classe só."""
  real = np.asarray(real, dtype=bool)
  previsto = np.asarray(previsto, dtype=bool)
  if real.all() or not real.any():
    return float('nan')
  return float((np.mean(previsto[real]) + np.mean(~previsto[~real])) / 2)


def _media_sem_nan(valores) -> float:
  v = [x for x in valores if not np.isnan(x)]
  return float(mean(v)) if v else float('nan')


def _juntar(**previsoes) -> pd.DataFrame:
  """Junta previsões fora do fold por `_linha` (só as linhas presentes em todas).

  Cada argumento vira as colunas y_<nome> e p_<nome>; _site e _pos vêm do primeiro.
  """
  nomes = list(previsoes)
  j = previsoes[nomes[0]].set_index('_linha')[['_site', '_pos']]
  for nome in nomes:
    p = previsoes[nome].set_index('_linha')[['y', 'yhat']]
    j = j.join(p.rename(columns={'y': f'y_{nome}', 'yhat': f'p_{nome}'}), how='inner')
  return j


def _atende_em(j: pd.DataFrame, limiares: dict, y_dn: str, y_up: str) -> np.ndarray:
  return ((j[y_dn] >= limiares['dn']) & (j[y_up] >= limiares['up'])).to_numpy()


def atende(prev_down: pd.DataFrame, prev_up: pd.DataFrame, aplicacoes: dict, amostras=None) -> dict:
  """Acurácia balanceada de "atende em throughput" por aplicação, real contra previsto.

  Atende = download >= limiar dn e upload >= limiar up, nas linhas com os dois alvos.
  Aplicação em que só uma classe aparece nos dados reais fica fora da média, com aviso.
  """
  j = _juntar(dn=prev_down, up=prev_up)
  pares, por_aplicacao, avisos = {}, {}, []
  for nome, limiares in aplicacoes.items():
    real = _atende_em(j, limiares, 'y_dn', 'y_up')
    previsto = _atende_em(j, limiares, 'p_dn', 'p_up')
    valor = _acuracia_balanceada(real, previsto)
    if np.isnan(valor):
      avisos.append(f'{nome}: só uma classe nos dados reais; fora da média')
      continue
    pares[nome] = (real, previsto)
    por_aplicacao[nome] = round(valor, 4)
  media = round(mean(por_aplicacao.values()), 4) if por_aplicacao else None
  intervalo = None
  if pares and len(j) > 1:
    amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
    intervalo = _intervalo([_media_sem_nan([_acuracia_balanceada(r[i], p[i]) for r, p in pares.values()])
                            for i in amostras])
  return {'por_aplicacao': por_aplicacao, 'media': media, 'intervalo': intervalo,
          'n': int(len(j)), 'avisos': avisos}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -3`
Expected: `OK`

---

### Task 13: Diferenças com intervalo e veredito de promoção

**Files:**
- Modify: `src/ml/core/avaliacao.py`
- Test: `tests/test_avaliacao.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
def delta(valor, lo, hi, mae_base=None):
  d = {'valor': valor, 'intervalo': [lo, hi]}
  if mae_base is not None:
    d['mae_base'] = mae_base
  return d


class TestPromocao(Base):
  def setUp(self):
    super().setUp()
    linhas = [f'a:{i}' for i in range(5)]
    y = [30.0, 1.0, 30.0, 1.0, 20.0]
    self.base = previsoes(linhas, y, [v + 10 for v in y])
    self.nova = previsoes(linhas, y, y)

  def test_delta_mae_da_nova_perfeita(self):
    d = A.delta_mae(self.nova, self.base)
    self.assertEqual(d['valor'], -10.0)
    self.assertLess(d['intervalo'][1], 0)
    self.assertEqual(d['mae_base'], 10.0)

  def test_delta_mae_sem_linhas_em_comum_levanta(self):
    outra = previsoes(['b:0'], [1.0], [1.0])
    with self.assertRaises(ValueError):
      A.delta_mae(self.nova, outra)

  def test_delta_atende(self):
    up = previsoes([f'a:{i}' for i in range(5)], [10.0] * 5, [10.0] * 5)
    ruim = previsoes([f'a:{i}' for i in range(5)], [30.0, 1.0, 30.0, 1.0, 20.0], [1.0] * 5)
    d = A.delta_atende(self.nova, up, ruim, up, APPS)
    self.assertEqual(d['valor'], 0.5)

  def test_delta_atende_sem_aplicacao_com_duas_classes_e_none(self):
    tudo = {'Tudo': APPS['Tudo']}
    self.assertIsNone(A.delta_atende(self.nova, self.nova, self.base, self.base, tudo))

  def test_mae_melhor_sem_piorar_atende_e_melhor(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), delta(0.0, -0.01, 0.01))
    self.assertEqual(v['resultado'], 'melhor')

  def test_atende_melhor_sem_piorar_mae_e_melhor(self):
    v = A.veredito_promocao(delta(0.5, -1.0, 2.0, 40.0), delta(0.05, 0.01, 0.09))
    self.assertEqual(v['resultado'], 'melhor')

  def test_atende_pior_e_pior_mesmo_com_mae_melhor(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), delta(-0.05, -0.09, -0.01))
    self.assertEqual(v['resultado'], 'pior')

  def test_intervalos_com_zero_e_empate(self):
    v = A.veredito_promocao(delta(-1.0, -3.0, 1.0, 40.0), delta(0.01, -0.02, 0.03))
    self.assertEqual(v['resultado'], 'empate')

  def test_latencia_decide_so_pelo_mae(self):
    v = A.veredito_promocao(delta(-5.0, -8.0, -2.0, 40.0), None)
    self.assertEqual(v['resultado'], 'melhor')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_avaliacao.TestPromocao -v`
Expected: `AttributeError: ... 'delta_mae'`

- [ ] **Step 3: Implementar**

Junto das constantes do topo de `src/ml/core/avaliacao.py`:

```python
# Piora tolerada na métrica que não melhorou: 0,02 de acurácia balanceada e 2% do MAE da base.
RUIDO_ATENDE = 0.02
RUIDO_MAE_REL = 0.02
```

Ao fim do arquivo:

```python
def delta_mae(nova: pd.DataFrame, base: pd.DataFrame, amostras=None) -> dict:
  """MAE da nova versão menos o da base, nas mesmas linhas e nas mesmas reamostragens."""
  j = _juntar(nova=nova, base=base)
  if j.empty:
    raise ValueError('as duas versões não têm previsões em comum para comparar')
  erro_nova = np.abs(j['y_nova'] - j['p_nova']).to_numpy(dtype=float)
  erro_base = np.abs(j['y_base'] - j['p_base']).to_numpy(dtype=float)
  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(float(erro_nova.mean() - erro_base.mean()), 4),
          'intervalo': _intervalo([erro_nova[i].mean() - erro_base[i].mean() for i in amostras]),
          'mae_base': round(float(erro_base.mean()), 4), 'n': int(len(j))}


def delta_atende(nova_dn, nova_up, base_dn, base_up, aplicacoes: dict, amostras=None):
  """Acurácia balanceada média de "atende" da nova menos a da base.

  None quando nenhuma aplicação tem as duas classes nos dados reais.
  """
  j = _juntar(ndn=nova_dn, nup=nova_up, bdn=base_dn, bup=base_up)
  trios = []
  for limiares in aplicacoes.values():
    real = _atende_em(j, limiares, 'y_ndn', 'y_nup')
    if real.all() or not real.any():
      continue
    trios.append((real, _atende_em(j, limiares, 'p_ndn', 'p_nup'), _atende_em(j, limiares, 'p_bdn', 'p_bup')))
  if not trios:
    return None

  def diferenca(idx):
    nova = _media_sem_nan([_acuracia_balanceada(r[idx], n[idx]) for r, n, _ in trios])
    base = _media_sem_nan([_acuracia_balanceada(r[idx], b[idx]) for r, _, b in trios])
    return nova - base

  amostras = reamostras(j['_pos'], j['_site']) if amostras is None else amostras
  return {'valor': round(diferenca(np.arange(len(j))), 4),
          'intervalo': _intervalo([diferenca(i) for i in amostras]), 'n': int(len(j))}


def _br(valor: float, casas: int) -> str:
  return f'{valor:.{casas}f}'.replace('.', ',')


def veredito_promocao(delta_mae: dict, delta_atende: dict = None) -> dict:
  """Melhor / empate / pior pela régua de promoção (nova − base, intervalo de 90%).

  Pior: o intervalo exclui 0 contra a nova em MAE ou em "atende". Melhor: exclui 0
  a favor numa delas e a outra não piora mais que o ruído. Empate: o resto.
  `delta_atende` é None em latência e jitter, que decidem só pelo MAE.
  """
  lo_m, hi_m = delta_mae['intervalo']
  faixa_m = f'{_br(lo_m, 1)} a {_br(hi_m, 1)}'
  if lo_m > 0:
    return {'resultado': 'pior', 'motivo': f'O MAE subiu {_br(delta_mae["valor"], 1)} (90%: {faixa_m}).'}
  if delta_atende is not None and delta_atende['intervalo'][1] < 0:
    lo_a, hi_a = delta_atende['intervalo']
    return {'resultado': 'pior', 'motivo': f'A acurácia de "atende" caiu {_br(-delta_atende["valor"], 3)} '
                                           f'(90%: {_br(lo_a, 3)} a {_br(hi_a, 3)}).'}
  mae_ok = delta_mae['valor'] <= RUIDO_MAE_REL * delta_mae['mae_base']
  atende_ok = delta_atende is None or delta_atende['valor'] >= -RUIDO_ATENDE
  if hi_m < 0 and atende_ok:
    return {'resultado': 'melhor', 'motivo': f'O MAE caiu {_br(-delta_mae["valor"], 1)} (90%: {faixa_m}) '
                                             'sem piorar "atende".'}
  if delta_atende is not None and delta_atende['intervalo'][0] > 0 and mae_ok:
    lo_a, hi_a = delta_atende['intervalo']
    return {'resultado': 'melhor', 'motivo': f'A acurácia de "atende" subiu {_br(delta_atende["valor"], 3)} '
                                             f'(90%: {_br(lo_a, 3)} a {_br(hi_a, 3)}) sem piorar o MAE.'}
  return {'resultado': 'empate', 'motivo': 'Os intervalos das diferenças incluem 0: com estes locais, '
                                           'não dá para separar as duas versões.'}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_avaliacao -v 2>&1 | tail -3`
Expected: `OK`

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `OK (skipped=1)`

- [ ] **Step 5: Checkpoint.** Peça ao usuário para revisar e commitar (Tasks 10 a 13).

---

### Task 14: Studio — régua na API e na interface

**Files:**
- Modify: `src/ml/studio/api.py` (imports, `modelos_listar`, `modelos_avaliar`, `avaliacao_completa`)
- Modify: `src/ml/studio/static/studio.js:14-20,342,349,355`
- Modify: `src/ml/studio/static/modelos.js:178-186`
- Modify: `src/ml/studio/static/assistente.js` (`cartaoVeredito`)
- Test: `tests/test_studio_assistente.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_studio_assistente.py`, acrescente `from ml.core import avaliacao as A` aos imports e, dentro de `TestRotasAssistente`:

```python
  def test_avaliar_com_base_traz_promocao_da_regua(self):
    r = api.modelos_avaliar(features='router_snr,router_signal_dbm', ds='a.csv', base='v1')
    self.assertIn(r['promocao']['veredito']['resultado'], {'melhor', 'empate', 'pior'})
    self.assertEqual(r['promocao']['versao_regua'], A.VERSAO_REGUA)
    self.assertIn('intervalo', r['promocao']['delta_mae'])

  def test_resumo_traz_intervalos(self):
    r = api.modelos_avaliar(features='router_snr', ds='a.csv')
    self.assertIn('pooled', r['resumo']['intervalos'])

  def test_listar_traz_versao_da_regua(self):
    self.assertEqual(api.modelos_listar()['versao_regua'], A.VERSAO_REGUA)

  def test_avaliacao_completa_traz_atende_e_versao(self):
    av = api.avaliacao_completa('a.csv', '', ['router_snr'])
    self.assertEqual(av['speedtest_down_mbps']['versao_regua'], A.VERSAO_REGUA)
    self.assertIn('media', av['atende_throughput'])
```

Em `tests/test_modelos_core.py`, acrescente (com `from ml.core import modelos as M` se o arquivo ainda não importar assim):

```python
class TestAvaliacaoComRegua(unittest.TestCase):
  def test_registro_aceita_avaliacao_com_versao_da_regua_e_atende(self):
    M.validar_registro({'ativo': 'v1', 'versoes': {'v1': {
      'features': ['router_snr'], 'descricao': 'x',
      'avaliacao': {'speedtest_down_mbps': {'pooled': 0.5, 'versao_regua': '2026-10-05.1'},
                    'atende_throughput': {'media': 0.8}}}}})
```

E em `Base.setUp`/`tearDown` desse arquivo (importado de `test_studio_features`), a troca para `A.ARVORES` já foi feita na Task 9.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_studio_assistente.TestRotasAssistente -v 2>&1 | tail -15`
Expected: `KeyError: 'promocao'`, `KeyError: 'versao_regua'`, `KeyError: 'atende_throughput'`

- [ ] **Step 3: API**

Em `src/ml/studio/api.py`:

1. Acrescente aos imports de `ml.core`:

```python
from ml.core import aplicacoes as core_aplicacoes
from ml.core import avaliacao as core_avaliacao
```

2. Em `modelos_listar`, no dicionário devolvido, depois de `'versao_catalogo': core_features.CATALOGO_VERSAO`:

```python
          'versao_regua': core_avaliacao.VERSAO_REGUA,
```

3. Acrescente, antes de `modelos_avaliar`:

```python
def _promocao(ds: str, ambiente: str, alvo: str, feats: list, feats_base: list, conj) -> dict:
  """Veredito de promoção da régua: intervalo da diferença em MAE e, para throughput, em "atende"."""
  def prever(c, lista):
    vazadas = studio_features.vazadas_do_conjunto(c)
    presentes = [f for f in lista if f in c.df.columns and f not in vazadas]
    return core_avaliacao.prever_fora_do_fold(c.df, presentes, c.alvo, vazadas)
  d_mae = core_avaliacao.delta_mae(prever(conj, feats), prever(conj, feats_base))
  d_atende = None
  if alvo in core_avaliacao.ALVOS_COM_TETO:
    dn, _ = _conjunto(ds, 'speedtest_down_mbps', ambiente)
    up, _ = _conjunto(ds, 'speedtest_up_mbps', ambiente)
    d_atende = core_avaliacao.delta_atende(prever(dn, feats), prever(up, feats), prever(dn, feats_base),
                                           prever(up, feats_base), core_aplicacoes.carregar())
  return {'delta_mae': d_mae, 'delta_atende': d_atende,
          'veredito': core_avaliacao.veredito_promocao(d_mae, d_atende),
          'versao_regua': core_avaliacao.VERSAO_REGUA}
```

4. Em `modelos_avaliar`, dentro do `if base:`, depois da linha que monta `saida['veredito'] = ...`:

```python
        saida['promocao'] = _promocao(ds, ambiente, alvo, feats, registro['versoes'][base]['features'], conj)
```

5. Troque `avaliacao_completa` inteira por:

```python
def avaliacao_completa(ds: str, ambiente: str, features: list) -> dict:
  """Avaliação dos quatro alvos e de "atende em throughput", guardada junto da versão."""
  saida, previsoes = {}, {}
  for alvo in studio_features.TARGETS:
    conj, _ = _conjunto(ds, alvo, ambiente)
    resumo, previsoes[alvo] = core_avaliacao.avaliar(conj, features, studio_features.vazadas_do_conjunto(conj),
                                                     com_previsoes=True)
    saida[alvo] = dict(resumo, datasets=conj.datasets, ambiente=_ambiente(ambiente) or 'todos',
                       versao_tabela=core_features.versao_tabela(),
                       versao_catalogo=core_features.CATALOGO_VERSAO)
  saida['atende_throughput'] = core_avaliacao.atende(previsoes['speedtest_down_mbps'],
                                                     previsoes['speedtest_up_mbps'],
                                                     core_aplicacoes.carregar())
  return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_studio_assistente -v 2>&1 | tail -3`
Expected: `OK`

- [ ] **Step 5: `studio.js` lê os limiares do payload**

Em `src/ml/studio/static/studio.js`, troque o bloco das linhas 14-20:

```js
  /* Limiares de referencia por aplicacao. Editaveis na view Limiares. */
  const PROFILES = {
    'Navegação':        { dn: 2,   up: 0.5, lat: 300, jit: 100 },
    'Chamada de vídeo': { dn: 3.8, up: 3.8, lat: 150, jit: 30 },
    'Streaming 4K':     { dn: 25,  up: 0,   lat: 500, jit: 100 },
    'Jogo em nuvem':    { dn: 15,  up: 1,   lat: 40,  jit: 10 },
  };
```

por:

```js
  /* Limiares de referencia por aplicacao: src/ml/core/aplicacoes.json, via payload.
     Editaveis na view Limiares (so na sessao). */
  let PROFILES = {};
```

E no `fetch('api/payload').then(...)`, logo depois de `state.data = data;`:

```js
    PROFILES = data.aplicacoes;
```

- [ ] **Step 6: `modelos.js` avisa régua antiga**

Em `src/ml/studio/static/modelos.js`, em `motivoDesatualizada`, depois da linha do catálogo:

```js
    if (av.versao_regua !== st.reg.versao_regua) motivos.push('régua de avaliação mudou');
```

- [ ] **Step 7: `assistente.js` mostra intervalo e promoção**

Em `src/ml/studio/static/assistente.js`, em `cartaoVeredito`:

1. Logo depois de `const linhas = ...join('');`, acrescente:

```js
    const faixa = (iv, casas) => (iv ? `<em>90%: ${num(iv[0], casas)} a ${num(iv[1], casas)}</em>` : '');
    const p = a.promocao;
    const promocao = p ? `<div class="veredito ${p.veredito.resultado}" style="margin-top:10px">
        <svg class="icon"><use href="#${VEREDITO[p.veredito.resultado][1]}"/></svg>
        <div><b>Régua de promoção: ${VEREDITO[p.veredito.resultado][0]}</b>
          <div class="gate-msg">${esc(p.veredito.motivo)}</div>
          <div class="gate-msg">Δ MAE ${num(p.delta_mae.valor, 1)} ${u} ${faixa(p.delta_mae.intervalo, 1)}${p.delta_atende
            ? ` · Δ atende ${num(p.delta_atende.valor, 3)} ${faixa(p.delta_atende.intervalo, 3)}` : ''}</div></div></div>` : '';
```

2. No KPI de R² pooled, troque:

```js
        <div><span>R² pooled</span><b>${num(a.resumo_base.pooled, 3)} → ${num(a.resumo.pooled, 3)}</b></div>
```

por:

```js
        <div><span>R² pooled</span><b>${num(a.resumo_base.pooled, 3)} → ${num(a.resumo.pooled, 3)}</b>${faixa((a.resumo.intervalos || {}).pooled, 3)}</div>
```

3. Logo depois do `</div>` que fecha `<div class="kpis">`, insira `${promocao}`.

- [ ] **Step 8: Conferir no navegador**

Run: `python3 src/ml/studio.py` (sobe o Studio; veja a porta impressa) e abra no navegador.

Expected:
- View "Capacidade por aplicação": o seletor de aplicação lista as 4 aplicações e os números são os mesmos de antes.
- View Modelos → Versões salvas: `v2-tr069` aparece como "desatualizada", com o motivo contendo "régua de avaliação mudou".
- Assistente, passo "Testar contra a versão ativa", com algum rascunho: o KPI de R² mostra "90%: … a …" e aparece o bloco "Régua de promoção".

Pare o servidor depois.

- [ ] **Step 9: Rodar a suíte**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `OK (skipped=1)`

- [ ] **Step 10: Checkpoint.** Peça ao usuário para revisar e commitar (Task 14).

---

### Task 15: `regression_mlflow.py` sobre a régua

**Files:**
- Modify: `src/ml/regression_mlflow.py` (reescrito)

- [ ] **Step 1: Reescrever o script**

Conteúdo completo de `src/ml/regression_mlflow.py`:

```python
"""Treina uma versão do registro e registra no MLflow, medida pela régua única.

Versão: MODELO=<nome> (padrão: a ativa em core/modelos.json). Alvo: ALVO= (padrão:
download). Datasets: DATASETS=a.zip,b.zip (nomes em data/; padrão: o conjunto
canônico, o mesmo do Studio). Cada configuração de árvore é avaliada deixando um
prédio de fora por vez, e o modelo final é treinado com todas as linhas fora do
teto de WAN.
"""

import os
import sys

import mlflow
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core.data import validate_columns

ALVO = os.environ.get('ALVO', 'speedtest_down_mbps')

CONFIGS = [
  {'model_type': 'RandomForest', 'n_estimators': 100, 'max_depth': 10},
  {'model_type': 'RandomForest', 'n_estimators': 200, 'max_depth': 20},
  {'model_type': 'ExtraTreesRegressor', 'n_estimators': 100, 'max_depth': 10},
  {'model_type': 'ExtraTreesRegressor', 'n_estimators': 200, 'max_depth': 20},
  {'model_type': 'GradientBoostingRegressor', 'n_estimators': 100, 'max_depth': 10},
  {'model_type': 'GradientBoostingRegressor', 'n_estimators': 200, 'max_depth': 20},
]
CLASSES = {'RandomForest': RandomForestRegressor, 'ExtraTreesRegressor': ExtraTreesRegressor,
           'GradientBoostingRegressor': GradientBoostingRegressor}


def montar(config: dict) -> Pipeline:
  regressor = CLASSES[config['model_type']](n_estimators=config['n_estimators'],
                                            max_depth=config['max_depth'], random_state=42)
  return Pipeline([('imputer', SimpleImputer(strategy='median')), ('reg', regressor)])


def registrar_metricas(resumo: dict) -> None:
  for chave in ('pooled', 'mae', 'mae_log', 'media'):
    if resumo.get(chave) is not None:
      mlflow.log_metric(chave, resumo[chave])
  for chave, intervalo in (resumo.get('intervalos') or {}).items():
    if intervalo:
      mlflow.log_metric(f'{chave}_lo90', intervalo[0])
      mlflow.log_metric(f'{chave}_hi90', intervalo[1])
  for site, valor in resumo['por_local'].items():
    mlflow.log_metric(f'r2_{site}', valor)
  for site, valor in resumo['mae_por_local'].items():
    mlflow.log_metric(f'mae_{site}', valor)


def main():
  registro = core_modelos.carregar()
  nome_modelo = os.environ.get('MODELO') or registro['ativo']
  if nome_modelo not in registro['versoes']:
    raise SystemExit(
      f"MODELO={nome_modelo!r} não existe em core/modelos.json; "
      f"versões disponíveis: {sorted(registro['versoes'])}")

  ids = [x for x in os.environ.get('DATASETS', '').split(',') if x] or None
  conj = core_carga.carregar(ALVO, ids=ids)
  for aviso in conj.avisos:
    print(f'aviso: {aviso}')
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  pedidas = list(registro['versoes'][nome_modelo]['features'])
  removidas = [f for f in pedidas if f in vazadas]
  features = [f for f in pedidas if f not in vazadas]
  if removidas:
    print(f'features com vazamento fora da conta: {removidas}')
  validate_columns(conj.df, features, 'feature')
  print(f"Modelo: {nome_modelo}" + (' (ativo)' if nome_modelo == registro['ativo'] else '')
        + f" — {len(features)} features, alvo {ALVO}, datasets {conj.datasets}")

  impressoes = {d['id']: d['fingerprint'] for d in core_carga.descobertos() if d.get('usable')}
  treino = ~conj.df['_limitado_wan']
  X_final = core_features.matriz(conj.df[treino], features)
  y_final = conj.df.loc[treino, ALVO].astype(float)

  mlflow.set_experiment('MLflow Wifi Regressions')
  for config in CONFIGS:
    with mlflow.start_run(run_name=f"{nome_modelo}-{config['model_type']}-{config['max_depth']}"):
      mlflow.log_params({
        'modelo_versao': nome_modelo, 'alvo': ALVO,
        'datasets': ','.join(conj.datasets),
        'fingerprints': ','.join(impressoes[i] for i in conj.datasets),
        'versao_tabela': core_features.versao_tabela(),
        'versao_catalogo': core_features.CATALOGO_VERSAO,
        'versao_regua': core_avaliacao.VERSAO_REGUA,
        'features': ','.join(features),
        'removidas_por_vazamento': ','.join(removidas),
        **config,
      })
      prev = core_avaliacao.prever_fora_do_fold(conj.df, features, ALVO, vazadas, estimador=montar(config))
      resumo = core_avaliacao.resumir(prev, len(features))
      registrar_metricas(resumo)
      final = montar(config).fit(X_final, y_final)
      mlflow.sklearn.log_model(sk_model=final, name=config['model_type'], serialization_format='skops')
      print('-' * 61)
      print(f"{config['model_type']} {config}: R² pooled {resumo['pooled']} "
            f"(90%: {resumo['intervalos'].get('pooled')}), MAE {resumo['mae']}, MAE log {resumo['mae_log']}")
      print(f"  por prédio: {resumo['por_local']}")


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Conferir que importa e lê o registro sem rodar o MLflow**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); import ml.regression_mlflow as m; print(m.ALVO, len(m.CONFIGS))"`
Expected: `speedtest_down_mbps 6`

- [ ] **Step 3: Rodar de verdade**

Run: `MODELO=v2-tr069 python3 src/ml/regression_mlflow.py 2>&1 | tail -20`
Expected: avisos da carga (testes falhos, linhas sem stats de estação, linhas no teto de WAN), `Modelo: v2-tr069 — 10 features ... datasets ['20260827-metrics.zip', ...]`, e 6 blocos com R² pooled, intervalo, MAE e "por prédio" com as 4 chaves `casa-marcelo`, `coworking`, `hotmilk` e `residencia`. Sem traceback.

- [ ] **Step 4: Checkpoint.** Peça ao usuário para revisar e commitar (Task 15). Lembre que `mlruns/` está no `.gitignore`.

---

### Task 16: `regression_benchmark.py` sobre a régua

**Files:**
- Modify: `src/ml/regression_benchmark.py`

- [ ] **Step 1: Trocar carga, folds e defaults**

Em `src/ml/regression_benchmark.py`:

1. Imports: troque `from ml.core.data import SITE_COLUMN, load_datasets, validate_columns` e `from ml.core.splits import outer_logo_folds` por:

```python
from ml.core import avaliacao as core_avaliacao
from ml.core import carga as core_carga
from ml.core import features as core_features
from ml.core import modelos as core_modelos
from ml.core.data import validate_columns
```

2. Apague a lista `DEFAULT_FEATURES` (são as features da `v1`, com contadores que vazam). `DEFAULT_FEATURES_STATS` fica.

3. Troque `evaluate_target` inteira por:

```python
def evaluate_target(conj, features, models, shap_config=None):
  """Avalia cada modelo pela régua (LOGO por prédio, teto de WAN, intervalos)."""
  target = conj.alvo
  vazadas = [c for c, k in conj.classes.items() if k is not None and k.vazamento]
  removidas = [f for f in features if f in vazadas]
  if removidas:
    print(f'features com vazamento fora da conta: {removidas}')
  features = [f for f in features if f not in vazadas]
  validate_columns(conj.df, features, 'feature')
  assert_comparable_scales(conj.df[target], conj.df['_site'], target)
  sites = sorted(conj.df['_site'].unique())
  print(format_fold_plan([tuple(s for s in sites if s != t) for t in sites], sites, group_level='building'))

  rows = []
  shap_rankings = []
  for name, model in models.items():
    fold_explanations = []

    def explicar(fold, fitted, name=name, fold_explanations=fold_explanations):
      if shap_config is None or not shap_config.wants(name):
        return
      # Uma falha do shap nunca pode custar as tabelas de r2/rmse do fold.
      try:
        explanation = explain_fold(fitted, fold.X_train, fold.X_test, name, shap_config)
        fold_explanations.append(explanation)
        if shap_config.per_fold:
          save_beeswarm(
            explanation,
            f'{target} - {name} - fold test_site={fold.test_site}',
            os.path.join(shap_config.out_dir, target, 'folds',
                         f'{name}_{fold.test_site}_beeswarm.png'),
            shap_config.max_display)
      except Exception as error:
        print(f'WARNING: shap falhou em {name}/{target}/{fold.test_site}: {error}')

    prev = core_avaliacao.prever_fora_do_fold(conj.df, features, target, vazadas, estimador=model,
                                              ao_ajustar=explicar)
    for site, grupo in prev.groupby('_site'):
      rows.append({'model': name, 'test_site': site,
                   **regression_metrics(grupo['y'].to_numpy(dtype=float), grupo['yhat'].to_numpy(dtype=float))})
    resumo = core_avaliacao.resumir(prev, len(features))
    print(f"{name}: R² pooled {resumo['pooled']} (90%: {resumo['intervalos'].get('pooled')}), "
          f"MAE {resumo['mae']} (90%: {resumo['intervalos'].get('mae')}), MAE log {resumo['mae_log']}")
    if fold_explanations:
      try:
        pooled = concat_explanations(fold_explanations)
        save_beeswarm(
          pooled,
          f'{target} - {name} - linhas fora do site, {len(fold_explanations)} folds agrupados',
          os.path.join(shap_config.out_dir, target, f'{name}_beeswarm.png'),
          shap_config.max_display)
        ranking = mean_abs_shap_frame(pooled.values, pooled.feature_names)
        ranking.insert(0, 'model', name)
        shap_rankings.append(ranking)
      except Exception as error:
        print(f'WARNING: shap agrupado falhou em {name}/{target}: {error}')

  shap_ranking = pd.concat(shap_rankings, ignore_index=True) if shap_rankings else None
  if shap_ranking is not None:
    csv_path = os.path.join(shap_config.out_dir, target, 'mean_abs_shap.csv')
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    shap_ranking.to_csv(csv_path, index=False)
    print(f'wrote {csv_path}')
  return pd.DataFrame(rows), shap_ranking
```

(Se `clone` de `sklearn.base` ficar sem uso no arquivo, remova o import.)

4. Em `parse_args`, troque o argumento `--csv` (obrigatório) e o `--group-level` por:

```python
  parser.add_argument('--datasets', default='',
                      help='Nomes de arquivo em data/, separados por vírgula (padrão: o conjunto canônico do Studio)')
  parser.add_argument('--csv', default=None,
                      help='REMOVIDO; use --datasets com nomes de data/')
  parser.add_argument('--group-level', default=None,
                      help='IGNORED; o grupo é sempre o prédio')
```

e troque o `--features`:

```python
  parser.add_argument(
    "--features",
    default="",
    help="Features separadas por vírgula (padrão: as da versão ativa em core/modelos.json)",
  )
```

5. Em `main`:
- Acrescente `('--group-level', args.group_level, 'the group is always the building'),` à tupla `ignored_flags`.
- Logo depois do laço `for flag, value, reason in ignored_flags:`, acrescente:

```python
  if args.csv is not None:
    raise SystemExit('--csv saiu: use --datasets com nomes de data/ (padrão: o conjunto canônico)')
```

- Troque a escolha de features e a carga:

```python
  if args.use_stats == True:
    features = DEFAULT_FEATURES_STATS
  else:
    features = parse_csv_list(args.features)
  targets = parse_csv_list(args.targets)

  df = load_datasets(parse_csv_list(args.csv), group_level=args.group_level)
  validate_columns(df, features, 'feature')
  validate_columns(df, targets, 'target')
```

por:

```python
  if args.use_stats == True:
    features = DEFAULT_FEATURES_STATS
  elif args.features:
    features = parse_csv_list(args.features)
  else:
    features = core_modelos.ativo(core_modelos.carregar())
  targets = parse_csv_list(args.targets)
  ids = parse_csv_list(args.datasets) or None
  tabela = core_features.carregar_tabela()
```

- Troque as quatro linhas `print(f'Dataset rows: ...')`, `print(f'Sites: ...')`, `print(f'Group level: ...')`, `print(f'Features ...')` por:

```python
  print(f'Features ({len(features)}): {features}')
```

- No laço por alvo, troque:

```python
    results, shap_ranking = evaluate_target(df, features, target, models, args.group_level,
                                            shap_config)
```

por:

```python
    conj = core_carga.carregar(target, ids=ids, tabela=tabela)
    for aviso in conj.avisos:
      print(f'aviso: {aviso}')
    print(f'Linhas: {len(conj.df)}  Prédios: {sorted(conj.df["_site"].unique())}  Datasets: {conj.datasets}')
    results, shap_ranking = evaluate_target(conj, features, models, shap_config)
```

- [ ] **Step 2: Conferir que não sobrou referência antiga**

Run: `grep -n "load_datasets\|SITE_COLUMN\|outer_logo_folds\|DEFAULT_FEATURES\b\|args.csv\b.*parse\|group_level=args" src/ml/regression_benchmark.py`
Expected: nenhuma linha.

- [ ] **Step 3: Rodar de verdade (rápido: um alvo, sem SHAP)**

Run: `python3 src/ml/regression_benchmark.py --targets speedtest_down_mbps 2>&1 | tail -25`
Expected: o plano de folds com `leave-one-building-out` e os 4 prédios, uma linha por modelo com R² pooled e intervalo, e as tabelas por prédio de `r2` e `rmse`. Sem traceback.

- [ ] **Step 4: Checkpoint.** Peça ao usuário para revisar e commitar (Task 16).

---

### Task 17: Experimento — v2 na régua nova e `v3-tr069`

**Files:**
- Modify: `src/ml/core/modelos.json` (via `salvar_versao`)

- [ ] **Step 1: Medir a `v2-tr069` na régua nova**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M
from ml.studio import api
ds = ','.join(C.ids_padrao(C.descobertos()))
v2 = M.carregar()['versoes']['v2-tr069']['features']
av = api.avaliacao_completa(ds, '', v2)
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms'):
  r = av[alvo]
  print(alvo, 'R2', r['pooled'], r['intervalos'].get('pooled'), 'MAE', r['mae'], r['intervalos'].get('mae'),
        'MAElog', r['mae_log'], 'por_local', r['por_local'])
print('atende', json.dumps(av['atende_throughput'], ensure_ascii=False))
EOF
```

Expected: uma linha por alvo e uma de `atende`. Anote os números de download, upload e `atende` para o CHANGELOG (passo 2 do experimento da spec, seção 6.3).

- [ ] **Step 2: Salvar a `v3-tr069` com a avaliação da régua nova**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys; sys.path.insert(0, 'src')
from ml.core import carga as C, features as F, modelos as M
from ml.studio import api
ds = ','.join(C.ids_padrao(C.descobertos()))
v3 = M.carregar()['versoes']['v2-tr069']['features'] + ['n_clients', 'concorrentes_mesmo_radio']
av = api.avaliacao_completa(ds, '', v3)
M.salvar_versao('v3-tr069', v3,
  'v2-tr069 + concorrência (n_clients e concorrentes_mesmo_radio). Em produção as duas '
  'dependem de o coletor ler estações ativas por rádio (spec 2026-10-05, seção 9).',
  api._colunas_conhecidas(), F.carregar_tabela(), origem='studio', avaliacao=av)
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  r = av[alvo]
  print(alvo, 'R2', r['pooled'], r['intervalos'].get('pooled'), 'MAE', r['mae'], r['intervalos'].get('mae'),
        'MAElog', r['mae_log'], 'por_local', r['por_local'])
print('atende', av['atende_throughput']['media'], av['atende_throughput']['intervalo'])
print('ativo continua', M.carregar()['ativo'])
EOF
```

Expected: os números da `v3-tr069` e `ativo continua v1`.

- [ ] **Step 3: Veredito de promoção v3 contra v2**

Run:

```bash
python3 - <<'EOF' 2>&1 | grep -v Warning
import sys, json; sys.path.insert(0, 'src')
from ml.core import carga as C, modelos as M
from ml.studio import api
api._modelos_cache.clear()
ds = ','.join(C.ids_padrao(C.descobertos()))
v3 = M.carregar()['versoes']['v3-tr069']['features']
for alvo in ('speedtest_down_mbps', 'speedtest_up_mbps'):
  r = api.modelos_avaliar(features=','.join(v3), ds=ds, alvo=alvo, base='v2-tr069')
  print(alvo, json.dumps(r['promocao'], ensure_ascii=False))
EOF
```

Expected: um `promocao` por alvo, com `delta_mae`, `delta_atende` e `veredito`. Anote para o CHANGELOG.

- [ ] **Step 4: Rodar a suíte**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `OK (skipped=1)`

---

### Task 18: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (entrada nova no topo)

- [ ] **Step 1: Escrever a entrada**

No topo de `CHANGELOG.md`, antes da entrada de 2026-10-02, com os números medidos na Task 17 no lugar de cada `<…>`. Os `<…>` são valores a copiar da saída dos comandos, não texto a inventar:

```markdown
# Changelog — Régua única, carga canônica e concorrência

**Data:** 2026-10-05

## Por quê

O Studio e os scripts de treino mediam com réguas diferentes: `regression_mlflow.py` agrupava por
posição (o mesmo prédio no treino e no teste), usava um fold só e lia um CSV antigo. E o fator que
mais move o download, quantos clientes testam ao mesmo tempo, não entrava em nenhuma versão: no
hotmilk o download mediano cai de 121 para 36 Mbps com 2 clientes.

## Mudanças

- `core/carga.py`: uma carga só para Studio e scripts. Descoberta e duplicatas (antes no Studio),
  `concorrentes_mesmo_radio` (clientes em teste simultâneo no mesmo `bssid`), descarte de linhas sem
  stats de estação (taxa PHY, SNR e sinal vazios), marca `_limitado_wan` (alvo no teto do plano de
  internet: residência 154/99 Mbps) e a chave `_linha`, estável entre alvos.
- `core/avaliacao.py`: uma régua só. LOGO por prédio, linhas no teto de WAN fora do treino e
  previsão cortada no teto, MAE em escala log, intervalo de 90% por bootstrap de posições,
  "atende em throughput" por aplicação (acurácia balanceada) e veredito de promoção pelo intervalo
  da diferença. Versão da régua `2026-10-05.1`.
- Limiares de aplicação saem do `studio.js` para `core/aplicacoes.json`.
- `n_clients` e `concorrentes_mesmo_radio` passam a `tr069`, marcadas como dependentes do coletor.
- `regression_mlflow.py` e `regression_benchmark.py` medem pela régua e leem o conjunto canônico
  (`DATASETS=` / `--datasets`). `--csv` e `DS_CSV` saíram.
- Nova `v3-tr069` (`v2-tr069` + concorrência), não ativa.

## Efeito medido (deixando um prédio de fora, 4 prédios)

| Versão | Régua | Download R² pooled (90%) | Download MAE (90%) | Atende (90%) |
|---|---|---|---|---|
| v2-tr069 | antiga | 0,59 | 45,0 | – |
| v2-tr069 | nova | <R² v2> (<lo> a <hi>) | <MAE v2> (<lo> a <hi>) | <atende v2> (<lo> a <hi>) |
| v3-tr069 | nova | <R² v3> (<lo> a <hi>) | <MAE v3> (<lo> a <hi>) | <atende v3> (<lo> a <hi>) |

Veredito de promoção v3 contra v2: download <resultado> (<motivo>); upload <resultado> (<motivo>).

## Para o responsável pela coleta

Ver `docs/superpowers/specs/2026-10-05-regua-unica-concorrencia-design.md`, seção 9: token
versionado em `src/get-all.py`, snapshot pré-teste, estações ativas por rádio, rodízio de clientes e
roteadores, `run_id` repetido e plano de WAN de cada local.

## Fica para depois

Frentes C (dados externos e fine-tuning) e D (latência e jitter): spec, seção 10.

---
```

- [ ] **Step 2: Conferir que não sobrou `<` de valor a preencher**

Run: `sed -n 1,60p CHANGELOG.md | grep -n "<"`
Expected: nenhuma linha.

- [ ] **Step 3: Checkpoint final.** Rode `python3 -m unittest discover -s tests -q` mais uma vez, mostre `git status --short` e peça ao usuário para revisar e commitar (Tasks 17 e 18).

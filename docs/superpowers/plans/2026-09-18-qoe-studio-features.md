# QoE Studio: view Features (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **POLÍTICA DE COMMIT (override do projeto):** o dono do repositório faz **todos** os commits e pushes.
> Nenhum agente deve executar os passos marcados **"Commit (AÇÃO DO USUÁRIO)"**. Nesses passos, pare, mostre o
> comando e espere.

> **Modelo:** este plano é executado com o **Sonnet**, e quem troca o modelo é o usuário.

**Goal:** criar a view **Features** do QoE Studio, que classifica a proveniência de cada coluna coletada (TR-069 ou auxiliar), mede o teto de desempenho de cada conjunto de features, o ganho de cada candidata TR-069 e se o TR-069 reconstrói as métricas auxiliares. Tudo isso sem deixar coluna com vazamento chegar a um ajuste.

**Architecture:**
- `src/ml/core/features.py` guarda a tabela de classificação (um JSON versionado, que o Studio grava) e o catálogo curado de derivadas.
- `src/ml/studio/features.py` tem as funções puras de análise (inventário, teto, ganho +1, proxy) sobre `core.splits`.
- `api.py` expõe `GET /api/features/inventario`, `GET /api/features/ajuste` e `POST /api/columns`.
- No front, `features.js` desenha a view e `graficos.js` ganha o gráfico de pontos.

**Tech Stack:** Python 3.12, pandas, scikit-learn (RandomForest + LOGO), FastAPI, `unittest`, JavaScript sem build (canvas).

**Spec:** `docs/superpowers/specs/2026-09-18-qoe-studio-features-planta-design.md`, seções 1 a 7 e 9 a 13.

---

## Antes de começar

- **O código deste plano já foi validado** numa cópia isolada do repositório: os testes novos e os antigos do `core` passam, os endpoints foram exercitados com `curl`, e a view foi renderizada com os dados reais do 0827 nos temas claro e escuro. **Copie o código literalmente.** Se algo divergir, pare e reporte em vez de improvisar.
- Rode tudo a partir da raiz do repositório, com o Python do venv: `./venv/bin/python`.
- Os testes usam `unittest`, como `tests/test_ml_core.py`: `./venv/bin/python -m unittest tests/<arquivo>.py -v`.
- O venv não tem `httpx`, então não existe `TestClient` do FastAPI. As rotas são verificadas com `curl` contra o servidor rodando.
- `GET /api/features/ajuste` leva **~80 s** no 0827. Isso é esperado: o botão da view mostra um cronômetro, e o resultado fica em cache.
- Estilo do projeto: indentação de 2 espaços, comentários curtos em português, sem emoji (use ícones SVG).

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `.gitignore` | alterar | ignorar `.superpowers/` (mockups do brainstorming) |
| `requirements.txt` | alterar | declarar `fastapi` e `uvicorn` (já usados pelo Studio) |
| `src/ml/core/column_provenance.json` | criar | tabela de classificação: prefixos + entradas exatas |
| `src/ml/core/arquivos.py` | criar | `gravar_json_atomico` (usado aqui e na fase da planta) |
| `src/ml/core/features.py` | criar | carregar/validar/classificar/sugerir/gravar; derivadas; `MODELO_ATUAL` |
| `src/ml/studio/features.py` | criar | `preparar`, `inventario`, `elegiveis`, `ajuste` |
| `src/ml/studio/data.py` | alterar | `descobertos()`: `discover()` uma vez por processo |
| `src/ml/studio/api.py` | substituir | rotas de features e gravação só a partir de loopback |
| `src/ml/studio/static/graficos.js` | alterar | `VENKO.drawDotRows` (gráfico do teto) |
| `src/ml/studio/static/features.js` | criar | a view Features |
| `src/ml/studio/static/index.html` | alterar | ícone, item de navegação, seção, scripts `?v=2` |
| `src/ml/studio/static/studio.js` | alterar | título da view e chamada de `V.views.features.render` |
| `src/ml/studio/static/styles.css` | alterar | estilos da view |
| `tests/test_features_core.py` | criar | 20 testes do núcleo |
| `tests/test_studio_features.py` | criar | 14 testes da análise |

---

### Task 0: Branch e arrumação

**Files:**
- Modify: `.gitignore`
- Modify: `requirements.txt`

- [ ] **Step 1: Conferir o estado do repositório**

Run: `git status --short`
Expected: só arquivos não rastreados, `?? .superpowers/`, `?? docs/planta/` e `?? docs/superpowers/...` (a spec e estes planos). Se aparecer qualquer arquivo modificado, **pare e pergunte ao usuário**.

- [ ] **Step 2: Atualizar o master e criar a branch**

```bash
git fetch origin
git checkout master
git merge --ff-only origin/master
git checkout -b qoe-studio-features-planta
```
Expected: o `merge --ff-only` avança o `master` até o merge do PR #2 (`0049290`), sem conflito. Os arquivos não rastreados vêm junto.

- [ ] **Step 3: Ignorar os mockups do brainstorming**

Acrescente uma linha ao final de `.gitignore`:
```
.superpowers/
```

- [ ] **Step 4: Declarar as dependências do Studio**

Acrescente ao final de `requirements.txt`:
```
fastapi
uvicorn
```

- [ ] **Step 5: Conferir**

Run: `git status --short`
Expected: ` M .gitignore`, ` M requirements.txt`, `?? docs/planta/` e `?? docs/superpowers/...`. O `.superpowers/` não aparece mais.

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO)**

```bash
git add .gitignore requirements.txt
git commit -m "chore: ignora mockups do brainstorming e declara dependencias do Studio"
```

---

### Task 1: Semente da tabela de classificação

**Files:**
- Create: `src/ml/core/column_provenance.json` (gerado)

A semente é gerada **uma vez** por um script que não fica no repositório. O regex de vazamento é aplicado só aqui; a tabela guarda apenas entradas explícitas.

- [ ] **Step 1: Gerar a semente**

Run (da raiz do repositório):
```bash
./venv/bin/python - <<'PYEOF'
import io, json, os, re, sys, zipfile
import pandas as pd

colunas = set()
for nome in sorted(os.listdir('data')):
  path = os.path.join('data', nome)
  if nome.endswith('.zip'):
    with zipfile.ZipFile(path) as z:
      csv = [x for x in z.namelist() if x.endswith('.csv')][0]
      colunas |= set(pd.read_csv(io.BytesIO(z.read(csv)), nrows=1).columns)
  elif nome.endswith('.csv'):
    colunas |= set(pd.read_csv(path, nrows=1).columns)

T = {}
def put(coluna, classe, **extra):
  T[coluna] = {'classe': classe, **extra}

for c in ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms', 'qoe_dw_score']:
  put(c, 'alvo')
for c in ['_time', 'stored_at', 'run_id', 'session_id', 'client_id', 'client_ID', 'old_client_id', 'client_name',
          'mac', 'bssid', 'ssid', 'local', 'local_test', 'combo', 'n_clients', 'router_model',
          'site_survey_strongest_ssid', 'stats_80211_raw', 'stats_80211_client_raw', 'stats_80211_global_timestamp',
          'stats_80211_client_assoc_ap', 'stats_80211_client_retry_top_flow_key',
          'stats_80211_global_retry_top_flow_key']:
  put(c, 'identificador')
for c in ['distance_m', 'related_distance', 'obstacles', 'house_x0', 'house_y0', 'house_z0',
          'router_x', 'router_y', 'router_z', 'station_x', 'station_y', 'station_z']:
  put(c, 'geometria')
for c in ['temperature_c', 'humidity_pct']:
  put(c, 'ambiente')
for c in ['RSSI', 'signal_level', 'link_speed_mbps', 'channel_width', 'client_opportunity_medium_use']:
  put(c, 'cliente')
put('AP_channel', 'tr069', parametro='Device.WiFi.Radio.{i}.Channel')
put('radio', 'tr069', parametro='Device.WiFi.Radio.{i}.OperatingFrequencyBand')
put('client_mode', 'tr069', parametro='Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.OperatingStandard')

P = {'router_': {'classe': 'tr069'}, 'stats_80211_': {'classe': 'sniffer'}, 'site_survey_': {'classe': 'cliente'},
     'download_': {'classe': 'cliente', 'vazamento': True}, 'upload_': {'classe': 'cliente', 'vazamento': True}}

def resolver(coluna):
  if coluna in T:
    return T[coluna]
  casados = [p for p in P if coluna.startswith(p)]
  return P[max(casados, key=len)] if casados else None

VAZA = re.compile(r'bytes|packets|throughput|_frames|_count$|_data$|qos_data|_msdu_total|subframes|elapsed')
NAO_VAZA = {'router_expected_throughput_mbps', 'stats_80211_per_ap_count', 'stats_80211_per_client_count'}
for c in sorted(colunas):
  r = resolver(c)
  if (r and r['classe'] in ('tr069', 'sniffer', 'cliente') and not r.get('vazamento')
      and VAZA.search(c) and c not in NAO_VAZA):
    T[c] = {'classe': r['classe'], 'vazamento': True}

sem_regra = sorted(c for c in colunas if resolver(c) is None)
with open('src/ml/core/column_provenance.json', 'w', encoding='utf-8') as handle:
  handle.write(json.dumps({'prefixos': P, 'colunas': T}, sort_keys=True, indent=2, ensure_ascii=False) + '\n')
print(f'{len(colunas)} colunas | sem regra: {sem_regra} | exatas: {len(T)} | '
      f'vazamento: {sum(1 for v in T.values() if v.get("vazamento"))}')
PYEOF
```
Expected, exatamente:
```
174 colunas | sem regra: [] | exatas: 92 | vazamento: 42
```

- [ ] **Step 2: Conferir as entradas que importam**

Run:
```bash
./venv/bin/python -c "
import json; t = json.load(open('src/ml/core/column_provenance.json'))
c = t['colunas']
print(c['router_expected_throughput_mbps'] if 'router_expected_throughput_mbps' in c else 'expected_throughput: so prefixo (sem vazamento)')
print(c['client_opportunity_medium_use'], c['router_tx_bytes'], c['AP_channel'])
print(sorted(t['prefixos']))"
```
Expected:
```
expected_throughput: so prefixo (sem vazamento)
{'classe': 'cliente'} {'classe': 'tr069', 'vazamento': True} {'classe': 'tr069', 'parametro': 'Device.WiFi.Radio.{i}.Channel'}
['download_', 'router_', 'site_survey_', 'stats_80211_', 'upload_']
```

- [ ] **Step 3: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/core/column_provenance.json
git commit -m "feat(core): semente da tabela de proveniencia das colunas"
```

---

### Task 2: Núcleo de classificação e derivadas

**Files:**
- Create: `src/ml/core/arquivos.py`
- Create: `src/ml/core/features.py`
- Test: `tests/test_features_core.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_features_core.py`:
```python
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core import features as F


def tabela_exemplo():
  return {
    'prefixos': {
      'router_': {'classe': 'tr069'},
      'router_tx_': {'classe': 'tr069', 'vazamento': True},
      'stats_80211_': {'classe': 'sniffer'},
    },
    'colunas': {
      'router_x': {'classe': 'geometria'},
      'RSSI': {'classe': 'cliente'},
      'client_id': {'classe': 'identificador'},
      'client_mode': {'classe': 'tr069'},
      'site_survey_total_aps': {'classe': 'cliente'},
    },
  }


class TestClassificar(unittest.TestCase):
  def test_entrada_exata_vence_prefixo(self):
    c = F.classificar('router_x', tabela_exemplo())
    self.assertEqual((c.classe, c.origem), ('geometria', 'exata'))

  def test_prefixo_mais_longo_vence(self):
    c = F.classificar('router_tx_bytes', tabela_exemplo())
    self.assertEqual((c.classe, c.vazamento, c.origem), ('tr069', True, 'prefixo'))
    c = F.classificar('router_snr', tabela_exemplo())
    self.assertEqual((c.classe, c.vazamento), ('tr069', False))

  def test_coluna_sem_regra_devolve_none(self):
    self.assertIsNone(F.classificar('temperature_c', tabela_exemplo()))


class TestSugerir(unittest.TestCase):
  def test_mais_tokens_em_comum_vence(self):
    self.assertEqual(F.sugerir('site_survey_new_metric', tabela_exemplo()), 'cliente')

  def test_empate_entre_classes_devolve_none(self):
    # client_id (identificador) e client_mode (tr069) empatam em 1 token.
    self.assertIsNone(F.sugerir('client_power', tabela_exemplo()))

  def test_sem_token_em_comum_devolve_none(self):
    self.assertIsNone(F.sugerir('humidity_pct', tabela_exemplo()))


class TestValidar(unittest.TestCase):
  def test_classe_invalida_levanta(self):
    with self.assertRaises(ValueError):
      F.validar_regra('x', {'classe': 'router'})

  def test_campo_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      F.validar_regra('x', {'classe': 'tr069', 'nota': 'oi'})

  def test_tabela_sem_secao_levanta(self):
    with self.assertRaises(ValueError):
      F.validar_tabela({'colunas': {}})


class TestGravar(unittest.TestCase):
  def setUp(self):
    self.pasta = tempfile.mkdtemp()
    self.path = os.path.join(self.pasta, 'tabela.json')
    with open(self.path, 'w', encoding='utf-8') as handle:
      json.dump(tabela_exemplo(), handle)

  def tearDown(self):
    shutil.rmtree(self.pasta)

  def test_grava_e_le_de_volta(self):
    F.gravar_classificacao('temperature_c', 'ambiente', False, None, {'temperature_c'}, path=self.path)
    c = F.classificar('temperature_c', F.carregar_tabela(self.path))
    self.assertEqual((c.classe, c.vazamento, c.origem), ('ambiente', False, 'exata'))

  def test_vazamento_e_parametro_sao_gravados(self):
    F.gravar_classificacao('AP_channel', 'tr069', True, 'Device.WiFi.Radio.{i}.Channel',
                           {'AP_channel'}, path=self.path)
    regra = F.carregar_tabela(self.path)['colunas']['AP_channel']
    self.assertEqual(regra, {'classe': 'tr069', 'vazamento': True,
                             'parametro': 'Device.WiFi.Radio.{i}.Channel'})

  def test_chaves_ordenadas_e_sem_temporario(self):
    F.gravar_classificacao('temperature_c', 'ambiente', False, None, {'temperature_c'}, path=self.path)
    with open(self.path, encoding='utf-8') as handle:
      texto = handle.read()
    self.assertLess(texto.index('"RSSI"'), texto.index('"client_id"'))
    self.assertTrue(texto.endswith('\n'))
    self.assertEqual(os.listdir(self.pasta), ['tabela.json'])

  def _ler(self):
    with open(self.path, encoding='utf-8') as handle:
      return handle.read()

  def test_classe_invalida_nao_grava(self):
    antes = self._ler()
    with self.assertRaises(ValueError):
      F.gravar_classificacao('temperature_c', 'clima', False, None, {'temperature_c'}, path=self.path)
    self.assertEqual(self._ler(), antes)

  def test_coluna_inexistente_levanta(self):
    with self.assertRaises(ValueError):
      F.gravar_classificacao('nao_existe', 'ambiente', False, None, {'temperature_c'}, path=self.path)


class TestDerivadas(unittest.TestCase):
  def test_classe_tr069_so_se_todos_insumos_forem_tr069(self):
    t = tabela_exemplo()
    so_tr069 = F.Derivada('d', ('router_snr', 'router_noise'), lambda df: df.router_snr, '')
    mista = F.Derivada('d', ('RSSI', 'router_snr'), lambda df: df.RSSI, '')
    self.assertEqual(F.classificar_derivada(so_tr069, t).classe, 'tr069')
    self.assertEqual(F.classificar_derivada(mista, t).classe, F.CLASSE_AUXILIAR)

  def test_vazamento_herdado_e_anulado_por_normaliza_volume(self):
    t = tabela_exemplo()
    herda = F.Derivada('d', ('router_tx_bytes', 'router_snr'), lambda df: df.router_snr, '')
    normaliza = F.Derivada('d', ('router_tx_bytes', 'router_snr'), lambda df: df.router_snr, '',
                           normaliza_volume=True)
    self.assertTrue(F.classificar_derivada(herda, t).vazamento)
    self.assertFalse(F.classificar_derivada(normaliza, t).vazamento)

  def test_insumo_sem_classificacao_devolve_none(self):
    d = F.Derivada('d', ('temperature_c',), lambda df: df.temperature_c, '')
    self.assertIsNone(F.classificar_derivada(d, tabela_exemplo()))

  def test_divisao_por_zero_vira_nan(self):
    df = pd.DataFrame({'router_tx_retries': [4.0, 3.0], 'router_tx_packets': [2.0, 0.0]})
    saida, _ = F.aplicar_derivadas(df, catalogo=[F.CATALOGO[0]])
    self.assertEqual(saida['retry_por_pacote'].iloc[0], 2.0)
    self.assertTrue(np.isnan(saida['retry_por_pacote'].iloc[1]))

  def test_insumo_ausente_omite_com_aviso(self):
    df = pd.DataFrame({'router_tx_retries': [1.0]})
    saida, avisos = F.aplicar_derivadas(df, catalogo=[F.CATALOGO[0]])
    self.assertNotIn('retry_por_pacote', saida.columns)
    self.assertEqual(len(avisos), 1)


class TestSemente(unittest.TestCase):
  def test_semente_do_repositorio_e_valida(self):
    tabela = F.carregar_tabela()
    self.assertEqual(F.classificar('router_expected_throughput_mbps', tabela).vazamento, False)
    self.assertEqual(F.classificar('client_opportunity_medium_use', tabela).classe, 'cliente')
    self.assertTrue(F.classificar('router_tx_bytes', tabela).vazamento)


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_features_core.py -v`
Expected: erro de importação, `ImportError: cannot import name 'features' from 'ml.core'`.

- [ ] **Step 3: Criar a escrita atômica**

Crie `src/ml/core/arquivos.py`:
```python
import json
import os
import tempfile


def gravar_json_atomico(path: str, dados) -> None:
  """Grava JSON com chaves ordenadas via arquivo temporário + os.replace.

  Quem lê nunca vê um arquivo pela metade, e a ordem estável deixa o git diff limpo.
  """
  texto = json.dumps(dados, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
  pasta = os.path.dirname(os.path.abspath(path))
  fd, temporario = tempfile.mkstemp(dir=pasta, prefix='.tmp-', suffix='.json')
  try:
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
      handle.write(texto)
    os.replace(temporario, path)
  except BaseException:
    if os.path.exists(temporario):
      os.unlink(temporario)
    raise
```

- [ ] **Step 4: Criar o núcleo**

Crie `src/ml/core/features.py`:
```python
"""Proveniência das colunas coletadas e catálogo curado de features derivadas.

A tabela vive em column_provenance.json, versionada e gravada pelo QoE Studio.
Coluna sem regra nunca é adivinhada: `classificar` devolve None.
"""

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ml.core.arquivos import gravar_json_atomico

TABELA_PATH = os.path.join(os.path.dirname(__file__), 'column_provenance.json')

CLASSES = ('tr069', 'sniffer', 'cliente', 'ambiente', 'geometria', 'identificador', 'alvo')
# Só derivadas recebem esta classe: algum insumo não é TR-069.
CLASSE_AUXILIAR = 'auxiliar'

# Cópia de compare_protocols.FEATURES. Unificar as duas listas está fora do escopo.
MODELO_ATUAL = (
  'router_expected_throughput_mbps', 'router_noise', 'router_rx_drop_misc',
  'router_rx_duration_us', 'router_rx_rate_mbps', 'router_signal_avg_dbm',
  'router_signal_dbm', 'router_snr', 'router_tx_duration_us', 'router_tx_failed',
  'router_tx_rate_mbps', 'router_tx_retries', 'router_opportunity_medium_use',
  'client_opportunity_medium_use',
)

_lock = threading.Lock()


@dataclass(frozen=True)
class Classificacao:
  classe: str
  vazamento: bool
  parametro: Optional[str]
  origem: str


def validar_regra(nome: str, regra) -> None:
  if not isinstance(regra, dict) or regra.get('classe') not in CLASSES:
    raise ValueError(f'{nome!r}: classe inválida em {regra!r}; esperado uma de {list(CLASSES)}')
  extras = set(regra) - {'classe', 'vazamento', 'parametro'}
  if extras:
    raise ValueError(f'{nome!r}: campos desconhecidos {sorted(extras)}')
  if not isinstance(regra.get('vazamento', False), bool):
    raise ValueError(f'{nome!r}: vazamento precisa ser booleano')
  parametro = regra.get('parametro')
  if parametro is not None and (not isinstance(parametro, str) or len(parametro) > 200):
    raise ValueError(f'{nome!r}: parametro precisa ser texto de até 200 caracteres')


def validar_tabela(tabela) -> None:
  if not isinstance(tabela, dict) or set(tabela) != {'prefixos', 'colunas'}:
    raise ValueError("a tabela precisa ter exatamente as chaves 'prefixos' e 'colunas'")
  for secao in ('prefixos', 'colunas'):
    for nome, regra in tabela[secao].items():
      validar_regra(nome, regra)


def carregar_tabela(path: str = TABELA_PATH) -> dict:
  with open(path, encoding='utf-8') as handle:
    tabela = json.load(handle)
  validar_tabela(tabela)
  return tabela


def versao_tabela(path: str = TABELA_PATH) -> str:
  try:
    with open(path, 'rb') as handle:
      return hashlib.sha256(handle.read()).hexdigest()[:12]
  except OSError:
    return 'ausente'


def classificar(coluna: str, tabela: dict) -> Optional[Classificacao]:
  regra = tabela['colunas'].get(coluna)
  origem = 'exata'
  if regra is None:
    casados = [p for p in tabela['prefixos'] if coluna.startswith(p)]
    if not casados:
      return None
    regra = tabela['prefixos'][max(casados, key=len)]
    origem = 'prefixo'
  return Classificacao(regra['classe'], bool(regra.get('vazamento', False)),
                       regra.get('parametro'), origem)


def _tokens_em_comum(a, b) -> int:
  n = 0
  for x, y in zip(a, b):
    if not x or x != y:
      break
    n += 1
  return n


def sugerir(coluna: str, tabela: dict) -> Optional[str]:
  """Classe da coluna já declarada com mais tokens iniciais em comum (mínimo 1).

  Serve só para pré-selecionar a interface. Empate entre classes diferentes devolve None.
  """
  tokens = coluna.split('_')
  melhor, classes = 0, set()
  for nome, regra in tabela['colunas'].items():
    comum = _tokens_em_comum(tokens, nome.split('_'))
    if comum == 0:
      continue
    if comum > melhor:
      melhor, classes = comum, {regra['classe']}
    elif comum == melhor:
      classes.add(regra['classe'])
  return next(iter(classes)) if len(classes) == 1 else None


def gravar_classificacao(coluna: str, classe: str, vazamento: bool, parametro: Optional[str],
                         colunas_conhecidas, path: str = TABELA_PATH) -> dict:
  if not isinstance(coluna, str) or not coluna.strip():
    raise ValueError('coluna vazia')
  regra = {'classe': classe}
  if vazamento:
    regra['vazamento'] = vazamento
  if parametro:
    regra['parametro'] = parametro
  validar_regra(coluna, regra)
  with _lock:
    tabela = carregar_tabela(path)
    if coluna not in colunas_conhecidas and coluna not in tabela['colunas']:
      raise ValueError(f'coluna {coluna!r} não existe em nenhum dataset')
    tabela['colunas'][coluna] = regra
    gravar_json_atomico(path, tabela)
  return tabela


@dataclass(frozen=True)
class Derivada:
  nome: str
  insumos: tuple
  calcular: Callable[[pd.DataFrame], pd.Series]
  descricao: str
  normaliza_volume: bool = False


def _razao(numerador: str, denominador: str):
  return lambda df: df[numerador] / df[denominador].replace(0, np.nan)


CATALOGO_VERSAO = '2026-09-18.1'

CATALOGO = (
  Derivada('retry_por_pacote', ('router_tx_retries', 'router_tx_packets'),
           _razao('router_tx_retries', 'router_tx_packets'),
           'Retransmissões por pacote enviado: qualidade do enlace, sem depender do volume.',
           normaliza_volume=True),
  Derivada('falha_por_pacote', ('router_tx_failed', 'router_tx_packets'),
           _razao('router_tx_failed', 'router_tx_packets'),
           'Falhas de envio por pacote.', normaliza_volume=True),
  Derivada('bytes_por_pacote_tx', ('router_tx_bytes', 'router_tx_packets'),
           _razao('router_tx_bytes', 'router_tx_packets'),
           'Tamanho médio do quadro enviado; depende do tipo de tráfego do teste.'),
  Derivada('eficiencia_phy', ('router_expected_throughput_mbps', 'router_tx_rate_mbps'),
           _razao('router_expected_throughput_mbps', 'router_tx_rate_mbps'),
           'Throughput esperado pelo rate control sobre a taxa PHY de envio.'),
  Derivada('instabilidade_sinal', ('router_signal_dbm', 'router_signal_avg_dbm'),
           lambda df: df['router_signal_dbm'] - df['router_signal_avg_dbm'],
           'Sinal instantâneo menos a média: variação do enlace.'),
  Derivada('assimetria_phy', ('router_tx_rate_mbps', 'router_rx_rate_mbps'),
           _razao('router_tx_rate_mbps', 'router_rx_rate_mbps'),
           'Taxa PHY de envio sobre a de recepção.'),
  Derivada('fracao_airtime_tx', ('router_tx_duration_us', 'router_rx_duration_us'),
           lambda df: df['router_tx_duration_us']
           / (df['router_tx_duration_us'] + df['router_rx_duration_us']).replace(0, np.nan),
           'Fração do tempo de rádio gasta enviando.'),
  Derivada('largura_x_nss', ('router_bandwith_TX_station', 'router_NSS_TX_Station'),
           lambda df: df['router_bandwith_TX_station'] * df['router_NSS_TX_Station'],
           'Largura de canal vezes fluxos espaciais: capacidade nominal do enlace.'),
  Derivada('assimetria_enlace', ('RSSI', 'router_signal_dbm'),
           lambda df: df['RSSI'] - df['router_signal_dbm'],
           'RSSI visto pelo cliente menos o sinal visto pelo roteador.'),
)


def classificar_derivada(derivada: Derivada, tabela: dict) -> Optional[Classificacao]:
  insumos = [classificar(c, tabela) for c in derivada.insumos]
  if any(c is None for c in insumos):
    return None
  classe = 'tr069' if all(c.classe == 'tr069' for c in insumos) else CLASSE_AUXILIAR
  vazamento = any(c.vazamento for c in insumos) and not derivada.normaliza_volume
  return Classificacao(classe, vazamento, None, 'derivada')


def aplicar_derivadas(df: pd.DataFrame, catalogo=CATALOGO):
  """Devolve (df com as derivadas calculáveis, avisos das que faltaram insumo)."""
  novas, avisos = {}, []
  for derivada in catalogo:
    faltando = [c for c in derivada.insumos if c not in df.columns]
    if faltando:
      avisos.append(f'derivada {derivada.nome} omitida: faltam {faltando}')
      continue
    novas[derivada.nome] = derivada.calcular(df).astype(float)
  if not novas:
    return df.copy(), avisos
  return pd.concat([df, pd.DataFrame(novas, index=df.index)], axis=1), avisos
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_features_core.py -v`
Expected: `Ran 20 tests` e `OK`.

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/core/arquivos.py src/ml/core/features.py tests/test_features_core.py
git commit -m "feat(core): classificacao de colunas por proveniencia e catalogo de derivadas"
```

---

### Task 3: Análise da view Features

**Files:**
- Create: `src/ml/studio/features.py`
- Test: `tests/test_studio_features.py`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_studio_features.py`:
```python
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.studio import features as SF

TABELA = {
  'prefixos': {'router_': {'classe': 'tr069'}, 'stats_80211_': {'classe': 'sniffer'}},
  'colunas': {
    'speedtest_down_mbps': {'classe': 'alvo'},
    'speedtest_up_mbps': {'classe': 'alvo'},
    'latency_ms': {'classe': 'alvo'},
    'jitter_ms': {'classe': 'alvo'},
    'local': {'classe': 'identificador'},
    'client_id': {'classe': 'identificador'},
    'router_tx_bytes': {'classe': 'tr069', 'vazamento': True},
    'AP_channel': {'classe': 'cliente'},
    'radio': {'classe': 'tr069'},
  },
}

LOCAIS = ['sala', 'quarto', 'suite', 'cwpb-1', 'cwpb-2']


def frame(locais=LOCAIS, linhas_por_local=12, seed=0):
  rng = np.random.default_rng(seed)
  n = len(locais) * linhas_por_local
  snr = np.tile([10.0, 20.0, 30.0, 40.0], n // 4 + 1)[:n]
  sinal = rng.normal(-60, 5, n)
  down = 2 * snr + rng.normal(0, 1, n)
  potencia = rng.normal(20, 1, n)
  potencia[::2] = np.nan
  dup = rng.normal(0, 1, n)
  return pd.DataFrame({
    'local': np.repeat(locais, linhas_por_local),
    'client_id': np.arange(n),
    'speedtest_down_mbps': down,
    'speedtest_up_mbps': down / 2,
    'latency_ms': rng.normal(20, 2, n),
    'jitter_ms': rng.normal(3, 1, n),
    'router_snr': snr,
    'router_signal_dbm': sinal,
    'router_power_dbm': potencia,
    'router_nss': rng.integers(1, 3, n).astype(float),
    'router_tx_bytes': down * 1000,
    'AP_channel': snr * 10,
    'radio': np.where(np.arange(n) % 2, '2.4ghz', '5ghz'),
    'stats_80211_a': dup,
    'stats_80211_b': dup,
    'stats_80211_zero': 0.0,
    'mystery_col': rng.normal(0, 1, n),
  })


class Base(unittest.TestCase):
  def setUp(self):
    self._arvores = (SF.ARVORES, SF.ARVORES_PROXY)
    SF.ARVORES, SF.ARVORES_PROXY = 25, 25

  def tearDown(self):
    SF.ARVORES, SF.ARVORES_PROXY = self._arvores


class TestPreparar(Base):
  def test_descarta_linhas_sem_alvo_e_avisa(self):
    f = frame()
    f.loc[0, 'speedtest_down_mbps'] = np.nan
    conj = SF.preparar({'a.csv': f}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(len(conj.df), len(f) - 1)
    self.assertTrue(any('1 linhas sem' in a for a in conj.avisos))

  def test_posicoes_e_dataset_de_origem(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    self.assertEqual(sorted(conj.df['_site'].unique()),
                     ['cwpb-1', 'cwpb-2', 'res-quarto', 'res-sala', 'res-suite'])
    self.assertEqual(set(conj.df['_ds']), {'a.csv'})

  def test_alvo_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      SF.preparar({'a.csv': frame()}, 'router_snr', TABELA)


class TestInventario(Base):
  def setUp(self):
    super().setUp()
    self.inv = SF.inventario(SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA))
    self.por_nome = {c['coluna']: c for c in self.inv['colunas']}

  def test_coluna_sem_regra_vai_para_sem_classificacao(self):
    self.assertEqual([c['coluna'] for c in self.inv['sem_classificacao']], ['mystery_col'])
    self.assertNotIn('mystery_col', self.por_nome)

  def test_constante_e_cobertura(self):
    self.assertTrue(self.por_nome['stats_80211_zero']['constante'])
    self.assertEqual(self.por_nome['router_power_dbm']['cobertura'], 0.5)

  def test_grupos_identicos_ignoram_constantes(self):
    self.assertEqual(self.inv['grupos_identicos'], [['stats_80211_a', 'stats_80211_b']])

  def test_suspeita_so_sem_vazamento(self):
    self.assertTrue(self.por_nome['router_snr']['suspeita'])
    self.assertFalse(self.por_nome['router_tx_bytes']['suspeita'])

  def test_alvo_nao_tem_rho(self):
    self.assertIsNone(self.por_nome['speedtest_up_mbps']['rho'])

  def test_candidatas_excluem_modelo_vazamento_e_baixa_cobertura(self):
    self.assertIn('router_nss', self.inv['candidatas'])
    self.assertNotIn('router_snr', self.inv['candidatas'])
    self.assertNotIn('router_tx_bytes', self.inv['candidatas'])
    self.assertNotIn('router_power_dbm', self.inv['candidatas'])

  def test_categorica_de_baixa_cardinalidade(self):
    self.assertEqual(self.por_nome['radio']['tipo'], 'categorica')


class TestElegiveis(Base):
  def test_filtros(self):
    inv = SF.inventario(SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA))
    ok = SF.elegiveis(inv)
    for fora in ('router_tx_bytes', 'stats_80211_zero', 'router_power_dbm', 'client_id',
                 'speedtest_down_mbps', 'stats_80211_b'):
      self.assertNotIn(fora, ok)
    for dentro in ('router_snr', 'radio', 'AP_channel', 'stats_80211_a'):
      self.assertIn(dentro, ok)


class TestAjuste(Base):
  def test_vazamento_nunca_chega_ao_ajuste(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    with self.assertRaises(AssertionError):
      SF.r2_por_posicao(conj.df, ['router_snr', 'router_tx_bytes'], 'speedtest_down_mbps',
                        ['router_tx_bytes'])

  def test_ajuste_completo(self):
    conj = SF.preparar({'a.csv': frame()}, 'speedtest_down_mbps', TABELA)
    aj = SF.ajuste(conj, SF.inventario(conj))
    self.assertEqual(set(aj['teto']), {'atual', 'tr069', 'tudo'})
    self.assertEqual(len(aj['teto']['tudo']['por_posicao']), 5)
    self.assertTrue(all(g['posicoes'] == 5 for g in aj['ganho']))
    canal = next(p for p in aj['proxy'] if p['coluna'] == 'AP_channel')
    self.assertTrue(canal['parece_tr069'])
    self.assertEqual(aj['avisos'], [])

  def test_poucas_posicoes_vira_aviso(self):
    conj = SF.preparar({'a.csv': frame(locais=['sala', 'quarto', 'suite'])}, 'speedtest_down_mbps', TABELA)
    aj = SF.ajuste(conj, SF.inventario(conj))
    self.assertTrue(any(a.startswith('só 3 posições') for a in aj['avisos']))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_features.py -v`
Expected: erro de importação, `ImportError: cannot import name 'features' from 'ml.studio'`.

- [ ] **Step 3: Criar a análise**

Crie `src/ml/studio/features.py`:
```python
"""Análise da view Features: inventário de colunas, teto, ganho +1 e proxies.

Funções puras sobre DataFrames. O api.py descobre os datasets e cuida do cache.
"""

import hashlib
import re
import time
import warnings
from dataclasses import dataclass, field
from statistics import mean

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline

from ml.core import features as F
from ml.core.sites import resolve_site_id
from ml.core.splits import outer_logo_folds

TARGETS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')

COBERTURA_MIN = 0.7
RHO_SUSPEITA = 0.9
PROXY_ALCANCAVEL = 0.7
PROXY_PARCIAL = 0.3
PROXY_TR069 = 0.99
MAX_PROXIES = 15
MAX_CATEGORIAS = 10
ARVORES = 200
ARVORES_PROXY = 100
CLASSES_FORA_DOS_AJUSTES = {'identificador', 'geometria', 'alvo'}
CLASSES_AUXILIARES = {'sniffer', 'cliente', 'ambiente'}
_INTERNAS = ('_ds', '_site')


@dataclass
class Conjunto:
  df: pd.DataFrame
  alvo: str
  datasets: list
  classes: dict
  tabela: dict
  avisos: list = field(default_factory=list)


def preparar(frames: dict, alvo: str, tabela: dict) -> Conjunto:
  """Junta os frames, descarta linhas sem alvo/posição e calcula as derivadas."""
  if alvo not in TARGETS:
    raise ValueError(f'alvo {alvo!r} desconhecido; esperado um de {list(TARGETS)}')
  if not frames:
    raise ValueError('nenhum dataset não-legacy ativo')
  avisos = []
  df = pd.concat([f.assign(_ds=ds) for ds, f in frames.items()], ignore_index=True)
  if alvo not in df.columns:
    raise ValueError(f'o alvo {alvo!r} não existe nos datasets ativos')
  sem_alvo = int(df[alvo].isna().sum())
  if sem_alvo:
    avisos.append(f'{sem_alvo} linhas sem {alvo} descartadas')
  df = df[df[alvo].notna()]

  posicoes = {}
  for valor in df['local'].dropna().unique():
    try:
      posicoes[valor] = resolve_site_id(pd.Series([valor])).iloc[0]
    except ValueError:
      pass
  fora = int((~df['local'].isin(list(posicoes))).sum())
  if fora:
    avisos.append(f'{fora} linhas com local desconhecido em core/sites.py descartadas')
  df = df[df['local'].isin(list(posicoes))].reset_index(drop=True)
  df['_site'] = df['local'].map(posicoes)

  df, avisos_derivadas = F.aplicar_derivadas(df)
  avisos += avisos_derivadas

  derivadas = {d.nome: d for d in F.CATALOGO}
  classes = {}
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    if coluna in derivadas:
      classes[coluna] = F.classificar_derivada(derivadas[coluna], tabela)
    else:
      classes[coluna] = F.classificar(coluna, tabela)
  return Conjunto(df, alvo, sorted(frames), classes, tabela, avisos)


def _tipo(serie: pd.Series) -> str:
  if pd.api.types.is_numeric_dtype(serie):
    return 'numerica'
  return 'categorica' if serie.nunique(dropna=True) <= MAX_CATEGORIAS else 'categorica_alta'


def _amostra(serie: pd.Series) -> str:
  valores = serie.dropna()
  if valores.empty:
    return 'vazia'
  if pd.api.types.is_numeric_dtype(valores):
    return f'{valores.min():.4g} a {valores.max():.4g}'
  return ', '.join(str(v) for v in valores.unique()[:3])


def _grupos_identicos(df: pd.DataFrame, colunas: list) -> list:
  por_hash = {}
  for coluna in colunas:
    valores = df[coluna].astype(float).round(9)
    digest = hashlib.sha1(pd.util.hash_pandas_object(valores, index=False).values.tobytes()).hexdigest()
    por_hash.setdefault(digest, []).append(coluna)
  return sorted(sorted(g) for g in por_hash.values() if len(g) > 1)


def inventario(conj: Conjunto) -> dict:
  df, alvo = conj.df, conj.alvo
  derivadas = {d.nome: d for d in F.CATALOGO}
  cobertura_ds = df.drop(columns=list(_INTERNAS)).notna().groupby(df['_ds']).mean()
  colunas, sem_classificacao, numericas = [], [], []
  for coluna in df.columns:
    if coluna in _INTERNAS:
      continue
    serie = df[coluna]
    c = conj.classes.get(coluna)
    tipo = _tipo(serie)
    constante = serie.nunique(dropna=True) <= 1
    cobertura = round(float(serie.notna().mean()), 3)
    if c is None:
      sem_classificacao.append({'coluna': coluna, 'sugestao': F.sugerir(coluna, conj.tabela),
                                'cobertura': cobertura, 'amostra': _amostra(serie)})
      continue
    rho = None
    if tipo == 'numerica' and not constante and c.classe != 'alvo':
      par = pd.concat([serie, df[alvo]], axis=1).dropna()
      if len(par) >= 3 and par.iloc[:, 0].nunique() > 1:
        rho = round(abs(float(par.iloc[:, 0].corr(par.iloc[:, 1], method='spearman'))), 3)
    if tipo == 'numerica' and not constante:
      numericas.append(coluna)
    colunas.append({
      'coluna': coluna, 'classe': c.classe, 'origem': c.origem, 'vazamento': c.vazamento,
      'parametro': c.parametro, 'derivada': coluna in derivadas,
      'normaliza_volume': coluna in derivadas and derivadas[coluna].normaliza_volume,
      'cobertura': cobertura,
      'cobertura_por_ds': {ds: round(float(v), 3) for ds, v in cobertura_ds[coluna].items()},
      'constante': bool(constante), 'tipo': tipo, 'rho': rho,
      'no_modelo': coluna in F.MODELO_ATUAL,
      'suspeita': rho is not None and rho >= RHO_SUSPEITA and not c.vazamento,
    })
  classe_de = {c['coluna']: c['classe'] for c in colunas}
  candidatas = [c['coluna'] for c in colunas
                if c['classe'] == 'tr069' and not c['no_modelo'] and not c['vazamento']
                and not c['constante'] and c['cobertura'] >= COBERTURA_MIN]
  contagem = {}
  for c in colunas:
    contagem[c['classe']] = contagem.get(c['classe'], 0) + 1
  avisos = list(conj.avisos)
  ausentes = [m for m in F.MODELO_ATUAL if m not in df.columns]
  if ausentes:
    avisos.append(f'features do modelo atual ausentes neste conjunto: {ausentes}')
  return {
    'alvo': alvo,
    'datasets': conj.datasets,
    'n_linhas': int(len(df)),
    'posicoes': sorted(df['_site'].unique()),
    'colunas': colunas,
    'candidatas': candidatas,
    'sem_classificacao': sem_classificacao,
    'grupos_identicos': _grupos_identicos(df, numericas),
    'modelo_fora_do_tr069': [m for m in F.MODELO_ATUAL if classe_de.get(m) not in (None, 'tr069')],
    'contagem_por_classe': contagem,
    'avisos': avisos,
  }


def elegiveis(inv: dict) -> list:
  repetidas = set()
  for grupo in inv['grupos_identicos']:
    repetidas.update(grupo[1:])
  return [c['coluna'] for c in inv['colunas']
          if c['classe'] not in CLASSES_FORA_DOS_AJUSTES
          and not c['vazamento'] and not c['constante']
          and c['cobertura'] >= COBERTURA_MIN
          and c['tipo'] != 'categorica_alta'
          and c['coluna'] not in repetidas]


def matriz(df: pd.DataFrame, colunas: list) -> pd.DataFrame:
  partes = []
  for coluna in colunas:
    serie = df[coluna]
    if pd.api.types.is_numeric_dtype(serie):
      partes.append(serie.astype(float).rename(coluna))
    else:
      partes.append(pd.get_dummies(serie.astype('string'), prefix=coluna, dtype=float))
  return pd.concat(partes, axis=1)


def assert_sem_vazamento(colunas, vazadas) -> None:
  proibidas = sorted(set(colunas) & set(vazadas))
  if proibidas:
    raise AssertionError(f'colunas com vazamento chegaram a um ajuste: {proibidas}')


def _modelo(arvores: int) -> Pipeline:
  return Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('reg', RandomForestRegressor(n_estimators=arvores, min_samples_leaf=2, n_jobs=-1, random_state=42)),
  ])


def r2_por_posicao(df, colunas, y_col, vazadas, arvores=None, min_teste=1, min_treino=1) -> dict:
  assert_sem_vazamento(colunas, vazadas)
  if not colunas:
    return {}
  sub = df[df[y_col].notna()].reset_index(drop=True)
  X = matriz(sub, colunas)
  y = sub[y_col].astype(float)
  resultado = {}
  for fold in outer_logo_folds(X, y, sub['_site']):
    if len(fold.y_test) < min_teste or len(fold.y_train) < min_treino:
      continue
    modelo = _modelo(arvores or ARVORES).fit(fold.X_train, fold.y_train)
    resultado[fold.test_site] = float(r2_score(fold.y_test, modelo.predict(fold.X_test)))
  return resultado


def _resumo(por_posicao: dict, n: int) -> dict:
  return {'n': n, 'media': round(mean(por_posicao.values()), 4) if por_posicao else None,
          'por_posicao': {s: round(v, 4) for s, v in sorted(por_posicao.items())}}


def _leitura(r2: float) -> str:
  if r2 >= PROXY_ALCANCAVEL:
    return 'alcancavel'
  return 'parcial' if r2 >= PROXY_PARCIAL else 'laboratorio'


_POUCAS_POSICOES = re.compile(r'only (\d+) sites available')


def ajuste(conj: Conjunto, inv: dict) -> dict:
  inicio = time.time()
  df, alvo = conj.df, conj.alvo
  ok = elegiveis(inv)
  por_nome = {c['coluna']: c for c in inv['colunas']}
  vazadas = [c['coluna'] for c in inv['colunas'] if c['vazamento']]
  tr069 = [c for c in ok if por_nome[c]['classe'] == 'tr069']
  atual = [c for c in F.MODELO_ATUAL if c in ok]
  avisos = []
  with warnings.catch_warnings(record=True) as capturados:
    warnings.simplefilter('always')
    brutos = {nome: r2_por_posicao(df, cols, alvo, vazadas)
              for nome, cols in (('atual', atual), ('tr069', tr069), ('tudo', ok))}
    teto = {nome: _resumo(brutos[nome], n) for nome, n in
            (('atual', len(atual)), ('tr069', len(tr069)), ('tudo', len(ok)))}

    ganho = []
    base = brutos['atual']
    if base:
      for coluna in [c for c in inv['candidatas'] if c in ok]:
        r = r2_por_posicao(df, atual + [coluna], alvo, vazadas)
        deltas = [r[s] - base[s] for s in base if s in r]
        ganho.append({'coluna': coluna, 'delta': round(mean(deltas), 4),
                      'melhora': sum(d > 0 for d in deltas), 'posicoes': len(deltas)})
    ganho.sort(key=lambda g: -g['delta'])

    proxy = []
    auxiliares = [por_nome[c] for c in ok if por_nome[c]['classe'] in CLASSES_AUXILIARES
                  and por_nome[c]['tipo'] == 'numerica' and por_nome[c]['rho'] is not None]
    auxiliares.sort(key=lambda c: -c['rho'])
    if auxiliares and not tr069:
      avisos.append('nenhuma coluna TR-069 elegível: proxies não calculados')
    for c in auxiliares[:MAX_PROXIES] if tr069 else []:
      r = r2_por_posicao(df, tr069, c['coluna'], vazadas, arvores=ARVORES_PROXY, min_teste=5, min_treino=20)
      if not r:
        continue
      valores = list(r.values())
      media = mean(valores)
      proxy.append({'coluna': c['coluna'], 'classe': c['classe'], 'rho': c['rho'],
                    'r2': round(media, 4), 'min': round(min(valores), 4), 'max': round(max(valores), 4),
                    'leitura': _leitura(media), 'parece_tr069': min(valores) >= PROXY_TR069})

  for aviso in capturados:
    casou = _POUCAS_POSICOES.search(str(aviso.message))
    if casou:
      avisos.append(f'só {casou.group(1)} posições: a dispersão por posição não é interpretável '
                    'e a estimativa é instável')
  return {
    'alvo': alvo, 'datasets': conj.datasets, 'posicoes': inv['posicoes'],
    'teto': teto, 'ganho': ganho, 'proxy': proxy,
    'avisos': sorted(set(avisos)), 'segundos': round(time.time() - inicio, 1),
  }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_features.py -v`
Expected: `Ran 14 tests` e `OK`, em alguns segundos. Os testes reduzem as árvores para 25 no `setUp`.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `./venv/bin/python -m unittest discover -s tests -p "test_*.py"`
Expected: `OK`. A linha `dropped 1 rows with empty target 'target'` vem de um teste antigo e é esperada.

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/studio/features.py tests/test_studio_features.py
git commit -m "feat(studio): inventario, teto, ganho +1 e proxy da view Features"
```

---

### Task 4: Rotas no servidor

**Files:**
- Modify: `src/ml/studio/data.py` (antes de `def _superseded` e dentro de `build_payload`)
- Replace: `src/ml/studio/api.py`

- [ ] **Step 1: Cachear a descoberta dos datasets**

Em `src/ml/studio/data.py`, substitua:
```python
def _superseded(datasets: list) -> dict:
```
por:
```python
_descobertos = None


def descobertos() -> list:
  """discover() uma vez por processo: reler o zip de 52 MB a cada requisicao travaria as views."""
  global _descobertos
  if _descobertos is None:
    _descobertos = discover()
  return _descobertos


def _superseded(datasets: list) -> dict:
```

E, dentro de `build_payload`, substitua:
```python
def build_payload() -> dict:
  datasets = discover()
```
por:
```python
def build_payload() -> dict:
  datasets = descobertos()
```

- [ ] **Step 2: Substituir o `api.py`**

Substitua todo o conteúdo de `src/ml/studio/api.py` por:
```python
"""Servidor local do QoE Studio.

O payload sai inteiro numa chamada e o recalculo de limiares acontece no cliente.
As unicas escritas sao arquivos versionados do repositorio, aceitas so a partir
da propria maquina; o commit e sempre humano.
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ml.core import features as core_features
from ml.studio import features as studio_features
from ml.studio.data import build_payload, descobertos

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)

_cache = {}
_ajustes = {}


def _payload() -> dict:
  if 'payload' not in _cache:
    _cache['payload'] = build_payload()
  return _cache['payload']


@app.get('/api/payload')
def payload():
  """Varre o repositorio e devolve o payload. Cacheado por processo.

  Reiniciar o servidor e o jeito de recarregar apos um `git pull` — deliberado:
  uma varredura por requisicao releria todo o CSV a cada F5.
  """
  return JSONResponse(_payload())


def _so_local(request: Request) -> None:
  if request.client is None or request.client.host not in LOOPBACK:
    raise HTTPException(403, 'gravação só é aceita a partir da própria máquina')


def _tabela():
  try:
    return core_features.carregar_tabela(), None
  except (OSError, ValueError) as erro:
    return {'prefixos': {}, 'colunas': {}}, f'tabela de classificação ilegível: {erro}'


def _conjunto(ds: str, alvo: str):
  pedidos = [x for x in ds.split(',') if x]
  por_id = {d['id']: d for d in descobertos() if d.get('usable')}
  desconhecidos = [x for x in pedidos if x not in por_id]
  if desconhecidos:
    raise HTTPException(400, f'datasets desconhecidos: {desconhecidos}')
  frames = {x: por_id[x]['_frame'] for x in pedidos if por_id[x]['generation'] == 'current'}
  legacy = [x for x in pedidos if por_id[x]['generation'] != 'current']
  tabela, erro_tabela = _tabela()
  try:
    conj = studio_features.preparar(frames, alvo, tabela)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  if legacy:
    conj.avisos.insert(0, f'datasets legacy ignorados nesta view: {legacy}')
  return conj, erro_tabela


@app.get('/api/features/inventario')
def features_inventario(ds: str = '', alvo: str = 'speedtest_down_mbps'):
  conj, erro_tabela = _conjunto(ds, alvo)
  inv = studio_features.inventario(conj)
  inv['tabela_erro'] = erro_tabela
  return inv


@app.get('/api/features/ajuste')
def features_ajuste(ds: str = '', alvo: str = 'speedtest_down_mbps'):
  conj, _ = _conjunto(ds, alvo)
  chave = (tuple(conj.datasets), alvo, core_features.versao_tabela(), core_features.CATALOGO_VERSAO)
  if chave not in _ajustes:
    try:
      _ajustes[chave] = studio_features.ajuste(conj, studio_features.inventario(conj))
    except ValueError as erro:
      raise HTTPException(422, str(erro))
  return _ajustes[chave]


class NovaClassificacao(BaseModel):
  coluna: str
  classe: str
  vazamento: bool = False
  parametro: Optional[str] = None


@app.post('/api/columns')
def classificar_coluna(corpo: NovaClassificacao, request: Request):
  _so_local(request)
  conhecidas = set()
  for d in descobertos():
    if d.get('usable'):
      conhecidas.update(d['_frame'].columns)
  try:
    core_features.gravar_classificacao(corpo.coluna, corpo.classe, corpo.vazamento,
                                       corpo.parametro, conhecidas)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  _ajustes.clear()
  return {'ok': True}


app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')
```

- [ ] **Step 3: Subir o servidor**

Run (em segundo plano): `./venv/bin/python src/ml/studio.py --port 8100`
Expected: `QoE Studio  ->  http://127.0.0.1:8100`.

- [ ] **Step 4: Verificar o inventário e os erros**

Run:
```bash
B=http://127.0.0.1:8100
curl -s "$B/api/features/inventario?ds=20260827-metrics.zip,metrics-office-20260722.csv&alvo=latency_ms" \
  | ./venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print(d['n_linhas'], d['posicoes'], d['avisos'], d['tabela_erro'], d['sem_classificacao'], d['modelo_fora_do_tr069'])"
curl -s -w " %{http_code}\n" "$B/api/features/inventario?ds=nao_existe.csv"
curl -s -w " %{http_code}\n" "$B/api/features/inventario?ds=20260827-metrics.zip&alvo=router_snr"
curl -s -w " %{http_code}\n" "$B/api/features/inventario?ds=metrics-office-20260722.csv"
curl -s -w " %{http_code}\n" -X POST $B/api/columns -H 'Content-Type: application/json' -d '{"coluna":"nao_existe","classe":"tr069"}'
curl -s -w " %{http_code}\n" -X POST $B/api/columns -H 'Content-Type: application/json' -d '{"coluna":"channel_width","classe":"xyz"}'
```
Expected:
```
638 ['cwpb-1', 'cwpb-2', 'res-quarto', 'res-sala', 'res-suite'] ["datasets legacy ignorados nesta view: ['metrics-office-20260722.csv']"] None [] ['client_opportunity_medium_use']
{"detail":"datasets desconhecidos: ['nao_existe.csv']"} 400
{"detail":"alvo 'router_snr' desconhecido; esperado um de ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']"} 422
{"detail":"nenhum dataset não-legacy ativo"} 422
{"detail":"coluna 'nao_existe' não existe em nenhum dataset"} 422
{"detail":"'channel_width': classe inválida em {'classe': 'xyz'}; esperado uma de ['tr069', 'sniffer', 'cliente', 'ambiente', 'geometria', 'identificador', 'alvo']"} 422
```

- [ ] **Step 5: Verificar o ajuste (~80 s)**

Run:
```bash
time curl -s "http://127.0.0.1:8100/api/features/ajuste?ds=20260827-metrics.zip&alvo=speedtest_down_mbps" \
  | ./venv/bin/python -c "import json,sys; d=json.load(sys.stdin); print({k:(v['n'],v['media']) for k,v in d['teto'].items()}); print([(p['coluna'],p['parece_tr069']) for p in d['proxy'] if p['parece_tr069']]); print(d['avisos'])"
```
Expected (o tempo fica perto de 80 s):
```
{'atual': (14, 0.685), 'tr069': (29, 0.7151), 'tudo': (85, 0.7239)}
[('channel_width', True)]
[]
```
Rodar a mesma linha de novo devolve na hora, porque o resultado fica em cache.

- [ ] **Step 6: Parar o servidor**

Encerre o processo iniciado no Step 3.

- [ ] **Step 7: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/studio/data.py src/ml/studio/api.py
git commit -m "feat(studio): rotas de inventario, ajuste e classificacao de colunas"
```

---

### Task 5: Gráfico de pontos do teto

**Files:**
- Modify: `src/ml/studio/static/graficos.js` (antes do bloco `/* ---------- hover partilhado ---------- */`)

- [ ] **Step 1: Inserir `VENKO.drawDotRows`**

Em `src/ml/studio/static/graficos.js`, substitua:
```javascript
  /* ---------- hover partilhado ---------- */
```
por:
```javascript
  /* ---------- pontos por linha: teto de desempenho ----------
     Eixo truncado de proposito: barras a partir de zero esconderiam
     diferencas de 0,02 entre conjuntos. Ponto nao carrega essa mentira. */
  VENKO.drawDotRows = function (canvas, spec) {
    const rowH = 52;
    const top = 10;
    const bottom = 30;
    const H = top + spec.rows.length * rowH + bottom;
    const { ctx, width } = prepare(canvas, H);
    const left = 178;
    const right = 74;
    const all = spec.rows.flatMap((r) => r.points.map((p) => p.v).concat([r.mean]))
      .filter((v) => v != null);
    if (!all.length) return [];
    let lo = Math.min(...all);
    let hi = Math.max(...all);
    const pad = Math.max(0.02, (hi - lo) * 0.08);
    lo -= pad; hi += pad;
    const x = (v) => left + ((v - lo) / (hi - lo)) * (width - left - right);
    const fmt = spec.fmt || ((v) => v.toFixed(2));
    const font = '11px system-ui, -apple-system, sans-serif';
    const bold = '600 12.5px system-ui, -apple-system, sans-serif';

    ctx.strokeStyle = css('--grid');
    ctx.lineWidth = 1;
    ctx.fillStyle = css('--ink-muted');
    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    niceTicks(lo, hi, 5).filter((t) => t >= lo && t <= hi).forEach((t) => {
      const X = Math.round(x(t)) + 0.5;
      ctx.beginPath(); ctx.moveTo(X, top); ctx.lineTo(X, H - bottom); ctx.stroke();
      ctx.fillText(fmt(t), X, H - bottom + 8);
    });

    const hits = [];
    spec.rows.forEach((r, i) => {
      const cy = top + i * rowH + rowH / 2;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = css('--ink-1'); ctx.font = bold;
      ctx.fillText(r.label, 0, cy - 7);
      ctx.fillStyle = css('--ink-muted'); ctx.font = font;
      ctx.fillText(r.sub, 0, cy + 9);
      if (r.mean != null) {
        ctx.strokeStyle = css('--ink-1'); ctx.lineWidth = 2.5;
        ctx.beginPath(); ctx.moveTo(x(r.mean), cy - 15); ctx.lineTo(x(r.mean), cy + 15); ctx.stroke();
        ctx.fillStyle = css('--ink-1'); ctx.font = bold;
        ctx.fillText((spec.fmtMean || fmt)(r.mean), width - right + 14, cy);
        hits.push({ x: x(r.mean), y: cy, r: 10, label: r.label, value: r.mean, at: 'média' });
      }
      r.points.forEach((p) => {
        const X = x(p.v);
        // Anel na cor da superficie: pontos de posicoes vizinhas nao se fundem.
        ctx.beginPath(); ctx.arc(X, cy, 7, 0, Math.PI * 2); ctx.fillStyle = css('--surface-1'); ctx.fill();
        ctx.beginPath(); ctx.arc(X, cy, 5.5, 0, Math.PI * 2); ctx.fillStyle = p.color; ctx.fill();
        hits.push({ x: X, y: cy, r: 9, label: r.label, value: p.v, at: p.key, color: p.color });
      });
    });
    return hits;
  };

  /* ---------- hover partilhado ---------- */
```

- [ ] **Step 2: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/graficos.js && echo ok`
Expected: `ok`

---

### Task 6: A view no navegador

**Files:**
- Create: `src/ml/studio/static/features.js`
- Modify: `src/ml/studio/static/index.html`
- Modify: `src/ml/studio/static/studio.js`
- Modify: `src/ml/studio/static/styles.css`

- [ ] **Step 1: Criar `features.js`**

Crie `src/ml/studio/static/features.js`:
```javascript
/* features.js — view Features. Estado proprio; studio.js chama render(ctx)
   sempre que a view esta visivel e algo muda (datasets, tema, resize). */
(function () {
  'use strict';
  const V = window.VENKO;
  V.views = V.views || {};
  const $ = (s) => document.querySelector(s);

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const num = (v, d) => (v == null ? '–'
    : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sinal = (v, d = 3) => (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d);
  const pct = (v) => Math.round(v * 100) + '%';
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const CLASSES = [['tr069', 'TR-069'], ['sniffer', 'Sniffer'], ['cliente', 'Cliente'],
    ['ambiente', 'Ambiente'], ['geometria', 'Geometria'], ['identificador', 'Identificador'], ['alvo', 'Alvo']];
  const ROTULO = Object.fromEntries(CLASSES.concat([['auxiliar', 'Auxiliar']]));
  const LEITURA = { alcancavel: ['ok', 'alcançável'], parcial: ['mid', 'parcial'], laboratorio: ['lab', 'só laboratório'] };
  const VAZAMENTO = 'Medida durante o teste: carrega o próprio alvo e não existe em produção.';

  const st = { ctx: null, alvo: 'speedtest_down_mbps', inv: null, invKey: null, invErro: null,
               aj: null, ajKey: null, ajHora: null, ajErro: null, rodando: false, inicio: 0,
               relogio: null, salvarErro: null, hits: null, abertos: [] };

  const chave = () => st.ctx.enabledIds.slice().sort().join(',') + '|' + st.alvo;
  const query = () => 'ds=' + encodeURIComponent(st.ctx.enabledIds.join(',')) +
    '&alvo=' + encodeURIComponent(st.alvo);

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }

  function carregarInventario() {
    const k = chave();
    if (st.invKey === k) return;
    st.invKey = k; st.inv = null; st.invErro = null;
    pedir('api/features/inventario?' + query())
      .then((inv) => { if (st.invKey === k) st.inv = inv; })
      .catch((e) => { if (st.invKey === k) st.invErro = e.message; })
      .finally(() => { if (st.invKey === k) desenhar(); });
  }

  function rodarAnalise() {
    if (st.rodando) return;
    const k = chave();
    st.rodando = true; st.ajErro = null; st.inicio = Date.now();
    st.relogio = setInterval(() => {
      const el = $('#fRelogio');
      if (el) el.textContent = Math.round((Date.now() - st.inicio) / 1000) + ' s';
    }, 500);
    desenhar();
    pedir('api/features/ajuste?' + query())
      .then((aj) => { st.aj = aj; st.ajKey = k; st.ajHora = new Date(); })
      .catch((e) => { st.ajErro = e.message; })
      .finally(() => { clearInterval(st.relogio); st.rodando = false; desenhar(); });
  }

  function classificar(coluna, classe, vazamento, parametro) {
    st.salvarErro = null;
    pedir('api/columns', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ coluna, classe, vazamento, parametro: parametro || null }) })
      .then(() => { st.invKey = null; st.ajKey = null; carregarInventario(); })
      .catch((e) => { st.salvarErro = `${coluna}: ${e.message}`; desenhar(); });
  }

  /* ---------------- blocos ---------------- */
  const gate = (sev, titulo, msg, extra = '') => `<div class="gate ${sev}">
    <svg class="icon"><use href="#${sev === 'good' ? 'i-check' : 'i-alert'}"/></svg>
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div>${extra}</div></div>`;

  function gates(inv, porNome) {
    let html = '';
    if (st.salvarErro) html += gate('critical', 'Não foi possível salvar', esc(st.salvarErro));
    if (inv.tabela_erro) html += gate('critical', 'Tabela de classificação ilegível', esc(inv.tabela_erro));
    if (inv.sem_classificacao.length) {
      const linhas = inv.sem_classificacao.map((c) => `<div class="frow" data-col="${esc(c.coluna)}">
        <code>${esc(c.coluna)}</code>
        <span class="gate-msg">${pct(c.cobertura)} · ${esc(c.amostra)}</span>
        <select>${CLASSES.map(([k, r]) => `<option value="${k}"${k === c.sugestao ? ' selected' : ''}>${r}${k === c.sugestao ? ' (sugerido)' : ''}</option>`).join('')}</select>
        <span><label class="gate-msg" title="${VAZAMENTO}"><input type="checkbox"> vazamento</label>
          <button class="btn-pri" data-acao="adicionar">Adicionar</button></span></div>`).join('');
      html += gate('critical', `${inv.sem_classificacao.length} coluna(s) sem classificação`,
        'Ficam fora de toda a análise até alguém classificar. A sugestão vem do nome e precisa ser confirmada.',
        linhas + '<div class="gate-msg" style="margin-top:6px">Salva em <code>src/ml/core/column_provenance.json</code>. Revise no <code>git diff</code> antes do commit.</div>');
    }
    if (st.aj && st.ajKey === chave()) {
      st.aj.proxy.filter((p) => p.parece_tr069).forEach((p) => {
        html += gate('warning', `<code>${esc(p.coluna)}</code> parece ser TR-069`,
          `O TR-069 reconstrói esta coluna com R² ≥ 0,99 em todas as posições (média ${num(p.r2, 2)}).`,
          `<div style="margin-top:8px"><button class="btn" data-acao="reclassificar" data-col="${esc(p.coluna)}">Reclassificar como TR-069</button></div>`);
      });
    }
    inv.colunas.filter((c) => c.suspeita && !c.derivada).forEach((c) => {
      html += gate('warning', `<code>${esc(c.coluna)}</code> pode ter vazamento`,
        `|ρ| = ${num(c.rho, 2)} com o alvo. ${VAZAMENTO} Confirme antes de usar.`,
        `<div style="margin-top:8px"><button class="btn" data-acao="vazar" data-col="${esc(c.coluna)}">Marcar vazamento</button></div>`);
    });
    inv.modelo_fora_do_tr069.forEach((c) => {
      html += gate('warning', `<code>${esc(c)}</code> está no modelo, mas não é TR-069`,
        `Classe: ${ROTULO[porNome[c].classe]}. O ACS não lê esta coluna em produção.`);
    });
    inv.avisos.forEach((a) => { html += gate('warning', 'Aviso', esc(a)); });
    return html;
  }

  function leituraTeto(aj) {
    const t = aj.teto;
    const n = aj.posicoes.length;
    if (t.atual.media == null) return 'Nenhuma feature do modelo atual está disponível neste conjunto.';
    const d = t.tr069.media - t.atual.media;
    const melhora = Object.keys(t.atual.por_posicao)
      .filter((s) => t.tr069.por_posicao[s] > t.atual.por_posicao[s]).length;
    const dt = t.tudo.media - t.tr069.media;
    return `Todo o TR-069 rende <b>${sinal(d)}</b> sobre o modelo atual e melhora ${melhora} de ${n} posições. ` +
      (Math.abs(dt) < 0.02 ? `Somar as auxiliares não muda o teto (${num(t.tudo.media, 3)}). `
        : `Somar as auxiliares leva a ${num(t.tudo.media, 3)} (${sinal(dt)}). `) +
      `Com ${n} posições, diferenças abaixo de ~0,02 são ruído.`;
  }

  function cardTeto() {
    const atual = st.aj && st.ajKey === chave();
    let status = '';
    if (st.rodando) status = 'calculando… <span id="fRelogio">0 s</span>';
    else if (st.ajErro) status = `<span style="color:var(--critical)">${esc(st.ajErro)}</span>`;
    else if (atual) status = `calculado às ${st.ajHora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })} · ${num(st.aj.segundos, 0)} s`;
    else if (st.aj) status = 'desatualizado: o conjunto ou o alvo mudou';
    let corpo = '<p class="hint">Clique em <b>Rodar análise</b>. Leva cerca de 75 s com os dados atuais.</p>';
    if (st.aj) {
      const pos = st.aj.posicoes;
      corpo = `<div class="${atual ? '' : 'stale'}"><div class="chartwrap"><canvas id="fTeto"></canvas><div class="tooltip" id="fTetoTip"></div></div>
        <div class="serieskey">${pos.map((p, i) => `<span><i style="background:var(--s${i % 5 + 1})"></i>${esc(p)}</span>`).join('')}</div>
        <p style="margin:12px 0 0;font-size:13px">${leituraTeto(st.aj)}</p></div>`;
    }
    return `<div class="card"><div class="card-head"><div><h2>Teto de desempenho</h2>
      <p class="hint">R² LOGO do alvo com três conjuntos de features. Cada ponto é uma posição deixada de fora; a barra vertical é a média.</p></div>
      <div style="text-align:right"><button class="btn-pri" data-acao="rodar"${st.rodando ? ' disabled' : ''}>Rodar análise</button>
      <div class="status">${status}</div></div></div>${corpo}</div>`;
  }

  function desenharTeto() {
    const canvas = $('#fTeto');
    if (!canvas || !st.aj) return;
    const aj = st.aj;
    const linhas = [['atual', 'Modelo atual'], ['tr069', 'TR-069 completo'], ['tudo', 'Tudo']].map(([k, rotulo]) => ({
      label: rotulo, sub: `${aj.teto[k].n} features`, mean: aj.teto[k].media,
      points: aj.posicoes.map((p, i) => ({ key: p, v: aj.teto[k].por_posicao[p], color: cssv('--s' + (i % 5 + 1)) }))
        .filter((p) => p.v != null),
    }));
    st.hits = V.drawDotRows(canvas, { rows: linhas, fmt: (v) => num(v, 2), fmtMean: (v) => num(v, 3) });
    V.attachTooltip(canvas, $('#fTetoTip'), () => st.hits,
      (h) => `<b>${esc(h.label)}</b>${esc(h.at)}: R² ${num(h.value, 3)}`);
  }

  const barra = (v, cor) => `<i class="bar" style="width:${Math.max(0, Math.min(1, v)) * 80}px${cor ? ';background:' + cor : ''}"></i>`;

  function cardCandidatas(inv) {
    const atual = st.aj && st.ajKey === chave();
    const ganho = atual ? Object.fromEntries(st.aj.ganho.map((g) => [g.coluna, g])) : {};
    const lista = inv.colunas.filter((c) => c.classe === 'tr069' && !c.no_modelo && !c.constante && c.cobertura >= 0.7);
    const limpas = lista.filter((c) => !c.vazamento).sort((a, b) =>
      atual ? ((ganho[b.coluna] || { delta: -9 }).delta - (ganho[a.coluna] || { delta: -9 }).delta)
        : ((b.rho || 0) - (a.rho || 0)));
    const vazadas = lista.filter((c) => c.vazamento).sort((a, b) => (b.rho || 0) - (a.rho || 0));
    const tipo = (c) => c.derivada
      ? '<span class="tag">derivada</span>' + (c.normaliza_volume ? ' <span class="tag ok" title="razão entre dois contadores de volume: o volume se cancela">normaliza volume</span>' : '')
      : '<span class="tag">bruta</span>';
    const linha = (c) => {
      const g = ganho[c.coluna];
      const cel = c.vazamento ? '<td class="num" colspan="2">fora dos ajustes</td>'
        : g ? `<td class="num">${sinal(g.delta)}</td><td class="num${g.melhora === g.posicoes ? ' good' : ''}">${g.melhora}/${g.posicoes}</td>`
          : '<td class="num">–</td><td class="num">–</td>';
      const t = c.vazamento ? `<span class="tag leak" title="${VAZAMENTO}">${c.derivada ? 'vazamento herdado' : 'vazamento'}</span>` : tipo(c);
      return `<tr${c.vazamento ? ' class="dim"' : ''}><td><code>${esc(c.coluna)}</code></td><td>${t}</td>
        <td class="num">${pct(c.cobertura)}</td><td>${c.rho == null ? '–' : barra(c.rho, c.vazamento ? 'var(--grid)' : '') + num(c.rho, 2)}</td>${cel}</tr>`;
    };
    return `<div class="card"><h2>Candidatas TR-069 fora do modelo</h2>
      <p class="hint">Ganho é o ΔR² LOGO médio ao somar a coluna às features atuais. Abaixo de ~0,01 é ruído; "melhora" diz se o ganho é consistente entre posições.</p>
      ${lista.length ? `<table><thead><tr><th>Coluna</th><th>Tipo</th><th class="num">Cobertura</th><th>|ρ| com o alvo</th><th class="num">Ganho</th><th class="num">Melhora</th></tr></thead>
      <tbody>${limpas.concat(vazadas).map(linha).join('')}</tbody></table>` : '<p class="hint">Nenhuma coluna TR-069 fora do modelo neste conjunto.</p>'}</div>`;
  }

  function cardProxy(inv) {
    let corpo = '<p class="hint">Rode a análise para ver os proxies.</p>';
    if (st.aj) {
      const idem = {};
      inv.grupos_identicos.forEach((g) => g.forEach((c) => { idem[c] = g.filter((x) => x !== c); }));
      const cor = { alcancavel: 'var(--good)', parcial: 'var(--warning)', laboratorio: 'var(--axis)' };
      corpo = st.aj.proxy.length ? `<div class="${st.ajKey === chave() ? '' : 'stale'}"><table><thead><tr><th>Auxiliar</th><th>Fonte</th><th class="num">|ρ| com o alvo</th><th>R² do proxy</th><th class="num">Faixa por posição</th><th>Leitura</th></tr></thead><tbody>` +
        st.aj.proxy.map((p) => `<tr><td><code>${esc(p.coluna)}</code>${idem[p.coluna] ? `<div class="gate-msg">idêntica a <code>${esc(idem[p.coluna].join(', '))}</code></div>` : ''}</td>
          <td>${ROTULO[p.classe]}</td><td class="num">${num(p.rho, 2)}</td><td>${barra(p.r2, cor[p.leitura])}${num(p.r2, 2)}</td>
          <td class="num gate-msg">${num(p.min, 2)} a ${num(p.max, 2)}</td>
          <td><span class="tag ${LEITURA[p.leitura][0]}">${LEITURA[p.leitura][1]}</span></td></tr>`).join('') + '</tbody></table></div>'
        : '<p class="hint">Nenhuma auxiliar elegível neste conjunto.</p>';
    }
    return `<div class="card"><h2>Auxiliares: o TR-069 consegue reconstruir?</h2>
      <p class="hint">R² LOGO de "auxiliar ≈ f(todas as TR-069)". Alcançável ≥ 0,7 · parcial 0,3 a 0,7 · só laboratório &lt; 0,3. Um sinal alcançável ainda precisa de uma receita TR-069 que o reproduza, então vira ideia de derivada.</p>${corpo}</div>`;
  }

  function blocos(inv) {
    const vazadas = inv.colunas.filter((c) => c.vazamento);
    const constantes = inv.colunas.filter((c) => c.constante);
    const contagem = Object.entries(inv.contagem_por_classe).sort((a, b) => b[1] - a[1])
      .map(([k, n]) => `${ROTULO[k]} ${n}`).join(' · ');
    const codes = (xs) => xs.map((x) => `<code>${esc(x)}</code>`).join(', ');
    return `<details class="fold"><summary>Vazamento <span>· ${vazadas.length} colunas</span></summary>
        <div class="inner"><p>${VAZAMENTO} Fica fora dos ajustes.</p>${codes(vazadas.map((c) => c.coluna))}</div></details>
      <details class="fold"><summary>Qualidade das colunas <span>· ${constantes.length} constantes · ${inv.grupos_identicos.length} grupos idênticos</span></summary>
        <div class="inner"><p><b>Constantes:</b> ${codes(constantes.map((c) => c.coluna)) || '—'}</p>
        <p><b>Idênticas:</b></p><ul>${inv.grupos_identicos.map((g) => `<li>${codes(g)}</li>`).join('') || '<li>—</li>'}</ul></div></details>
      <details class="fold"><summary>Inventário completo <span>· ${inv.colunas.length} colunas · ${contagem}</span></summary>
        <div class="inner"><table><thead><tr><th>Coluna</th><th>Classe</th><th>Origem</th><th>Tipo</th><th class="num">Cobertura</th><th class="num">|ρ|</th><th>Vazamento</th></tr></thead><tbody>` +
      inv.colunas.slice().sort((a, b) => a.coluna.localeCompare(b.coluna)).map((c) => `<tr><td><code>${esc(c.coluna)}</code></td>
        <td>${ROTULO[c.classe]}</td><td>${c.origem}</td><td>${c.tipo}</td><td class="num">${pct(c.cobertura)}</td>
        <td class="num">${c.rho == null ? '–' : num(c.rho, 2)}</td><td>${c.vazamento ? 'sim' : ''}</td></tr>`).join('') +
      '</tbody></table></div></details>';
  }

  function desenhar() {
    const host = $('#fBody');
    if (!st.ctx) return;
    // Guarda quais blocos estavam abertos antes de qualquer troca de conteúdo:
    // o "Carregando…" intermediário apagaria os <details> e o estado com eles.
    const atuais = host.querySelectorAll('details.fold');
    if (atuais.length) st.abertos = [...atuais].map((d) => d.open);
    if (!st.ctx.enabledIds.length) { host.innerHTML = '<p class="hint">Nenhum dataset ativo.</p>'; $('#fChip').textContent = ''; return; }
    if (st.invErro) { host.innerHTML = gate('critical', 'Não foi possível montar o inventário', esc(st.invErro)); return; }
    if (!st.inv) { host.innerHTML = '<p class="hint">Carregando inventário…</p>'; return; }
    const inv = st.inv;
    const porNome = Object.fromEntries(inv.colunas.map((c) => [c.coluna, c]));
    $('#fChip').textContent = `${inv.datasets.join(', ')} · ${inv.n_linhas.toLocaleString('pt-BR')} amostras · ${inv.posicoes.length} posições`;
    host.innerHTML = gates(inv, porNome) + cardTeto() + cardCandidatas(inv) + cardProxy(inv) + blocos(inv);
    host.querySelectorAll('details.fold').forEach((d, i) => { d.open = !!st.abertos[i]; });
    desenharTeto();
  }

  $('#fBody').addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-acao]');
    if (!alvo) return;
    const acao = alvo.dataset.acao;
    const porNome = st.inv ? Object.fromEntries(st.inv.colunas.map((c) => [c.coluna, c])) : {};
    if (acao === 'rodar') rodarAnalise();
    if (acao === 'adicionar') {
      const linha = alvo.closest('.frow');
      classificar(linha.dataset.col, linha.querySelector('select').value, linha.querySelector('input').checked, null);
    }
    if (acao === 'reclassificar') {
      const c = porNome[alvo.dataset.col];
      classificar(c.coluna, 'tr069', false, c.parametro);
    }
    if (acao === 'vazar') {
      const c = porNome[alvo.dataset.col];
      classificar(c.coluna, c.classe, true, c.parametro);
    }
  });
  $('#fAlvo').addEventListener('change', (ev) => { st.alvo = ev.target.value; carregarInventario(); desenhar(); });

  V.views.features = {
    render(ctx) {
      st.ctx = ctx;
      carregarInventario();
      desenhar();
    },
  };
})();
```

- [ ] **Step 2: Ícone, navegação, seção e scripts no `index.html`**

Em `src/ml/studio/static/index.html`, faça quatro substituições.

(a) Substitua:
```html
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
```
por:
```html
  <symbol id="i-layers" viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
```

(b) Substitua:
```html
    <button data-view="plan"><svg class="icon"><use href="#i-plan"/></svg> Planta</button>
```
por:
```html
    <button data-view="features"><svg class="icon"><use href="#i-layers"/></svg> Features</button>
    <button data-view="plan"><svg class="icon"><use href="#i-plan"/></svg> Planta</button>
```

(c) Substitua:
```html
  <section id="view-plan" class="view hide">
```
por:
```html
  <section id="view-features" class="view hide">
    <div class="controls">
      <label for="fAlvo">Alvo</label>
      <select id="fAlvo">
        <option value="speedtest_down_mbps">Download (Mbps)</option>
        <option value="speedtest_up_mbps">Upload (Mbps)</option>
        <option value="latency_ms">Latência (ms)</option>
        <option value="jitter_ms">Jitter (ms)</option>
      </select>
      <span class="chip" id="fChip"></span>
    </div>
    <div id="fBody"></div>
  </section>

  <section id="view-plan" class="view hide">
```

(d) Substitua `styles.css?v=1` por `styles.css?v=2`, e substitua:
```html
<script src="graficos.js?v=1"></script>
<script src="studio.js?v=1"></script>
```
por:
```html
<script src="graficos.js?v=2"></script>
<script src="features.js?v=2"></script>
<script src="studio.js?v=2"></script>
```

- [ ] **Step 3: Ligar a view no `studio.js`**

Em `src/ml/studio/static/studio.js`, substitua:
```javascript
    constraint: ['Restrição dominante', 'Qual das quatro métricas reprova mais em cada posição.'],
```
por:
```javascript
    constraint: ['Restrição dominante', 'Qual das quatro métricas reprova mais em cada posição.'],
    features: ['Features', 'O que dá para levar para produção a partir do TR-069.'],
```

E, em `renderAll`, substitua:
```javascript
    if (state.view === 'plan') renderPlan();
```
por:
```javascript
    if (state.view === 'features') {
      V.views.features.render({ enabledIds: Object.keys(state.enabled).filter((id) => state.enabled[id]) });
    }
    if (state.view === 'plan') renderPlan();
```

- [ ] **Step 4: Estilos**

Acrescente ao final de `src/ml/studio/static/styles.css`:
```css
/* ---------- view Features ---------- */
code { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }
.chip { font-size: 12px; color: var(--ink-2); border: 1px solid var(--border); border-radius: 999px;
        padding: 3px 10px; background: var(--surface-1); }
.btn, .btn-pri { font: inherit; font-size: 12.5px; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.btn { border: 1px solid var(--border); background: var(--surface-1); color: var(--ink-1); }
.btn-pri { border: 1px solid var(--s1); background: var(--s1); color: #fff; font-weight: 600; }
.btn-pri:disabled { opacity: .55; cursor: progress; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }
.card-head .status { font-size: 12px; color: var(--ink-muted); margin-top: 6px; }
.frow { display: grid; grid-template-columns: minmax(180px, 1.5fr) .8fr 1fr auto; gap: 10px;
        align-items: center; padding: 7px 0; border-top: 1px solid var(--grid); font-size: 12.5px; }
.bar { display: inline-block; height: 7px; border-radius: 4px; background: var(--seq-300);
       vertical-align: middle; margin-right: 6px; }
tr.dim td { color: var(--ink-muted); }
td.good { color: var(--good); font-weight: 600; }
.tag.leak { border-color: var(--critical); color: var(--critical); }
.tag.ok { border-color: var(--good); color: var(--good); }
.tag.mid { border-color: var(--warning); color: var(--ink-2); }
.tag.lab { color: var(--ink-muted); }
.stale { opacity: .45; }
details.fold { background: var(--surface-1); border: 1px solid var(--border); border-radius: var(--radius);
               padding: 11px 16px; margin-bottom: 10px; }
details.fold summary { cursor: pointer; font-weight: 600; font-size: 13px; }
details.fold summary span { font-weight: 400; color: var(--ink-2); }
details.fold .inner { margin-top: 10px; font-size: 12.5px; color: var(--ink-2); }
```

- [ ] **Step 5: Conferir a sintaxe**

Run: `node --check src/ml/studio/static/features.js && node --check src/ml/studio/static/studio.js && echo ok`
Expected: `ok`

- [ ] **Step 6: Verificar no navegador**

Suba o servidor (`./venv/bin/python src/ml/studio.py --port 8100`) e abra `http://127.0.0.1:8100/#features`. Confira cada item:

1. Item **Features** na navegação (ícone de camadas), entre Restrição e Planta.
2. Chip: `20260827-metrics.zip · 638 amostras · 5 posições`.
3. Aviso amarelo: `client_opportunity_medium_use` **está no modelo, mas não é TR-069**.
4. "Candidatas TR-069 fora do modelo" lista as candidatas ordenadas por |ρ|, com Ganho/Melhora em "–". No fim, esmaecidas e com a tag vermelha "vazamento", aparecem `router_tx_bytes`, `router_tx_packets`, `router_rx_packets` e `router_rx_bytes`, e também `bytes_por_pacote_tx`, com a tag "vazamento herdado".
5. Clique **Rodar análise**. O cronômetro conta os segundos e, depois de ~80 s:
   - O gráfico mostra três linhas (Modelo atual 0,685; TR-069 completo 0,715; Tudo 0,724), cada uma com 5 pontos coloridos por posição e a legenda das posições.
   - A frase de leitura diz "Todo o TR-069 rende +0,030 sobre o modelo atual…".
   - A tabela de candidatas passa a ordenar por ganho, e `largura_x_nss` mostra `5/5` em verde.
   - Aparece o aviso "`channel_width` parece ser TR-069", com o botão **Reclassificar como TR-069**.
   - A tabela de auxiliares mostra `stats_80211_client_amsdu_msdu_avg` como "alcançável" e `link_speed_mbps` como "só laboratório".
6. Passe o mouse num ponto do gráfico: a tooltip mostra a posição e o R².
7. Troque o alvo para **Latência**. O inventário recarrega, e o resultado do teto fica esmaecido com "desatualizado: o conjunto ou o alvo mudou".
8. Abra os três blocos recolhidos (Vazamento, Qualidade, Inventário completo) e troque o alvo: eles continuam abertos.
9. Tema escuro (botão Tema): o gráfico e as tabelas continuam legíveis.
10. Volte ao alvo Download, rode a análise de novo (vem do cache, na hora) e clique **Reclassificar como TR-069** em `channel_width`. Rode `git diff src/ml/core/column_provenance.json`: a mudança deve ser só a entrada de `channel_width`, de `"classe": "cliente"` para `"classe": "tr069"`. **Mostre o diff ao usuário e pergunte se ele quer manter.** Se não quiser, desfaça com `git checkout -- src/ml/core/column_provenance.json`.

Pare o servidor ao terminar.

- [ ] **Step 7: Commit (AÇÃO DO USUÁRIO)**

```bash
git add src/ml/studio/static/graficos.js src/ml/studio/static/features.js src/ml/studio/static/index.html src/ml/studio/static/studio.js src/ml/studio/static/styles.css
git commit -m "feat(studio): view Features com teto, candidatas TR-069 e proxies"
```

---

### Task 7: Fechamento da fase

- [ ] **Step 1: Suíte completa**

Run: `./venv/bin/python -m unittest discover -s tests -p "test_*.py"`
Expected: `OK`.

- [ ] **Step 2: Conferir que nenhuma coluna com vazamento entra em ajuste**

Run: `grep -n "assert_sem_vazamento" src/ml/studio/features.py`
Expected: a definição e uma chamada, dentro de `r2_por_posicao`. Todo ajuste passa por essa função.

- [ ] **Step 3: Relatar ao usuário**

Informe o que foi entregue, os commits pendentes (se ele ainda não os fez) e que a fase 2 (planta) está em `docs/superpowers/plans/2026-09-18-qoe-studio-planta.md`.

# Studio novo, parte 1: fundação, Dados e Conjunto (plano de implementação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o pacote `src/studio/` com a área Dados e o painel Conjunto (com upload) funcionando, isolado do benchmark do Fabiano: nada é escrito em `data/`, `src/ml/`, `mlflow.db` ou `mlruns/`.

**Architecture:** Pacote Python novo `studio` (fora de `src/ml/`), que nunca importa `ml.*`. O que a área Dados usava de `ml.core.carga`, `ml.core.sites` e `ml/studio/*` é portado (copiado e simplificado). Caminhos ficam num módulo `caminhos`, lido na hora da chamada, para os testes apontarem tudo para pastas temporárias. O payload de Dados tem o mesmo formato do Studio atual, então `logica.js`, `dados.js`, `planta.js` e `graficos.js` são copiados sem mudança. `conjunto.js`, `studio.js` e `index.html` são reescritos.

**Tech Stack:** Python 3.12, FastAPI 0.141 + uvicorn, pandas, Pillow, JS puro sem build, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-22-studio-mlflow-design.md` (seções 2, 3, 4, 6, 7, 8). A parte 2 (Modelo + MLflow) fica em `docs/superpowers/plans/2026-10-22-studio-novo-modelo.md` e depende desta.

**Regras do projeto para quem executa:**
- Indentação de 2 espaços no Python (padrão do repositório).
- Rodar testes com `./venv/bin/python -m unittest <arquivo>` a partir da raiz do repositório.
- **Não rodar `git commit` nem `git push`.** O usuário faz os commits. Nos pontos marcados "Ponto de commit", pare, liste os arquivos e sugira a mensagem (sem linha `Co-Authored-By`).
- Não editar nada em `src/ml/`, `data/`, `mlflow.db`, `mlruns/`.

---

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/studio/__init__.py` | Docstring do pacote |
| `src/studio/caminhos.py` | Todos os caminhos lidos e gravados pelo Studio |
| `src/studio/arquivos.py` | Gravação atômica de JSON |
| `src/studio/aplicacoes.py` | Limiares por aplicação (`config/aplicacoes.json`) |
| `src/studio/predios.py` | Cadastro de prédios e resolução de `local` (`config/predios.json`) |
| `src/studio/catalogo.py` | Datasets de `data/` (só leitura) + `.studio/uploads/` |
| `src/studio/conjunto.py` | Conjunto ativo (`.studio/conjunto.json`) |
| `src/studio/plantas.py` | Planta em escala (cópia de `ml/studio/plans.py`) |
| `src/studio/upload.py` | Prévia, revisão e confirmação de upload |
| `src/studio/dados.py` | Payload da área Dados |
| `src/studio/portas.py` | Teste de porta livre |
| `src/studio/api.py` | Rotas FastAPI |
| `src/studio/run.py` | Sobe o Studio |
| `src/studio/config/predios.json`, `aplicacoes.json`, `colunas.json` | Configuração do Studio, semeada do core uma vez |
| `src/studio/web/*` | Front (index.html, styles.css, util.js, logica.js, graficos.js, planta.js, dados.js, conjunto.js, studio.js) |
| `tests/apoio_studio_novo.py` | CSVs de teste e pastas temporárias |
| `tests/test_studio_novo_*.py` | Testes |
| `tests/js/logica_studio_novo.test.js` | Testes JS de `logica.js` no caminho novo |
| `.gitignore` | Acrescenta `.studio/` |

---

### Task 1: Pacote, caminhos, gravação atômica e teste de imports

**Files:**
- Create: `src/studio/__init__.py`
- Create: `src/studio/caminhos.py`
- Create: `src/studio/arquivos.py`
- Create: `tests/test_studio_novo_isolamento.py`
- Modify: `.gitignore`

- [ ] **Step 1: Escrever o teste de imports (com teste do próprio detector)**

`tests/test_studio_novo_isolamento.py`:

```python
"""Isolamento do Studio novo: não importa ml.* e não escreve no que é do benchmark."""

import ast
import os
import tempfile
import unittest

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


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_isolamento.py -v`
Expected: `test_pacote_studio_nao_importa_ml` FAIL (`False is not true`, a pasta não existe). O teste do detector passa.

- [ ] **Step 3: Criar o pacote**

`src/studio/__init__.py`:

```python
"""QoE Studio novo: área Dados e, na parte 2, modelos no MLflow próprio do Studio.

Não importa nada de `ml`: o benchmark e o MLflow do Fabiano ficam fora de alcance.
"""
```

`src/studio/caminhos.py`:

```python
"""Onde o Studio lê e grava.

Os outros módulos leem estes nomes na hora da chamada (`caminhos.DATA_DIR`), nunca
como valor padrão de argumento: assim os testes trocam tudo por pastas temporárias
com mock.patch.multiple.
"""

import os

PACOTE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(PACOTE, '..', '..'))

# Só leitura. É a pasta que o benchmark varre inteira (ml.core.carga.discover):
# qualquer arquivo gravado aqui mudaria o conjunto canônico dele.
DATA_DIR = os.path.join(REPO, 'data')

CONFIG_DIR = os.path.join(PACOTE, 'config')
PREDIOS_PATH = os.path.join(CONFIG_DIR, 'predios.json')
APLICACOES_PATH = os.path.join(CONFIG_DIR, 'aplicacoes.json')
COLUNAS_PATH = os.path.join(CONFIG_DIR, 'colunas.json')

# Plantas: o benchmark não usa docs/planta/.
PLANTA_DIR = os.path.join(REPO, 'docs', 'planta')

# Estado local, fora do git.
ESTADO_DIR = os.path.join(REPO, '.studio')
UPLOADS_DIR = os.path.join(ESTADO_DIR, 'uploads')
CONJUNTO_PATH = os.path.join(ESTADO_DIR, 'conjunto.json')
```

`src/studio/arquivos.py`:

```python
"""Gravação atômica: quem lê nunca vê um arquivo pela metade."""

import json
import os
import tempfile


def gravar_json_atomico(path: str, dados) -> None:
  """Grava JSON com chaves ordenadas via arquivo temporário + os.replace."""
  texto = json.dumps(dados, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
  pasta = os.path.dirname(os.path.abspath(path))
  os.makedirs(pasta, exist_ok=True)
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

- [ ] **Step 4: Ignorar o estado local no git**

Acrescentar ao fim de `.gitignore`:

```
.studio/
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_isolamento.py -v`
Expected: 2 testes, OK.

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/studio/__init__.py`, `src/studio/caminhos.py`, `src/studio/arquivos.py`, `tests/test_studio_novo_isolamento.py`, `.gitignore`.
Mensagem sugerida: `feat(studio-novo): pacote src/studio isolado de ml.* e caminhos próprios`

---

### Task 2: Configuração semeada e limiares por aplicação

**Files:**
- Create: `src/studio/config/predios.json` (cópia)
- Create: `src/studio/config/aplicacoes.json` (cópia)
- Create: `src/studio/config/colunas.json` (gerado)
- Create: `src/studio/aplicacoes.py`
- Create: `tests/test_studio_novo_config.py`

- [ ] **Step 1: Semear a configuração (uma vez; depois é independente do core)**

```bash
mkdir -p src/studio/config
cp src/ml/core/predios.json src/studio/config/predios.json
cp src/ml/core/aplicacoes.json src/studio/config/aplicacoes.json
./venv/bin/python - <<'EOF'
import json
with open('src/ml/core/column_provenance.json', encoding='utf-8') as handle:
  d = json.load(handle)
cols = d['colunas']
saida = {
  'vazamento': sorted(k for k, v in cols.items() if v.get('vazamento') is True),
  'vazamento_prefixos': sorted(k for k, v in d['prefixos'].items() if v.get('vazamento') is True),
  'excluir': sorted(k for k, v in cols.items() if v.get('classe') in ('identificador', 'alvo')),
}
with open('src/studio/config/colunas.json', 'w', encoding='utf-8') as handle:
  handle.write(json.dumps(saida, sort_keys=True, indent=2, ensure_ascii=False) + '\n')
print(len(saida['vazamento']), saida['vazamento_prefixos'], len(saida['excluir']))
EOF
```

Expected na saída: `47 ['download_', 'upload_'] 27`.
Conferir que `router_tx_retries` e `router_tx_bytes` estão em `vazamento` (contadores da janela do speedtest) e que `local`, `run_id`, `speedtest_down_mbps` estão em `excluir`:

Run: `grep -c '"router_tx_retries"\|"router_tx_bytes"\|"run_id"\|"local"' src/studio/config/colunas.json`
Expected: `4`

- [ ] **Step 2: Escrever o teste**

`tests/test_studio_novo_config.py`:

```python
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from studio import aplicacoes, caminhos


class TestAplicacoes(unittest.TestCase):
  def test_config_do_studio_carrega(self):
    apps = aplicacoes.carregar()
    self.assertIn('Chamada de vídeo', apps)
    self.assertEqual(set(apps['Chamada de vídeo']), {'dn', 'up', 'lat', 'jit'})

  def test_chave_faltando_recusa(self):
    with tempfile.TemporaryDirectory() as pasta:
      path = os.path.join(pasta, 'a.json')
      with open(path, 'w', encoding='utf-8') as handle:
        json.dump({'aplicacoes': {'X': {'dn': 1, 'up': 1, 'lat': 1}}}, handle)
      with self.assertRaises(ValueError):
        aplicacoes.carregar(path)

  def test_config_aponta_para_o_studio_e_nao_para_o_core(self):
    self.assertTrue(caminhos.APLICACOES_PATH.endswith(os.path.join('src', 'studio', 'config', 'aplicacoes.json')))
    self.assertTrue(caminhos.PREDIOS_PATH.endswith(os.path.join('src', 'studio', 'config', 'predios.json')))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_config.py -v`
Expected: ERROR `ImportError: cannot import name 'aplicacoes' from 'studio'`.

- [ ] **Step 4: Implementar**

`src/studio/aplicacoes.py`:

```python
"""Limiares de QoE por aplicação: o que cada uma precisa de download, upload, latência e jitter.

Vive em src/studio/config/aplicacoes.json, copiado do core em 2026-10-22 e
independente dele desde então.
"""

import json

from studio import caminhos

# dn/up em Mbps (mínimo), lat/jit em ms (máximo). Os nomes curtos são os do logica.js.
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


def carregar(path: str = None) -> dict:
  with open(path or caminhos.APLICACOES_PATH, encoding='utf-8') as handle:
    dados = json.load(handle)
  validar(dados)
  return dados['aplicacoes']
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_config.py tests/test_studio_novo_isolamento.py -v`
Expected: 5 testes, OK.

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/studio/config/*.json`, `src/studio/aplicacoes.py`, `tests/test_studio_novo_config.py`.
Mensagem sugerida: `feat(studio-novo): configuração própria (prédios, aplicações, colunas) semeada do core`

---

### Task 3: Cadastro de prédios

**Files:**
- Create: `tests/apoio_studio_novo.py`
- Create: `src/studio/predios.py`
- Create: `tests/test_studio_novo_predios.py`

- [ ] **Step 1: Escrever o apoio dos testes**

`tests/apoio_studio_novo.py` (não começa com `test`, a descoberta não o roda):

```python
"""Apoio dos testes do Studio novo: CSVs pequenos e pastas temporárias no lugar das reais."""

import contextlib
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from studio import caminhos, catalogo, predios  # noqa: E402

PREDIOS = {'aliases': {}, 'predios': {
  'alfa': {'rotulo': 'Alfa', 'studio': 'alfa', 'ambiente': 'domestico', 'prefixos': ['alfa'],
           'tetos_wan': {'speedtest_down_mbps': 100.0}},
  'beta': {'rotulo': 'Beta', 'studio': 'beta', 'ambiente': 'corporativo', 'prefixos': ['beta']},
  'gama': {'rotulo': 'Gama', 'studio': 'gama', 'ambiente': 'corporativo', 'prefixos': ['gama']},
}}


def frame(locais, n=12, semente=0, deslocamento=0.0) -> pd.DataFrame:
  """n linhas por local, geração atual (combo, n_clients, station_x, house_x0), alvos ligados ao SNR."""
  rng = np.random.default_rng(semente)
  linhas = []
  for local in locais:
    for i in range(n):
      snr = float(rng.uniform(10, 40))
      linhas.append({
        'local': local,
        'router_snr': snr,
        'router_signal_dbm': -90.0 + snr,
        'router_tx_retries': float(rng.integers(0, 50)),
        'speedtest_down_mbps': round(2.0 * snr + deslocamento + float(rng.normal(0, 1)), 6),
        'speedtest_up_mbps': round(snr + float(rng.normal(0, 1)), 6),
        'latency_ms': round(60.0 - snr + float(rng.normal(0, 1)), 6),
        'jitter_ms': round(10.0 - snr / 5.0 + float(rng.uniform(0, 1)), 6),
        'combo': 'c1', 'n_clients': 1,
        'station_x': 100.0 + i, 'station_y': 200.0, 'station_z': 0.0,
        'house_x0': 400.0, 'house_y0': 900.0, 'house_z0': 280.0,
        'router_x': 50.0, 'router_y': 60.0, 'router_z': 100.0,
      })
  return pd.DataFrame(linhas)


def gravar_csv(pasta: str, nome: str, df: pd.DataFrame) -> str:
  os.makedirs(pasta, exist_ok=True)
  path = os.path.join(pasta, nome)
  df.to_csv(path, index=False)
  return path


@contextlib.contextmanager
def pastas_temporarias(registro: dict = None):
  """Aponta data/, .studio/, predios.json e docs/planta/ para uma pasta temporária."""
  raiz = tempfile.mkdtemp(prefix='studio-novo-')
  p = SimpleNamespace(
    raiz=raiz,
    data=os.path.join(raiz, 'data'),
    estado=os.path.join(raiz, 'estado'),
    uploads=os.path.join(raiz, 'estado', 'uploads'),
    planta=os.path.join(raiz, 'planta'),
    predios_path=os.path.join(raiz, 'predios.json'),
  )
  for pasta in (p.data, p.uploads, p.planta):
    os.makedirs(pasta)
  with open(p.predios_path, 'w', encoding='utf-8') as handle:
    json.dump(registro if registro is not None else PREDIOS, handle)
  troca = {'DATA_DIR': p.data, 'ESTADO_DIR': p.estado, 'UPLOADS_DIR': p.uploads,
           'CONJUNTO_PATH': os.path.join(p.estado, 'conjunto.json'),
           'PREDIOS_PATH': p.predios_path, 'PLANTA_DIR': p.planta}
  with mock.patch.multiple(caminhos, **troca):
    catalogo.esquecer()
    predios.esquecer()
    try:
      yield p
    finally:
      catalogo.esquecer()
      predios.esquecer()
      shutil.rmtree(raiz, ignore_errors=True)
```

Este apoio importa `studio.catalogo`, que só nasce na Task 4. Até lá, troque temporariamente a linha de import por `from studio import caminhos, predios` e as duas chamadas `catalogo.esquecer()` por nada. **Na Task 4, Step 3, volte o import e as chamadas como estão acima.**

- [ ] **Step 2: Escrever os testes de prédios**

`tests/test_studio_novo_predios.py`:

```python
import copy
import json
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, predios as P  # noqa: E402


class TestResolver(unittest.TestCase):
  def setUp(self):
    self.reg = copy.deepcopy(A.PREDIOS)
    self.reg['aliases'] = {'velho-1': 'alfa-1'}
    self.reg['predios']['casa'] = {'rotulo': 'Casa', 'studio': 'casa', 'ambiente': 'domestico', 'prefixos': [],
                                   'posicoes': {'1': 'res-sala', 'sala': 'res-sala'}}

  def test_prefixo_resolve_predio_e_posicao(self):
    s = pd.Series(['alfa-1', 'BETA-sala'])
    self.assertEqual(list(P.resolver(s, 'predio', self.reg)), ['alfa', 'beta'])
    self.assertEqual(list(P.resolver(s, 'posicao', self.reg)), ['alfa-1', 'beta-sala'])

  def test_posicao_numerica_e_alias(self):
    s = pd.Series(['1.0', 'Sala', 'velho-1'])
    self.assertEqual(list(P.resolver(s, 'predio', self.reg)), ['casa', 'casa', 'alfa'])
    self.assertEqual(list(P.resolver(s, 'posicao', self.reg)), ['res-sala', 'res-sala', 'alfa-1'])

  def test_local_desconhecido_levanta(self):
    with self.assertRaises(ValueError):
      P.resolver(pd.Series(['zeta-1']), 'predio', self.reg)

  def test_teto_wan(self):
    self.assertEqual(P.teto_wan('alfa', 'speedtest_down_mbps', A.PREDIOS), 100.0)
    self.assertIsNone(P.teto_wan('beta', 'speedtest_down_mbps', A.PREDIOS))


class TestCadastro(unittest.TestCase):
  def test_config_real_do_studio_e_valida(self):
    P.carregar(caminhos.PREDIOS_PATH)

  def test_cadastrar_grava_so_no_arquivo_apontado(self):
    with A.pastas_temporarias() as p:
      P.cadastrar([{'chave': 'delta', 'rotulo': 'Delta', 'ambiente': 'domestico', 'prefixo': 'delta'}])
      with open(p.predios_path, encoding='utf-8') as handle:
        self.assertIn('delta', json.load(handle)['predios'])
      self.assertIn('delta', P.atual()['predios'])

  def test_prefixo_em_conflito_recusa(self):
    with A.pastas_temporarias():
      with self.assertRaises(ValueError):
        P.cadastrar([{'chave': 'alfa-dois', 'rotulo': 'A2', 'ambiente': 'domestico', 'prefixo': 'alfa'}])

  def test_atual_rele_quando_o_caminho_muda(self):
    with A.pastas_temporarias():
      self.assertEqual(set(P.atual()['predios']), {'alfa', 'beta', 'gama'})
    self.assertNotIn('gama', P.atual()['predios'])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_predios.py -v`
Expected: ERROR `ImportError: cannot import name 'predios' from 'studio'`.

- [ ] **Step 4: Implementar**

`src/studio/predios.py`:

```python
"""Cadastro de prédios do Studio: de qual prédio e posição é cada `local`.

Vive em src/studio/config/predios.json, copiado de src/ml/core/predios.json em
2026-10-22 e independente dele desde então. O Studio nunca lê nem grava o arquivo
do core: ele decide o agrupamento por prédio do benchmark.
"""

import copy
import json
import math
import re
import threading

import pandas as pd

from studio import caminhos
from studio.arquivos import gravar_json_atomico

DOMESTICO = 'domestico'
CORPORATIVO = 'corporativo'
AMBIENTES = (DOMESTICO, CORPORATIVO)
NIVEIS = ('posicao', 'predio')

NOME = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
CAMPOS_OBRIGATORIOS = {'rotulo', 'studio', 'ambiente', 'prefixos'}
CAMPOS = CAMPOS_OBRIGATORIOS | {'posicoes', 'tetos_wan'}
CAMPOS_NOVO = {'chave', 'rotulo', 'ambiente', 'prefixo'}

_cache = {'path': None, 'registro': None}
_lock = threading.Lock()


def _texto(valor) -> bool:
  return isinstance(valor, str) and bool(valor.strip())


def _validar_predio(chave: str, p) -> None:
  if not NOME.match(chave):
    raise ValueError(f'{chave!r}: chave de prédio inválida (minúsculas, dígitos e hífen, 2 a 40 caracteres)')
  if not isinstance(p, dict) or not CAMPOS_OBRIGATORIOS <= set(p) <= CAMPOS:
    raise ValueError(f'{chave!r}: campos inválidos {sorted(p) if isinstance(p, dict) else p!r}; '
                     f'obrigatórios {sorted(CAMPOS_OBRIGATORIOS)}')
  if not _texto(p['rotulo']) or len(p['rotulo']) > 60:
    raise ValueError(f'{chave!r}: rótulo obrigatório, de até 60 caracteres')
  if not isinstance(p['studio'], str) or not NOME.match(p['studio']):
    raise ValueError(f"{chave!r}: chave do Studio {p['studio']!r} inválida")
  if p['ambiente'] not in AMBIENTES:
    raise ValueError(f"{chave!r}: ambiente {p['ambiente']!r} inválido; esperado um de {list(AMBIENTES)}")
  prefixos = p['prefixos']
  if not isinstance(prefixos, list) or not all(isinstance(x, str) and NOME.match(x) for x in prefixos):
    raise ValueError(f'{chave!r}: prefixos precisam ser minúsculas, dígitos e hífen, 2 a 40 caracteres')
  posicoes = p.get('posicoes', {})
  if not isinstance(posicoes, dict) or not all(
      isinstance(k, str) and k == k.strip().lower() and _texto(v) for k, v in posicoes.items()):
    raise ValueError(f'{chave!r}: posicoes precisa ser {{valor em minúsculas: posição}}')
  if not prefixos and not posicoes:
    raise ValueError(f'{chave!r}: prédio sem prefixos precisa de posicoes')
  tetos = p.get('tetos_wan', {})
  if not isinstance(tetos, dict) or not all(
      isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in tetos.values()):
    raise ValueError(f'{chave!r}: tetos_wan precisa ser {{alvo: Mbps positivo}}')


def validar(registro) -> None:
  """Levanta ValueError com a causa; não devolve nada quando o registro é válido."""
  if not isinstance(registro, dict) or set(registro) != {'predios', 'aliases'}:
    raise ValueError("predios.json precisa ter exatamente as chaves 'predios' e 'aliases'")
  predios, aliases = registro['predios'], registro['aliases']
  if not isinstance(predios, dict) or not predios:
    raise ValueError('predios.json precisa de pelo menos um prédio')
  if not isinstance(aliases, dict) or not all(_texto(k) and _texto(v) for k, v in aliases.items()):
    raise ValueError('aliases precisa ser {valor antigo: valor corrigido}')
  donos_studio, prefixos = {}, []
  for chave, p in predios.items():
    _validar_predio(chave, p)
    if p['studio'] in donos_studio:
      raise ValueError(f"{chave!r}: chave do Studio {p['studio']!r} já usada por {donos_studio[p['studio']]!r}")
    donos_studio[p['studio']] = chave
    prefixos += [(x, chave) for x in p['prefixos']]
  # `startswith` decide o prédio: dois prefixos em que um começa com o outro
  # tornariam a resolução dependente da ordem do arquivo.
  for i, (a, dono_a) in enumerate(prefixos):
    for b, dono_b in prefixos[i + 1:]:
      if a.startswith(b) or b.startswith(a):
        raise ValueError(f'prefixos em conflito: {a!r} ({dono_a}) e {b!r} ({dono_b}); um começa com o outro')
  soltos = [k for p in predios.values() for k in p.get('posicoes', {})] + list(aliases)
  for valor in soltos:
    for prefixo, dono in prefixos:
      if valor.startswith(prefixo):
        raise ValueError(f'{valor!r} começa com o prefixo {prefixo!r} de {dono!r}: a resolução ficaria ambígua')


def carregar(path: str = None) -> dict:
  with open(path or caminhos.PREDIOS_PATH, encoding='utf-8') as handle:
    registro = json.load(handle)
  validar(registro)
  return registro


def atual() -> dict:
  """Cópia do registro em uso. Relê quando caminhos.PREDIOS_PATH aponta para outro arquivo."""
  with _lock:
    if _cache['registro'] is None or _cache['path'] != caminhos.PREDIOS_PATH:
      _cache['registro'] = carregar(caminhos.PREDIOS_PATH)
      _cache['path'] = caminhos.PREDIOS_PATH
    return copy.deepcopy(_cache['registro'])


def esquecer() -> None:
  with _lock:
    _cache['registro'] = None


def _entrada_nova(novo) -> tuple:
  if not isinstance(novo, dict) or set(novo) != CAMPOS_NOVO or not all(_texto(novo[c]) for c in CAMPOS_NOVO):
    raise ValueError(f'prédio novo precisa de {sorted(CAMPOS_NOVO)} preenchidos')
  chave = novo['chave'].strip()
  return chave, {'rotulo': novo['rotulo'].strip(), 'studio': chave, 'ambiente': novo['ambiente'],
                 'prefixos': [novo['prefixo'].strip().lower()]}


def com_novos(registro: dict, novos) -> dict:
  """Cópia de `registro` com os prédios novos ({chave, rotulo, ambiente, prefixo}). Não valida o todo."""
  saida = copy.deepcopy(registro)
  for novo in novos:
    chave, entrada = _entrada_nova(novo)
    if chave in saida['predios']:
      raise ValueError(f'o prédio {chave!r} já existe')
    saida['predios'][chave] = entrada
  return saida


def cadastrar(novos) -> dict:
  """Acrescenta prédios a config/predios.json. Valida o registro inteiro antes de gravar."""
  with _lock:
    path = caminhos.PREDIOS_PATH
    registro = com_novos(carregar(path), novos)
    validar(registro)
    gravar_json_atomico(path, registro)
    _cache['registro'], _cache['path'] = registro, path
  return copy.deepcopy(registro)


def teto_wan(predio: str, alvo: str, registro: dict = None):
  """Teto de WAN do prédio para o alvo (Mbps), ou None quando não há teto cadastrado."""
  reg = registro if registro is not None else atual()
  return reg['predios'].get(predio, {}).get('tetos_wan', {}).get(alvo)


def _chave_local(valor) -> str:
  """Canonicaliza uma célula de `local`: '1.0' e 'Sala' viram chaves de busca."""
  if pd.isna(valor):
    raise ValueError("local vazio: toda linha precisa de uma posição conhecida")
  texto = str(valor).strip().lower()
  try:
    numero = float(texto)
  except ValueError:
    return texto
  if not math.isfinite(numero) or not numero.is_integer():
    raise ValueError(f'local desconhecido: {valor!r}')
  return str(int(numero))


def _resolver_um(valor, nivel: str, registro: dict) -> str:
  chave = _chave_local(valor)
  chave = registro['aliases'].get(chave, chave)
  for nome, p in registro['predios'].items():
    if any(chave.startswith(prefixo) for prefixo in p['prefixos']):
      return nome if nivel == 'predio' else chave
  for nome, p in registro['predios'].items():
    posicao = p.get('posicoes', {}).get(chave)
    if posicao is not None:
      return nome if nivel == 'predio' else posicao
  raise ValueError(f'local desconhecido: {valor!r}. Cadastre o prédio em src/studio/config/predios.json '
                   '(Conjunto > Adicionar dados).')


def resolver(valores: pd.Series, nivel: str = 'posicao', registro: dict = None) -> pd.Series:
  """Valores brutos de `local` -> prédio (nivel='predio') ou posição (nivel='posicao')."""
  if nivel not in NIVEIS:
    raise ValueError(f'nível {nivel!r} desconhecido; esperado um de {list(NIVEIS)}')
  reg = registro if registro is not None else atual()
  return valores.map(lambda valor: _resolver_um(valor, nivel, reg))
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_predios.py -v`
Expected: 8 testes, OK.

- [ ] **Step 6: Ponto de commit**

Arquivos: `src/studio/predios.py`, `tests/apoio_studio_novo.py`, `tests/test_studio_novo_predios.py`.
Mensagem sugerida: `feat(studio-novo): cadastro de prédios próprio do Studio`

---

### Task 4: Catálogo de datasets

**Files:**
- Create: `src/studio/catalogo.py`
- Modify: `tests/apoio_studio_novo.py` (voltar o import de `catalogo`)
- Create: `tests/test_studio_novo_catalogo.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_catalogo.py`:

```python
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import catalogo  # noqa: E402


class TestDescoberta(unittest.TestCase):
  def test_duplicata_contido_ignorado_inutilizavel_e_origem(self):
    with A.pastas_temporarias() as p:
      base = A.frame(['alfa-1', 'beta-1'], semente=1)
      A.gravar_csv(p.data, 'a.csv', base)
      A.gravar_csv(p.data, 'a-fix.csv', base)
      A.gravar_csv(p.data, 'c.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'x-qoe.csv', base)
      A.gravar_csv(p.data, 'sem_alvo.csv', base.drop(columns=['latency_ms']))
      A.gravar_csv(p.uploads, 'd.csv', A.frame(['gama-1'], semente=2))
      A.gravar_csv(p.uploads, 'a.csv', A.frame(['gama-1'], semente=3))
      itens = catalogo.descobrir()
      por_id = {}
      for d in itens:
        por_id.setdefault(d['id'], []).append(d)
      self.assertNotIn('x-qoe.csv', por_id)
      self.assertFalse(por_id['sem_alvo.csv'][0]['usable'])
      self.assertIn('latency_ms', por_id['sem_alvo.csv'][0]['error'])
      self.assertEqual([d['origem'] for d in por_id['a.csv']], ['data', 'upload'])
      self.assertFalse(por_id['a.csv'][1]['usable'])
      self.assertEqual(por_id['d.csv'][0]['origem'], 'upload')
      self.assertEqual(catalogo.duplicatas(itens), {'a.csv': 'a-fix.csv'})
      self.assertIn(catalogo.contidos(itens)['c.csv'], {'a.csv', 'a-fix.csv'})
      self.assertEqual(catalogo.ids_padrao(itens), ['a-fix.csv', 'd.csv'])

  def test_descobertos_fica_em_cache_ate_esquecer(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      self.assertEqual([d['id'] for d in catalogo.descobertos()], ['a.csv'])
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], semente=2))
      self.assertEqual([d['id'] for d in catalogo.descobertos()], ['a.csv'])
      catalogo.esquecer()
      self.assertEqual([d['id'] for d in catalogo.descobertos()], ['a.csv', 'b.csv'])

  def test_le_zip_com_um_csv(self):
    with A.pastas_temporarias() as p:
      buffer = io.StringIO()
      A.frame(['alfa-1'], n=3).to_csv(buffer, index=False)
      with zipfile.ZipFile(os.path.join(p.data, 'z.zip'), 'w') as arquivo:
        arquivo.writestr('z.csv', buffer.getvalue())
      itens = catalogo.descobrir()
      self.assertEqual([(d['id'], d['usable'], d['rows']) for d in itens], [('z.zip', True, 3)])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_catalogo.py -v`
Expected: ERROR `ImportError: cannot import name 'catalogo' from 'studio'`.

- [ ] **Step 3: Implementar e voltar o import no apoio**

`src/studio/catalogo.py`:

```python
"""Catálogo de datasets do Studio: data/ (só leitura) e .studio/uploads/.

Porta de ml/core/carga.py (descoberta, fingerprint, duplicatas e contidos), sem
importar de lá. Nada aqui grava: data/ é a pasta que o benchmark varre inteira.
"""

import hashlib
import io
import os
import threading
import zipfile

import pandas as pd

from studio import caminhos

TARGETS = ('speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms')
# Geração atual do esquema: só ela tem o eixo de contenção (combo, n_clients) e a geometria.
CURRENT_MARKERS = ['combo', 'n_clients', 'station_x', 'house_x0']
# As versões -fix/-distcalc recalculam os alvos e diferem da original em ~1e-14.
FINGERPRINT_DECIMALS = 6
# Os -qoe.csv carregam qoe_dw_score de fórmula perdida; filllast é intermediário.
IGNORADOS = ('-qoe', 'filllast')
# Entre datasets com os mesmos alvos, fica a versão corrigida.
MARCAS_CORRECAO = ('fix', 'distcalc')

_cache = {'itens': None}
_lock = threading.Lock()


def ler(path: str) -> pd.DataFrame:
  """Lê CSV ou o único CSV dentro de um zip, sem gravar nada em disco."""
  if path.endswith('.zip'):
    with zipfile.ZipFile(path) as arquivo:
      nomes = [n for n in arquivo.namelist() if n.endswith('.csv')]
      if len(nomes) != 1:
        raise ValueError(f'{os.path.basename(path)}: esperado exatamente 1 CSV no zip, achei {len(nomes)}')
      with arquivo.open(nomes[0]) as handle:
        return pd.read_csv(io.BytesIO(handle.read()), low_memory=False)
  return pd.read_csv(path, low_memory=False)


def geracao(colunas) -> str:
  return 'current' if all(m in colunas for m in CURRENT_MARKERS) else 'legacy'


def fingerprint(frame: pd.DataFrame) -> str:
  """Identidade dos alvos até a 6a casa: o mesmo critério das duplicatas."""
  alvos = frame[list(TARGETS)].round(FINGERPRINT_DECIMALS)
  digest = hashlib.sha256(pd.util.hash_pandas_object(alvos, index=False).values.tobytes())
  return digest.hexdigest()[:12]


def chaves_alvos(frame: pd.DataFrame) -> set:
  """Linhas de alvos como tuplas de texto: um dataset está contido noutro quando o conjunto está."""
  return set(map(tuple, frame[list(TARGETS)].round(FINGERPRINT_DECIMALS).astype(str).values))


def _pastas() -> list:
  return [('data', caminhos.DATA_DIR), ('upload', caminhos.UPLOADS_DIR)]


def descobrir() -> list:
  """Um descritor por .csv/.zip das duas pastas. Ilegível ou sem colunas vira inutilizável com o motivo."""
  achados, vistos = [], set()
  for origem, pasta in _pastas():
    if not os.path.isdir(pasta):
      continue
    for nome in sorted(os.listdir(pasta)):
      if not nome.endswith(('.csv', '.zip')) or any(m in nome for m in IGNORADOS):
        continue
      path = os.path.join(pasta, nome)
      base = {'id': nome, 'path': path, 'origem': origem, 'usable': False}
      if nome in vistos:
        achados.append(dict(base, error=f'nome repetido: {nome} já existe em data/'))
        continue
      vistos.add(nome)
      try:
        frame = ler(path)
      except Exception as erro:  # o motivo vai para a tela
        achados.append(dict(base, error=str(erro)))
        continue
      faltam = [c for c in ('local',) + TARGETS if c not in frame.columns]
      if faltam:
        achados.append(dict(base, error=f'faltam colunas {faltam}'))
        continue
      achados.append(dict(base, usable=True, rows=int(len(frame)), columns=int(len(frame.columns)),
                          generation=geracao(frame.columns), fingerprint=fingerprint(frame), _frame=frame))
  return achados


def contidos(itens: list) -> dict:
  """{id: id maior} para datasets cujas linhas estão inteiras dentro de outro (0817 dentro de 0827)."""
  veredito, chaves = {}, {}
  for item in itens:
    if item.get('usable'):
      chaves[item['id']] = chaves_alvos(item['_frame'])
  for a, chaves_a in chaves.items():
    for b, chaves_b in chaves.items():
      if a != b and chaves_a and chaves_a <= chaves_b and len(chaves_a) < len(chaves_b):
        veredito[a] = b
  return veredito


def _preferencia(item) -> tuple:
  """Ordem entre datasets com os mesmos alvos: corrigido, depois mais colunas, depois o nome."""
  corrigido = any(m in item['id'].lower() for m in MARCAS_CORRECAO)
  return (not corrigido, -int(item.get('columns') or 0), item['id'])


def duplicatas(itens: list) -> dict:
  """{id: id que fica} para datasets com o mesmo fingerprint: só um do grupo fica."""
  grupos = {}
  for item in itens:
    if item.get('usable'):
      grupos.setdefault(item['fingerprint'], []).append(item)
  duplicata_de = {}
  for grupo in grupos.values():
    primeiro, *resto = sorted(grupo, key=_preferencia)
    for item in resto:
      duplicata_de[item['id']] = primeiro['id']
  return duplicata_de


def ids_padrao(itens: list) -> list:
  """O conjunto padrão: utilizável, geração atual, nem contido nem duplicado."""
  fora = set(contidos(itens)) | set(duplicatas(itens))
  return [d['id'] for d in itens
          if d.get('usable') and d['generation'] == 'current' and d['id'] not in fora]


def descobertos() -> list:
  """descobrir() uma vez por processo: reler o zip de 52 MB a cada requisição travaria as telas."""
  with _lock:
    if _cache['itens'] is None:
      _cache['itens'] = descobrir()
    return _cache['itens']


def esquecer() -> None:
  """Dataset novo: a próxima chamada de descobertos() varre as pastas de novo."""
  with _lock:
    _cache['itens'] = None
```

Em `tests/apoio_studio_novo.py`, garantir que o import é `from studio import caminhos, catalogo, predios  # noqa: E402` e que as duas chamadas `catalogo.esquecer()` estão presentes, como no Step 1 da Task 3.

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_catalogo.py tests/test_studio_novo_predios.py -v`
Expected: 11 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/catalogo.py`, `tests/apoio_studio_novo.py`, `tests/test_studio_novo_catalogo.py`.
Mensagem sugerida: `feat(studio-novo): catálogo de datasets (data/ só leitura + uploads do Studio)`

---

### Task 5: Conjunto ativo

**Files:**
- Create: `src/studio/conjunto.py`
- Create: `tests/test_studio_novo_conjunto.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_conjunto.py`:

```python
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import catalogo, conjunto  # noqa: E402


class TestConjunto(unittest.TestCase):
  def test_sem_arquivo_usa_o_conjunto_padrao(self):
    with A.pastas_temporarias() as p:
      df = A.frame(['alfa-1'], semente=1)
      A.gravar_csv(p.data, 'a.csv', df)
      A.gravar_csv(p.data, 'a-fix.csv', df)
      self.assertEqual(conjunto.ler(), ['a-fix.csv'])

  def test_gravar_e_ler(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], semente=2))
      self.assertEqual(conjunto.gravar(['b.csv', 'a.csv']), ['a.csv', 'b.csv'])
      self.assertEqual(conjunto.ler(), ['a.csv', 'b.csv'])
      with open(os.path.join(p.estado, 'conjunto.json'), encoding='utf-8') as handle:
        self.assertEqual(json.load(handle), {'datasets': ['a.csv', 'b.csv']})

  def test_id_desconhecido_recusa(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      with self.assertRaises(ValueError):
        conjunto.gravar(['nao-existe.csv'])

  def test_id_que_sumiu_sai_na_leitura(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], semente=2))
      conjunto.gravar(['a.csv', 'b.csv'])
      os.remove(os.path.join(p.data, 'b.csv'))
      catalogo.esquecer()
      self.assertEqual(conjunto.ler(), ['a.csv'])

  def test_arquivo_ilegivel_cai_no_padrao(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], semente=1))
      os.makedirs(p.estado, exist_ok=True)
      with open(os.path.join(p.estado, 'conjunto.json'), 'w', encoding='utf-8') as handle:
        handle.write('isto não é json')
      self.assertEqual(conjunto.ler(), ['a.csv'])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_conjunto.py -v`
Expected: ERROR `ImportError: cannot import name 'conjunto' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/conjunto.py`:

```python
"""Conjunto ativo: quais datasets do catálogo as telas e o treino usam por padrão.

Gravado em .studio/conjunto.json. Sem arquivo (ou ilegível), vale o conjunto
padrão do catálogo; ids que sumiram do catálogo saem na leitura.
"""

import json

from studio import caminhos, catalogo
from studio.arquivos import gravar_json_atomico


def _usaveis(itens: list) -> set:
  return {d['id'] for d in itens if d.get('usable')}


def ler(itens: list = None) -> list:
  itens = catalogo.descobertos() if itens is None else itens
  try:
    with open(caminhos.CONJUNTO_PATH, encoding='utf-8') as handle:
      ids = json.load(handle)['datasets']
  except FileNotFoundError:
    return catalogo.ids_padrao(itens)
  except (ValueError, KeyError, TypeError):
    return catalogo.ids_padrao(itens)
  usaveis = _usaveis(itens)
  return [i for i in ids if i in usaveis]


def gravar(ids, itens: list = None) -> list:
  itens = catalogo.descobertos() if itens is None else itens
  desconhecidos = sorted(set(ids) - _usaveis(itens))
  if desconhecidos:
    raise ValueError(f'datasets desconhecidos ou inutilizáveis: {desconhecidos}')
  saida = sorted(set(ids))
  gravar_json_atomico(caminhos.CONJUNTO_PATH, {'datasets': saida})
  return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_conjunto.py -v`
Expected: 5 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/conjunto.py`, `tests/test_studio_novo_conjunto.py`.
Mensagem sugerida: `feat(studio-novo): conjunto ativo gravado em .studio/conjunto.json`

---

### Task 6: Plantas (porta de `ml/studio/plans.py`)

**Files:**
- Create: `src/studio/plantas.py` (cópia + 3 trocas)
- Create: `tests/test_studio_novo_plantas.py` (cópia + 1 troca)

- [ ] **Step 1: Copiar o teste e trocar o import**

```bash
cp tests/test_plans.py tests/test_studio_novo_plantas.py
sed -i 's/^from ml\.studio import plans as P$/from studio import plantas as P/' tests/test_studio_novo_plantas.py
grep -n "^from studio import plantas as P$" tests/test_studio_novo_plantas.py
```

Expected: uma linha encontrada.

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_plantas.py`
Expected: ERROR `ImportError: cannot import name 'plantas' from 'studio'`.

- [ ] **Step 3: Copiar o módulo e trocar as dependências**

```bash
cp src/ml/studio/plans.py src/studio/plantas.py
sed -i 's/^from ml\.core\.arquivos import gravar_json_atomico$/from studio import caminhos\nfrom studio.arquivos import gravar_json_atomico/' src/studio/plantas.py
sed -i '/^PLANTA_DIR = /d' src/studio/plantas.py
sed -i 's/pasta or PLANTA_DIR/pasta or caminhos.PLANTA_DIR/g' src/studio/plantas.py
grep -n "PLANTA_DIR\|from ml\|import ml" src/studio/plantas.py
```

Expected: só linhas com `caminhos.PLANTA_DIR` (5 ocorrências: em `caminho`, `listar_arquivos`, `carregar_config` e duas em `_salvar_andar`/`salvar_calibracao`). Nenhuma linha com `ml`.

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_plantas.py tests/test_studio_novo_isolamento.py`
Expected: OK, com o mesmo número de testes de `./venv/bin/python -m unittest tests/test_plans.py` mais 2.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/plantas.py`, `tests/test_studio_novo_plantas.py`.
Mensagem sugerida: `feat(studio-novo): planta em escala portada para o pacote do Studio`

---

### Task 7: Upload (prévia, revisão, confirmação)

**Files:**
- Create: `src/studio/upload.py`
- Create: `tests/test_studio_novo_upload.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_upload.py`:

```python
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import upload  # noqa: E402


def guardar(df, nome='novo.csv'):
  return upload.guardar(nome, df.to_csv(index=False).encode('utf-8'))


class TestUpload(unittest.TestCase):
  def test_confirmar_grava_em_uploads_e_nunca_em_data(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'base.csv', A.frame(['alfa-1'], semente=1))
      token = guardar(A.frame(['beta-1'], semente=5))
      r = upload.confirmar(token, 'novo.csv')
      self.assertEqual(r, {'dataset': 'novo.csv', 'predios': [], 'linhas': 12})
      self.assertTrue(os.path.exists(os.path.join(p.uploads, 'novo.csv')))
      self.assertEqual(sorted(os.listdir(p.data)), ['base.csv'])

  def test_nome_existente_em_data_ou_uploads_bloqueia(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'base.csv', A.frame(['alfa-1'], semente=1))
      A.gravar_csv(p.uploads, 'up.csv', A.frame(['gama-1'], semente=2))
      token = guardar(A.frame(['beta-1'], semente=5))
      self.assertIn('já existe data/base.csv', upload.previa(token, 'base.csv')['bloqueios'])
      self.assertIn('já existe .studio/uploads/up.csv', upload.previa(token, 'up.csv')['bloqueios'])

  def test_local_desconhecido_pede_cadastro_e_cadastra_no_config_do_studio(self):
    with A.pastas_temporarias() as p:
      token = guardar(A.frame(['villa_r1'], semente=7))
      previa = upload.previa(token, 'villa.csv')
      self.assertEqual([g['prefixo'] for g in previa['desconhecidos']], ['villa'])
      self.assertTrue(previa['bloqueios'])
      novo = {'chave': 'villa', 'rotulo': 'Villa', 'ambiente': 'domestico', 'prefixo': 'villa'}
      self.assertEqual(upload.previa(token, 'villa.csv', [novo])['bloqueios'], [])
      upload.confirmar(token, 'villa.csv', [novo])
      with open(p.predios_path, encoding='utf-8') as handle:
        self.assertIn('villa', json.load(handle)['predios'])

  def test_duplicata_bloqueia(self):
    with A.pastas_temporarias() as p:
      df = A.frame(['alfa-1'], semente=1)
      A.gravar_csv(p.data, 'base.csv', df)
      token = guardar(df)
      previa = upload.previa(token, 'copia.csv')
      self.assertEqual(previa['duplicata_de'], 'base.csv')
      with self.assertRaises(ValueError):
        upload.confirmar(token, 'copia.csv')

  def test_sem_colunas_obrigatorias_bloqueia(self):
    with A.pastas_temporarias():
      token = guardar(A.frame(['alfa-1']).drop(columns=['jitter_ms']))
      previa = upload.previa(token, 'x.csv')
      self.assertTrue(any('jitter_ms' in b for b in previa['bloqueios']))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_upload.py -v`
Expected: ERROR `ImportError: cannot import name 'upload' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/upload.py`:

```python
"""Entrada de datasets pelo Studio: prévia guardada sob um token e confirmação que grava em .studio/uploads/.

Porta de ml/studio/ingestao.py. A diferença que importa: nada vai para data/, que o
benchmark varre inteira, nem para src/ml/core/predios.json. O arquivo vai para
.studio/uploads/ e os prédios novos para src/studio/config/predios.json. A
confirmação refaz a prévia inteira: a tela nunca é a única a validar.
"""

import os
import re
import shutil
import tempfile
import threading
import time
import uuid

import pandas as pd

from studio import caminhos, catalogo, predios

LIMITE_BYTES = 100 * 1024 * 1024
VALIDADE_S = 3600
# Abaixo disto, uma coluna-chave da geração atual quase não ajuda: avisar na prévia.
LIMIAR_PREENCHIMENTO = 0.5
OBRIGATORIAS = ('local',) + tuple(catalogo.TARGETS)
COLUNAS_CHAVE = OBRIGATORIAS + tuple(catalogo.CURRENT_MARKERS)
NOME_ARQUIVO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.(csv|zip)$')

_previas = {}
_lock = threading.Lock()


def _extensao(nome: str) -> str:
  for ext in ('.csv', '.zip'):
    if nome.lower().endswith(ext):
      return ext
  raise ValueError(f'{nome!r}: o arquivo precisa ser .csv ou .zip')


def _limpar_expiradas(agora: float) -> None:
  for token in [t for t, p in _previas.items() if agora - p['criado'] > VALIDADE_S]:
    shutil.rmtree(_previas.pop(token)['pasta'], ignore_errors=True)


def guardar(nome: str, conteudo: bytes, agora: float = None) -> str:
  """Guarda o arquivo enviado numa pasta temporária do sistema e devolve o token da prévia."""
  if not conteudo:
    raise ValueError('arquivo vazio')
  if len(conteudo) > LIMITE_BYTES:
    raise ValueError(f'arquivo acima de {LIMITE_BYTES // 2 ** 20} MB')
  ext = _extensao(nome)
  agora = time.time() if agora is None else agora
  pasta = tempfile.mkdtemp(prefix='qoe-upload-')
  path = os.path.join(pasta, 'arquivo' + ext)
  with open(path, 'wb') as handle:
    handle.write(conteudo)
  token = uuid.uuid4().hex
  with _lock:
    _limpar_expiradas(time.time())
    _previas[token] = {'pasta': pasta, 'path': path, 'ext': ext, 'criado': agora}
  return token


def _arquivo(token: str) -> dict:
  with _lock:
    _limpar_expiradas(time.time())
    item = _previas.get(token)
  if item is None:
    raise KeyError('prévia expirada ou desconhecida; envie o arquivo de novo')
  return item


def descartar(token: str) -> None:
  with _lock:
    item = _previas.pop(token, None)
  if item:
    shutil.rmtree(item['pasta'], ignore_errors=True)


def _bloqueios_de_nome(nome: str, ext: str) -> list:
  saida = []
  if not NOME_ARQUIVO.match(nome) or '..' in nome:
    saida.append(f'nome {nome!r} inválido: letras, dígitos, ponto, hífen e sublinhado, terminando em .csv ou .zip')
  elif not nome.lower().endswith(ext):
    saida.append(f'o nome precisa terminar em {ext}, como o arquivo enviado')
  if any(m in nome for m in catalogo.IGNORADOS):
    saida.append(f'nomes com {" ou ".join(catalogo.IGNORADOS)} são ignorados pelo catálogo')
  for rotulo, pasta in (('data/', caminhos.DATA_DIR), ('.studio/uploads/', caminhos.UPLOADS_DIR)):
    if os.path.exists(os.path.join(pasta, nome)):
      saida.append(f'já existe {rotulo}{nome}')
  return saida


def _prefixo_candidato(valor) -> str:
  """Texto antes do primeiro separador: `villa_r1` e `villa-sala` são da `villa`."""
  return re.split(r'[-_.\s]', str(valor).strip().lower(), maxsplit=1)[0]


def _preenchimento(frame: pd.DataFrame) -> dict:
  return {c: (round(float(frame[c].notna().mean()), 4) if c in frame.columns and len(frame) else None)
          for c in COLUNAS_CHAVE}


def _locais(frame: pd.DataFrame, registro: dict, conhecidos: set) -> tuple:
  """(prédios reconhecidos, grupos de valores desconhecidos por prefixo candidato)."""
  achados, desconhecidos = {}, {}
  for valor, linhas in frame['local'].dropna().value_counts().items():
    try:
      predio = predios.resolver(pd.Series([valor]), 'predio', registro).iloc[0]
      posicao = predios.resolver(pd.Series([valor]), 'posicao', registro).iloc[0]
    except ValueError:
      grupo = desconhecidos.setdefault(_prefixo_candidato(valor), {'valores': [], 'linhas': 0})
      grupo['valores'].append(str(valor))
      grupo['linhas'] += int(linhas)
      continue
    item = achados.setdefault(predio, {'linhas': 0, 'posicoes': set()})
    item['linhas'] += int(linhas)
    item['posicoes'].add(posicao)
  lista_predios = [{'predio': k, 'rotulo': registro['predios'][k]['rotulo'], 'novo': k not in conhecidos,
                    'linhas': v['linhas'], 'posicoes': sorted(v['posicoes'])} for k, v in sorted(achados.items())]
  lista_desc = [{'prefixo': k, 'valores': sorted(v['valores']), 'linhas': v['linhas']}
                for k, v in sorted(desconhecidos.items())]
  return lista_predios, lista_desc


def _relacoes(frame: pd.DataFrame, existentes: list) -> dict:
  usaveis = [d for d in existentes if d.get('usable')]
  digest = catalogo.fingerprint(frame)
  duplicata = next((d['id'] for d in usaveis if d['fingerprint'] == digest), None)
  chaves = catalogo.chaves_alvos(frame)
  contido, contem = [], []
  for d in usaveis:
    outras = catalogo.chaves_alvos(d['_frame'])
    if chaves and chaves < outras:
      contido.append(d['id'])
    elif outras and outras < chaves:
      contem.append(d['id'])
  return {'fingerprint': digest, 'duplicata_de': duplicata, 'contido_em': contido, 'contem': contem}


def previa(token: str, nome: str, predios_novos=(), existentes: list = None) -> dict:
  """O que entraria em .studio/uploads/ com este nome e estes prédios novos. Não grava nada."""
  existentes = catalogo.descobertos() if existentes is None else existentes
  item = _arquivo(token)
  bloqueios, avisos = _bloqueios_de_nome(nome, item['ext']), []
  try:
    frame = catalogo.ler(item['path'])
  except Exception as erro:  # o motivo vai para a tela
    return {'nome': nome, 'bloqueios': bloqueios + [f'arquivo ilegível: {erro}'], 'avisos': avisos}
  saida = {'nome': nome, 'linhas': int(len(frame)), 'colunas': int(len(frame.columns))}
  faltam = [c for c in OBRIGATORIAS if c not in frame.columns]
  if faltam:
    return dict(saida, bloqueios=bloqueios + [f'faltam colunas obrigatórias: {faltam}'], avisos=avisos)

  saida['geracao'] = catalogo.geracao(frame.columns)
  saida['marcadores_ausentes'] = [m for m in catalogo.CURRENT_MARKERS if m not in frame.columns]
  if saida['geracao'] == 'legacy':
    avisos.append(f"geração legada (faltam {saida['marcadores_ausentes']}): entra, mas fica fora do conjunto padrão")
  saida['preenchimento'] = _preenchimento(frame)
  for coluna in catalogo.CURRENT_MARKERS:
    valor = saida['preenchimento'][coluna]
    if valor is not None and valor < LIMIAR_PREENCHIMENTO:
      avisos.append(f'{coluna} preenchido em só {valor:.0%} das linhas')

  atual = predios.atual()
  try:
    registro = predios.com_novos(atual, predios_novos)
    predios.validar(registro)
  except ValueError as erro:
    bloqueios.append(f'cadastro de prédio: {erro}')
    registro = atual
  vazios = int(frame['local'].isna().sum())
  if vazios:
    bloqueios.append(f'{vazios} linhas com local vazio')
  saida['predios'], saida['desconhecidos'] = _locais(frame, registro, set(atual['predios']))
  if saida['desconhecidos']:
    prefixos = [g['prefixo'] for g in saida['desconhecidos']]
    bloqueios.append(f'local desconhecido: cadastre o prédio dos prefixos {prefixos}')

  saida.update(_relacoes(frame, existentes))
  if saida['duplicata_de']:
    bloqueios.append(f"mesmos alvos de {saida['duplicata_de']}: seria descartado como duplicata")
  if saida['contido_em']:
    avisos.append(f"todas as linhas já estão em {saida['contido_em']}: seria marcado como contido")
  if saida['contem']:
    avisos.append(f"contém todas as linhas de {saida['contem']}: esses passariam a ser marcados como contidos")
  return dict(saida, bloqueios=bloqueios, avisos=avisos)


def confirmar(token: str, nome: str, predios_novos=(), existentes: list = None) -> dict:
  """Refaz a prévia; sem bloqueio, cadastra os prédios e grava .studio/uploads/<nome>."""
  p = previa(token, nome, predios_novos, existentes)
  if p['bloqueios']:
    raise ValueError('; '.join(p['bloqueios']))
  item = _arquivo(token)
  novos = [n['chave'].strip() for n in predios_novos]
  if predios_novos:
    predios.cadastrar(predios_novos)
  os.makedirs(caminhos.UPLOADS_DIR, exist_ok=True)
  destino = os.path.join(caminhos.UPLOADS_DIR, nome)
  # .tmp não termina em .csv nem .zip: o catálogo nunca vê o arquivo pela metade.
  temporario = destino + '.tmp'
  try:
    shutil.copyfile(item['path'], temporario)
    os.replace(temporario, destino)
  except OSError as erro:
    if os.path.exists(temporario):
      os.unlink(temporario)
    extra = f'; os prédios {novos} já ficaram cadastrados em src/studio/config/predios.json' if novos else ''
    raise OSError(f'não foi possível gravar .studio/uploads/{nome}: {erro}{extra}') from erro
  descartar(token)
  return {'dataset': nome, 'predios': novos, 'linhas': p['linhas']}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_upload.py -v`
Expected: 5 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/upload.py`, `tests/test_studio_novo_upload.py`.
Mensagem sugerida: `feat(studio-novo): upload grava em .studio/uploads, nunca em data/`

---

### Task 8: Payload da área Dados

**Files:**
- Create: `src/studio/dados.py`
- Create: `tests/test_studio_novo_dados.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_dados.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import dados  # noqa: E402


class TestPayload(unittest.TestCase):
  def test_linhas_datasets_inutilizaveis_e_envelope(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'beta-1'], n=6, semente=1))
      A.gravar_csv(p.data, 'quebrado.csv', A.frame(['alfa-1'], n=2).drop(columns=['latency_ms']))
      payload = dados.montar_payload()
      self.assertEqual(len(payload['rows']), 12)
      r = payload['rows'][0]
      self.assertEqual({k: r[k] for k in ('ds', 'gen', 'b', 'p', 'n', 'combo')},
                       {'ds': 'a.csv', 'gen': 'current', 'b': 'alfa', 'p': 'alfa-1', 'n': 1, 'combo': 'c1'})
      self.assertEqual([d['id'] for d in payload['datasets']], ['a.csv'])
      self.assertEqual(payload['datasets'][0]['origem'], 'data')
      self.assertEqual(payload['datasets'][0]['buildings'], ['alfa', 'beta'])
      self.assertEqual([d['id'] for d in payload['inutilizaveis']], ['quebrado.csv'])
      self.assertEqual(set(payload['buildings']), {'alfa', 'beta', 'gama'})
      self.assertEqual(payload['envelopes']['alfa']['w'], 400.0)
      self.assertIn('Chamada de vídeo', payload['aplicacoes'])

  def test_local_desconhecido_vira_aviso(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1', 'zeta-1'], n=3, semente=1))
      payload = dados.montar_payload()
      self.assertEqual(len(payload['rows']), 3)
      self.assertEqual(payload['locaisDesconhecidos'],
                       [{'dataset': 'a.csv', 'valores': ['zeta-1'], 'linhas': 3}])

  def test_com_conjunto_marca_enabled(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], n=3, semente=2))
      payload = dados.montar_payload()
      com = dados.com_conjunto(payload, ['b.csv'])
      self.assertEqual({d['id']: d['enabled'] for d in com['datasets']}, {'a.csv': False, 'b.csv': True})
      self.assertIsNot(com['datasets'], payload['datasets'])


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_dados.py -v`
Expected: ERROR `ImportError: cannot import name 'dados' from 'studio'`.

- [ ] **Step 3: Implementar**

`src/studio/dados.py`:

```python
"""Payload da área Dados: as linhas cruas dos quatro alvos, e o navegador agrega.

Porta de ml/studio/data.py com o mesmo formato, para que logica.js, dados.js e
planta.js funcionem sem mudança. Diferenças: prédios de config/predios.json,
datasets inutilizáveis à parte e `enabled` posto por com_conjunto() a cada pedido.
"""

from collections import Counter

import pandas as pd

from studio import aplicacoes, catalogo, predios
from studio.plantas import andar_de, montar_plantas

TARGETS = list(catalogo.TARGETS)
AMBIENTES = {predios.DOMESTICO: 'Doméstico', predios.CORPORATIVO: 'Corporativo'}
# quarto-marcelo: rótulo antigo que o 20260917-metrics-fix regravou como hotmilk-aquario.
POSITION_LABELS = {'1': 'sala', '2': 'quarto', '3': 'suite', 'quarto-marcelo': 'hotmilk-aquario'}


def predios_studio(registro: dict) -> dict:
  """{chave do Studio: {'label', 'ambiente'}} de todos os prédios do cadastro."""
  return {p['studio']: {'label': p['rotulo'], 'ambiente': p['ambiente']} for p in registro['predios'].values()}


def _canonical_local(local_value) -> str:
  """'1.0', 'Sala' e 'sala' precisam cair na mesma chave."""
  text = str(local_value).strip().lower()
  try:
    number = float(text)
  except ValueError:
    return text
  return str(int(number)) if number.is_integer() else text


def _resolvedor(registro: dict):
  """local -> chave do Studio do prédio, com memória por valor. ValueError para vazio ou desconhecido."""
  memoria = {}

  def predio_de(local_value) -> str:
    if pd.isna(local_value):
      raise ValueError('local vazio')
    texto = str(local_value)
    if texto not in memoria:
      try:
        nome = predios.resolver(pd.Series([texto]), 'predio', registro).iloc[0]
        memoria[texto] = registro['predios'][nome]['studio']
      except ValueError:
        memoria[texto] = None
    if memoria[texto] is None:
      raise ValueError(f'local desconhecido: {texto!r}')
    return memoria[texto]

  return predio_de


def _registro_linha(item: dict, row, building: str, position: str) -> dict:
  record = {
    'ds': item['id'],
    'gen': item['generation'],
    'b': building,
    'p': position,
    'dn': round(float(row[TARGETS[0]]), 3),
    'up': round(float(row[TARGETS[1]]), 3),
    'lat': round(float(row[TARGETS[2]]), 3),
    'jit': round(float(row[TARGETS[3]]), 3),
  }
  if item['generation'] == 'current':
    record['n'] = int(row['n_clients']) if not pd.isna(row.get('n_clients')) else None
    record['combo'] = row.get('combo') if not pd.isna(row.get('combo')) else None
    for src, dst in (('station_x', 'x'), ('station_y', 'y'), ('station_z', 'z')):
      value = row.get(src)
      record[dst] = None if pd.isna(value) else float(value)
  return record


def _envelopes(itens: list, predio_de) -> dict:
  """Vence o envelope mais frequente do prédio, não o da primeira linha (o 20260925 abriu com
  4 linhas do envelope de outro prédio)."""
  votos = {}
  for item in itens:
    if not item.get('usable') or item['generation'] != 'current':
      continue
    for _, row in item['_frame'].iterrows():
      try:
        building = predio_de(row['local'])
      except ValueError:
        continue
      if pd.isna(row.get('house_x0')):
        continue
      chave = (float(row['house_x0']), float(row['house_y0']), float(row['house_z0']),
               float(row['router_x']), float(row['router_y']),
               None if pd.isna(row.get('router_z')) else float(row['router_z']))
      votos.setdefault(building, Counter())[chave] += 1
  envelopes = {}
  for building, contagem in votos.items():
    w, h, z, router_x, router_y, router_z = contagem.most_common(1)[0][0]
    envelopes[building] = {'w': w, 'h': h, 'z': z, 'routerX': router_x, 'routerY': router_y, 'routerZ': router_z}
  return envelopes


def montar_payload(itens: list = None) -> dict:
  itens = catalogo.descobertos() if itens is None else itens
  registro = predios.atual()
  predio_de = _resolvedor(registro)
  substituidos, duplicados = catalogo.contidos(itens), catalogo.duplicatas(itens)
  padrao = set(catalogo.ids_padrao(itens))
  rows, descriptors, inutilizaveis, locais_desconhecidos = [], [], [], []

  for item in itens:
    if not item.get('usable'):
      inutilizaveis.append({'id': item['id'], 'origem': item['origem'], 'erro': item.get('error')})
      continue
    buildings, positions, desconhecidos = set(), set(), Counter()
    for _, row in item['_frame'].iterrows():
      local = row['local']
      try:
        building = predio_de(local)
      except ValueError:
        desconhecidos[str(local)] += 1
        continue
      canonical = _canonical_local(local)
      position = POSITION_LABELS.get(canonical, canonical)
      buildings.add(building)
      positions.add(position)
      if any(pd.isna(row[t]) for t in TARGETS):
        continue
      rows.append(_registro_linha(item, row, building, position))

    if desconhecidos:
      locais_desconhecidos.append({'dataset': item['id'], 'valores': sorted(desconhecidos),
                                   'linhas': int(sum(desconhecidos.values()))})
    descriptors.append({
      'id': item['id'],
      'origem': item['origem'],
      'rows': item['rows'],
      'columns': item['columns'],
      'generation': item['generation'],
      'fingerprint': item['fingerprint'],
      'buildings': sorted(buildings),
      'positions': sorted(positions),
      'enabled': item['id'] in padrao,
      'supersededBy': substituidos.get(item['id']),
      'duplicateOf': duplicados.get(item['id']),
      'hasContention': item['generation'] == 'current',
    })

  envelopes = _envelopes(itens, predio_de)
  plantas, plantas_avisos = montar_plantas(envelopes)
  for record in rows:
    andares = (plantas.get(record['b']) or {}).get('andares')
    if andares:
      record['andar'] = andar_de(record.get('z'), andares)
  return {
    'datasets': descriptors,
    'inutilizaveis': inutilizaveis,
    'rows': rows,
    'buildings': predios_studio(registro),
    'ambientes': AMBIENTES,
    'aplicacoes': aplicacoes.carregar(),
    'envelopes': envelopes,
    'plantas': plantas,
    'plantasAvisos': plantas_avisos,
    'locaisDesconhecidos': locais_desconhecidos,
  }


def com_conjunto(payload: dict, ativos) -> dict:
  """Cópia rasa do payload com `enabled` de cada dataset vindo do conjunto ativo."""
  ativos = set(ativos)
  return dict(payload, datasets=[dict(d, enabled=d['id'] in ativos) for d in payload['datasets']])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_dados.py -v`
Expected: 3 testes, OK.

- [ ] **Step 5: Ponto de commit**

Arquivos: `src/studio/dados.py`, `tests/test_studio_novo_dados.py`.
Mensagem sugerida: `feat(studio-novo): payload da área Dados no formato do Studio atual`

---

### Task 9: Front (web/)

**Files:**
- Create (cópia sem mudança): `src/studio/web/styles.css`, `util.js`, `logica.js`, `graficos.js`, `planta.js`, `dados.js`
- Create: `src/studio/web/index.html`, `src/studio/web/studio.js`, `src/studio/web/conjunto.js`
- Create: `tests/js/logica_studio_novo.test.js`

- [ ] **Step 1: Copiar os arquivos que não mudam**

```bash
mkdir -p src/studio/web
for f in styles.css util.js logica.js graficos.js planta.js dados.js; do
  cp src/ml/studio/static/$f src/studio/web/$f
done
ls src/studio/web
```

Expected: `dados.js graficos.js logica.js planta.js styles.css util.js`.

- [ ] **Step 2: Teste JS de `logica.js` no caminho novo**

```bash
sed 's#../../src/ml/studio/static/logica.js#../../src/studio/web/logica.js#; s#src/ml/studio/static/logica.js#src/studio/web/logica.js#' \
  tests/js/logica.test.js > tests/js/logica_studio_novo.test.js
grep -n "require('../../src/studio/web/logica.js')" tests/js/logica_studio_novo.test.js
node --test tests/js/logica_studio_novo.test.js 2>&1 | tail -4
```

Expected: a linha do require é encontrada; `# fail 0`.

- [ ] **Step 3: Escrever `index.html`**

`src/studio/web/index.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
<script>
/* Tema aplicado antes do primeiro paint. Aceita ?theme=dark para links diretos. */
(function () {
  var p = new URLSearchParams(location.search);
  var t = p.get('theme');
  try { t = t || localStorage.getItem('qoe-theme'); } catch (e) { /* modo privado */ }
  if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
})();
</script>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QoE Studio</title>
<link rel="stylesheet" href="styles.css?v=1">
</head>
<body>

<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <symbol id="i-bars" viewBox="0 0 24 24"><line x1="5" y1="21" x2="5" y2="11"/><line x1="12" y1="21" x2="12" y2="4"/><line x1="19" y1="21" x2="19" y2="15"/></symbol>
  <symbol id="i-db" viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></symbol>
  <symbol id="i-alert" viewBox="0 0 24 24"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24"><path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><polyline points="22 4 12 14.01 9 11.01"/></symbol>
  <symbol id="i-equal" viewBox="0 0 24 24"><line x1="5" y1="9" x2="19" y2="9"/><line x1="5" y1="15" x2="19" y2="15"/></symbol>
  <symbol id="i-wifi" viewBox="0 0 24 24"><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><line x1="12" y1="20" x2="12.01" y2="20"/><path d="M1.5 9a15 15 0 0 1 21 0"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></symbol>
  <symbol id="i-plus" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></symbol>
  <symbol id="i-more" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/></symbol>
  <symbol id="i-undo" viewBox="0 0 24 24"><polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/></symbol>
  <symbol id="i-refresh" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/></symbol>
</defs></svg>

<header class="topo">
  <div class="brand"><svg class="icon" aria-hidden="true"><use href="#i-wifi"/></svg> QoE Studio</div>
  <nav class="abas" aria-label="Áreas">
    <a href="#dados" data-area="dados">Dados</a>
  </nav>
  <button class="chip-conjunto" id="chipConjunto" aria-haspopup="dialog" aria-controls="painelConjunto" aria-expanded="false"></button>
  <button class="btn-icone" id="themeBtn" aria-label="Alternar tema claro ou escuro"><svg class="icon" aria-hidden="true"><use href="#i-moon"/></svg></button>
</header>

<main>
  <section id="area-dados" class="area">
    <div class="area-cab"><div><h1>Dados</h1>
      <p class="sub">Nesta posição, com esta quantidade de gente na rede, a aplicação funciona? Se não, por quê?</p></div></div>
    <div id="dVazio" class="vazio hide"><p>Nenhum dataset ativo.</p><button class="btn-pri" data-acao="conjunto">Abrir Conjunto</button></div>
    <div id="dConteudo">
      <div class="limiares" id="dLimiares"></div>
      <div id="dCritico"></div>
      <div class="dados-grade">
        <div class="card">
          <div class="card-head">
            <div class="seg" role="group" aria-label="Visão"><button data-visao="matriz">Matriz</button><button data-visao="planta">Planta</button></div>
            <button class="linkbtn link" id="dTodas" data-acao="todas" aria-controls="dTodasCorpo">Ver todas as posições</button>
          </div>
          <div id="dMatriz"></div>
          <div id="dPlanta" class="hide">
            <p class="hint">Posições reais de medição, em escala, sem interpolação. Os vazios são onde falta coletar,
              não onde o sinal é ruim. Clique num ponto para ver o detalhe.</p>
            <div class="controls">
              <button class="toggle" id="planGirar" aria-pressed="false"><span class="dot"></span> Retrato</button>
              <button class="toggle hide" id="planFoto" aria-pressed="true"><span class="dot"></span> Foto ao fundo</button>
            </div>
            <div id="planAvisos"></div>
            <div id="plans"></div>
            <div id="planCal" class="hide"></div>
          </div>
        </div>
        <aside class="card detalhe" id="dDetalhe" aria-live="polite"></aside>
      </div>
      <div id="dTodasCorpo" class="hide">
        <div class="card">
          <h2>Queda com dispositivos simultâneos</h2>
          <p class="hint">Mediana por posição com 1, 2 e 3 clientes competindo (desenho <code>combo</code>).
            A linha tracejada é o limiar da aplicação.</p>
          <div class="controls">
            <label for="dMetrica">Métrica</label>
            <select id="dMetrica">
              <option value="dn">Download (Mbps)</option>
              <option value="up">Upload (Mbps)</option>
              <option value="lat">Latência (ms)</option>
              <option value="jit">Jitter (ms)</option>
            </select>
          </div>
          <div class="chartwrap"><canvas id="cContention"></canvas><div class="tooltip" id="tContention"></div></div>
          <div class="serieskey" id="kContention"></div>
        </div>
        <div class="card">
          <h2>Qual métrica reprova mais</h2>
          <p class="hint">Percentual de amostras que falham em cada limiar, por posição. A barra mais alta é o gargalo.</p>
          <div class="chartwrap"><canvas id="cConstraint"></canvas><div class="tooltip" id="tConstraint"></div></div>
          <div class="serieskey" id="kConstraint"></div>
        </div>
      </div>
    </div>
  </section>
</main>

<div class="veu hide" id="veuConjunto"></div>
<aside class="painel hide" id="painelConjunto" role="dialog" aria-modal="true" aria-labelledby="painelTitulo">
  <div class="painel-cab">
    <h2 id="painelTitulo">Conjunto ativo</h2>
    <button class="btn-icone" data-acao="fechar" aria-label="Fechar o painel"><svg class="icon" aria-hidden="true"><use href="#i-x"/></svg></button>
  </div>
  <div id="painelCorpo"></div>
</aside>

<script src="graficos.js?v=1"></script>
<script src="logica.js?v=1"></script>
<script src="util.js?v=1"></script>
<script src="planta.js?v=1"></script>
<script src="conjunto.js?v=1"></script>
<script src="dados.js?v=1"></script>
<script src="studio.js?v=1"></script>
</body>
</html>
```

- [ ] **Step 4: Escrever `studio.js`**

`src/studio/web/studio.js`:

```js
/* studio.js — estado global do Studio novo, rotas, chip do conjunto e tema.
   Cada área se desenha a partir de render(ctx): dados.js (e modelo.js, na parte 2).
   O conjunto ativo é gravado no servidor (.studio/conjunto.json) a cada mudança. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);
  const { esc } = V.util;

  const AREAS = ['dados'];
  /* Limiares de referência por aplicação: src/studio/config/aplicacoes.json, via payload.
     Editáveis na área Dados, só na sessão. */
  let PERFIS = {};
  const state = { data: null, app: 'Chamada de vídeo', thr: null, personalizado: false, legacy: false,
                  enabled: {}, area: null, ambiente: 'todos', erroConjunto: null };

  const ambienteDe = (b) => state.data.buildings[b].ambiente;
  function activeRows() {
    return state.data.rows.filter((r) => state.enabled[r.ds]
      && (state.ambiente === 'todos' || ambienteDe(r.b) === state.ambiente));
  }
  const enabledIds = () => Object.keys(state.enabled).filter((id) => state.enabled[id]);

  function ctx() {
    return { data: state.data, rows: activeRows(), enabled: state.enabled, enabledIds: enabledIds(),
             ambiente: state.ambiente, ambientes: state.data.ambientes, legacy: state.legacy,
             app: state.app, personalizado: state.personalizado, thr: state.thr, perfis: PERFIS,
             erroConjunto: state.erroConjunto };
  }

  function renderChip(c) {
    const predios = new Set(c.rows.map((r) => r.b)).size;
    const amb = c.ambiente === 'todos' ? 'todos os ambientes' : c.ambientes[c.ambiente].toLowerCase();
    const n = V.conjunto.contagem();
    const chip = $('#chipConjunto');
    chip.innerHTML = `<svg class="icon" aria-hidden="true"><use href="#i-db"/></svg>
      <span><b>${c.rows.length.toLocaleString('pt-BR')}</b> amostras · <b>${predios}</b> prédios · ${esc(amb)}</span>
      ${n.avisos ? `<span class="badge${n.critico ? ' critico' : ''}">${n.avisos}</span>` : ''}`;
    chip.setAttribute('aria-label', `Conjunto ativo: ${c.rows.length} amostras, ${predios} prédios, ${amb}` +
      (n.avisos ? `, ${n.avisos} avisos` : '') + '. Abrir o painel.');
  }

  function renderAll() {
    if (!state.data || !state.area) return;
    const c = ctx();
    V.conjunto.render(c);
    renderChip(c);
    V.areas[state.area].render(c);
  }

  function show(area) {
    state.area = area;
    AREAS.forEach((a) => $('#area-' + a).classList.toggle('hide', a !== area));
    document.querySelectorAll('[data-area]').forEach((el) =>
      el.setAttribute('aria-current', String(el.dataset.area === area)));
    renderAll();
  }

  function rota() {
    const h = location.hash.slice(1);
    const area = AREAS.includes(h) ? h : 'dados';
    if (h !== area && h !== 'datasets') history.replaceState(null, '', '#' + area);
    show(area);
    if (h === 'datasets') V.conjunto.abrir();
  }

  // Grava o conjunto no servidor. Se falhar, a tela segue com o estado local e o painel mostra o erro.
  function gravarConjunto() {
    V.util.post('api/conjunto', { datasets: enabledIds() })
      .then(() => { state.erroConjunto = null; })
      .catch((e) => { state.erroConjunto = e.message; })
      .finally(renderAll);
  }

  function aplicarLegacy(on) {
    state.legacy = on;
    state.data.datasets.forEach((d) => {
      if (d.generation === 'legacy') state.enabled[d.id] = on && !d.supersededBy && !d.duplicateOf;
    });
  }

  V.app = {
    ctx,
    atualizar: renderAll,
    atualizarChip() { if (state.data) renderChip(ctx()); },
    irPara(area) { location.hash = area; },
    ligar(id, on) { state.enabled[id] = on; renderAll(); gravarConjunto(); },
    definirLegacy(on) { aplicarLegacy(on); renderAll(); gravarConjunto(); },
    definirAmbiente(a) { state.ambiente = a; renderAll(); },
    definirAplicacao(app) { state.app = app; state.thr = { ...PERFIS[app] }; state.personalizado = false; renderAll(); },
    definirLimiar(key, valor) { state.thr[key] = valor; state.personalizado = true; renderAll(); },
    // Dataset ou prédio novo: relê o payload, mantém o que estava ligado ou desligado
    // e liga os datasets que acabaram de chegar.
    recarregarPayload(ligar) {
      return V.util.pedir('api/payload').then((data) => {
        const antes = state.enabled;
        state.data = data;
        state.enabled = {};
        data.datasets.forEach((d) => { state.enabled[d.id] = d.id in antes ? antes[d.id] : d.enabled; });
        (ligar || []).forEach((id) => { state.enabled[id] = true; });
        renderAll();
        if (ligar && ligar.length) gravarConjunto();
      });
    },
  };

  V.util.pedir('api/payload').then((data) => {
    state.data = data;
    PERFIS = data.aplicacoes;
    data.datasets.forEach((d) => { state.enabled[d.id] = d.enabled; });
    const q = new URLSearchParams(location.search);
    if (q.get('legacy') === '1') aplicarLegacy(true);
    const amb = q.get('ambiente');
    if (amb && data.ambientes[amb]) state.ambiente = amb;
    state.thr = { ...PERFIS[state.app] };

    $('#chipConjunto').addEventListener('click', () => V.conjunto.abrir());
    $('#themeBtn').addEventListener('click', () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      const next = dark ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('qoe-theme', next); } catch (e) { /* modo privado */ }
      renderAll();
    });
    window.addEventListener('hashchange', rota);
    window.addEventListener('resize', renderAll);
    rota();
  }).catch((e) => {
    document.querySelector('main').innerHTML = V.util.gate('critical', 'Não foi possível carregar os dados', esc(e.message));
  });
})();
```

- [ ] **Step 5: Escrever `conjunto.js`**

`src/studio/web/conjunto.js`:

```js
/* conjunto.js — painel do conjunto ativo: avisos, ambiente, datasets e upload.
   Abre pelo chip do topo, por cima de qualquer área. studio.js chama render(ctx) a
   cada mudança. Uploads vão para .studio/uploads/ e prédios novos para
   src/studio/config/predios.json: nada é gravado em data/. */
(function () {
  'use strict';
  const V = window.VENKO;
  const L = V.logica;
  const U = V.util;
  const { esc } = U;
  const $ = (s) => document.querySelector(s);

  const st = { ctx: null, aberto: false, voltarPara: null, up: null, upMsg: null };

  function contagem() {
    if (!st.ctx) return { avisos: 0, critico: false };
    const avisos = L.avisosConjunto(st.ctx.data, st.ctx.rows, st.ctx.enabled, st.ctx.ambiente);
    return { avisos: avisos.length, critico: avisos.some((a) => a.sev === 'critical') };
  }

  /* ---------------- adicionar dados ---------------- */
  function enviar(arquivo) {
    st.upMsg = null;
    st.up = { nome: arquivo.name, token: null, previa: null, novos: {}, sujo: false, ocupado: true, erro: null };
    desenhar();
    U.pedir('api/upload/previa?nome=' + encodeURIComponent(arquivo.name),
      { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: arquivo })
      .then((r) => { st.up.token = r.token; usarPrevia(r.previa); })
      .catch((e) => { st.up.erro = e.message; })
      .finally(() => { if (st.up) st.up.ocupado = false; desenhar(); });
  }

  // Os formulários de prédio ficam enquanto a prévia existir: depois de Verificar, os
  // prefixos deixam de ser desconhecidos, mas o cadastro ainda precisa ir na confirmação.
  function usarPrevia(p) {
    st.up.previa = p;
    st.up.sujo = false;
    (p.desconhecidos || []).forEach((g) => {
      if (!st.up.novos[g.prefixo]) {
        st.up.novos[g.prefixo] = { chave: g.prefixo, rotulo: '', ambiente: 'domestico', prefixo: g.prefixo };
      }
    });
  }

  const novosLista = () => Object.values(st.up.novos).map((n) =>
    ({ chave: n.chave.trim(), rotulo: n.rotulo.trim(), ambiente: n.ambiente, prefixo: n.prefixo.trim() }));

  function revisar() {
    const up = st.up;
    up.ocupado = true; up.erro = null; desenhar();
    U.post('api/upload/revisar', { token: up.token, nome: up.nome, predios_novos: novosLista() })
      .then(usarPrevia)
      .catch((e) => { up.erro = e.message; })
      .finally(() => { up.ocupado = false; desenhar(); });
  }

  function confirmarUpload() {
    const up = st.up;
    up.ocupado = true; up.erro = null; desenhar();
    U.post('api/upload/confirmar', { token: up.token, nome: up.nome, predios_novos: novosLista() })
      .then((r) => {
        st.up = null;
        st.upMsg = `${r.dataset} adicionado em .studio/uploads/` +
          (r.predios.length ? ` e ${r.predios.join(', ')} em src/studio/config/predios.json` : '') + '.';
        return V.app.recarregarPayload([r.dataset]);
      })
      .catch((e) => { if (st.up) { st.up.erro = e.message; st.up.ocupado = false; } else { st.upMsg = e.message; } desenhar(); });
  }

  /* ---------------- seções ---------------- */
  function secaoAvisos(avisos) {
    if (!avisos.length) return '<p class="gate-msg">Nenhum aviso.</p>';
    return avisos.map((a) => U.gate(a.sev, esc(a.titulo), esc(a.msg),
      (a.causas.length ? '<ul>' + a.causas.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>' : '') +
      (a.acao ? `<div class="aviso-acao"><button class="btn" data-acao="desligar" data-ds="${esc(a.acao.ds)}"
        data-k="desligar-${esc(a.acao.ds)}">Desligar ${esc(a.acao.ds)}</button></div>` : ''))).join('');
  }

  function secaoAmbiente() {
    const c = st.ctx;
    const opcoes = [['todos', 'Todos']].concat(Object.entries(c.ambientes));
    return `<div class="seg" role="group" aria-label="Ambiente">${opcoes.map(([k, r]) =>
      `<button data-acao="ambiente" data-amb="${k}" data-k="amb-${k}" aria-pressed="${c.ambiente === k}">${esc(r)}</button>`).join('')}</div>`;
  }

  function linhaDs(d) {
    const c = st.ctx;
    const predios = d.buildings.map((b) => c.data.buildings[b].label).join(', ') || '—';
    const obs = d.supersededBy ? `contido em ${d.supersededBy}` : d.duplicateOf ? `idêntico a ${d.duplicateOf}` : '';
    const origem = d.origem === 'upload' ? ' <span class="tag">upload</span>' : '';
    return `<label class="ds"><input type="checkbox" data-ds="${esc(d.id)}" data-k="ds-${esc(d.id)}"${c.enabled[d.id] ? ' checked' : ''}>
      <code>${esc(d.id)}</code>${origem}<span class="gate-msg num">${d.rows.toLocaleString('pt-BR')} linhas</span>
      <span class="gate-msg">${esc(predios)}${obs ? ' · ' + esc(obs) : ''}</span></label>`;
  }

  const lista = (itens) => '<ul>' + itens.map((x) => `<li>${esc(x)}</li>`).join('') + '</ul>';

  function formPredio(prefixo, n, grupo) {
    const campo = (c, rotulo, extra = '') => `<label>${rotulo}<input type="text" data-novo="${esc(prefixo)}"
      data-campo="${c}" data-k="novo-${esc(prefixo)}-${c}" value="${esc(n[c])}"${extra}></label>`;
    return `<div class="pend-item ${grupo ? 'warning' : 'good'}"><div style="flex:1">
      <b>Prédio novo para <code>${esc(prefixo)}-…</code></b>
      ${grupo ? `<div class="gate-msg">${grupo.linhas.toLocaleString('pt-BR')} linhas: ${grupo.valores.map(esc).join(', ')}</div>` : ''}
      <div class="upload-campos">${campo('rotulo', 'Nome', ' placeholder="ex.: Casa do Rodrigo"')}${campo('chave', 'Chave')}${campo('prefixo', 'Prefixo')}
        <label>Ambiente<select data-novo="${esc(prefixo)}" data-campo="ambiente" data-k="novo-${esc(prefixo)}-ambiente">${Object.entries(st.ctx.ambientes).map(([a, r]) =>
          `<option value="${a}"${a === n.ambiente ? ' selected' : ''}>${esc(r)}</option>`).join('')}</select></label></div>
    </div></div>`;
  }

  function secaoAdicionar() {
    const up = st.up;
    const msg = st.upMsg ? U.gate('good', 'Dados adicionados', esc(st.upMsg)) : '';
    const botao = `<div class="controls"><button class="btn" data-acao="escolher-arquivo" data-k="escolher-arquivo"${up && up.ocupado ? ' disabled' : ''}>
        ${U.icone('i-plus')} Adicionar dados</button>
      <input type="file" id="cArquivo" accept=".csv,.zip" class="hide"></div>`;
    if (!up) return msg + botao;
    if (!up.previa) {
      return botao + (up.ocupado ? '<p class="gate-msg">Lendo o arquivo…</p>' : '') +
        (up.erro ? U.gate('critical', 'Não foi possível ler o arquivo', esc(up.erro)) : '');
    }
    const p = up.previa;
    const resumo = p.linhas != null ? `<p class="gate-msg">${p.linhas.toLocaleString('pt-BR')} linhas · ${p.colunas} colunas` +
      (p.geracao ? ` · geração ${p.geracao === 'current' ? 'atual' : 'legada'}` : '') + '</p>' : '';
    const predios = (p.predios || []).map((x) => `<li><b>${esc(x.rotulo)}</b>${x.novo ? ' <span class="tag">novo</span>' : ''}
      · ${x.linhas.toLocaleString('pt-BR')} linhas · ${x.posicoes.map(esc).join(', ')}</li>`).join('');
    const preench = Object.entries(p.preenchimento || {}).map(([c, v]) =>
      `<li><code>${esc(c)}</code> ${v == null ? 'ausente' : U.pct(v)}</li>`).join('');
    const forms = Object.entries(up.novos).map(([k, n]) =>
      formPredio(k, n, (p.desconhecidos || []).find((g) => g.prefixo === k))).join('');
    const pode = !up.ocupado && !up.sujo && !p.bloqueios.length;
    return `<div class="upload">
      <label class="upload-nome">Nome do arquivo<input type="text" data-campo="nome-arquivo" data-k="nome-arquivo" value="${esc(up.nome)}"></label>
      ${resumo}${predios ? `<ul class="upload-predios">${predios}</ul>` : ''}
      ${preench ? `<details class="fold" data-k="up-preench"><summary>Preenchimento das colunas-chave</summary>
        <div class="inner"><ul>${preench}</ul></div></details>` : ''}
      ${forms}
      ${p.bloqueios.length ? U.gate('critical', 'Ainda não dá para confirmar', lista(p.bloqueios)) : ''}
      ${p.avisos.length ? U.gate('warning', 'Avisos', lista(p.avisos)) : ''}
      ${up.erro ? U.gate('critical', 'Algo deu errado', esc(up.erro)) : ''}
      ${up.sujo ? '<p class="gate-msg">Clique em Verificar depois de mudar o nome ou os prédios.</p>' : ''}
      <div class="controls"><button class="btn" data-acao="cancelar-upload" data-k="cancelar-upload">Cancelar</button>
        <button class="btn" data-acao="revisar-upload" data-k="revisar-upload"${up.ocupado ? ' disabled' : ''}>Verificar</button>
        <button class="btn-pri" data-acao="confirmar-upload" data-k="confirmar-upload"${pode ? '' : ' disabled'}>${up.ocupado ? 'Aguarde…' : 'Confirmar'}</button></div>
    </div>`;
  }

  function secaoDatasets() {
    const c = st.ctx;
    const atuais = c.data.datasets.filter((d) => d.generation !== 'legacy');
    const legacy = c.data.datasets.filter((d) => d.generation === 'legacy');
    const inutil = c.data.inutilizaveis || [];
    return atuais.map(linhaDs).join('') + (legacy.length ? `<details class="fold" data-k="legacy"${c.legacy ? ' open' : ''}>
      <summary>Legacy <span>· ${legacy.length} datasets</span></summary>
      <div class="inner"><label class="ds"><input type="checkbox" data-acao="legacy" data-k="legacy-tudo"${c.legacy ? ' checked' : ''}>
        <span>Incluir datasets legacy</span><span></span>
        <span class="gate-msg">Sem contagem de dispositivos nem geometria: entram só no resumo e no detalhe das posições.</span></label>
        ${legacy.map(linhaDs).join('')}</div></details>` : '') +
      (inutil.length ? `<details class="fold" data-k="inutil"><summary>Inutilizáveis <span>· ${inutil.length} arquivos</span></summary>
        <div class="inner"><ul>${inutil.map((d) => `<li><code>${esc(d.id)}</code> (${esc(d.origem)}): ${esc(d.erro || '')}</li>`).join('')}</ul></div></details>` : '');
  }

  function desenhar() {
    if (!st.aberto || !st.ctx) return;
    const c = st.ctx;
    const avisos = L.avisosConjunto(c.data, c.rows, c.enabled, c.ambiente);
    const predios = new Set(c.rows.map((r) => r.b)).size;
    U.redesenhar($('#painelCorpo'), `<p class="resumo"><b>${c.rows.length.toLocaleString('pt-BR')}</b> amostras ·
        <b>${predios}</b> prédios · <b>${L.posicoes(c.rows).length}</b> posições.</p>
      ${c.erroConjunto ? U.gate('critical', 'Conjunto não foi gravado', esc(c.erroConjunto)) : ''}
      <h3>Avisos (${avisos.length})</h3>${secaoAvisos(avisos)}
      <h3>Ambiente</h3>${secaoAmbiente()}
      <h3>Datasets</h3>${secaoAdicionar()}${secaoDatasets()}`);
  }

  /* ---------------- abrir, fechar e foco ---------------- */
  function focaveis() {
    return [...$('#painelConjunto').querySelectorAll('button, [href], input, select, summary')]
      .filter((el) => !el.disabled && el.offsetParent !== null);
  }

  function abrir() {
    if (st.aberto) return;
    st.aberto = true;
    st.voltarPara = document.activeElement;
    $('#painelConjunto').classList.remove('hide');
    $('#veuConjunto').classList.remove('hide');
    $('#chipConjunto').setAttribute('aria-expanded', 'true');
    desenhar();
    const f = focaveis();
    (f[0] || $('#painelConjunto')).focus();
  }

  function fechar() {
    if (!st.aberto) return;
    st.aberto = false;
    $('#painelConjunto').classList.add('hide');
    $('#veuConjunto').classList.add('hide');
    $('#chipConjunto').setAttribute('aria-expanded', 'false');
    if (st.voltarPara && st.voltarPara.focus) st.voltarPara.focus();
  }

  // Esc fecha; Tab fica preso no painel enquanto ele está aberto.
  document.addEventListener('keydown', (ev) => {
    if (!st.aberto) return;
    if (ev.key === 'Escape') { ev.preventDefault(); fechar(); return; }
    if (ev.key !== 'Tab') return;
    const f = focaveis();
    if (!f.length) return;
    const primeiro = f[0];
    const ultimo = f[f.length - 1];
    if (!$('#painelConjunto').contains(document.activeElement)) { ev.preventDefault(); primeiro.focus(); }
    else if (ev.shiftKey && document.activeElement === primeiro) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primeiro.focus(); }
  });

  /* ---------------- eventos ---------------- */
  $('#veuConjunto').addEventListener('click', fechar);
  $('#painelConjunto').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-acao]');
    if (!b || b.disabled) return;
    const acao = b.dataset.acao;
    if (acao === 'fechar') fechar();
    if (acao === 'desligar') V.app.ligar(b.dataset.ds, false);
    if (acao === 'ambiente') V.app.definirAmbiente(b.dataset.amb);
    if (acao === 'escolher-arquivo') $('#cArquivo').click();
    if (acao === 'cancelar-upload') { st.up = null; desenhar(); }
    if (acao === 'revisar-upload') revisar();
    if (acao === 'confirmar-upload') confirmarUpload();
  });
  $('#painelConjunto').addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.id === 'cArquivo' && t.files && t.files[0]) { enviar(t.files[0]); return; }
    if (t.dataset.ds) V.app.ligar(t.dataset.ds, t.checked);
    if (t.dataset.acao === 'legacy') V.app.definirLegacy(t.checked);
  });
  // Redesenhar a cada tecla é seguro: U.redesenhar devolve foco e cursor pelo data-k.
  $('#painelConjunto').addEventListener('input', (ev) => {
    const t = ev.target;
    if (!st.up || !t.dataset.campo) return;
    if (t.dataset.campo === 'nome-arquivo') st.up.nome = t.value;
    else if (t.dataset.novo) st.up.novos[t.dataset.novo][t.dataset.campo] = t.value;
    st.up.sujo = true;
    desenhar();
  });

  V.conjunto = {
    render(ctx) { st.ctx = ctx; desenhar(); },
    contagem, abrir, fechar,
  };
})();
```

- [ ] **Step 6: Conferir que nenhum JS copiado chama rota que não existe no Studio novo**

Run: `grep -no "api/[a-z/]*" src/studio/web/*.js | sort -u`
Expected: só `api/conjunto`, `api/payload`, `api/plan/...` e `api/upload/...`. Se aparecer outra rota (por exemplo `api/columns` ou `api/pendencias`), o arquivo copiado tem dependência que esta tarefa não previu: pare e reporte.

- [ ] **Step 7: Ponto de commit**

Arquivos: `src/studio/web/*`, `tests/js/logica_studio_novo.test.js`.
Mensagem sugerida: `feat(studio-novo): front da área Dados e do painel Conjunto`

---

### Task 10: API, portas e inicialização

**Files:**
- Create: `src/studio/portas.py`
- Create: `src/studio/api.py`
- Create: `src/studio/run.py`
- Create: `tests/test_studio_novo_api.py`

- [ ] **Step 1: Escrever os testes**

`tests/test_studio_novo_api.py`:

```python
import json
import os
import socket
import sys
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import api, portas  # noqa: E402

LOCAL = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))


class TestApi(unittest.TestCase):
  def setUp(self):
    api.dados_mudaram()

  def tearDown(self):
    api.dados_mudaram()

  def test_conjunto_gravado_aparece_no_payload(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      A.gravar_csv(p.data, 'b.csv', A.frame(['beta-1'], n=3, semente=2))
      api.dados_mudaram()
      self.assertEqual(api.conjunto_gravar(api.Conjunto(datasets=['b.csv']), LOCAL), {'datasets': ['b.csv']})
      corpo = json.loads(api.payload().body)
      self.assertEqual({d['id']: d['enabled'] for d in corpo['datasets']}, {'a.csv': False, 'b.csv': True})
      api.dados_mudaram()

  def test_conjunto_com_dataset_desconhecido_da_422(self):
    with A.pastas_temporarias() as p:
      A.gravar_csv(p.data, 'a.csv', A.frame(['alfa-1'], n=3, semente=1))
      api.dados_mudaram()
      with self.assertRaises(HTTPException) as ctx:
        api.conjunto_gravar(api.Conjunto(datasets=['x.csv']), LOCAL)
      self.assertEqual(ctx.exception.status_code, 422)
      api.dados_mudaram()

  def test_post_de_fora_e_recusado(self):
    with self.assertRaises(HTTPException):
      api._so_local(SimpleNamespace(client=SimpleNamespace(host='10.0.0.2')))
    self.assertFalse(api._post_permitido('evil.example', None))
    self.assertFalse(api._post_permitido('127.0.0.1:8100', 'http://evil.example'))
    self.assertTrue(api._post_permitido('127.0.0.1:8100', None))


class TestPortas(unittest.TestCase):
  def test_porta_ocupada_e_livre(self):
    with socket.socket() as s:
      s.bind(('127.0.0.1', 0))
      s.listen()
      porta = s.getsockname()[1]
      self.assertFalse(portas.livre(porta))
    self.assertTrue(portas.livre(porta))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_api.py -v`
Expected: ERROR `ImportError: cannot import name 'api' from 'studio'`.

- [ ] **Step 3: Implementar `portas.py`**

`src/studio/portas.py`:

```python
"""Porta livre em localhost: o Studio nunca se pendura num serviço que já está rodando."""

import socket


def livre(porta: int, host: str = '127.0.0.1') -> bool:
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
      s.bind((host, porta))
    except OSError:
      return False
  return True
```

- [ ] **Step 4: Implementar `api.py`**

`src/studio/api.py`:

```python
"""API do Studio novo. Lê data/ e grava só em .studio/ e em src/studio/config/.

POST só a partir da própria máquina: Host e Origin de loopback (middleware) e
cliente de loopback (_so_local).
"""

import os
from typing import Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from studio import catalogo, conjunto, dados, plantas, predios, upload

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}

app = FastAPI(title='QoE Studio', docs_url=None, redoc_url=None)


def _post_permitido(host: Optional[str], origin: Optional[str]) -> bool:
  """POST só com Host de loopback (contra DNS rebinding) e Origin ausente ou de loopback."""
  if not host or urlsplit('//' + host).hostname not in LOOPBACK:
    return False
  return origin is None or urlsplit(origin).hostname in LOOPBACK


@app.middleware('http')
async def _so_post_local(request: Request, call_next):
  if request.method == 'POST' and not _post_permitido(request.headers.get('host'),
                                                      request.headers.get('origin')):
    return JSONResponse({'detail': 'POST só a partir da própria máquina (Host e Origin de loopback)'},
                        status_code=403)
  return await call_next(request)


def _so_local(request: Request) -> None:
  if request.client is None or request.client.host not in LOOPBACK:
    raise HTTPException(403, 'gravação só é aceita a partir da própria máquina')


_cache = {}


def _payload() -> dict:
  if 'payload' not in _cache:
    _cache['payload'] = dados.montar_payload()
  return _cache['payload']


def dados_mudaram() -> None:
  """Dataset ou prédio novo: catálogo, cadastro e payload são refeitos no próximo pedido."""
  catalogo.esquecer()
  predios.esquecer()
  _cache.clear()


# ---------------- Dados e conjunto ----------------

@app.get('/api/payload')
def payload():
  """Cacheado por processo; o conjunto ativo entra a cada pedido, sem refazer a varredura."""
  return JSONResponse(dados.com_conjunto(_payload(), conjunto.ler()))


class Conjunto(BaseModel):
  datasets: list[str]


@app.get('/api/conjunto')
def conjunto_ler():
  return {'datasets': conjunto.ler()}


@app.post('/api/conjunto')
def conjunto_gravar(corpo: Conjunto, request: Request):
  _so_local(request)
  try:
    return {'datasets': conjunto.gravar(corpo.datasets)}
  except ValueError as erro:
    raise HTTPException(422, str(erro))


# ---------------- Upload ----------------

@app.post('/api/upload/previa')
async def upload_previa(request: Request, nome: str):
  """Corpo cru (application/octet-stream): sem multipart, sem python-multipart."""
  _so_local(request)
  limite = upload.LIMITE_BYTES
  tamanho = request.headers.get('content-length')
  if tamanho and tamanho.isdigit() and int(tamanho) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  conteudo = await request.body()
  if len(conteudo) > limite:
    raise HTTPException(413, f'arquivo acima de {limite // 2 ** 20} MB')
  try:
    token = upload.guardar(nome, conteudo)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  previa = await run_in_threadpool(upload.previa, token, nome, (), catalogo.descobertos())
  return {'token': token, 'previa': previa}


class PredioNovo(BaseModel):
  chave: str
  rotulo: str
  ambiente: str
  prefixo: str


class Revisao(BaseModel):
  token: str
  nome: str
  predios_novos: list[PredioNovo] = []


@app.post('/api/upload/revisar')
def upload_revisar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    return upload.previa(corpo.token, corpo.nome, novos, catalogo.descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])


@app.post('/api/upload/confirmar')
def upload_confirmar(corpo: Revisao, request: Request):
  _so_local(request)
  novos = [p.model_dump() for p in corpo.predios_novos]
  try:
    resultado = upload.confirmar(corpo.token, corpo.nome, novos, catalogo.descobertos())
  except KeyError as erro:
    raise HTTPException(404, erro.args[0])
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  except OSError as erro:
    # O prédio pode ter sido cadastrado antes da falha.
    dados_mudaram()
    raise HTTPException(422, str(erro))
  dados_mudaram()
  return resultado


# ---------------- Planta ----------------

def _envelope(predio: str) -> dict:
  env = _payload()['envelopes'].get(predio)
  if env is None:
    raise HTTPException(404, f'prédio {predio!r} sem envelope nos dados')
  return env


@app.get('/api/plan/arquivos')
def plan_arquivos():
  return plantas.listar_arquivos()


@app.get('/api/plan/arquivo/{nome}')
def plan_arquivo(nome: str):
  try:
    path = plantas.caminho(nome)
  except ValueError as erro:
    raise HTTPException(422, str(erro))
  if not os.path.exists(path):
    raise HTTPException(404, f'{nome!r} não encontrado em docs/planta/')
  return FileResponse(path)


@app.get('/api/plan/{predio}/paredes')
def plan_paredes(predio: str, arquivo: str, origem: str, eixo_x: str, formato: str = 'px',
                 dx: float = 0.0, dy: float = 0.0):
  env = _envelope(predio)
  registro = {'arquivo': arquivo, 'origem': origem, 'eixo_x': eixo_x, 'formato': formato, 'dx': dx, 'dy': dy}
  try:
    paredes, papel = plantas.ler_registro(registro, env['w'], env['h'])
    return {'paredes': paredes, 'papel': papel}
  except (OSError, ValueError, KeyError) as erro:
    raise HTTPException(422, str(erro))


@app.get('/api/plan/{predio}/foto.png')
def plan_foto(predio: str, arquivo: Optional[str] = None, cantos: Optional[str] = None,
              v: Optional[str] = None):
  env = _envelope(predio)
  previa = arquivo is not None
  if previa:
    try:
      numeros = [float(t) for t in (cantos or '').split(',') if t]
    except ValueError:
      raise HTTPException(422, 'cantos inválidos')
    lista = [numeros[i:i + 2] for i in range(0, len(numeros), 2)]
  else:
    calibrada = (_payload()['plantas'].get(predio) or {}).get('calibracao', {}).get('foto') or {}
    arquivo, lista = calibrada.get('arquivo'), calibrada.get('cantos')
    if not arquivo or not lista:
      raise HTTPException(404, 'foto ainda não calibrada')
  try:
    path = plantas.caminho(arquivo)
    lista = plantas.validar_cantos(lista, *plantas.tamanho_imagem(path))
    png = plantas.endireitar(path, lista, env['w'], env['h'], cache=not previa)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  return Response(png, media_type='image/png')


class Calibracao(BaseModel):
  paredes: Optional[dict] = None
  foto: Optional[dict] = None
  andar: Optional[str] = None


@app.post('/api/plan/{predio}')
def plan_salvar(predio: str, corpo: Calibracao, request: Request):
  _so_local(request)
  if predio not in dados.predios_studio(predios.atual()):
    raise HTTPException(404, f'prédio {predio!r} desconhecido')
  _envelope(predio)
  try:
    plantas.salvar_calibracao(predio, corpo.paredes, corpo.foto, andar=corpo.andar)
  except (OSError, ValueError) as erro:
    raise HTTPException(422, str(erro))
  atual = _payload()
  atual['plantas'], atual['plantasAvisos'] = plantas.montar_plantas(atual['envelopes'])
  return {'plantas': atual['plantas'], 'plantasAvisos': atual['plantasAvisos']}


app.mount('/', StaticFiles(directory=WEB_DIR, html=True), name='static')
```

- [ ] **Step 5: Implementar `run.py`**

`src/studio/run.py`:

```python
#!/usr/bin/env python3
"""Sobe o QoE Studio novo em localhost.

  ./venv/bin/python src/studio/run.py [--port 8100]
"""

import argparse
import os
import sys

# Rodado como script, sys.path[0] é src/studio: troca por src para `import studio` funcionar.
sys.path[0] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def main():
  parser = argparse.ArgumentParser(description='QoE Studio (novo)')
  parser.add_argument('--port', type=int, default=8100)
  args = parser.parse_args()

  from studio import portas
  if not portas.livre(args.port):
    raise SystemExit(f'porta {args.port} ocupada: feche o que está nela ou use --port')

  import uvicorn
  from studio.api import app
  print(f'QoE Studio  ->  http://127.0.0.1:{args.port}')
  uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
  main()
```

- [ ] **Step 6: Rodar e ver passar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_api.py tests/test_studio_novo_isolamento.py -v`
Expected: 6 testes, OK.

- [ ] **Step 7: Ponto de commit**

Arquivos: `src/studio/portas.py`, `src/studio/api.py`, `src/studio/run.py`, `tests/test_studio_novo_api.py`.
Mensagem sugerida: `feat(studio-novo): API de Dados, Conjunto, upload e planta; run.py`

---

### Task 11: Teste de não escrita, verificação manual e CHANGELOG

**Files:**
- Modify: `tests/test_studio_novo_isolamento.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Acrescentar o teste de não escrita**

Em `tests/test_studio_novo_isolamento.py`, trocar o bloco de imports do topo por:

```python
import ast
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apoio_studio_novo as A  # noqa: E402

from studio import caminhos, conjunto, dados, predios, upload  # noqa: E402
```

E acrescentar, antes do `if __name__ == '__main__':`:

```python
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
```

`mock.patch.multiple` (dentro de `pastas_temporarias`) restaura `caminhos.DATA_DIR` ao sair, inclusive a troca feita dentro do bloco.

- [ ] **Step 2: Rodar**

Run: `./venv/bin/python -m unittest tests/test_studio_novo_isolamento.py -v`
Expected: 3 testes, OK. Leva alguns segundos (lê o `data/` real).

- [ ] **Step 3: Rodar a suíte inteira**

Run: `./venv/bin/python -m unittest discover -s tests -q 2>&1 | tail -4`
Expected: `OK`. São os 523 testes que já existiam mais os novos. Se algum teste antigo quebrar, pare e reporte: esta parte não deveria tocar em nada fora de `src/studio/` e `tests/`.

Run: `node --test tests/js/ 2>&1 | grep -E "^# (pass|fail)"`
Expected: `# fail 0`.

- [ ] **Step 4: Verificação manual no navegador**

Run: `./venv/bin/python src/studio/run.py --port 8200`
Expected: `QoE Studio  ->  http://127.0.0.1:8200`.

Usar a porta 8200 para não colidir com o Studio antigo (8100), se ele estiver aberto. No navegador (Playwright, se disponível):
1. Abrir `http://127.0.0.1:8200/#dados`. A matriz aparece com os prédios do conjunto padrão.
2. Clicar no chip do conjunto. O painel lista os datasets e, no fim, a dobra "Inutilizáveis" com os CSVs antigos de `data/` sem `local`.
3. Desligar um dataset, recarregar a página e conferir que ele continua desligado (`.studio/conjunto.json`).
4. Alternar Matriz e Planta. A planta abre como no Studio antigo.
5. Em Adicionar dados, escolher um CSV de teste (ex.: gerar com `A.frame` num script do scratchpad), verificar e confirmar. O arquivo aparece em `.studio/uploads/` e **não** em `data/`.
6. Rodar `git status --short data/ src/ml/` e conferir que está vazio.

Parar o servidor com Ctrl+C.

- [ ] **Step 5: CHANGELOG**

Acrescentar no topo de `CHANGELOG.md` (antes da entrada de 2026-10-20):

```markdown
# Changelog — Studio novo, parte 1: Dados e Conjunto

**Data:** 2026-10-22

## Mudanças

- Pacote novo `src/studio/` (sobe com `./venv/bin/python src/studio/run.py`), construído ao lado do Studio antigo, que continua em `src/ml/studio/` até o novo cobrir tudo.
- Isolado do benchmark: não importa `ml.*`, lê `data/` sem nunca escrever lá, e tem configuração própria em `src/studio/config/` (prédios, aplicações, colunas), copiada do core uma vez. Teste automático confere que um ciclo de upload, conjunto e payload não altera `data/`, `src/ml/`, `mlflow.db` nem `mlruns/`.
- Uploads vão para `.studio/uploads/` (fora do git); prédios novos para `src/studio/config/predios.json`. O conjunto ativo fica gravado em `.studio/conjunto.json`.
- Área Dados e painel Conjunto migrados do Studio antigo. Saíram as pendências de classificação de colunas, contadores, Laboratório e Modelo antigo.

---
```

- [ ] **Step 6: Ponto de commit**

Arquivos: `tests/test_studio_novo_isolamento.py`, `CHANGELOG.md`.
Mensagem sugerida: `test(studio-novo): Dados e Conjunto não escrevem no que é do benchmark`

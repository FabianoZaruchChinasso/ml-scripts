# Correção de Escala e Níveis de Agrupamento — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **POLÍTICA DE COMMIT — OVERRIDE DO PROJETO:** o dono do repositório faz **todos** os commits. Passos
> marcados **"Commit (AÇÃO DO USUÁRIO)"** NÃO devem ser executados por um agente. Pare, mostre o
> comando e aguarde. Isso sobrepõe a orientação padrão de "o agente commita com frequência".

**Goal:** Colocar os alvos dos dois prédios na mesma unidade física e permitir avaliar em dois níveis
de agrupamento — por posição (7 grupos, número principal) e por prédio (2 grupos, viabilidade).

**Architecture:** Um script versionado regenera `metrics-20260630-out.csv` desfazendo a normalização
dos alvos (multiplicando pelos máximos do CSV bruto — inversão provada exata contra o arquivo
`-out-filllast.csv`). O `core/sites.py` passa a resolver `local` em dois níveis, e os três scripts de
CLI ganham `--group-level`.

**Tech Stack:** Python 3.12, pandas, scikit-learn 1.5.2, `unittest` (stdlib).

**Decisões que originaram este plano:** agrupamento **B principal + A secundário**; escala em
**unidades físicas**; correção via **script de regeração**.

---

## Contexto essencial para quem implementa

1. **`local` NÃO é a residência — é a posição de medição dentro de um prédio.** O dataset bruto usa
   nomes de cômodo (`sala` 1–2 m, `quarto` 10 m, `suite` 13 m) e o transform os reescreve como
   `1`/`2`/`3`. O coworking usa rótulos de distância (`cwpb-2m`, `cwpb-10m`, `cwpb-10m-2a`,
   `cwpb-13m`). São **2 prédios e 7 posições**, não 4 residências.
2. **O `core/sites.py` atual está errado** — rotula três cômodos de uma residência como `home-1/2/3`.
   A Task 3 corrige isso e **quebra dois testes existentes de propósito**; a própria task os atualiza.
3. **Só `data/metrics-20260630-out.csv` tem alvos normalizados** (3 dos 4). O
   `metrics-20260630-out-filllast.csv` já está em unidades físicas e serve de **referência de
   verdade** para verificar a correção.
4. **Todos os CSVs estão versionados** (commit `b482348`). Sobrescrever é seguro:
   `git checkout data/metrics-20260630-out.csv` restaura.
5. **Classificação está fora deste plano.** `qoe_dw_score` foi derivado dos alvos já normalizados e
   sua fórmula vivia no `.dsc`, que nunca foi versionado. Ver seção "Bloqueado" no fim.
6. Rode tudo a partir da raiz `/home/venko/ml/TR069/ml-scripts`. Verifique com
   `python3 -m unittest tests.test_ml_core -v` — **nunca** com `unittest discover` (a suíte antiga
   `test_fn_metrics.py` está quebrada por um fixture ausente, o que não é culpa sua).
7. Convenção do repo: indentação de 2 espaços.

## Estrutura de arquivos

| Caminho | Status | Responsabilidade |
|---|---|---|
| `src/ml/fix_target_scale.py` | Criar | Regenera um `-out.csv` com alvos em unidade física. |
| `src/ml/core/sites.py` | Modificar | Resolução em dois níveis: `position` e `building`. |
| `src/ml/core/data.py` | Modificar | Repassa `group_level` para `resolve_site_id`. |
| `src/ml/regression_benchmark.py` | Modificar | Flag `--group-level`. |
| `src/ml/classification_benchmark.py` | Modificar | Flag `--group-level`. |
| `src/ml/compare_protocols.py` | Modificar | Flag `--group-level`. |
| `tests/test_ml_core.py` | Modificar | Testes novos + atualização dos que mudam de propósito. |
| `data/metrics-20260630-out.csv` | Regenerar | Alvos passam de `[0,1]` para Mbps/ms. |
| `CHANGELOG.md` | Modificar | Registrar a correção e os novos números. |

---

## Task 1: Lógica pura de desnormalização

**Files:**
- Create: `src/ml/fix_target_scale.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Escreva os testes que falham**

Acrescente em `tests/test_ml_core.py`, acima do bloco `if __name__`:

```python
from ml.fix_target_scale import denormalise_targets


class TestDenormaliseTargets(unittest.TestCase):
  def test_normalised_column_is_multiplied_back(self):
    df = pd.DataFrame({'speedtest_down_mbps': [0.0, 0.5, 1.0]})
    fixed, report = denormalise_targets(df, {'speedtest_down_mbps': 600.0})
    self.assertEqual(list(fixed['speedtest_down_mbps']), [0.0, 300.0, 600.0])
    self.assertIn('600', report['speedtest_down_mbps'])

  def test_already_physical_column_is_untouched(self):
    # Idempotência: rodar o script duas vezes não pode multiplicar duas vezes.
    df = pd.DataFrame({'latency_ms': [10.0, 500.0, 1947.1]})
    fixed, report = denormalise_targets(df, {'latency_ms': 4464.33})
    self.assertEqual(list(fixed['latency_ms']), [10.0, 500.0, 1947.1])
    self.assertEqual(report['latency_ms'], 'already physical')

  def test_absent_column_is_skipped_silently(self):
    df = pd.DataFrame({'jitter_ms': [0.0, 1.0]})
    fixed, report = denormalise_targets(df, {'nao_existe': 100.0})
    self.assertNotIn('nao_existe', report)
    self.assertEqual(list(fixed['jitter_ms']), [0.0, 1.0])
```

- [ ] **Step 2: Rode os testes e confirme a falha**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ModuleNotFoundError: No module named 'ml.fix_target_scale'`

- [ ] **Step 3: Escreva a implementação**

Crie `src/ml/fix_target_scale.py`:

```python
"""Converte alvos normalizados de volta para unidades físicas num CSV transformado.

O transform da residência dividiu três colunas-alvo pelo máximo da própria coluna;
o transform do coworking não dividiu nenhuma. Isso torna os dois prédios
incomparáveis: 0,5 significa 334 Mbps num e 284 no outro. Este script multiplica as
colunas normalizadas de volta pelos máximos encontrados no CSV bruto, deixando todos
os prédios com os alvos em Mbps / ms.

Idempotente: uma coluna que já está em unidade física é deixada intacta.
"""

import argparse
import os
import sys

import pandas as pd

TARGETS = ['speedtest_down_mbps', 'speedtest_up_mbps', 'latency_ms', 'jitter_ms']

# Uma coluna normalizada tem máximo exatamente 1.0; todo alvo físico deste projeto
# fica muito acima disso (o menor observado é ~292 Mbps).
NORMALISED_MAX = 1.5


def denormalise_targets(df: pd.DataFrame, raw_maxima: dict):
  """Devolve (df_corrigido, relatorio).

  Colunas ausentes são ignoradas; colunas já em unidade física são preservadas,
  o que torna a operação segura de repetir.
  """
  corrected = df.copy()
  report = {}
  for column, maximum in raw_maxima.items():
    if column not in corrected.columns:
      continue
    observed = corrected[column].max()
    if pd.isna(observed) or observed > NORMALISED_MAX:
      report[column] = 'already physical'
      continue
    corrected[column] = corrected[column] * maximum
    report[column] = f'multiplied by {maximum:.6f}'
  return corrected, report
```

- [ ] **Step 4: Rode os testes e confirme que passam**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 39 tests` … `OK` (36 anteriores + 3 novos)

- [ ] **Step 5: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/fix_target_scale.py tests/test_ml_core.py
git commit -m "feat(ml): add target denormalisation logic"
```

---

## Task 2: CLI do script e regeração do CSV

**Files:**
- Modify: `src/ml/fix_target_scale.py`
- Regenerate: `data/metrics-20260630-out.csv`

- [ ] **Step 1: Acrescente o CLI**

Adicione ao fim de `src/ml/fix_target_scale.py`:

```python
def read_raw_maxima(raw_path: str) -> dict:
  """Máximos por alvo no CSV bruto — as constantes exatas usadas no normalize."""
  raw = pd.read_csv(raw_path, low_memory=False)
  return {c: float(raw[c].max()) for c in TARGETS if c in raw.columns}


def main():
  parser = argparse.ArgumentParser(
    description='Reescreve um -out.csv com os alvos em unidade física')
  parser.add_argument('--raw', required=True,
                      help='CSV bruto de onde os máximos originais são lidos')
  parser.add_argument('--out', required=True,
                      help='CSV transformado a corrigir (sobrescrito no lugar)')
  parser.add_argument('--reference', default=None,
                      help='CSV opcional já em unidade física, para verificar a correção')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='Mostra o que faria sem escrever')
  args = parser.parse_args()

  maxima = read_raw_maxima(args.raw)
  df = pd.read_csv(args.out, low_memory=False)
  fixed, report = denormalise_targets(df, maxima)

  print(f'{args.out}:')
  for column, action in sorted(report.items()):
    print(f'  {column:22} {action}')

  if args.reference is not None:
    ref = pd.read_csv(args.reference, low_memory=False)
    if len(ref) != len(fixed):
      print(f'  AVISO: referência tem {len(ref)} linhas e o alvo {len(fixed)}; '
            'verificação pulada')
    else:
      for column in report:
        if column not in ref.columns:
          continue
        both = fixed[column].notna() & ref[column].notna()
        worst = (fixed[column][both] - ref[column][both]).abs().max()
        status = 'OK' if worst < 1e-6 else 'DIVERGE'
        print(f'  verificação {column:22} maior_diferenca={worst:.3e} {status}')

  if args.dry_run:
    print('  (dry-run: nada foi escrito)')
    return

  fixed.to_csv(args.out, index=False)
  print(f'  escrito: {args.out}')


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Rode em dry-run e confira a verificação**

Run:
```bash
python3 src/ml/fix_target_scale.py \
  --raw data/metrics-20260630.csv \
  --out data/metrics-20260630-out.csv \
  --reference data/metrics-20260630-out-filllast.csv \
  --dry-run
```
Expected: `speedtest_down_mbps`, `latency_ms` e `jitter_ms` com `multiplied by ...`;
`speedtest_up_mbps` com `already physical`; as três linhas de `verificação` com
`maior_diferenca` na ordem de `1e-13` e status `OK`; e `(dry-run: nada foi escrito)`.

**Se alguma verificação disser `DIVERGE`, PARE e reporte** — significa que a constante de inversão
não confere e o CSV não deve ser sobrescrito.

- [ ] **Step 3: Aplique de verdade**

Run:
```bash
python3 src/ml/fix_target_scale.py \
  --raw data/metrics-20260630.csv \
  --out data/metrics-20260630-out.csv \
  --reference data/metrics-20260630-out-filllast.csv
```
Expected: mesma saída, terminando em `escrito: data/metrics-20260630-out.csv`.

- [ ] **Step 4: Confirme idempotência**

Rode exatamente o mesmo comando de novo.
Expected: agora os quatro alvos devem dizer `already physical` e os valores não podem mudar.

Confirme que os dois prédios ficaram comparáveis:
```bash
python3 -c "
import pandas as pd
r = pd.read_csv('data/metrics-20260630-out.csv', low_memory=False)
o = pd.read_csv('data/metrics-office-20260722-out.csv', low_memory=False)
for c in ['speedtest_down_mbps','speedtest_up_mbps','latency_ms','jitter_ms']:
    print(f'{c:22} residencia_max={r[c].max():10.2f}  coworking_max={o[c].max():10.2f}')
"
```
Expected: nenhum máximo igual a `1.00` — todos em dezenas/centenas/milhares.

- [ ] **Step 5: Confirme que a suíte segue verde**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 39 tests` … `OK`

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/fix_target_scale.py data/metrics-20260630-out.csv
git commit -m "fix(data): restore residence targets to physical units"
```

---

## Task 3: Resolução em dois níveis no `sites.py`

**Files:**
- Modify: `src/ml/core/sites.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Atualize os testes existentes que mudam de propósito**

Em `tests/test_ml_core.py`, na classe `TestResolveSiteId`, **substitua** os dois primeiros métodos
(`test_numeric_locals_become_home_ids` e `test_all_office_values_collapse_to_one_site`) por:

```python
  def test_numeric_locals_become_residence_positions(self):
    result = resolve_site_id(pd.Series([1.0, 2.0, 3.0, 1.0]))
    self.assertEqual(list(result),
                     ['res-sala', 'res-quarto', 'res-suite', 'res-sala'])

  def test_room_names_resolve_to_the_same_positions_as_their_numbers(self):
    # O transform reescreve os nomes como 1/2/3; as duas grafias são a mesma posição.
    numbers = resolve_site_id(pd.Series([1.0, 2.0, 3.0]))
    names = resolve_site_id(pd.Series(['sala', 'quarto', 'suite']))
    self.assertEqual(list(numbers), list(names))

  def test_office_positions_stay_distinct_at_position_level(self):
    office = pd.Series(['cwpb-2m', 'cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m'])
    result = resolve_site_id(office)
    self.assertEqual(result.nunique(), 4)

  def test_building_level_collapses_to_two_groups(self):
    mixed = pd.Series([1.0, 2.0, 3.0, 'cwpb-2m', 'cwpb-13m'])
    result = resolve_site_id(mixed, level='building')
    self.assertEqual(sorted(result.unique()), ['coworking', 'residencia'])

  def test_unknown_level_raises(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_site_id(pd.Series([1.0]), level='predio')
    self.assertIn('predio', str(ctx.exception))
```

Os quatro testes restantes da classe (`test_unknown_value_raises`, `test_empty_value_raises`,
`test_non_integer_float_raises`, `test_infinite_value_raises`) **não mudam**.

- [ ] **Step 2: Rode e confirme a falha**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: falhas em `TestResolveSiteId` — `res-sala` esperado mas `home-1` recebido, e
`TypeError` sobre o argumento `level`.

- [ ] **Step 3: Reescreva `src/ml/core/sites.py`**

Substitua o conteúdo inteiro do arquivo por:

```python
import math

import pandas as pd

OFFICE_PREFIX = 'cwpb'
RESIDENCE_BUILDING = 'residencia'
COWORKING_BUILDING = 'coworking'

# `local` grava a POSIÇÃO de medição dentro de um prédio, não o prédio. O
# transform da residência reescreve os nomes de cômodo como 1/2/3 antes de os
# dados chegarem aqui, então as duas grafias resolvem para a mesma posição.
RESIDENCE_POSITIONS = {
  '1': 'res-sala',
  'sala': 'res-sala',
  '2': 'res-quarto',
  'quarto': 'res-quarto',
  '3': 'res-suite',
  'suite': 'res-suite',
}

GROUP_LEVELS = ('position', 'building')


def _lookup_key(value) -> str:
  """Canonicaliza uma célula de `local`: '1.0' e 'Sala' viram chaves de busca."""
  if pd.isna(value):
    raise ValueError(
      "site resolution failed: 'local' contains an empty value. "
      'Every row must belong to a known position.'
    )
  text = str(value).strip().lower()
  try:
    number = float(text)
  except ValueError:
    return text
  if not math.isfinite(number) or not number.is_integer():
    raise ValueError(
      f'site resolution failed: unrecognised local value {value!r}. '
      'Add an explicit rule in core/sites.py; never let an unknown value form its own group.'
    ) from None
  return str(int(number))


def _resolve_one(value, level: str) -> str:
  key = _lookup_key(value)
  if key.startswith(OFFICE_PREFIX):
    return COWORKING_BUILDING if level == 'building' else key
  if key in RESIDENCE_POSITIONS:
    return RESIDENCE_BUILDING if level == 'building' else RESIDENCE_POSITIONS[key]
  raise ValueError(
    f'site resolution failed: unrecognised local value {value!r}. '
    'Add an explicit rule in core/sites.py; never let an unknown value form its own group.'
  )


def resolve_site_id(local_values: pd.Series, level: str = 'position') -> pd.Series:
  """Mapeia valores brutos de `local` para identificadores canônicos de grupo.

  `local` é a posição de medição dentro de um prédio: a residência usa nomes de
  cômodo (reescritos como 1/2/3 pelo transform) e o coworking usa rótulos de
  distância (`cwpb-*`).

  level='position' -> 7 grupos, um por ponto de medição (padrão, número principal).
  level='building' -> 2 grupos, `residencia` e `coworking` (viabilidade, n=2).
  """
  if level not in GROUP_LEVELS:
    raise ValueError(
      f'unknown group level {level!r}; expected one of {list(GROUP_LEVELS)}')
  return local_values.map(lambda value: _resolve_one(value, level))
```

- [ ] **Step 4: Rode e confirme que passam**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 42 tests` … `OK`

Se o `TestIntegration` falhar por esperar `home-*`/`office-cwpb`, ajuste **apenas** as asserções
sobre os nomes dos grupos — as propriedades que ele verifica (disjunção, cada grupo testado uma vez)
continuam valendo.

- [ ] **Step 5: Verifique contra os dados reais**

Run:
```bash
python3 -c "
import sys; sys.path.append('src')
import pandas as pd
from ml.core.sites import resolve_site_id
for f in ['data/metrics-20260630-out.csv','data/metrics-office-20260722-out.csv']:
    loc = pd.read_csv(f, low_memory=False)['local']
    print(f)
    print('   position:', sorted(resolve_site_id(loc).unique()))
    print('   building:', sorted(resolve_site_id(loc, level='building').unique()))
"
```
Expected:
```
data/metrics-20260630-out.csv
   position: ['res-quarto', 'res-sala', 'res-suite']
   building: ['residencia']
data/metrics-office-20260722-out.csv
   position: ['cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m', 'cwpb-2m']
   building: ['coworking']
```

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/core/sites.py tests/test_ml_core.py
git commit -m "fix(ml): resolve local as measurement position, add building level"
```

---

## Task 4: Repasse de `group_level` no `data.py`

**Files:**
- Modify: `src/ml/core/data.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Escreva o teste que falha**

Acrescente à classe `TestData` em `tests/test_ml_core.py`:

```python
  def test_group_level_building_merges_positions(self):
    a = self._write_csv([{'local': 1.0, 'feat': 1.0, 'target': 2.0},
                         {'local': 2.0, 'feat': 2.0, 'target': 3.0}])
    b = self._write_csv([{'local': 'cwpb-2m', 'feat': 3.0, 'target': 4.0}])
    by_position = load_datasets([a, b])
    by_building = load_datasets([a, b], group_level='building')
    self.assertEqual(by_position['site_id'].nunique(), 3)
    self.assertEqual(sorted(by_building['site_id'].unique()),
                     ['coworking', 'residencia'])
```

- [ ] **Step 2: Rode e confirme a falha**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `TypeError: load_datasets() got an unexpected keyword argument 'group_level'`

- [ ] **Step 3: Implemente**

Em `src/ml/core/data.py`, troque a assinatura de `load_datasets` e a chamada a `resolve_site_id`:

```python
def load_datasets(paths, target: str = None, group_level: str = 'position') -> pd.DataFrame:
```

e, dentro do laço:

```python
    frame[SITE_COLUMN] = resolve_site_id(frame[RAW_SITE_COLUMN], level=group_level)
```

Atualize também a docstring da função para:

```python
  """Load and concatenate CSVs, attaching a canonical site_id column.

  `group_level` selects the grouping granularity: 'position' (default, one group
  per measurement spot) or 'building' (one group per physical building).
  Rows whose target is empty are dropped and the count reported.
  """
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 43 tests` … `OK`

- [ ] **Step 5: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/core/data.py tests/test_ml_core.py
git commit -m "feat(ml): thread group_level through the dataset loader"
```

---

## Task 5: Flag `--group-level` nos três scripts

**Files:**
- Modify: `src/ml/regression_benchmark.py`
- Modify: `src/ml/classification_benchmark.py`
- Modify: `src/ml/compare_protocols.py`

- [ ] **Step 1: `regression_benchmark.py`**

Em `parse_args()`, logo após o argumento `--csv`, acrescente:

```python
  parser.add_argument('--group-level', choices=['position', 'building'], default='position',
                      help="'position' (padrão): 7 grupos, um por ponto de medição. "
                           "'building': 2 grupos, residencia/coworking (viabilidade, n=2)")
```

Em `main()`, troque a chamada de carga por:

```python
  df = load_datasets(parse_csv_list(args.csv), group_level=args.group_level)
```

e, logo abaixo da linha que imprime `Sites:`, acrescente:

```python
  print(f'Group level: {args.group_level}')
```

- [ ] **Step 2: `classification_benchmark.py`**

Em `parse_args()`, logo após `--csv`, acrescente o **mesmo** bloco:

```python
  parser.add_argument('--group-level', choices=['position', 'building'], default='position',
                      help="'position' (padrão): 7 grupos, um por ponto de medição. "
                           "'building': 2 grupos, residencia/coworking (viabilidade, n=2)")
```

Em `main()`, troque a carga por:

```python
  df = load_datasets(parse_csv_list(args.csv), target=args.qoe_column,
                     group_level=args.group_level)
```

e troque a linha de estratégia por:

```python
  print(f'Split strategy: leave-one-{args.group_level}-out '
        f'({df[SITE_COLUMN].nunique()} folds)')
```

- [ ] **Step 3: `compare_protocols.py`**

Em `main()`, acrescente o argumento após `--target`:

```python
  parser.add_argument('--group-level', choices=['position', 'building'], default='position',
                      help="'position' (padrão) ou 'building' (viabilidade, n=2)")
```

e troque a carga por:

```python
  df = load_datasets(args.csv.split(','), target=args.target, group_level=args.group_level)
```

- [ ] **Step 4: Verifique os três nos dois níveis**

Run:
```bash
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps --group-level position 2>&1 | head -14
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps --group-level building 2>&1 | head -12
```
Expected: o primeiro imprime `Group level: position` e um plano com **7 folds**; o segundo imprime
`Group level: building` e um plano com **2 folds** (`residencia`, `coworking`) mais o aviso
`only 2 sites available`. Nenhum dos dois pode levantar exceção.

- [ ] **Step 5: Confirme que a suíte segue verde**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 43 tests` … `OK`

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/regression_benchmark.py src/ml/classification_benchmark.py src/ml/compare_protocols.py
git commit -m "feat(ml): add --group-level to the benchmark and comparison scripts"
```

---

## Task 6: Gerar os dois números e registrar

**Files:**
- Modify: `docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md`

- [ ] **Step 1: Número principal (B — por posição)**

Run:
```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps --group-level position 2>&1 | tee /tmp/b_position.txt
```
Guarde a saída. Agora que a escala foi corrigida, os R² **não** devem mais ser fortemente negativos.

- [ ] **Step 2: Número secundário (A — por prédio)**

Run:
```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps --group-level building 2>&1 | tee /tmp/a_building.txt
```
Espere o aviso `only 2 sites available` — ele é correto e deve constar do registro.

- [ ] **Step 3: Registre no spec**

Primeiro confirme qual é a última seção do spec:

Run: `grep -n "^## " docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md | tail -1`
Expected: `## 13. Measured optimism of the legacy protocol` (se for outro número, use o próximo
inteiro depois dele no comando abaixo, no lugar de `14`).

Agora monte a seção a partir das saídas já capturadas — isto evita colagem manual:

```bash
SPEC=docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md
{
  printf '\n## 14. Resultados após a correção de escala\n\n'
  printf 'Alvo: `speedtest_down_mbps`, pool combinado (residência + coworking), alvos em unidade física.\n\n'
  printf '### Principal — leave-one-position-out (7 folds)\n\n'
  printf '```\n'; cat /tmp/b_position.txt; printf '```\n\n'
  printf '### Viabilidade — leave-one-building-out (2 folds)\n\n'
  printf '```\n'; cat /tmp/a_building.txt; printf '```\n\n'
  printf '**Leitura.** O número por posição é a estimativa rigorosa: mede generalização para um\n'
  printf 'ponto de medição não visto, em prédio conhecido. O número por prédio é uma demonstração\n'
  printf 'única de transferência entre prédios — com n=2 evidencia viabilidade, mas não estima\n'
  printf 'desempenho.\n'
} >> "$SPEC"
```

- [ ] **Step 3b: Confira o resultado**

Run: `tail -40 docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md`
Expected: a nova seção `## 14`, com os dois blocos de saída preenchidos e nenhum marcador vazio.

- [ ] **Step 4: Commit (AÇÃO DO USUÁRIO — não execute)**

O spec é gitignored, então não entra no commit; nada a versionar nesta task.

---

## Task 7: Atualizar o CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Corrija a seção 5.2**

Em `CHANGELOG.md`, na seção `### 5.2`, substitua o parágrafo final que começa com
`Das 36 colunas numéricas compartilhadas` por:

```markdown
Das 36 colunas numéricas compartilhadas, **apenas essas 3 divergiam** — todas as features já estavam
consistentes.

**Corrigido** pelo `src/ml/fix_target_scale.py`: os três alvos da residência foram multiplicados de
volta pelos máximos do CSV bruto, deixando os dois prédios em Mbps/ms. A inversão é exata — verificada
contra `metrics-20260630-out-filllast.csv` (o gêmeo não-normalizado do mesmo transform), com diferença
máxima de 1e-13 nas 9.635 linhas. O script é idempotente: colunas já em unidade física são preservadas.
```

- [ ] **Step 2: Atualize a seção 6 (pendências)**

Substitua o primeiro item (`**core/sites.py precisa ser corrigido**` e suas três alternativas) por:

```markdown
- **Resolvido:** `core/sites.py` agora trata `local` como posição de medição e oferece dois níveis de
  agrupamento (`--group-level position|building`). A decisão adotada foi **B principal + A
  secundário**: o número rigoroso é por posição (7 folds) e o de viabilidade é por prédio (2 folds,
  n=2, explicitamente caveated). **C — coletar mais prédios** segue sendo o desbloqueio real.
- **Resolvido:** a normalização inconsistente dos alvos (5.2).
```

- [ ] **Step 3: Confirme que nada mais afirma "4 sites"**

Run: `grep -n "4 sites independentes\|3 residências\|home-1\|home-2\|home-3\|office-cwpb" CHANGELOG.md`
Expected: só ocorrências dentro do aviso de correção da seção 5 e/ou da tabela histórica da 5.1 —
nenhuma afirmando o estado atual do código.

- [ ] **Step 4: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add CHANGELOG.md
git commit -m "docs: record scale fix and grouping-level decision"
```

---

## Verificação final

- [ ] **Suíte verde**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 43 tests` … `OK`

- [ ] **Nenhum alvo continua normalizado**

Run:
```bash
python3 -c "
import pandas as pd
for f in ['data/metrics-20260630-out.csv','data/metrics-office-20260722-out.csv']:
    d = pd.read_csv(f, low_memory=False)
    bad = [c for c in ['speedtest_down_mbps','speedtest_up_mbps','latency_ms','jitter_ms']
           if c in d.columns and d[c].max() <= 1.5]
    print(f, '-> normalizados:', bad or 'nenhum')
"
```
Expected: `nenhum` para os dois arquivos.

- [ ] **Os três scripts rodam nos dois níveis**

Run:
```bash
for lvl in position building; do
  python3 src/ml/regression_benchmark.py \
    --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
    --targets speedtest_down_mbps --group-level $lvl >/dev/null 2>&1 \
    && echo "regression --group-level $lvl OK" || echo "regression --group-level $lvl FALHOU"
done
```
Expected: `OK` nos dois.

- [ ] **Nenhum `home-1`/`office-cwpb` sobrou no código**

Run: `grep -rn "home-1\|home-2\|home-3\|office-cwpb" src/ tests/ --include=*.py | grep -v experimental/`
Expected: sem saída.

---

## Fora deste plano — bloqueado

**Classificação / `qoe_dw_score`.** Nos arquivos `-qoe.csv` os quatro alvos estão normalizados nos
**dois** prédios, mas por constantes diferentes (o máximo de cada prédio). O `qoe_dw_score` foi
calculado a partir desses valores, o que explica a divergência de escala (residência até 6269,
coworking até 1,96): dividir a latência por 4464 em vez de 1947 faz a razão explodir.

Corrigir exige **recalcular `qoe_dw_score` a partir dos valores em unidade física** — e a fórmula
vivia no arquivo `.dsc` de diretivas, que **nunca foi versionado** (`git log --all -- "*.dsc"` não
retorna nada). A correlação com `speedtest_down/latency_ms` é 0,86 / 0,84, então é derivado dessas
grandezas, mas não por uma fórmula que dê para inferir com segurança.

**Para desbloquear:** recupere o `.dsc` usado para gerar os `-qoe.csv` (ou informe a fórmula do
`qoe_dw_score`) e versione-o no repositório. Enquanto isso, o `classification_benchmark.py` só
produz números confiáveis dentro de um único prédio, nunca no pool combinado.

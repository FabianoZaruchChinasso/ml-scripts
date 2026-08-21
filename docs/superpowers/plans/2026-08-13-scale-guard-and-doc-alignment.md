# Guard de Escala e Alinhamento da Documentação — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **POLÍTICA DE COMMIT — OVERRIDE DO PROJETO:** o dono do repositório faz **todos** os commits. Passos
> marcados **"Commit (AÇÃO DO USUÁRIO)"** NÃO devem ser executados por um agente. Pare, mostre o
> comando e aguarde.

**Goal:** Tornar barulhenta de novo a incompatibilidade de escala entre prédios — que hoje passa
silenciosa na classificação — e corrigir quatro afirmações obsoletas na documentação.

**Architecture:** Um guard novo em `core/metrics.py` detecta quando a faixa inteira de um grupo fica
abaixo do primeiro quartil de outro (sinal estrutural de unidades diferentes), chamado nos três
scripts antes de qualquer treino. Mais quatro substituições de texto em documentos que descrevem o
estado atual do código.

**Tech Stack:** Python 3.12, pandas, `unittest` (stdlib).

---

## Por que este plano existe

Antes da correção do modelo de sites, a classificação no pool combinado **falhava alto**: o escritório
inteiro era um grupo, ao ser isolado no fold de teste os limiares vinham só da residência, todo o
escritório caía em `bad`, e `assert_multiclass` disparava.

Depois da correção (correta) para agrupamento por posição, o escritório está sempre também no treino.
Os limiares passam a ser calculados sobre uma mistura de duas escalas incompatíveis — e o guard
existente não vê problema, porque cada fold tem ≥2 classes. Medido no pool real:

```
             bad     mid   good
coworking   81,6%   18,4%   0,0%      ← zero 'good'
residencia  15,2%   55,5%  29,3%
```

A classe virou proxy de "de qual prédio veio esta linha", que o modelo infere trivialmente das
features. **O `qoe_dw_score` continua com escalas incompatíveis** (residência 0–6269, escritório
0–1,96) — isso não foi corrigido, só deixou de ser detectado. A correção de raiz depende da fórmula
perdida do `.dsc` e segue bloqueada; este plano restaura a detecção.

## A regra escolhida, e por que ela não tem constante mágica

**Se o máximo de um grupo fica abaixo do primeiro quartil de outro, os dois não estão na mesma
unidade.** Duas medições da mesma grandeza física têm distribuições que se sobrepõem; faixas
completamente disjuntas indicam unidades diferentes, não qualidade diferente.

Medido nos dados reais, nos dois níveis de agrupamento:

| Alvo | Nível posição (7 grupos) | Nível prédio (2 grupos) |
|---|---|---|
| `speedtest_down_mbps` | não dispara | não dispara |
| `speedtest_up_mbps` | não dispara | não dispara |
| `latency_ms` | não dispara | não dispara |
| `jitter_ms` | não dispara | não dispara |
| `qoe_dw_score` (quebrado) | **dispara** (7 pares) | **dispara** |

Ou seja: zero falso-positivo nos quatro alvos que hoje funcionam — inclusive entre posições distintas
do mesmo prédio, que era o risco real — e detecção do caso quebrado nos dois níveis.

## Estrutura de arquivos

| Caminho | Status | Responsabilidade |
|---|---|---|
| `src/ml/core/metrics.py` | Modificar | Novo `assert_comparable_scales`. |
| `tests/test_ml_core.py` | Modificar | Testes do guard. |
| `src/ml/regression_benchmark.py` | Modificar | Chamar o guard. |
| `src/ml/classification_benchmark.py` | Modificar | Chamar o guard. |
| `src/ml/compare_protocols.py` | Modificar | Chamar o guard. |
| `docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md` | Modificar | 3 afirmações obsoletas. |
| `CHANGELOG.md` | Modificar | 1 contagem obsoleta. |

**NÃO editar** os arquivos em `docs/superpowers/plans/` — são registros históricos do que foi
planejado em determinada data. Corrigi-los retroativamente apagaria o histórico. As afirmações
obsoletas neles ficam como estão, de propósito.

---

## Task 1: O guard `assert_comparable_scales`

**Files:**
- Modify: `src/ml/core/metrics.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Escreva os testes que falham**

Acrescente à classe `TestMetrics` em `tests/test_ml_core.py` (a classe já existe; adicione estes três
métodos ao final dela):

```python
  def test_disjoint_scales_raise(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([0.1, 0.5, 1.9, 3.0, 20.0, 6000.0])
    groups = pd.Series(['coworking'] * 3 + ['residencia'] * 3)
    with self.assertRaises(ValueError) as ctx:
      assert_comparable_scales(y, groups, 'qoe_dw_score')
    message = str(ctx.exception)
    self.assertIn('coworking', message)
    self.assertIn('residencia', message)
    self.assertIn('qoe_dw_score', message)

  def test_overlapping_scales_pass(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([38.0, 94.0, 204.0, 567.0, 48.0, 105.0, 208.0, 667.0])
    groups = pd.Series(['coworking'] * 4 + ['residencia'] * 4)
    assert_comparable_scales(y, groups, 'speedtest_down_mbps')

  def test_single_group_has_nothing_to_compare(self):
    from ml.core.metrics import assert_comparable_scales
    y = pd.Series([1.0, 2.0, 3.0])
    groups = pd.Series(['residencia'] * 3)
    assert_comparable_scales(y, groups, 'qualquer_alvo')
```

(Os dois últimos não usam `assertRaises`: passam se a função **não** levantar. Um teste que só chama a
função e não explode é legítimo aqui — o comportamento sob teste é justamente "ficar quieto".)

- [ ] **Step 2: Rode e confirme a falha**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ImportError: cannot import name 'assert_comparable_scales' from 'ml.core.metrics'`

- [ ] **Step 3: Implemente**

Acrescente ao final de `src/ml/core/metrics.py` (depois de `assert_multiclass`):

```python
def assert_comparable_scales(y: pd.Series, group_ids: pd.Series, target: str) -> None:
  """Levanta erro quando a faixa inteira de um grupo fica abaixo do Q1 de outro.

  Dois grupos medindo a mesma grandeza física têm distribuições que se sobrepõem.
  Um grupo cujo MÁXIMO fica abaixo do primeiro quartil de outro está quase
  certamente registrado em outra unidade — o sintoma clássico de um dataset ter
  passado por `normalize` e o outro não.

  Isso importa mais na classificação: limiares de quartil calculados sobre escalas
  incompatíveis transformam o rótulo de classe num proxy de "de qual grupo veio
  esta linha", que o modelo infere trivialmente das features. Essa falha é
  silenciosa — diferente da regressão, onde aparece como um R² absurdo.
  """
  stats = y.groupby(group_ids).agg(maximum='max', q1=lambda values: values.quantile(0.25))
  for low in stats.index:
    for high in stats.index:
      if low == high:
        continue
      if stats.loc[low, 'maximum'] < stats.loc[high, 'q1']:
        raise ValueError(
          f'escalas incompatíveis para {target!r}: todo valor de {low!r} '
          f'(max={stats.loc[low, "maximum"]:.4f}) fica abaixo do primeiro quartil de '
          f'{high!r} (Q1={stats.loc[high, "q1"]:.4f}). Os grupos quase certamente estão '
          'em unidades diferentes — verifique se um dataset passou por normalize e o '
          'outro não.'
        )
```

- [ ] **Step 4: Rode e confirme que passam**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 51 tests` … `OK` (48 anteriores + 3 novos)

- [ ] **Step 5: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/core/metrics.py tests/test_ml_core.py
git commit -m "feat(ml): detect incompatible target scales across groups"
```

---

## Task 2: Chamar o guard nos três scripts

**Files:**
- Modify: `src/ml/regression_benchmark.py`
- Modify: `src/ml/classification_benchmark.py`
- Modify: `src/ml/compare_protocols.py`

- [ ] **Step 1: `regression_benchmark.py`**

Na linha de import de `ml.core.metrics`, acrescente o novo nome. Troque:

```python
from ml.core.metrics import regression_metrics
```

por:

```python
from ml.core.metrics import assert_comparable_scales, regression_metrics
```

Em `evaluate_target`, logo depois da linha `sites = df[SITE_COLUMN]` e antes de
`folds = list(outer_logo_folds(...))`, acrescente:

```python
  assert_comparable_scales(y, sites, target)
```

- [ ] **Step 2: `classification_benchmark.py`**

Na linha de import de `ml.core.metrics`, troque:

```python
from ml.core.metrics import CLASS_NAMES, apply_thresholds, assert_multiclass, quartile_thresholds
```

por:

```python
from ml.core.metrics import (CLASS_NAMES, apply_thresholds, assert_comparable_scales,
                             assert_multiclass, quartile_thresholds)
```

Em `evaluate`, logo depois da linha `sites = df[SITE_COLUMN]` e antes de
`folds = list(outer_logo_folds(...))`, acrescente:

```python
  assert_comparable_scales(y_raw, sites, qoe_column)
```

- [ ] **Step 3: `compare_protocols.py`**

Na linha de import de `ml.core.metrics`, troque:

```python
from ml.core.metrics import regression_metrics
```

por:

```python
from ml.core.metrics import assert_comparable_scales, regression_metrics
```

Em `main()`, logo depois da linha `X, y = df[FEATURES], df[args.target]`, acrescente:

```python
  assert_comparable_scales(y, df[SITE_COLUMN], args.target)
```

- [ ] **Step 4: Confirme que o guard DISPARA no caso quebrado**

Run:
```bash
python3 src/ml/classification_benchmark.py \
  --csv data/metrics-20260630-qoe.csv,data/metrics-office-20260722-qoe.csv --no-tune 2>&1 | tail -6
```
Expected: um `ValueError` com a mensagem `escalas incompatíveis para 'qoe_dw_score'`, nomeando um par
de grupos (ex.: `cwpb-10m` e `res-quarto`) com seus valores de max/Q1. **Este erro é o objetivo desta
task, não uma falha** — antes desta mudança o comando rodava até o fim e imprimia tabelas inválidas.

- [ ] **Step 5: Confirme que o guard FICA QUIETO nos alvos que funcionam**

Run (nível posição, o padrão):
```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps 2>&1 | tail -4
```
Expected: roda normalmente até `Optimism of the legacy number: ...`, sem nenhum erro de escala.

Run (nível prédio):
```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps --group-level building 2>&1 | tail -4
```
Expected: idem, sem erro de escala.

Run (classificação só na residência, um prédio só):
```bash
python3 src/ml/classification_benchmark.py \
  --csv data/metrics-20260630-qoe.csv --no-tune 2>&1 | tail -4
```
Expected: roda até o fim e imprime as tabelas por site. Um único prédio não tem par para comparar, e o
guard corretamente não dispara — a incompatibilidade só existe **entre** os dois prédios.

- [ ] **Step 6: Confirme os 4 alvos de regressão**

Run:
```bash
for t in speedtest_down_mbps speedtest_up_mbps latency_ms jitter_ms; do
  timeout 300 python3 src/ml/regression_benchmark.py \
    --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
    --targets $t >/dev/null 2>&1 \
    && echo "$t OK" || echo "$t FALHOU"
done
```
Expected: `OK` nos quatro. Se algum falhar, o guard tem falso-positivo e a task está BLOCKED — reporte
sem tentar afrouxar a regra.

Nota: cada execução leva minutos (ensembles de 600–1000 árvores × 7 folds × 5 modelos). O `timeout 300`
é por alvo; não reduza.

- [ ] **Step 7: Confirme que a suíte segue verde**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 51 tests` … `OK`

- [ ] **Step 8: Commit (AÇÃO DO USUÁRIO — não execute)**

```bash
git add src/ml/regression_benchmark.py src/ml/classification_benchmark.py src/ml/compare_protocols.py
git commit -m "feat(ml): guard against incompatible target scales in all three scripts"
```

---

## Task 3: Corrigir a documentação obsoleta

**Files:**
- Modify: `docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Spec §4 — descrição de `core/sites.py` na tabela de arquitetura**

Encontre esta linha EXATA:

```
| `core/sites.py` | Canonical site key. Maps `local` 1/2/3 → `home-1..3` and every `cwpb-*` → a single `office-cwpb`. Raises on unrecognised patterns. |
```

Substitua por:

```
| `core/sites.py` | Canonical group key, two levels. `level='position'` (default) → 7 groups (`res-sala`/`res-quarto`/`res-suite` + the four `cwpb-*`); `level='building'` → 2 groups (`residencia`/`coworking`). Raises on unrecognised patterns. See §14. |
```

- [ ] **Step 2: Spec §8 — linha da tabela de testes que descreve um teste que não existe mais**

Encontre esta linha EXATA:

```
| All `cwpb-*` values collapse to one site (`nunique() == 1`) | M5 |
```

Substitua por:

```
| `cwpb-*` values stay distinct at position level (`nunique() == 4`) and collapse only at building level | M5, revisto — ver §14 |
```

- [ ] **Step 3: Spec §10 — o caveat ainda fala em "four sites"**

Encontre este parágrafo EXATO:

```
This design maximises what four sites can support; it cannot make four sites sufficient. If cross-site
scores land near zero, the correct conclusion is that these 14 router-side features do not yet
transfer across homes — a genuine finding, not a failure. The real unlock is **more sites**. Code
changes are not a substitute for data collection, and this document should not be read as implying
otherwise.
```

Substitua por:

```
This design maximises what the available data can support; it cannot make it sufficient. The site
count stated earlier in this document (four) was itself wrong — see §14: there are **2 buildings** and
**7 measurement positions**. That makes the "brand-new home" claim demonstrable (n=2) but not
estimable. If cross-building scores land near zero, the correct conclusion is that these 14
router-side features do not yet transfer across buildings — a genuine finding, not a failure. The real
unlock is **more buildings**. Code changes are not a substitute for data collection, and this document
should not be read as implying otherwise.
```

- [ ] **Step 4: CHANGELOG §2.2 — contagem de testes obsoleta**

Encontre esta linha EXATA:

```
Suíte nova com **36 testes** cobrindo todo o `core/`, usando `unittest` (mesma convenção de
```

Substitua por:

```
Suíte nova com **51 testes** cobrindo todo o `core/`, usando `unittest` (mesma convenção de
```

- [ ] **Step 5: Verifique**

Run:
```bash
grep -n "home-1\.\.3\|office-cwpb\`. Raises\|nunique() == 1\|what four sites can support\|36 testes" \
  docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md CHANGELOG.md
```
Expected: sem saída — nenhuma das quatro afirmações obsoletas sobrou.

Run: `python3 -m unittest tests.test_ml_core 2>&1 | grep -E "^Ran|^OK"`
Expected: `Ran 51 tests` e `OK` — confirma que a contagem escrita no CHANGELOG bate com a real.

- [ ] **Step 6: Commit (AÇÃO DO USUÁRIO — não execute)**

O spec é gitignored; só o CHANGELOG entra:

```bash
git add CHANGELOG.md
git commit -m "docs: align stale claims with current site model and test count"
```

---

## Verificação final

- [ ] **Suíte verde**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 51 tests` … `OK`

- [ ] **O guard está nos três scripts**

Run: `grep -c "assert_comparable_scales" src/ml/regression_benchmark.py src/ml/classification_benchmark.py src/ml/compare_protocols.py`
Expected: `2` em cada arquivo (o import e a chamada).

- [ ] **O caso quebrado falha alto**

Run:
```bash
python3 src/ml/classification_benchmark.py \
  --csv data/metrics-20260630-qoe.csv,data/metrics-office-20260722-qoe.csv --no-tune 2>&1 | grep -c "escalas incompatíveis"
```
Expected: `1`.

- [ ] **Os planos históricos não foram tocados**

Run: `git status --short docs/superpowers/plans/ 2>/dev/null; ls docs/superpowers/plans/`
Expected: os três arquivos de plano listados, nenhum modificado (o diretório é gitignored, então
`git status` não mostra nada — confirme por `ls` que os arquivos antigos continuam lá e não foram
reescritos).

---

## Fora deste plano — continua bloqueado

A **causa raiz** da incompatibilidade do `qoe_dw_score` não é corrigida aqui. Os `-qoe.csv` têm os 4
alvos normalizados nos dois prédios, mas por constantes diferentes, e o `qoe_dw_score` foi derivado
desses valores — por isso residência vai a 6269 e escritório a 1,96. Recalculá-lo exige a fórmula, que
vivia no `.dsc` **nunca versionado**.

Este plano só restaura a **detecção**: depois dele, rodar classificação no pool combinado falha com uma
mensagem clara em vez de produzir tabelas silenciosamente inválidas. Para destravar de verdade,
recupere o `.dsc` (ou informe a fórmula do `qoe_dw_score`) e versione-o.

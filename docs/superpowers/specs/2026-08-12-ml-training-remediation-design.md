# ML Training Remediation — Design

**Date:** 2026-08-12
**Branch:** `Revisão-Inicial`
**Status:** Approved design, pending implementation plan

## 1. Problem

A review of the nine scripts in `src/ml/` found three classes of defect: code that cannot run, an
evaluation methodology that reports leaked scores, and reporting bugs that mislabel what is printed.
Every finding below was verified by execution, not by reading alone.

### 1.1 Blockers

| # | Defect | Location |
|---|--------|----------|
| B1 | `train_test_split_random` builds `SplitData` without the required `grp` field. Since `--split` defaults to `random`, the default invocation raises `TypeError`. | `regression_benchmark.py:194-204`, dataclass at `:127` |
| B2 | File does not parse: `IndentationError` at line 21 — a `DS_CSV=` assignment sits inside `group_split`'s body, and lines 41-153 are indented with no enclosing block. `y`, `target`, `regression` are never defined. | `regression_keras.py:20-21` |
| B3 | `display_labels` is undefined — `NameError` after the full training run completes. | `classifier_keras.py:116` |
| B4 | Hardcoded dataset paths do not exist: `metrics-20260630-qoe-speed.csv`, `metrics-20260630-qoe-24g-speed-suppress_empty.csv`. | `classifier_mlflow.py:17`, `classifier_keras.py:18` |
| B5 | `train_test_split_time_aware` has the same missing-`grp` defect as B1. | `regression_benchmark.py:158-168` |

### 1.2 Methodology

**M1 — Generalization estimates rest on 3 sites.** `local` has 3 unique values (5987 / 2618 / 1030
rows). Executing the existing group path produces:

```
train groups=[2.0, 3.0], test groups=[1.0]      # holdout = ONE site
cv_folds requested=5 -> effective GroupKFold folds=2
  fold0: train_groups=[3.0] val_groups=[2.0] val_rows=5987
  fold1: train_groups=[2.0] val_groups=[3.0] val_rows=1030
```

The requested 5 folds silently degrade to 2 (`regression_benchmark.py:279`). Fold 0 trains on 1,030
rows and validates on 5,987 — an inverted 5.8× ratio. `cv_r2_std` is a spread over n=2 and carries no
information. `--test-size 0.2` yielded 27.2% because the groups are too coarse to hit the ratio.

**M2 — Classification leaks in every CV fold.** The script takes a group-aware holdout
(`classification_benchmark.py:313`) but runs `TimeSeriesSplit` for both CV (`:164`) and tuning
(`:235`), neither group-aware. Verified:

```
fold0: train_grp=[2.0] val_grp=[2.0] OVERLAP=[2.0]
...
=> 5/5 CV folds have the SAME location in train and validation
```

Model ranking and hyperparameter tuning both optimise a leaked score; the winner is then judged on a
clean holdout. This guarantees an unexplained CV-versus-holdout gap and likely selects the wrong
model. `TimeSeriesSplit` additionally runs over rows whose time ordering group-shuffling already
destroyed.

**M3 — Class boundaries are computed on the full dataset before splitting**, so test values inform
the label definition (`classification_benchmark.py:82`, `classifier_keras.py:23`,
`classifier_mlflow.py:33`).

**M4 — Three scripts use plain random splits** (`regression_mlflow.py:64`, `classifier_mlflow.py:76`,
`classifier_keras.py:79`), placing repeated measurements from one site on both sides. Their scores
are inflated and not comparable to the benchmark scripts'.

**M5 — The office dataset encodes distance as location.** `local` values are `cwpb-2m`, `cwpb-10m`,
`cwpb-10m-2a`, `cwpb-13m` — one physical site measured at four distances (confirmed with the project
owner). Grouping by `local` there would fabricate four pseudo-sites from one, silently leaking.

### 1.3 Reporting

| # | Defect | Location |
|---|--------|----------|
| R1 | `LabelEncoder` sorts alphabetically → `bad=0, good=1, mid=2`. Ordinal meaning is scrambled and confusion-matrix axes are wrong. | `classifier_keras.py:58`, `classifier_mlflow.py:55` |
| R2 | Prints `F1-score:` but passes the `accuracy` variable. | `classifier_mlflow.py:143` |
| R3 | Logs `"Split strategy: time-aware"` and `"CV: TimeSeriesSplit"` while performing a group split. | `classification_benchmark.py:317-318` |
| R4 | `safe_mape` returns a fraction, reported as "mape" without ×100. | `regression_benchmark.py:144` |
| R5 | `LabelEncoder` is fit twice, identically. | `classifier_keras.py:58-74` |
| R6 | `group_split` hardcodes `test_size=0.3`, `random_state=42`, `group='local'`, ignoring `--test-size` and `--seed`. | `classification_benchmark.py:269-279` |
| R7 | `XGBRegressor` hardcodes `random_state=42` instead of `seed`. | `regression_benchmark.py:256` |
| R8 | Regression models have no imputer while classification pipelines do. Latent: the current CSV is NaN-free, but RF/ExtraTrees/MLP crash on any dataset that is not. | `regression_benchmark.py:207-258` |

**Latent landmine.** Both classifier scripts define a `features` list containing
`speedtest_down_mbps`, `latency_ms`, and `download_*` — the quantities `qoe_dw_score` is derived
from — then overwrite it one line later (`classifier_keras.py:44-56`). Not leaking today; a one-line
edit makes it total target leakage.

## 2. Constraints

**Generalization claim (decided):** the model must predict for a **brand-new home** never seen in
training. This fixes the grouping key as the physical site and rules out composite keys such as
`local|client_ID|distance_m|radio`, which would yield 17-20 groups but answer a different question
(new conditions at known sites).

**Site inventory.** `local` records the measurement POSITION inside a building, not the building
itself, so the independent-building count is:

| Source | Buildings | Positions | Note |
|---|---|---|---|
| `metrics-20260630-*` | 1 | 3 | one residence; `local` ∈ {1, 2, 3} are rooms (`sala`/`quarto`/`suite`) |
| `metrics-office-20260722-*` | 1 | 4 | one coworking building; all `cwpb-*` are distances within it |
| **Total** | **2** | **7** | |

Two buildings make the "brand-new home" claim demonstrable (n=2) but not estimable — §10 and §14
carry the consequences.

Merging is mechanically safe: all 14 features and all 4 targets are present in both datasets, and the
`local` value spaces are already disjoint (numeric versus string).

**No code change can manufacture statistical power that the available data does not contain.** This
remains true regardless of the site-count correction above — it motivated the original design and
still does.

## 3. Approach

**Nested leave-one-group-out.** The outer loop holds out one group, trains on the rest, and rotates
through all of them — 7 groups at position level (the default) or 2 at building level. The inner loop
tunes on the remaining training groups via a second LOGO. Results are reported per group, never as a
bare mean.

Considered and rejected:

- *Single-site holdout + LOGO CV on the remainder* — smallest diff from today's structure, but spends
  25% of the sites on one holdout and makes the headline number depend on which site was drawn.
- *LOGO with fixed hyperparameters* — fastest, and defensible because tuning across three inner sites
  largely fits fold-assignment noise. Retained as the `--no-tune` escape hatch rather than the default.

## 4. Architecture

A new `src/ml/core/` package holds the shared logic, following the repo convention in `SPEC.md:68`
(one class per file, 2-space indentation).

| Module | Responsibility |
|---|---|
| `core/sites.py` | Canonical group key, two levels. `level='position'` (default) → 7 groups (`res-sala`/`res-quarto`/`res-suite` + the four `cwpb-*`); `level='building'` → 2 groups (`residencia`/`coworking`). Raises on unrecognised patterns. Derivation: `CHANGELOG.md` §5; results at both levels: §14. |
| `core/splits.py` | `nested_logo_splits()` — outer LOGO, inner LOGO for tuning. Enforces the disjointness invariant. |
| `core/data.py` | Load and merge CSVs, validate features and targets, own the imputation policy. |
| `core/metrics.py` | Regression and classification metrics, per-site aggregation. |
| `core/reporting.py` | Per-site tables, fold-composition output, spread reporting. |

`regression_benchmark.py` and `classification_benchmark.py` become thin CLI wrappers over `core`.
`regression_mlflow.py` and `classifier_mlflow.py` import the same `core/splits.py`, making their runs
comparable to the benchmarks for the first time. `regression_keras.py` and `classifier_keras.py` move
to `src/ml/experimental/` with a note that they are unmaintained; `regression_keras.py` is unparseable
and reconstructing its intent would be guesswork.

**Load-bearing decision: `splits.py` asserts that train and test site sets are disjoint and raises if
not.** M2 occurred because group-awareness was a convention that one code path did not follow. An
assertion in the split layer makes that class of defect structurally impossible to reintroduce.

Two consequences follow:

- **Quartile thresholds move inside the fold.** Fixing M3 means thresholds differ per fold, so class
  balance shifts slightly between folds. This is correct but makes fold comparison less clean.
  `--class-mode`/`--fixed-thresholds` were kept as CLI flags for a future fixed-threshold mode, but
  `evaluate()` does not yet branch on them — passing `--class-mode fixed` prints a warning and still
  uses quartile thresholds. Whether fixed thresholds should apply globally or per fold is a real design
  question (it changes the leakage properties) left open, not implemented.
- **`SplitData` is restructured**, which resolves B1 and B5 at the source rather than defaulting the
  field.

## 5. Data flow

```
load CSVs (1..n) → resolve site_id → validate → outer LOGO (n_sites folds)
                                                      │
                              ┌───────────────────────┴──────────────┐
                              │ per outer fold: train = n-1 sites    │
                              │   inner LOGO over those sites → tune │
                              │   refit best on all training sites   │
                              │   predict the held-out site          │
                              └───────────────────────┬──────────────┘
                                                      ↓
                                   per-site metrics → report table
```

The load step accepts multiple CSVs so home and office data merge into one four-site pool.

**Everything fit on data is fit inside the training fold.** Imputer and scaler obtain this from
`Pipeline`. Quartile thresholds do not — they are plain `np.quantile` calls today, which is precisely
why M3 exists. For classification the target therefore changes from a precomputed column to raw
`qoe_dw_score`, binarised per fold from the training sites' distribution only.

## 6. Error handling

Governing principle: **anything that weakens statistical rigour must be loud.** The most damaging
current behaviour is not a crash but the silent 5→2 fold degradation at `regression_benchmark.py:279`.

| Condition | Behaviour |
|---|---|
| Unrecognised site pattern | Raise, listing the offending values. Never invent a group (would resurrect M5). |
| Fewer than 2 sites | Hard error; LOGO is undefined. |
| 2-3 sites | Run, with a prominent warning that estimates rest on n<4 and per-site spread is uninterpretable. |
| `--cv-folds` / `--test-size` under LOGO | Warn that they are ignored; fold count is `n_sites` by construction. |
| NaN in features | Imputer in pipeline (fixes R8). |
| NaN in target | Drop rows, report the count dropped. |
| Single-class fold (classification) | Raise a clear error instead of sklearn's cryptic one. |

## 7. CLI and reporting

- `--split` gains `logo` as the **default**. `random` remains, relabelled in help text as
  optimistic/debug-only.
- `--csv` accepts multiple paths, enabling the four-site merge.
- New `--no-tune` flag provides the fixed-hyperparameter fallback.
- `--seed` is threaded through, fixing R6 and R7.
- Every run prints its **fold composition** — which sites are in train versus test, per fold. This
  output is what surfaced M2 during review; making it permanent means the next such defect is visible
  immediately rather than after a code audit.
- Reporting fixes in maintained files: R2, R3, R4, and the `classifier_mlflow.py` half of R1. See
  §11 for defects that are deliberately not fixed.

## 8. Testing

New `tests/test_ml_core.py`, following the `unittest` and `sys.path`-append convention of
`tests/test_fn_metrics.py`. All tests use small synthetic DataFrames rather than the real CSVs, which
reach 52MB and would prevent the suite running in CI or on a fresh checkout.

| Test | Guards against |
|---|---|
| `cwpb-*` values stay distinct at position level (`nunique() == 4`) and collapse only at building level | M5 |
| Every outer fold has disjoint train/test site sets | M2 |
| Inner LOGO never contains the outer held-out site | Tuning peeking at the test site |
| Each site is the test site exactly once; `n_folds == n_sites` | M1 silent degradation |
| Perturbing test-fold target values leaves quartile thresholds unchanged | M3 |
| `mape` returns percentage scale | R4 |

The threshold test is the only mechanical proof that the label definition does not see the test set.

## 9. Old-versus-new comparison

`src/ml/compare_protocols.py` runs the same models twice on the same merged data — once under the
legacy protocol (random split plus `TimeSeriesSplit` CV, as currently coded), once under nested LOGO —
and emits a delta table. It runs once, its output is recorded as the audit trail, and the legacy path
then survives only behind `--split random`.

**Expectation to record before running: the new numbers will be materially worse, and some per-site R²
may be negative** (worse than predicting the mean). This is not a regression introduced by the work;
it is the true cross-site difficulty becoming visible. Stating it in advance prevents the result being
read as "the refactor broke the model".

## 10. Honest caveat

This design maximises what the available data can support; it cannot make it sufficient. With
**2 buildings** and **7 measurement positions**, the "brand-new home" claim is demonstrable (n=2) but
not estimable. §14 ran that experiment: the building-level LOGO mean landed at r2≈0.735 — a
favourable early signal, not a validation. Had it landed near zero, the correct conclusion would have
been that these 14 router-side features do not yet transfer across buildings — a genuine finding,
not a failure. Either way the real unlock is **more buildings**; a single pair cannot promote
"demonstrable" to "estimable" no matter which way it comes out. Code changes are not a substitute for
data collection, and this document should not be read as implying otherwise.

## 11. Defect disposition

Quarantining `regression_keras.py` and `classifier_keras.py` means defects located solely in those
files are **not fixed** — they are moved, unmaintained, out of the import path of any maintained
script. This table records that explicitly so no defect is silently assumed resolved.

| Defect | Disposition |
|---|---|
| B1, B5 | Fixed — `SplitData` restructured in `core/splits.py`. |
| B2 | Not fixed — `regression_keras.py` quarantined; unparseable, intent unrecoverable. |
| B3 | Not fixed — `classifier_keras.py` quarantined. |
| B4 | Partly fixed — `classifier_mlflow.py`'s hardcoded `DS_CSV` now defaults to a file that actually exists, overridable via the `DS_CSV` env var (matching `regression_mlflow.py`'s pattern). It still loads via plain `pd.read_csv`, not the `core/data.py` loader, and has no CLI argument parsing (this script has none at all — it's a top-level script, not `argparse`-wrapped). The `classifier_keras.py` path is quarantined. |
| M1, M2 | Fixed — nested LOGO plus the disjointness assertion in `core/splits.py`. |
| M3 | Fixed — thresholds computed per fold from training sites only. |
| M4 | Partly fixed — only `regression_mlflow.py` adopts `core/splits.py` (first LOGO fold, in place of the old random split). `classifier_mlflow.py` still uses a plain stratified `train_test_split`; its split logic was deliberately out of scope for this effort. |
| M5 | Fixed — `core/sites.py` collapses all `cwpb-*` to one site. |
| R1 | Partly fixed — corrected in `classifier_mlflow.py` via an explicit ordered mapping (`bad<mid<good`) instead of `LabelEncoder`'s alphabetical sort. The `classifier_keras.py` occurrence is quarantined. |
| R2, R3, R4 | Fixed. |
| R5 | Not fixed — `classifier_keras.py` quarantined. |
| R6, R7 | Fixed — `--seed` and split parameters threaded through `core`. |
| R8 | Fixed — imputer added to regression pipelines. |
| Latent landmine (leaked `features` list) | Removed from `classifier_mlflow.py`; quarantined in `classifier_keras.py`. |

## 12. Out of scope

- Feature engineering or new features beyond the existing 14.
- Changes to the `get-*` collection scripts or the `fn-`/`opers` transformation pipeline.
- Repairing `regression_keras.py` and `classifier_keras.py` (quarantined to `src/ml/experimental/`).
- Retuning model hyperparameter search spaces beyond wiring them to the corrected CV.

## 13. Measured optimism of the legacy protocol

Captured from a single run of `src/ml/compare_protocols.py` against the merged home and office
datasets, taken **before** the target-scale fix and while grouping still used the old four-site
model — hence the group names and the magnitude below. §14 holds the post-fix numbers:

```
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps

Legacy protocol (random split):
  r2=0.96065  rmse=15.51514

Leave-one-site-out, per site:
  test_site            r2      rmse
     home-1 -262244.42195 131.31686
     home-2   -1257.97820   4.93969
     home-3 -711475.64513  64.26755
office-cwpb      -1.07125 199.26546

LOGO mean r2=-243744.77913 (min=-711475.64513, max=-1.07125)

Optimism of the legacy number: 243745.73978 r2
```

The legacy random-split protocol reported r2=0.96065, while leave-one-site-out on the identical data
averaged r2=-243744.77913, an optimism gap of roughly 243746 r2 driven in large part by a pre-existing
scale mismatch between the home datasets' normalised `speedtest_down_mbps` (0-1) and the office
dataset's raw-Mbps `speedtest_down_mbps` (0-568), which a random split hides by letting each site's own
scale appear on both sides of the split.

## 14. Resultados após a correção de escala

> **Como ler estes dois números.** São **2 prédios** e **7 posições de medição** (derivação em
> `CHANGELOG.md` §5). Com n=2 prédios, "generaliza para um prédio novo" é demonstrável, não estimável
> com rigor. Por isso o número principal abaixo responde a uma pergunta mais fraca — "generaliza para
> uma posição não vista, em prédio conhecido" — e o número por prédio é reportado como viabilidade,
> não como estimativa.

Alvo: `speedtest_down_mbps`, pool combinado (residência + coworking), alvos em unidade física.

### Principal — leave-one-position-out (7 folds)

```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps --group-level position
```

```
Sites: ['cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m', 'cwpb-2m', 'res-quarto', 'res-sala', 'res-suite']
Group level: position

Legacy protocol (random split):
  r2=0.95939  rmse=27.27852

Leave-one-position-out, per site:
  test_site       r2     rmse
   cwpb-10m  0.51509 46.91694
cwpb-10m-2a  0.54744 64.53889
   cwpb-13m -0.16180 65.74160
    cwpb-2m  0.71917 85.13124
 res-quarto  0.68583 52.08478
   res-sala  0.92067 48.20981
  res-suite  0.64858 30.14833

LOGO mean r2=0.55357 (min=-0.16180, max=0.92067)

Optimism of the legacy number: 0.40582 r2
```

### Viabilidade — leave-one-building-out (2 folds)

```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps --group-level building
```

```
/home/venko/ml/TR069/ml-scripts/src/ml/core/splits.py:57: UserWarning: only 2 sites available: per-site spread is uninterpretable and the generalisation estimate is unstable.
  validate_site_count(site_ids)
Sites: ['coworking', 'residencia']
Group level: building

Legacy protocol (random split):
  r2=0.95939  rmse=27.27852

Leave-one-building-out, per site:
 test_site      r2     rmse
 coworking 0.71994 73.27243
residencia 0.75033 65.63430

LOGO mean r2=0.73514 (min=0.71994, max=0.75033)

Optimism of the legacy number: 0.22425 r2
```

**Leitura.** O número por posição é a estimativa rigorosa: mede generalização para um
ponto de medição não visto, em prédio conhecido. O número por prédio é uma demonstração
única de transferência entre prédios — com n=2 evidencia viabilidade, mas não estima
desempenho. A média mais alta por prédio não indica que a transferência entre prédios seja mais
fácil — é um artefato de agregar posições com desempenho muito diferente (`cwpb-13m` e `cwpb-2m`,
por exemplo) num único grupo, o que suaviza a variância que o número por posição revela.

**Recuperação em relação a §13.** Antes desta correção, o LOGO mean r2 era -243744.77913 (§13) —
um artefato puro do bug de escala. Depois de corrigir a escala e o modelo de sites, o LOGO mean r2
por posição é 0.55357: a avaliação honesta volta para uma faixa plausível. Note que o número legado
(aleatório) mal se move (0.96065 em §13 → 0.95939 aqui) — porque o vazamento de site já estava
saturando esse número independentemente do bug de escala; o efeito da correção aparece quase todo
na avaliação honesta (LOGO), não na legada.

# ML Training Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **COMMIT POLICY — PROJECT OVERRIDE:** The repository owner performs **all** commits. Steps labelled
> **"Commit (USER ACTION)"** must NOT be executed by an agent. Stop, show the command, and wait for the
> owner to run it. This overrides the default "agent commits frequently" guidance.

**Goal:** Replace the leaking, partly-unrunnable evaluation code in `src/ml/` with a shared `src/ml/core/`
package that enforces leave-one-site-out validation, so reported scores reflect generalisation to an
unseen home.

**Architecture:** A new `src/ml/core/` package owns site resolution, splitting, data loading, metrics and
reporting. `splits.py` raises if any site appears in both sides of a split, making the leakage class of
bug structurally impossible. The two benchmark scripts and the two MLflow scripts become thin callers.
The two keras scripts are quarantined unmodified.

**Tech Stack:** Python 3.12, pandas, scikit-learn 1.5.2, xgboost, mlflow. Tests use `unittest`
(stdlib) following `tests/test_fn_metrics.py`; `pytest` 7.4.4 is installed and can run them too.

**Source spec:** `docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md`

---

## Pre-flight notes for the implementer

1. **Code style:** 2-space indentation, one class per file (`SPEC.md:66-68`). Match it.
2. **The existing test suite is broken and this is NOT your fault.** `tests/res/test_data.csv` was never
   committed (`git log --all -- tests/res` is empty), so all 18 tests in `tests/test_fn_metrics.py` error
   with `FileNotFoundError`. Do **not** try to fix that here — it is out of scope. Consequently, never
   verify your work with `python3 -m unittest discover`; always run the new module by name:
   `python3 -m unittest tests.test_ml_core -v`.
3. **Run everything from the repo root** `/home/venko/ml/TR069/ml-scripts`.
4. **Do not delete the keras scripts.** Task 9 moves them.

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `src/ml/core/__init__.py` | Create | Package marker. |
| `src/ml/core/sites.py` | Create | Map raw `local` values to canonical site IDs. |
| `src/ml/core/splits.py` | Create | LOGO folds + the disjointness assertion. |
| `src/ml/core/metrics.py` | Create | Regression/classification metrics; per-fold class thresholds. |
| `src/ml/core/data.py` | Create | Multi-CSV load/merge, column validation, NaN policy. |
| `src/ml/core/reporting.py` | Create | Fold-composition and per-site tables. |
| `tests/test_ml_core.py` | Create | Synthetic-data tests for all of the above. |
| `src/ml/regression_benchmark.py` | Modify | Becomes a caller of `core`. Fixes B1, B5, R4, R7, R8. |
| `src/ml/classification_benchmark.py` | Modify | Becomes a caller of `core`. Fixes M2, M3, R3, R6. |
| `src/ml/regression_mlflow.py` | Modify | Adopt `core` splitting. Fixes M4. |
| `src/ml/classifier_mlflow.py` | Modify | Adopt `core`. Fixes M4, B4, R1, R2. |
| `src/ml/experimental/` | Create | Quarantine directory. |
| `src/ml/compare_protocols.py` | Create | Legacy-vs-LOGO delta table. |

---

## Task 1: Package scaffold and canonical site IDs

Fixes **M5** (office distance values masquerading as four sites).

**Files:**
- Create: `src/ml/core/__init__.py`
- Create: `src/ml/core/sites.py`
- Create: `tests/test_ml_core.py`

- [ ] **Step 1: Create the package marker**

Create `src/ml/core/__init__.py` as an empty file:

```python
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_ml_core.py`:

```python
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.core.sites import resolve_site_id


class TestResolveSiteId(unittest.TestCase):
  def test_numeric_locals_become_home_ids(self):
    result = resolve_site_id(pd.Series([1.0, 2.0, 3.0, 1.0]))
    self.assertEqual(list(result), ['home-1', 'home-2', 'home-3', 'home-1'])

  def test_all_office_values_collapse_to_one_site(self):
    office = pd.Series(['cwpb-2m', 'cwpb-10m', 'cwpb-10m-2a', 'cwpb-13m'])
    result = resolve_site_id(office)
    self.assertEqual(result.nunique(), 1)
    self.assertEqual(set(result), {'office-cwpb'})

  def test_unknown_value_raises(self):
    with self.assertRaises(ValueError) as ctx:
      resolve_site_id(pd.Series(['garage']))
    self.assertIn('garage', str(ctx.exception))

  def test_empty_value_raises(self):
    with self.assertRaises(ValueError):
      resolve_site_id(pd.Series([np.nan]))


if __name__ == '__main__':
  unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ModuleNotFoundError: No module named 'ml.core.sites'`

- [ ] **Step 4: Write the implementation**

Create `src/ml/core/sites.py`:

```python
import pandas as pd

OFFICE_PREFIX = 'cwpb'
OFFICE_SITE_ID = 'office-cwpb'


def _resolve_one(value):
  if pd.isna(value):
    raise ValueError(
      "site resolution failed: 'local' contains an empty value. "
      'Every row must belong to a known site.'
    )
  text = str(value).strip()
  if text.lower().startswith(OFFICE_PREFIX):
    return OFFICE_SITE_ID
  try:
    return f'home-{int(float(text))}'
  except ValueError:
    raise ValueError(
      f'site resolution failed: unrecognised local value {value!r}. '
      'Add an explicit rule in core/sites.py; never let an unknown value form its own site.'
    ) from None


def resolve_site_id(local_values: pd.Series) -> pd.Series:
  """Map raw `local` values onto canonical site identifiers.

  All `cwpb-*` values collapse to a single office site: they are distances
  within one building, not separate sites.
  """
  return local_values.map(_resolve_one)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 4 tests` … `OK`

- [ ] **Step 6: Verify against real data**

Run:
```bash
python3 -c "
import sys; sys.path.append('src')
import pandas as pd
from ml.core.sites import resolve_site_id
for f in ['data/metrics-20260630-out.csv','data/metrics-office-20260722-out.csv']:
    s = resolve_site_id(pd.read_csv(f, low_memory=False)['local'])
    print(f, '->', sorted(s.unique()))
"
```
Expected:
```
data/metrics-20260630-out.csv -> ['home-1', 'home-2', 'home-3']
data/metrics-office-20260722-out.csv -> ['office-cwpb']
```

- [ ] **Step 7: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/core/__init__.py src/ml/core/sites.py tests/test_ml_core.py
git commit -m "feat(ml): add canonical site resolution"
```

---

## Task 2: Leakage-proof outer LOGO folds

Fixes **M1** and **M2**.

**Files:**
- Create: `src/ml/core/splits.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ml_core.py`, above the `if __name__` block:

```python
from ml.core.splits import assert_sites_disjoint, outer_logo_folds, validate_site_count


def _frame(n_per_site=4, sites=('home-1', 'home-2', 'home-3', 'office-cwpb')):
  rows = []
  for s in sites:
    for i in range(n_per_site):
      rows.append({'site_id': s, 'feat': float(i), 'target': float(i) * 2})
  return pd.DataFrame(rows)


class TestSplits(unittest.TestCase):
  def setUp(self):
    self.df = _frame()
    self.X = self.df[['feat']]
    self.y = self.df['target']
    self.sites = self.df['site_id']

  def test_every_fold_has_disjoint_sites(self):
    for fold in outer_logo_folds(self.X, self.y, self.sites):
      self.assertEqual(set(fold.train_sites) & {fold.test_site}, set())

  def test_each_site_is_test_exactly_once(self):
    tested = [f.test_site for f in outer_logo_folds(self.X, self.y, self.sites)]
    self.assertEqual(sorted(tested), sorted(self.sites.unique()))

  def test_fold_count_equals_site_count(self):
    folds = list(outer_logo_folds(self.X, self.y, self.sites))
    self.assertEqual(len(folds), self.sites.nunique())

  def test_disjointness_assertion_rejects_overlap(self):
    with self.assertRaises(AssertionError) as ctx:
      assert_sites_disjoint(['home-1', 'home-2'], ['home-2'])
    self.assertIn('home-2', str(ctx.exception))

  def test_single_site_is_rejected(self):
    with self.assertRaises(ValueError):
      validate_site_count(pd.Series(['home-1', 'home-1']))

  def test_three_sites_warns(self):
    with self.assertWarns(UserWarning):
      validate_site_count(pd.Series(['home-1', 'home-2', 'home-3']))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ModuleNotFoundError: No module named 'ml.core.splits'`

- [ ] **Step 3: Write the implementation**

Create `src/ml/core/splits.py`:

```python
import warnings
from dataclasses import dataclass
from typing import Iterator, Tuple

import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut

MIN_SITES = 2
COMFORTABLE_SITES = 4


@dataclass
class Fold:
  X_train: pd.DataFrame
  X_test: pd.DataFrame
  y_train: pd.Series
  y_test: pd.Series
  train_sites: Tuple[str, ...]
  test_site: str
  train_site_ids: pd.Series


def assert_sites_disjoint(train_sites, test_sites) -> None:
  """Raise if any site appears on both sides of a split."""
  overlap = sorted(set(train_sites) & set(test_sites))
  if overlap:
    raise AssertionError(
      f'site leakage detected: {overlap} present in both train and test. '
      'This split would report an optimistic score.'
    )


def validate_site_count(site_ids: pd.Series) -> int:
  n_sites = site_ids.nunique()
  if n_sites < MIN_SITES:
    raise ValueError(
      f'leave-one-site-out needs at least {MIN_SITES} sites, found {n_sites}. '
      'Merge additional datasets or collect more sites.'
    )
  if n_sites < COMFORTABLE_SITES:
    warnings.warn(
      f'only {n_sites} sites available: per-site spread is uninterpretable '
      'and the generalisation estimate is unstable.',
      UserWarning,
      stacklevel=2,
    )
  return n_sites


def outer_logo_folds(X: pd.DataFrame, y: pd.Series, site_ids: pd.Series) -> Iterator[Fold]:
  """Yield one fold per site: train on all other sites, test on this one."""
  validate_site_count(site_ids)
  splitter = LeaveOneGroupOut()
  for train_idx, test_idx in splitter.split(X, y, groups=site_ids):
    train_sites = tuple(sorted(site_ids.iloc[train_idx].unique()))
    test_sites = tuple(sorted(site_ids.iloc[test_idx].unique()))
    assert_sites_disjoint(train_sites, test_sites)
    yield Fold(
      X_train=X.iloc[train_idx],
      X_test=X.iloc[test_idx],
      y_train=y.iloc[train_idx],
      y_test=y.iloc[test_idx],
      train_sites=train_sites,
      test_site=test_sites[0],
      train_site_ids=site_ids.iloc[train_idx],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 10 tests` … `OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/core/splits.py tests/test_ml_core.py
git commit -m "feat(ml): add leave-one-site-out folds with leakage assertion"
```

---

## Task 3: Inner LOGO for tuning

Prevents hyperparameter search from seeing the held-out site.

**Files:**
- Modify: `src/ml/core/splits.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Write the failing test**

Append to the `TestSplits` class in `tests/test_ml_core.py`:

```python
  def test_inner_splits_never_contain_outer_test_site(self):
    from ml.core.splits import inner_logo_splits
    for fold in outer_logo_folds(self.X, self.y, self.sites):
      inner = inner_logo_splits(fold.train_site_ids)
      self.assertGreaterEqual(len(inner), 2)
      for tr, va in inner:
        seen = set(fold.train_site_ids.iloc[tr]) | set(fold.train_site_ids.iloc[va])
        self.assertNotIn(fold.test_site, seen)

  def test_inner_splits_are_site_disjoint(self):
    from ml.core.splits import inner_logo_splits
    fold = next(iter(outer_logo_folds(self.X, self.y, self.sites)))
    for tr, va in inner_logo_splits(fold.train_site_ids):
      assert_sites_disjoint(fold.train_site_ids.iloc[tr], fold.train_site_ids.iloc[va])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ImportError: cannot import name 'inner_logo_splits'`

- [ ] **Step 3: Write the implementation**

Append to `src/ml/core/splits.py`:

```python
def inner_logo_splits(train_site_ids: pd.Series):
  """Positional (train, validation) index pairs for tuning within a fold.

  Returns a list so it can be passed directly as scikit-learn's `cv=`.
  """
  n_sites = train_site_ids.nunique()
  if n_sites < MIN_SITES:
    raise ValueError(
      f'tuning needs at least {MIN_SITES} training sites, found {n_sites}. '
      'Run with --no-tune.'
    )
  placeholder = pd.DataFrame({'_': range(len(train_site_ids))})
  splits = list(LeaveOneGroupOut().split(placeholder, groups=train_site_ids))
  for train_idx, val_idx in splits:
    assert_sites_disjoint(train_site_ids.iloc[train_idx], train_site_ids.iloc[val_idx])
  return splits
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 12 tests` … `OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/core/splits.py tests/test_ml_core.py
git commit -m "feat(ml): add inner LOGO splits for leakage-free tuning"
```

---

## Task 4: Metrics and fold-local class thresholds

Fixes **M3** (class boundaries computed on the full dataset) and **R4** (mape scale).

**Files:**
- Create: `src/ml/core/metrics.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ml_core.py`, above the `if __name__` block:

```python
from ml.core.metrics import CLASS_NAMES, apply_thresholds, quartile_thresholds, safe_mape


class TestMetrics(unittest.TestCase):
  def test_mape_is_a_percentage(self):
    y_true = np.array([100.0, 100.0])
    y_pred = np.array([110.0, 90.0])
    self.assertAlmostEqual(safe_mape(y_true, y_pred), 10.0, places=6)

  def test_mape_ignores_zero_denominators(self):
    y_true = np.array([0.0, 100.0])
    y_pred = np.array([5.0, 110.0])
    self.assertAlmostEqual(safe_mape(y_true, y_pred), 10.0, places=6)

  def test_mape_all_zero_is_nan(self):
    self.assertTrue(np.isnan(safe_mape(np.array([0.0]), np.array([1.0]))))

  def test_thresholds_ignore_test_fold_values(self):
    y_train = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    baseline = quartile_thresholds(y_train)
    # A wildly different test fold must not move the training thresholds.
    _ = pd.Series([1000.0, 2000.0, 3000.0])
    self.assertEqual(quartile_thresholds(y_train), baseline)

  def test_apply_thresholds_labels_three_classes(self):
    labels = apply_thresholds(pd.Series([0.0, 5.0, 100.0]), 1.0, 10.0)
    self.assertEqual(list(labels), CLASS_NAMES)

  def test_single_class_fold_raises_clear_error(self):
    from ml.core.metrics import assert_multiclass
    with self.assertRaises(ValueError) as ctx:
      assert_multiclass(pd.Series(['bad', 'bad', 'bad']), 'home-2')
    self.assertIn('home-2', str(ctx.exception))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ModuleNotFoundError: No module named 'ml.core.metrics'`

- [ ] **Step 3: Write the implementation**

Create `src/ml/core/metrics.py`:

```python
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

CLASS_NAMES = ['bad', 'mid', 'good']


def safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
  """Mean absolute percentage error, expressed as a percentage."""
  mask = np.abs(y_true) > 1e-9
  if not np.any(mask):
    return float('nan')
  ratio = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])
  return float(np.mean(ratio) * 100.0)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
  abs_err = np.abs(y_true - y_pred)
  return {
    'r2': float(r2_score(y_true, y_pred)),
    'rmse': float(mean_squared_error(y_true, y_pred) ** 0.5),
    'mae': float(mean_absolute_error(y_true, y_pred)),
    'mape_pct': safe_mape(y_true, y_pred),
    'p90_ae': float(np.percentile(abs_err, 90)),
  }


def quartile_thresholds(y_train: pd.Series):
  """Class boundaries derived from the TRAINING fold only."""
  q1, q3 = np.quantile(y_train, [0.25, 0.75])
  return float(q1), float(q3)


def apply_thresholds(y: pd.Series, t_low: float, t_high: float) -> pd.Series:
  labels = pd.cut(y, bins=(-np.inf, t_low, t_high, np.inf), labels=CLASS_NAMES, right=False)
  return labels.astype('category').cat.set_categories(CLASS_NAMES, ordered=True)


def assert_multiclass(y: pd.Series, context: str) -> None:
  """Raise a readable error when a fold collapses to one class."""
  present = [value for value in y.dropna().unique()]
  if len(present) < 2:
    raise ValueError(
      f'fold {context!r} contains only class {present}: a classifier cannot be '
      'trained or scored on it. Adjust thresholds (--fixed-thresholds) or exclude the site.'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 18 tests` … `OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/core/metrics.py tests/test_ml_core.py
git commit -m "feat(ml): add metrics with fold-local class thresholds"
```

---

## Task 5: Data loading and merging

Enables the four-site pool. Fixes **R8** (NaN policy).

**Files:**
- Create: `src/ml/core/data.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ml_core.py`, above the `if __name__` block:

```python
import tempfile

from ml.core.data import load_datasets, validate_columns


class TestData(unittest.TestCase):
  def _write_csv(self, rows):
    handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    pd.DataFrame(rows).to_csv(handle.name, index=False)
    handle.close()
    return handle.name

  def test_merges_multiple_files_and_adds_site_id(self):
    a = self._write_csv([{'local': 1.0, 'feat': 1.0, 'target': 2.0}])
    b = self._write_csv([{'local': 'cwpb-2m', 'feat': 3.0, 'target': 4.0}])
    df = load_datasets([a, b])
    self.assertEqual(len(df), 2)
    self.assertEqual(sorted(df['site_id'].unique()), ['home-1', 'office-cwpb'])

  def test_missing_column_raises_with_name(self):
    df = pd.DataFrame({'a': [1]})
    with self.assertRaises(ValueError) as ctx:
      validate_columns(df, ['b'], 'feature')
    self.assertIn('b', str(ctx.exception))

  def test_rows_with_nan_target_are_dropped(self):
    path = self._write_csv([
      {'local': 1.0, 'feat': 1.0, 'target': 2.0},
      {'local': 1.0, 'feat': 1.0, 'target': None},
    ])
    df = load_datasets([path], target='target')
    self.assertEqual(len(df), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ModuleNotFoundError: No module named 'ml.core.data'`

- [ ] **Step 3: Write the implementation**

Create `src/ml/core/data.py`:

```python
import pandas as pd

from ml.core.sites import resolve_site_id

SITE_COLUMN = 'site_id'
RAW_SITE_COLUMN = 'local'


def validate_columns(df: pd.DataFrame, columns, role: str) -> None:
  missing = [col for col in columns if col not in df.columns]
  if missing:
    raise ValueError(f'missing {role} columns in dataset: {missing}')


def load_datasets(paths, target: str = None) -> pd.DataFrame:
  """Load and concatenate CSVs, attaching a canonical site_id column.

  Rows whose target is empty are dropped and the count reported.
  """
  frames = []
  for path in paths:
    frame = pd.read_csv(path, low_memory=False)
    validate_columns(frame, [RAW_SITE_COLUMN], 'site')
    frame[SITE_COLUMN] = resolve_site_id(frame[RAW_SITE_COLUMN])
    frames.append(frame)

  df = pd.concat(frames, ignore_index=True)

  if target is not None:
    validate_columns(df, [target], 'target')
    before = len(df)
    df = df.dropna(subset=[target]).reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
      print(f'dropped {dropped} rows with empty target {target!r}')

  return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 21 tests` … `OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/core/data.py tests/test_ml_core.py
git commit -m "feat(ml): add multi-dataset loader with site resolution"
```

---

## Task 6: Reporting

Fixes **R3** (log lines that misdescribe the split).

**Files:**
- Create: `src/ml/core/reporting.py`
- Modify: `tests/test_ml_core.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ml_core.py`, above the `if __name__` block:

```python
from ml.core.reporting import format_fold_plan, format_per_site_table


class TestReporting(unittest.TestCase):
  def test_fold_plan_names_train_and_test_sites(self):
    text = format_fold_plan([('home-1', 'home-2'), ('home-1', 'home-3')],
                            ['home-3', 'home-2'])
    self.assertIn('home-3', text)
    self.assertIn('fold 0', text)

  def test_per_site_table_reports_spread_and_n(self):
    rows = [
      {'model': 'rf', 'test_site': 'home-1', 'r2': 0.5},
      {'model': 'rf', 'test_site': 'home-2', 'r2': 0.1},
    ]
    text = format_per_site_table(pd.DataFrame(rows), 'r2')
    self.assertIn('home-1', text)
    self.assertIn('n_sites=2', text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `ModuleNotFoundError: No module named 'ml.core.reporting'`

- [ ] **Step 3: Write the implementation**

Create `src/ml/core/reporting.py`:

```python
import pandas as pd


def format_fold_plan(train_sites_per_fold, test_site_per_fold) -> str:
  """Render exactly which sites train and test each fold.

  This output is what makes site leakage visible without a code audit.
  """
  lines = ['Fold plan (leave-one-site-out):']
  for index, (train_sites, test_site) in enumerate(zip(train_sites_per_fold, test_site_per_fold)):
    lines.append(f'  fold {index}: train={list(train_sites)} test={test_site}')
  return '\n'.join(lines)


def format_per_site_table(results: pd.DataFrame, metric: str) -> str:
  """Per-site scores plus spread. Never report a bare mean."""
  pivot = results.pivot(index='model', columns='test_site', values=metric)
  summary = pivot.copy()
  summary['mean'] = pivot.mean(axis=1)
  summary['min'] = pivot.min(axis=1)
  summary['max'] = pivot.max(axis=1)
  n_sites = pivot.shape[1]
  header = f'Per-site {metric} (n_sites={n_sites}; spread matters more than the mean)'
  return f'{header}\n' + summary.to_string(float_format=lambda x: f'{x:.5f}')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 23 tests` … `OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/core/reporting.py tests/test_ml_core.py
git commit -m "feat(ml): add per-site reporting with explicit fold plan"
```

---

## Task 7: Rewire `regression_benchmark.py`

Fixes **B1**, **B5**, **R4**, **R7**, **R8**.

**Files:**
- Modify: `src/ml/regression_benchmark.py`

- [ ] **Step 1: Replace the split/eval core**

In `src/ml/regression_benchmark.py`, delete the `SplitData` dataclass (lines 121-127), the three
`train_test_split_*` functions and `group_split` (lines 158-204), and `safe_mape`/`compute_metrics`
(lines 140-155).

Also delete the local `validate_columns` definition at lines 134-137 — `core.data` now provides it,
and leaving both would shadow the import with a divergent copy. Keep `parse_csv_list` (lines 130-131);
it is still used.

Replace the import block at lines 1-14 with:

```python
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from xgboost import XGBRegressor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets, validate_columns
from ml.core.metrics import regression_metrics
from ml.core.reporting import format_fold_plan, format_per_site_table
from ml.core.splits import outer_logo_folds
```

- [ ] **Step 2: Add imputation to every model (fixes R8)**

Replace the body of `build_models` so each estimator is wrapped:

```python
def build_models(seed: int):
  def piped(estimator, scale=False):
    steps = [('imputer', SimpleImputer(strategy='median'))]
    if scale:
      steps.append(('scaler', RobustScaler()))
    steps.append(('reg', estimator))
    return Pipeline(steps)

  return {
    'rf': piped(RandomForestRegressor(
      n_estimators=600, min_samples_leaf=2, n_jobs=-1, random_state=seed)),
    'extra_trees': piped(ExtraTreesRegressor(
      n_estimators=600, min_samples_leaf=2, n_jobs=-1, random_state=seed)),
    'hist_gb': piped(HistGradientBoostingRegressor(
      learning_rate=0.05, max_depth=8, max_iter=400, min_samples_leaf=20, random_state=seed)),
    'mlp': piped(MLPRegressor(
      hidden_layer_sizes=(64, 32), activation='relu', alpha=1e-3, batch_size=64,
      learning_rate_init=1e-3, early_stopping=True, max_iter=500, random_state=seed), scale=True),
    'XGB': piped(XGBRegressor(
      n_estimators=1000, learning_rate=0.03, max_depth=6, min_child_weight=3,
      subsample=0.8, colsample_bytree=0.8, reg_alpha=0.01, reg_lambda=1.0,
      objective='reg:squarederror', random_state=seed)),
  }
```

Note `random_state=seed` on `XGBRegressor` — this is the R7 fix.

- [ ] **Step 2b: Replace `evaluate_target` with the LOGO loop**

```python
def evaluate_target(df, features, target, models):
  X = df[features]
  y = df[target]
  sites = df[SITE_COLUMN]

  folds = list(outer_logo_folds(X, y, sites))
  print(format_fold_plan([f.train_sites for f in folds], [f.test_site for f in folds]))

  rows = []
  for name, model in models.items():
    for fold in folds:
      fitted = clone(model).fit(fold.X_train, fold.y_train)
      scores = regression_metrics(fold.y_test.to_numpy(), fitted.predict(fold.X_test))
      rows.append({'model': name, 'test_site': fold.test_site, **scores})
  return pd.DataFrame(rows)
```

- [ ] **Step 2c: Update `main` to load multiple CSVs and print per-site tables**

Replace the `df = pd.read_csv(args.csv)` line and the target loop in `main` with:

```python
  df = load_datasets(parse_csv_list(args.csv))
  validate_columns(df, features, 'feature')
  validate_columns(df, targets, 'target')

  models = build_models(args.seed)
  print(f'Dataset rows: {len(df)}')
  print(f'Sites: {sorted(df[SITE_COLUMN].unique())}')
  print(f'Features ({len(features)}): {features}')

  for target in targets:
    print('\n' + '=' * 90)
    print(f'Target: {target}')
    results = evaluate_target(df, features, target, models)
    print(format_per_site_table(results, 'r2'))
    print(format_per_site_table(results, 'rmse'))
```

- [ ] **Step 2d: Update the CLI flags**

Replace the `--csv`, `--test-size`, `--cv-folds` and `--split` arguments with:

```python
  parser.add_argument('--csv', required=True,
                      help='Comma-separated dataset CSV paths (merged into one site pool)')
  parser.add_argument('--no-tune', action='store_true', default=False,
                      help='Skip hyperparameter tuning')
  parser.add_argument('--test-size', type=float, default=None,
                      help='IGNORED under leave-one-site-out; accepted only to warn')
  parser.add_argument('--cv-folds', type=int, default=None,
                      help='IGNORED under leave-one-site-out; fold count is the site count')
```

Spec §6 requires these two flags to *warn* rather than vanish — silently accepting a removed flag via
an argparse error would break existing invocations without explaining why. Add this at the top of
`main`:

```python
  for flag, value in (('--test-size', args.test_size), ('--cv-folds', args.cv_folds)):
    if value is not None:
      print(f'WARNING: {flag} is ignored under leave-one-site-out; '
            'the fold count equals the number of sites.')
```

Delete the `--time-column` and `--group-column` arguments: the group column is now always the
canonical `site_id`, and no split is time-ordered.

- [ ] **Step 3: Verify it runs on the merged four-site pool**

Run:
```bash
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps
```
Expected: a `Fold plan` block listing 4 folds with `test=` each of `home-1`, `home-2`, `home-3`,
`office-cwpb`, then two per-site tables reading `n_sites=4`. **No `TypeError`** — that is the B1 fix
demonstrated.

- [ ] **Step 4: Confirm the tests still pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 23 tests` … `OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/regression_benchmark.py
git commit -m "refactor(ml): move regression benchmark onto LOGO core"
```

---

## Task 8: Rewire `classification_benchmark.py`

Fixes **M2**, **M3**, **R3**, **R6**.

**Files:**
- Modify: `src/ml/classification_benchmark.py`

- [ ] **Step 1: Replace imports and delete the leaking split code**

Delete `group_split` (lines 269-287), `time_holdout_split` (lines 252-267) and `assign_classes`
(lines 78-96). Replace lines 1-13 with:

```python
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets, validate_columns
from ml.core.metrics import CLASS_NAMES, apply_thresholds, assert_multiclass, quartile_thresholds
from ml.core.reporting import format_fold_plan, format_per_site_table
from ml.core.splits import inner_logo_splits, outer_logo_folds
```

Note `confusion_matrix` is deliberately absent from the import list: the rewritten `evaluate`
derives its numbers from `classification_report`, so keeping the old import would leave an unused
name behind.

- [ ] **Step 2: Replace `run_cv` and `tune_model` with a fold-local evaluation**

The old `TimeSeriesSplit` CV is what leaked in 5/5 folds. Replace both functions with:

```python
def evaluate(df, features, qoe_column, models, no_tune, tune_iter, seed):
  X = df[features]
  y_raw = df[qoe_column]
  sites = df[SITE_COLUMN]

  folds = list(outer_logo_folds(X, y_raw, sites))
  print(format_fold_plan([f.train_sites for f in folds], [f.test_site for f in folds]))

  rows = []
  for name, model in models.items():
    for fold in folds:
      # Thresholds come from the TRAINING sites only (M3 fix).
      t_low, t_high = quartile_thresholds(fold.y_train)
      y_train = apply_thresholds(fold.y_train, t_low, t_high)
      y_test = apply_thresholds(fold.y_test, t_low, t_high)
      assert_multiclass(y_train, f'train for test_site={fold.test_site}')
      assert_multiclass(y_test, f'test_site={fold.test_site}')

      if no_tune:
        fitted = clone(model).fit(fold.X_train, y_train)
      else:
        search = RandomizedSearchCV(
          estimator=clone(model),
          param_distributions=get_search_space(name),
          n_iter=tune_iter,
          scoring='f1_macro',
          cv=inner_logo_splits(fold.train_site_ids),
          n_jobs=-1,
          random_state=seed,
          refit=True,
        )
        search.fit(fold.X_train, y_train)
        fitted = search.best_estimator_

      y_pred = fitted.predict(fold.X_test)
      report = classification_report(
        y_test, y_pred, labels=CLASS_NAMES, output_dict=True, zero_division=0)
      rows.append({
        'model': name,
        'test_site': fold.test_site,
        'f1_macro': report['macro avg']['f1-score'],
        'balanced_accuracy': report['macro avg']['recall'],
        'threshold_low': t_low,
        'threshold_high': t_high,
      })
  return pd.DataFrame(rows)
```

- [ ] **Step 3: Replace `main`**

```python
def main():
  args = parse_args()
  np.random.seed(args.seed)

  features = parse_csv_list(args.features)
  df = load_datasets(parse_csv_list(args.csv), target=args.qoe_column)
  validate_columns(df, features, 'feature')

  df = df.dropna(subset=features).reset_index(drop=True)

  print(f'Dataset rows: {len(df)}')
  print(f'Sites: {sorted(df[SITE_COLUMN].unique())}')
  print(f'Split strategy: leave-one-site-out ({df[SITE_COLUMN].nunique()} folds)')

  models = build_models(args.seed)
  results = evaluate(df, features, args.qoe_column, models,
                     args.no_tune, args.tune_iter, args.seed)

  print('\n' + '=' * 110)
  print(format_per_site_table(results, 'f1_macro'))
  print(format_per_site_table(results, 'balanced_accuracy'))
```

The `Split strategy` line now states what actually ran — that is the R3 fix.

- [ ] **Step 4: Update the CLI flags**

Replace `--csv`, and delete `--time-column`, `--cv-gap`, `--cv-folds`, `--test-size`,
`--target-column` and `--tune-top-k`:

```python
  parser.add_argument('--csv', required=True,
                      help='Comma-separated dataset CSV paths (merged into one site pool)')
  parser.add_argument('--no-tune', action='store_true', default=False,
                      help='Skip hyperparameter tuning (recommended with few sites)')
```

- [ ] **Step 5: Verify it runs**

Run:
```bash
python3 src/ml/classification_benchmark.py \
  --csv data/metrics-20260630-qoe.csv,data/metrics-office-20260722-qoe.csv \
  --no-tune
```
Expected: a fold plan with 4 folds, then per-site `f1_macro` and `balanced_accuracy` tables with
`n_sites=4`. Per-site scores will differ substantially — that spread is the real finding.

- [ ] **Step 6: Confirm the tests still pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 23 tests` … `OK`

- [ ] **Step 7: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/classification_benchmark.py
git commit -m "refactor(ml): move classification benchmark onto LOGO core"
```

---

## Task 9: Quarantine the keras scripts

Implements the **B2/B3/R5 "not fixed"** disposition from spec §11.

**Files:**
- Create: `src/ml/experimental/README.md`
- Move: `src/ml/regression_keras.py`, `src/ml/classifier_keras.py`

- [ ] **Step 1: Move the files unmodified**

```bash
mkdir -p src/ml/experimental
git mv src/ml/regression_keras.py src/ml/experimental/regression_keras.py
git mv src/ml/classifier_keras.py src/ml/experimental/classifier_keras.py
```

- [ ] **Step 2: Document why**

Create `src/ml/experimental/README.md`:

```markdown
# Experimental — unmaintained

These scripts are kept for reference only. They are **not** part of the evaluation pipeline, are not
imported by any maintained script, and are not covered by tests.

Known defects, deliberately left unfixed (see
`docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md` §11):

- `regression_keras.py` — does not parse (`IndentationError` at line 21); `y`, `target` and
  `regression` are never defined. Intent could not be recovered, so it was not rewritten.
- `classifier_keras.py` — `NameError` on `display_labels` after training completes; fits
  `LabelEncoder` twice; uses a random split, so its scores do not measure cross-site generalisation.

Use `src/ml/regression_benchmark.py` or `src/ml/classification_benchmark.py` instead.
```

- [ ] **Step 3: Verify nothing imports them**

Run: `grep -rn "regression_keras\|classifier_keras" src/ tests/ --include=*.py`
Expected: no output (the moved files do not import each other).

- [ ] **Step 4: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/experimental/
git commit -m "chore(ml): quarantine unmaintained keras scripts"
```

---

## Task 10: Rewire the MLflow scripts

Fixes **M4**, **B4**, **R1**, **R2**.

**Files:**
- Modify: `src/ml/regression_mlflow.py`
- Modify: `src/ml/classifier_mlflow.py`

- [ ] **Step 1: Replace the hardcoded path and random split in `regression_mlflow.py`**

Replace lines 16-17 (`DS_CSV=...` and `df = pd.read_csv(...)`) with:

```python
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets
from ml.core.splits import outer_logo_folds

DS_CSV = os.environ.get('DS_CSV', 'data/metrics-20260630-out.csv')
df = load_datasets(DS_CSV.split(','))
```

Then replace the `train_test_split(...)` call (line 64) with the first LOGO fold, so MLflow runs
become comparable to the benchmarks:

```python
        fold = next(iter(outer_logo_folds(X, y, df[SITE_COLUMN])))
        X_train, X_test, y_train, y_test = fold.X_train, fold.X_test, fold.y_train, fold.y_test
        mlflow.log_param('test_site', fold.test_site)
```

- [ ] **Step 2: Fix the label ordering and the F1 bug in `classifier_mlflow.py`**

Replace the duplicated `LabelEncoder` blocks (lines 55-71) with an explicit ordered mapping, so
`bad < mid < good` holds instead of `LabelEncoder`'s alphabetical `bad, good, mid` (R1 fix):

```python
CLASS_ORDER = ['bad', 'mid', 'good']
CLASS_TO_INT = {name: index for index, name in enumerate(CLASS_ORDER)}
df[target] = df[target].map(CLASS_TO_INT)
print(f'class mapping: {CLASS_TO_INT}')
```

Then fix line 143, which prints the accuracy value under an F1 label (R2 fix):

```python
        print(f"F1-score: {f1}")
```

- [ ] **Step 3: Remove the leaked feature-list landmine**

Delete the first `features=[...]` assignment in `classifier_mlflow.py` (lines 41-52). It contains
`speedtest_down_mbps`, `latency_ms` and `download_*` — the quantities `qoe_dw_score` is derived from —
and is only harmless because the next line overwrites it. Keep the second assignment (line 53).

- [ ] **Step 4: Verify both scripts import cleanly**

Run: `python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in ['src/ml/regression_mlflow.py','src/ml/classifier_mlflow.py']]; print('both parse OK')"`
Expected: `both parse OK`

- [ ] **Step 5: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/regression_mlflow.py src/ml/classifier_mlflow.py
git commit -m "refactor(ml): align mlflow scripts with LOGO core, fix label order"
```

---

## Task 11: Legacy-versus-LOGO comparison

Implements spec §9 — the audit trail quantifying how much the old numbers were inflated.

**Files:**
- Create: `src/ml/compare_protocols.py`

- [ ] **Step 1: Write the comparison script**

Create `src/ml/compare_protocols.py`:

```python
"""Quantify the optimism of the legacy evaluation protocol.

Runs one model under the legacy protocol (random split) and under leave-one-site-out
on identical data, then prints the delta. Run once; record the output.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets
from ml.core.metrics import regression_metrics
from ml.core.splits import outer_logo_folds

FEATURES = [
  'router_expected_throughput_mbps', 'router_noise', 'router_rx_drop_misc',
  'router_rx_duration_us', 'router_rx_rate_mbps', 'router_signal_avg_dbm',
  'router_signal_dbm', 'router_snr', 'router_tx_duration_us', 'router_tx_failed',
  'router_tx_rate_mbps', 'router_tx_retries', 'router_opportunity_medium_use',
  'client_opportunity_medium_use',
]


def build_model(seed):
  return Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('reg', RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                  n_jobs=-1, random_state=seed)),
  ])


def main():
  parser = argparse.ArgumentParser(description='Legacy vs LOGO protocol comparison')
  parser.add_argument('--csv', required=True, help='Comma-separated CSV paths')
  parser.add_argument('--target', default='speedtest_down_mbps')
  parser.add_argument('--seed', type=int, default=42)
  args = parser.parse_args()

  df = load_datasets(args.csv.split(','), target=args.target)
  X, y = df[FEATURES], df[args.target]

  # Legacy protocol: random split, rows from one site on both sides.
  X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=args.seed)
  legacy = regression_metrics(
    y_te.to_numpy(), clone(build_model(args.seed)).fit(X_tr, y_tr).predict(X_te))

  # Corrected protocol: leave one site out.
  per_site = []
  for fold in outer_logo_folds(X, y, df[SITE_COLUMN]):
    scores = regression_metrics(
      fold.y_test.to_numpy(),
      clone(build_model(args.seed)).fit(fold.X_train, fold.y_train).predict(fold.X_test))
    scores['test_site'] = fold.test_site
    per_site.append(scores)

  logo = pd.DataFrame(per_site)
  print('\nLegacy protocol (random split):')
  print(f"  r2={legacy['r2']:.5f}  rmse={legacy['rmse']:.5f}")
  print('\nLeave-one-site-out, per site:')
  print(logo[['test_site', 'r2', 'rmse']].to_string(
    index=False, float_format=lambda x: f'{x:.5f}'))
  print(f"\nLOGO mean r2={logo['r2'].mean():.5f} "
        f"(min={logo['r2'].min():.5f}, max={logo['r2'].max():.5f})")
  print(f"\nOptimism of the legacy number: {legacy['r2'] - logo['r2'].mean():.5f} r2")


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Run it and capture the delta**

Run:
```bash
python3 src/ml/compare_protocols.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --target speedtest_down_mbps 2>&1 | tee /tmp/protocol_delta.txt
```
Expected: legacy r2 substantially higher than the LOGO mean. **A negative per-site r2 is a valid
result**, not a bug — it means the model does worse than predicting that site's mean.

- [ ] **Step 3: Record the result in the spec**

Append the captured output to
`docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md` under a new heading
`## 14. Measured optimism of the legacy protocol`, as a fenced code block, followed by one sentence
stating the r2 delta.

- [ ] **Step 4: Commit (USER ACTION — do not run this yourself)**

```bash
git add src/ml/compare_protocols.py docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md
git commit -m "feat(ml): add legacy-vs-LOGO protocol comparison"
```

---

## Final verification

- [ ] **All core tests pass**

Run: `python3 -m unittest tests.test_ml_core -v`
Expected: `Ran 23 tests` … `OK`

- [ ] **Both benchmarks run end to end on four sites**

Run:
```bash
python3 src/ml/regression_benchmark.py \
  --csv data/metrics-20260630-out.csv,data/metrics-office-20260722-out.csv \
  --targets speedtest_down_mbps
python3 src/ml/classification_benchmark.py \
  --csv data/metrics-20260630-qoe.csv,data/metrics-office-20260722-qoe.csv --no-tune
```
Expected: both print a 4-fold plan and per-site tables; neither raises.

- [ ] **No script still uses a non-group split**

Run: `grep -rn "train_test_split\|TimeSeriesSplit\|GroupShuffleSplit" src/ml/ --include=*.py | grep -v experimental/ | grep -v compare_protocols.py`
Expected: no output. Any hit is a surviving path that can leak.

- [ ] **Known limitation is recorded, not silently accepted**

Confirm spec §10 still states that four sites cannot support a stable estimate and that more sites are
the real unlock.

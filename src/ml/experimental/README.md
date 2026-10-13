# Experimental — unmaintained

These scripts are kept for reference only. They are **not** part of the evaluation pipeline, are not
imported by any maintained script, and are not covered by tests.

Known defects, deliberately left unfixed (see
`docs/superpowers/specs/2026-08-12-ml-training-remediation-design.md` §11):

- `regression_keras.py` — does not parse (`IndentationError` at line 21); `y`, `target` and
  `regression` are never defined. Intent could not be recovered, so it was not rewritten.
- `classifier_keras.py` — `NameError` on `display_labels` after training completes; fits
  `LabelEncoder` twice; uses a random split, so its scores do not measure cross-site generalisation.
- `classifier_mlflow.py` — moved here on 2026-10-09. Reads `data/metrics-20260630-qoe.csv` (old schema
  generation, outside the canonical loader), classifies `qoe_dw_score` (formula lost, see
  `core/carga.py:discover`), uses a random split, and trains on the speedtest-window counters marked as
  leakage in `column_provenance.json`. Its scores do not measure anything the régua measures.

Use `src/ml/regression_mlflow.py`, `src/ml/regression_benchmark.py` or `src/ml/classification_benchmark.py` instead.

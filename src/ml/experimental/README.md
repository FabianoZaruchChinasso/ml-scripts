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

import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets, validate_columns
from ml.core.metrics import (CLASS_NAMES, apply_thresholds, assert_comparable_scales,
                             assert_multiclass, quartile_thresholds)
from ml.core.reporting import format_fold_plan, format_per_site_table
from ml.core.splits import inner_logo_splits, outer_logo_folds


DEFAULT_FEATURES = [
  "router_expected_throughput_mbps",
  "router_noise",
  "router_rx_drop_misc",
  "router_rx_duration_us",
  "router_rx_rate_mbps",
  "router_signal_avg_dbm",
  "router_signal_dbm",
  "router_snr",
  "router_tx_duration_us",
  "router_tx_failed",
  "router_tx_rate_mbps",
  "router_tx_retries",
  "router_opportunity_medium_use",
  "client_opportunity_medium_use",
]


def parse_csv_list(raw: str):
  return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args():
  parser = argparse.ArgumentParser(description="Benchmark WiFi QoE classifiers")
  parser.add_argument('--csv', required=True,
                      help='Comma-separated dataset CSV paths (merged into one site pool)')
  parser.add_argument('--group-level', choices=['position', 'building'], default='position',
                      help="'position' (padrão): 7 grupos, um por ponto de medição. "
                           "'building': 2 grupos, residencia/coworking (viabilidade, n=2)")
  parser.add_argument("--qoe-column", default="qoe_dw_score", help="Raw QoE score column")
  parser.add_argument(
    "--features",
    default=",".join(DEFAULT_FEATURES),
    help="Comma-separated feature columns",
  )
  parser.add_argument(
    "--class-mode",
    choices=["quartile", "fixed"],
    default="quartile",
    help="Class binning strategy",
  )
  parser.add_argument(
    "--fixed-thresholds",
    default="0.25,0.74",
    help="Two thresholds for fixed mode: bad<x<t1, mid<t2, good>=t2",
  )
  parser.add_argument("--tune-iter", type=int, default=20, help="Randomized search iterations per tuned model")
  parser.add_argument('--no-tune', action='store_true', default=False,
                      help='Skip hyperparameter tuning (recommended with few sites)')
  parser.add_argument("--seed", type=int, default=42, help="Random seed")
  parser.add_argument('--test-size', type=float, default=None,
                      help='IGNORED under leave-one-site-out; accepted only to warn')
  parser.add_argument('--cv-folds', type=int, default=None,
                      help='IGNORED under leave-one-site-out; fold count is the site count')
  parser.add_argument('--cv-gap', type=int, default=None,
                      help='IGNORED; leave-one-site-out has no time-ordered gap')
  parser.add_argument('--target-column', default=None,
                      help='IGNORED; class labels are computed per fold, not stored in a column')
  parser.add_argument('--time-column', default=None,
                      help='IGNORED; no split in this script is time-ordered')
  parser.add_argument('--tune-top-k', type=int, default=None,
                      help='IGNORED; every model is tuned, not just the top-k by CV score')
  parser.add_argument('--plot-confusion', action='store_true', default=None,
                      help='IGNORED; this script no longer builds a confusion matrix')
  return parser.parse_args()


def build_models(seed: int):
  return {
    "rf": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        (
          "clf",
          RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=seed,
          ),
        ),
      ]
    ),
    "extra_trees": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        (
          "clf",
          ExtraTreesClassifier(
            n_estimators=600,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=seed,
          ),
        ),
      ]
    ),
    "hist_gb": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        (
          "clf",
          HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=8,
            max_iter=400,
            min_samples_leaf=20,
            random_state=seed,
          ),
        ),
      ]
    ),
    "log_reg": Pipeline(
      [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        (
          "clf",
          LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=seed,
          ),
        ),
      ]
    ),
  }


def get_search_space(model_name: str):
  if model_name == "rf":
    return {
      "clf__n_estimators": [300, 500, 800, 1000],
      "clf__max_depth": [None, 8, 12, 16, 24],
      "clf__min_samples_leaf": [1, 2, 4, 8],
      "clf__max_features": ["sqrt", "log2", None],
    }
  if model_name == "extra_trees":
    return {
      "clf__n_estimators": [300, 600, 900, 1200],
      "clf__max_depth": [None, 8, 12, 16, 24],
      "clf__min_samples_leaf": [1, 2, 4, 8],
      "clf__max_features": ["sqrt", "log2", None],
    }
  if model_name == "hist_gb":
    return {
      "clf__learning_rate": [0.01, 0.03, 0.05, 0.08, 0.12],
      "clf__max_depth": [None, 4, 6, 8, 10],
      "clf__max_iter": [200, 300, 400, 600],
      "clf__min_samples_leaf": [10, 20, 40, 80],
      "clf__l2_regularization": [0.0, 1e-4, 1e-3, 1e-2],
    }
  if model_name == "log_reg":
    return {
      "clf__C": [0.01, 0.1, 0.5, 1.0, 3.0, 10.0],
      "clf__solver": ["lbfgs", "newton-cg", "saga"],
    }
  raise ValueError(f"No search space defined for model: {model_name}")


def evaluate(df, features, qoe_column, models, no_tune, tune_iter, seed, group_level):
  X = df[features]
  y_raw = df[qoe_column]
  sites = df[SITE_COLUMN]
  assert_comparable_scales(y_raw, sites, qoe_column)

  folds = list(outer_logo_folds(X, y_raw, sites))
  print(format_fold_plan([f.train_sites for f in folds], [f.test_site for f in folds],
                         group_level=group_level))

  rows = []
  for fold in folds:
    # Thresholds come from the TRAINING sites only (M3 fix) and depend only on
    # the fold, not the model, so they're computed once per fold here.
    t_low, t_high = quartile_thresholds(fold.y_train)
    y_train = apply_thresholds(fold.y_train, t_low, t_high)
    y_test = apply_thresholds(fold.y_test, t_low, t_high)
    assert_multiclass(y_train, f'train for test_site={fold.test_site}')
    assert_multiclass(y_test, f'test_site={fold.test_site}')
    print(f'  test_site={fold.test_site}: thresholds low={t_low:.5f} high={t_high:.5f}')

    for name, model in models.items():
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


def main():
  args = parse_args()

  ignored_flags = (
    ('--test-size', args.test_size,
     'the fold count equals the number of sites'),
    ('--cv-folds', args.cv_folds,
     'the fold count equals the number of sites'),
    ('--cv-gap', args.cv_gap,
     'leave-one-site-out has no time-ordered gap'),
    ('--target-column', args.target_column,
     'class labels are computed per fold, not stored in a column'),
    ('--time-column', args.time_column,
     'no split in this script is time-ordered'),
    ('--tune-top-k', args.tune_top_k,
     'every model is tuned, not just the top-k by CV score'),
    ('--plot-confusion', args.plot_confusion,
     'this script no longer builds a confusion matrix'),
  )
  for flag, value, reason in ignored_flags:
    if value is not None:
      print(f'WARNING: {flag} is ignored under leave-one-site-out; {reason}.')

  np.random.seed(args.seed)

  if args.class_mode != 'quartile':
    print('WARNING: --class-mode/--fixed-thresholds are not yet honored; '
          'evaluate() always uses per-fold quartile thresholds.')

  features = parse_csv_list(args.features)
  df = load_datasets(parse_csv_list(args.csv), target=args.qoe_column,
                     group_level=args.group_level)
  validate_columns(df, features, 'feature')

  df = df.dropna(subset=features).reset_index(drop=True)

  print(f'Dataset rows: {len(df)}')
  print(f'Sites: {sorted(df[SITE_COLUMN].unique())}')
  print(f'Split strategy: leave-one-{args.group_level}-out '
        f'({df[SITE_COLUMN].nunique()} folds)')

  models = build_models(args.seed)
  results = evaluate(df, features, args.qoe_column, models,
                     args.no_tune, args.tune_iter, args.seed, args.group_level)

  print('\n' + '=' * 110)
  print(format_per_site_table(results, 'f1_macro'))
  print(format_per_site_table(results, 'balanced_accuracy'))


if __name__ == "__main__":
  main()

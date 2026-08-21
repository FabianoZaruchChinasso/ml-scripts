"""Quantify the optimism of the legacy evaluation protocol.

Runs one model under the legacy protocol (random split) and under leave-one-site-out
on identical data, then prints the delta. Run once; record the output.
"""

import argparse
import os
import sys

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets, validate_columns
from ml.core.metrics import assert_comparable_scales, regression_metrics
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
  parser.add_argument('--group-level', choices=['position', 'building'], default='position',
                      help="'position' (padrão) ou 'building' (viabilidade, n=2)")
  parser.add_argument('--seed', type=int, default=42)
  args = parser.parse_args()

  df = load_datasets(args.csv.split(','), target=args.target, group_level=args.group_level)
  print(f'Sites: {sorted(df[SITE_COLUMN].unique())}')
  print(f'Group level: {args.group_level}')
  validate_columns(df, FEATURES, 'feature')
  X, y = df[FEATURES], df[args.target]
  assert_comparable_scales(y, df[SITE_COLUMN], args.target)

  # Legacy protocol: random split, rows from one site on both sides.
  X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=args.seed)
  legacy = regression_metrics(
    y_te.to_numpy(), build_model(args.seed).fit(X_tr, y_tr).predict(X_te))

  # Corrected protocol: leave one site out.
  per_site = []
  for fold in outer_logo_folds(X, y, df[SITE_COLUMN]):
    scores = regression_metrics(
      fold.y_test.to_numpy(),
      build_model(args.seed).fit(fold.X_train, fold.y_train).predict(fold.X_test))
    scores['test_site'] = fold.test_site
    per_site.append(scores)

  logo = pd.DataFrame(per_site)
  print('\nLegacy protocol (random split):')
  print(f"  r2={legacy['r2']:.5f}  rmse={legacy['rmse']:.5f}")
  print(f'\nLeave-one-{args.group_level}-out, per site:')
  print(logo[['test_site', 'r2', 'rmse']].to_string(
    index=False, float_format=lambda x: f'{x:.5f}'))
  print(f"\nLOGO mean r2={logo['r2'].mean():.5f} "
        f"(min={logo['r2'].min():.5f}, max={logo['r2'].max():.5f})")
  print(f"\nOptimism of the legacy number: {legacy['r2'] - logo['r2'].mean():.5f} r2")


if __name__ == '__main__':
  main()

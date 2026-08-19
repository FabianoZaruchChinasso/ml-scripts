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
from ml.core.metrics import assert_comparable_scales, regression_metrics
from ml.core.reporting import format_fold_plan, format_per_site_table
from ml.core.splits import outer_logo_folds


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
DEFAULT_FEATURES_STATS = [
  "client_opportunity_medium_use",
  "router_expected_throughput_mbps",
  "router_noise",
  "router_opportunity_medium_use",
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
  "signal_level",
  #"stats_80211_client_ampdu_avg_length",
  #"stats_80211_client_ampdu_count",
  #"stats_80211_client_ampdu_efficiency_pct",
  #"stats_80211_client_ampdu_subframes",
  ###"stats_80211_client_amsdu_frames",
  #"stats_80211_client_assoc_ap",
  "stats_80211_client_beamforming",
  "stats_80211_client_block_ack_req",
  "stats_80211_client_block_ack_tx",
  "stats_80211_client_cts",
  #"stats_80211_client_cts_retransmission",
  #"stats_80211_client_data",
  "stats_80211_client_data_retransmission",
  "stats_80211_client_mac_bytes",
  #"stats_80211_client_mpdu_bytes",
  "stats_80211_client_msdu_bytes",
  "stats_80211_client_overhead_pct",
  "stats_80211_client_payload_bytes",
  #"stats_80211_client_qos_data",
  #"stats_80211_client_raw",
  "stats_80211_client_retry_bytes",
  "stats_80211_client_retry_overhead_pct",
  "stats_80211_client_rts",
  "stats_80211_client_rts_retransmission",
  #"stats_80211_client_total_frames",
  "stats_80211_global_ack",
  #"stats_80211_global_ampdu_avg_length",
  #"stats_80211_global_ampdu_count",
  #"stats_80211_global_ampdu_efficiency_pct",
  #"stats_80211_global_ampdu_subframes",
  #"stats_80211_global_amsdu_frames",
  "stats_80211_global_beamforming_actions",
  "stats_80211_global_beamforming_frames",
  "stats_80211_global_block_ack",
  "stats_80211_global_block_ack_req",
  "stats_80211_global_ctrl_frames",
  "stats_80211_global_cts",
  #"stats_80211_global_data_frames",
  #"stats_80211_global_data_frames_count",
  "stats_80211_global_data_retry_frames",
  "stats_80211_global_data_retry_pct",
  "stats_80211_global_elapsed_seconds",
  #"stats_80211_global_filtered_frames",
  "stats_80211_global_mac_bytes",
  "stats_80211_global_mac_throughput_mbps",
  "stats_80211_global_mgmt_frames",
  #"stats_80211_global_mpdu_bytes",
  "stats_80211_global_msdu_bytes",
  #"stats_80211_global_msdu_count",
  #"stats_80211_global_ndp_announce",
  "stats_80211_global_overhead_pct",
  "stats_80211_global_payload_bytes",
  "stats_80211_global_payload_throughput_mbps",
  #"stats_80211_global_qos_data",
  "stats_80211_global_retry_bytes",
  "stats_80211_global_retry_frames",
  "stats_80211_global_retry_frames_pct",
  "stats_80211_global_retry_overhead_pct",
  "stats_80211_global_rts",
  "stats_80211_global_rts_retransmission",
  #"stats_80211_global_timestamp",
  #"stats_80211_global_total_frames",
  "stats_80211_per_ap_count",
  "stats_80211_per_client_count",
  #"stats_80211_raw"
]

DEFAULT_TARGETS = []
DEFAULT_TARGETS = ["speedtest_down_mbps", "speedtest_up_mbps"]
DEFAULT_TARGETS += ['latency_ms', 'jitter_ms']


def parse_csv_list(raw: str):
  return [item.strip() for item in raw.split(",") if item.strip()]


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


def evaluate_target(df, features, target, models, group_level):
  valid = df[target].notna()
  dropped = (~valid).sum()
  if dropped:
    print(f'dropped {dropped} rows with empty target {target!r}')
  df = df[valid]

  X = df[features]
  y = df[target]
  sites = df[SITE_COLUMN]
  assert_comparable_scales(y, sites, target)

  folds = list(outer_logo_folds(X, y, sites))
  print(format_fold_plan([f.train_sites for f in folds], [f.test_site for f in folds],
                         group_level=group_level))

  rows = []
  for name, model in models.items():
    for fold in folds:
      fitted = clone(model).fit(fold.X_train, fold.y_train)
      scores = regression_metrics(fold.y_test.to_numpy(), fitted.predict(fold.X_test))
      rows.append({'model': name, 'test_site': fold.test_site, **scores})
  return pd.DataFrame(rows)


def parse_args():
  parser = argparse.ArgumentParser(description="Benchmark regressors for WiFi throughput estimation")
  parser.add_argument('--csv', required=True,
                      help='Comma-separated dataset CSV paths (merged into one site pool)')
  parser.add_argument('--group-level', choices=['position', 'building'], default='position',
                      help="'position' (padrão): 7 grupos, um por ponto de medição. "
                           "'building': 2 grupos, residencia/coworking (viabilidade, n=2)")
  parser.add_argument(
    "--targets",
    default=",".join(DEFAULT_TARGETS),
    help="Comma-separated regression targets",
  )
  parser.add_argument(
    "--features",
    default=",".join(DEFAULT_FEATURES),
    help="Comma-separated feature columns",
  )
  parser.add_argument("--seed", type=int, default=42, help="Random seed")
  parser.add_argument("--use-stats", action='store_true', default=False, help="Use stats feat")
  parser.add_argument('--test-size', type=float, default=None,
                      help='IGNORED under leave-one-site-out; accepted only to warn')
  parser.add_argument('--cv-folds', type=int, default=None,
                      help='IGNORED under leave-one-site-out; fold count is the site count')
  parser.add_argument('--split', choices=['group', 'random'], default=None,
                      help='IGNORED; leave-one-site-out replaced both split strategies')
  parser.add_argument('--group-column', default=None,
                      help='IGNORED; the group is always the resolved site_id')
  parser.add_argument('--time-column', default=None,
                      help='IGNORED; no split in this script is time-ordered')
  return parser.parse_args()


def main():
  args = parse_args()

  ignored_flags = (
    ('--test-size', args.test_size,
     'the fold count equals the number of sites'),
    ('--cv-folds', args.cv_folds,
     'the fold count equals the number of sites'),
    ('--split', args.split,
     'leave-one-site-out replaced both the group and random split strategies'),
    ('--group-column', args.group_column,
     'the group is always the resolved site_id, not a raw column name'),
    ('--time-column', args.time_column,
     'no split in this script is time-ordered'),
  )
  for flag, value, reason in ignored_flags:
    if value is not None:
      print(f'WARNING: {flag} is ignored under leave-one-site-out; {reason}.')

  np.random.seed(args.seed)

  if args.use_stats == True:
    features = DEFAULT_FEATURES_STATS
  else:
    features = parse_csv_list(args.features)
  targets = parse_csv_list(args.targets)

  df = load_datasets(parse_csv_list(args.csv), group_level=args.group_level)
  validate_columns(df, features, 'feature')
  validate_columns(df, targets, 'target')

  models = build_models(args.seed)
  print(f'Dataset rows: {len(df)}')
  print(f'Sites: {sorted(df[SITE_COLUMN].unique())}')
  print(f'Group level: {args.group_level}')
  print(f'Features ({len(features)}): {features}')

  for target in targets:
    print('\n' + '=' * 90)
    print(f'Target: {target}')
    results = evaluate_target(df, features, target, models, args.group_level)
    print(format_per_site_table(results, 'r2'))
    print(format_per_site_table(results, 'rmse'))


if __name__ == "__main__":
  main()

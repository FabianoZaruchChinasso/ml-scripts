import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, TimeSeriesSplit, cross_validate, GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from xgboost import XGBRegressor
from sklearn.model_selection import GroupShuffleSplit


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


@dataclass
class SplitData:
  X_train: pd.DataFrame
  X_test: pd.DataFrame
  y_train: pd.Series
  y_test: pd.Series
  grp: pd.Series


def parse_csv_list(raw: str):
  return [item.strip() for item in raw.split(",") if item.strip()]


def validate_columns(df: pd.DataFrame, columns, role: str):
  missing = [col for col in columns if col not in df.columns]
  if missing:
    raise ValueError(f"Missing {role} columns in dataset: {missing}")


def safe_mape(y_true: np.ndarray, y_pred: np.ndarray):
  mask = np.abs(y_true) > 1e-9
  if not np.any(mask):
    return np.nan
  return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray):
  abs_err = np.abs(y_true - y_pred)
  return {
    "r2": r2_score(y_true, y_pred),
    "rmse": mean_squared_error(y_true, y_pred) ** 0.5,
    "mae": mean_absolute_error(y_true, y_pred),
    "mape": safe_mape(y_true, y_pred),
    "p90_ae": float(np.percentile(abs_err, 90)),
  }


def train_test_split_time_aware(df: pd.DataFrame, features, target: str, time_column: str, test_size: float):
  ordered = df.sort_values(time_column)
  split_idx = int(len(ordered) * (1.0 - test_size))
  train_df = ordered.iloc[:split_idx]
  test_df = ordered.iloc[split_idx:]
  return SplitData(
    X_train=train_df[features],
    X_test=test_df[features],
    y_train=train_df[target],
    y_test=test_df[target],
  )

def group_split(df, features, target, test_size, group='local'):
    #cols=['local','AP_channel','channel_width','radio','distance_m']
    #cols=['distance_m']
    #for c in cols:
    #    df[c] = df[c].fillna(0).astype(str)
    #df['group']=df[cols].agg(' '.join, axis=1)
    X = df[features]
    y = df[target]
    gss = GroupShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=42
    )
    train_idx, test_idx = next(
        gss.split(X, y, groups=df[group])
    )
    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]
    grp = df[group].iloc[train_idx]
    return SplitData(X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test, grp = grp)


def train_test_split_random(df: pd.DataFrame, features, target: str, test_size: float, seed: int):
  from sklearn.model_selection import train_test_split

  X_train, X_test, y_train, y_test = train_test_split(
    df[features],
    df[target],
    test_size=test_size,
    random_state=seed,
    shuffle=True,
  )
  return SplitData(X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test)


def build_models(seed: int):
  return {
    "rf": RandomForestRegressor(
      n_estimators=600,
      min_samples_leaf=2,
      n_jobs=-1,
      random_state=seed,
    ),
    "extra_trees": ExtraTreesRegressor(
      n_estimators=600,
      min_samples_leaf=2,
      n_jobs=-1,
      random_state=seed,
    ),
    "hist_gb": HistGradientBoostingRegressor(
      learning_rate=0.05,
      max_depth=8,
      max_iter=400,
      min_samples_leaf=20,
      random_state=seed,
    ),
    "mlp": Pipeline(
      [
        ("scaler", RobustScaler()),
        (
          "reg",
          MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            alpha=1e-3,
            batch_size=64,
            learning_rate_init=1e-3,
            early_stopping=True,
            max_iter=500,
            random_state=seed,
          ),
        ),
      ]
    ),
    "XGB" : XGBRegressor(
      n_estimators=1000,
      learning_rate=0.03,
      max_depth=6,
      min_child_weight=3,
      subsample=0.8,
      colsample_bytree=0.8,
      reg_alpha=0.01,
      reg_lambda=1.0,
      objective="reg:squarederror",
      random_state=42
    ),
  }


def evaluate_target(
  df: pd.DataFrame,
  features,
  target: str,
  models,
  use_group_split: bool,
  time_column: str,
  group_column: str,
  test_size: float,
  cv_folds: int,
  seed: int,
):
  if use_group_split:
    print(f"Unique groups: {df[group_column].nunique()}")
    #split = train_test_split_time_aware(df, features, target, time_column, test_size)
    #cv = TimeSeriesSplit(n_splits=cv_folds)
    split = group_split(df, features, target, test_size, group=group_column)
    n_groups = split.grp.nunique()
    effective_folds = min(cv_folds, n_groups)
    if effective_folds < 2:
        raise ValueError("Need at least 2 groups for GroupKFold")
    print(f"Train groups: {n_groups}, using {effective_folds} CV folds")
    cv = GroupKFold(n_splits=effective_folds)
    groups = split.grp
  else:
    split = train_test_split_random(df, features, target, test_size, seed)
    cv = KFold(n_splits=cv_folds, shuffle=False)#True, random_state=seed)
    groups = None


  rows = []
  for name, model in models.items():
    cv_scores = cross_validate(
      clone(model),
      split.X_train,
      split.y_train,
      cv=cv,
      groups=groups,
      scoring={
        "r2": "r2",
        "rmse": "neg_root_mean_squared_error",
        "mae": "neg_mean_absolute_error",
      },
      n_jobs=-1,
    )

    fitted = clone(model).fit(split.X_train, split.y_train)
    holdout_pred = fitted.predict(split.X_test)
    holdout = compute_metrics(split.y_test.to_numpy(), holdout_pred)

    rows.append(
      {
        "model": name,
        "cv_r2_mean": float(np.mean(cv_scores["test_r2"])),
        "cv_r2_std": float(np.std(cv_scores["test_r2"])),
        "cv_rmse_mean": float(-np.mean(cv_scores["test_rmse"])),
        "cv_mae_mean": float(-np.mean(cv_scores["test_mae"])),
        "holdout_r2": holdout["r2"],
        "holdout_rmse": holdout["rmse"],
        "holdout_mae": holdout["mae"],
        "holdout_mape": holdout["mape"],
        "holdout_p90_ae": holdout["p90_ae"],
      }
    )

  result = pd.DataFrame(rows).sort_values("cv_r2_mean", ascending=False)
  return result.reset_index(drop=True)


def parse_args():
  parser = argparse.ArgumentParser(description="Benchmark regressors for WiFi throughput estimation")
  parser.add_argument("--csv", required=True, help="Input dataset CSV path")
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
  parser.add_argument("--time-column", default="_time", help="Timestamp column used for time-aware split")
  parser.add_argument("--group-column", default="local", help="Timestamp column used for time-aware split")
  parser.add_argument("--test-size", type=float, default=0.2, help="Holdout ratio")
  parser.add_argument("--cv-folds", type=int, default=5, help="Cross-validation folds")
  parser.add_argument("--seed", type=int, default=42, help="Random seed")
  parser.add_argument("--use-stats", action='store_true', default=False, help="Use stats feat")
  parser.add_argument(
    "--split",
    choices=["group", "random"],
    default="random",
    help="Use 'time' for realistic generalization or 'random' for quick baseline",
  )
  return parser.parse_args()


def main():
  args = parse_args()

  np.random.seed(args.seed)

  if args.use_stats == True:
    features = DEFAULT_FEATURES_STATS
  else:
    features = parse_csv_list(args.features)
  targets = parse_csv_list(args.targets)
  use_group_split = args.split == "group"

  df = pd.read_csv(args.csv)
  validate_columns(df, features, "feature")
  validate_columns(df, targets, "target")

  if use_group_split:
    validate_columns(df, [args.group_column], args.group_column)

  models = build_models(args.seed)
  print(f"Dataset rows: {len(df)}")
  print(f"Features ({len(features)}): {features}")
  print(f"Targets: {targets}")
  print(f"Split strategy: {args.split}")
  if use_group_split:
    print(f"  Split group: {args.group_column}")

  for target in targets:
    print("\n" + "=" * 90)
    print(f"Target: {target}")
    table = evaluate_target(
      df=df,
      features=features,
      target=target,
      models=models,
      use_group_split=use_group_split,
      time_column=args.time_column,
      group_column=args.group_column,
      test_size=args.test_size,
      cv_folds=args.cv_folds,
      seed=args.seed,
    )
    print(table.to_string(index=False, float_format=lambda x: f"{x:.5f}"))


if __name__ == "__main__":
  main()

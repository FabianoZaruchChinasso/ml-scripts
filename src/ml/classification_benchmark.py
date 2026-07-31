import argparse

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, confusion_matrix
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
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

CLASS_NAMES = ["bad", "mid", "good"]


def parse_csv_list(raw: str):
  return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args():
  parser = argparse.ArgumentParser(description="Benchmark WiFi QoE classifiers")
  parser.add_argument("--csv", required=True, help="Input dataset CSV path")
  parser.add_argument("--qoe-column", default="qoe_dw_score", help="Raw QoE score column")
  parser.add_argument("--target-column", default="qoe_class", help="Generated class label column")
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
  parser.add_argument("--test-size", type=float, default=0.2, help="Holdout ratio")
  parser.add_argument("--cv-folds", type=int, default=5, help="TimeSeriesSplit folds")
  parser.add_argument("--time-column", default="_time", help="Timestamp column for time-aware split")
  parser.add_argument("--cv-gap", type=int, default=0, help="Gap between train and validation windows")
  parser.add_argument("--tune-top-k", type=int, default=2, help="How many top CV models to tune")
  parser.add_argument("--tune-iter", type=int, default=20, help="Randomized search iterations per tuned model")
  parser.add_argument("--plot-confusion", action="store_true", help="Display confusion matrix plot")
  parser.add_argument("--seed", type=int, default=42, help="Random seed")
  return parser.parse_args()


def validate_columns(df: pd.DataFrame, columns, role: str):
  missing = [col for col in columns if col not in df.columns]
  if missing:
    raise ValueError(f"Missing {role} columns in dataset: {missing}")


def assign_classes(df: pd.DataFrame, qoe_column: str, class_mode: str, fixed_thresholds: str):
  scores = df[qoe_column]

  if class_mode == "quartile":
    q1, _, q3 = np.quantile(scores, [0.25, 0.5, 0.75])
    bins = (-np.inf, q1, q3, np.inf)
    print(f"Class mode: quartile (q1={q1:.5f}, q3={q3:.5f})")
  else:
    thresholds = parse_csv_list(fixed_thresholds)
    if len(thresholds) != 2:
      raise ValueError("--fixed-thresholds must provide exactly two values")
    t1, t2 = sorted([float(thresholds[0]), float(thresholds[1])])
    bins = (-np.inf, t1, t2, np.inf)
    print(f"Class mode: fixed (t1={t1:.5f}, t2={t2:.5f})")

  labels = pd.cut(scores, bins=bins, labels=CLASS_NAMES, right=False)
  labels = labels.astype("category")
  labels = labels.cat.set_categories(CLASS_NAMES, ordered=True)
  return labels


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


def run_cv(models, X_train: pd.DataFrame, y_train: pd.Series, cv_folds: int, cv_gap: int):
  cv = TimeSeriesSplit(n_splits=cv_folds, gap=cv_gap)
  rows = []
  for name, model in models.items():
    scores = cross_validate(
      clone(model),
      X_train,
      y_train,
      cv=cv,
      scoring={
        "accuracy": "accuracy",
        "balanced_accuracy": "balanced_accuracy",
        "f1_macro": "f1_macro",
        "precision_macro": "precision_macro",
        "recall_macro": "recall_macro",
      },
      n_jobs=-1,
    )
    rows.append(
      {
        "model": name,
        "cv_acc_mean": float(np.mean(scores["test_accuracy"])),
        "cv_bal_acc_mean": float(np.mean(scores["test_balanced_accuracy"])),
        "cv_f1_macro_mean": float(np.mean(scores["test_f1_macro"])),
        "cv_f1_macro_std": float(np.std(scores["test_f1_macro"])),
        "cv_precision_macro_mean": float(np.mean(scores["test_precision_macro"])),
        "cv_recall_macro_mean": float(np.mean(scores["test_recall_macro"])),
      }
    )

  return pd.DataFrame(rows).sort_values(
    ["cv_f1_macro_mean", "cv_bal_acc_mean"], ascending=False
  ).reset_index(drop=True)


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


def tune_model(model_name: str, model, X_train: pd.DataFrame, y_train: pd.Series, cv_folds: int, cv_gap: int, seed: int, tune_iter: int):
  search = RandomizedSearchCV(
    estimator=clone(model),
    param_distributions=get_search_space(model_name),
    n_iter=tune_iter,
    scoring="f1_macro",
    cv=TimeSeriesSplit(n_splits=cv_folds, gap=cv_gap),
    n_jobs=-1,
    random_state=seed,
    verbose=0,
    refit=True,
  )
  search.fit(X_train, y_train)
  return search.best_estimator_, search.best_score_, search.best_params_


def print_class_distribution(y: pd.Series, title: str):
  counts = y.value_counts(normalize=True).reindex(CLASS_NAMES).fillna(0.0)
  print(title)
  for cls_name in CLASS_NAMES:
    print(f"  {cls_name}: {counts[cls_name]:.3f}")


def time_holdout_split(df: pd.DataFrame, features, target_col: str, time_col: str, test_size: float):
  ordered = df.copy()
  time_values = pd.to_datetime(ordered[time_col], errors="coerce", utc=True)
  if time_values.notna().all():
    ordered = ordered.assign(__time_parsed=time_values).sort_values("__time_parsed").drop(columns=["__time_parsed"])
  else:
    ordered = ordered.sort_values(time_col)

  split_idx = int(len(ordered) * (1.0 - test_size))
  if split_idx <= 0 or split_idx >= len(ordered):
    raise ValueError("Invalid split index. Check --test-size and dataset size")

  train_df = ordered.iloc[:split_idx]
  test_df = ordered.iloc[split_idx:]

  return train_df[features], test_df[features], train_df[target_col], test_df[target_col]

def group_split(df, X, y, group='local'):
    #cols=['local','AP_channel','channel_width','radio','distance_m']
    #cols=['distance_m']
    #for c in cols:
    #    df[c] = df[c].fillna(0).astype(str)
    #df['group']=df[cols].agg(' '.join, axis=1)
    gss = GroupShuffleSplit(
        n_splits=1,
        test_size=0.3,
        random_state=42
    )
    train_idx, test_idx = next(
        gss.split(X, y, groups=df[group])
    )
    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]
    return X_train, X_test, y_train, y_test

def main():
  args = parse_args()
  np.random.seed(args.seed)

  features = parse_csv_list(args.features)
  df = pd.read_csv(args.csv)

  validate_columns(df, [args.qoe_column], "QoE")
  validate_columns(df, features, "feature")
  validate_columns(df, [args.time_column], "time")

  df = df.copy()
  df[args.target_column] = assign_classes(df, args.qoe_column, args.class_mode, args.fixed_thresholds)
  df = df.dropna(subset=features + [args.target_column, args.time_column]).reset_index(drop=True)

  #X_train, X_test, y_train, y_test = time_holdout_split(
  #  df,
  #  features,
  #  args.target_column,
  #  args.time_column,
  #  args.test_size,
  #)
  X = df[features]
  y = df[args.target_column]
  X_train, X_test, y_train, y_test = X_train, X_test, y_train, y_test = group_split(df, X, y)

  print(f"Dataset rows: {len(df)}")
  print(f"Features ({len(features)}): {features}")
  print(f"Split strategy: time-aware ({args.time_column})")
  print(f"CV strategy: TimeSeriesSplit(n_splits={args.cv_folds}, gap={args.cv_gap})")
  print_class_distribution(y_train, "Train class distribution:")
  print_class_distribution(y_test, "Holdout class distribution:")

  models = build_models(args.seed)
  leaderboard = run_cv(models, X_train, y_train, args.cv_folds, args.cv_gap)

  print("\n" + "=" * 110)
  print("CV Leaderboard (sorted by macro-F1)")
  print(leaderboard.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

  top_k = min(args.tune_top_k, len(leaderboard))
  tuned_rows = []
  tuned_models = {}
  print("\n" + "=" * 110)
  print(f"Hyperparameter tuning (top {top_k} models by CV macro-F1)")
  for _, row in leaderboard.head(top_k).iterrows():
    model_name = row["model"]
    tuned_model, tuned_cv_score, tuned_params = tune_model(
      model_name=model_name,
      model=models[model_name],
      X_train=X_train,
      y_train=y_train,
      cv_folds=args.cv_folds,
      cv_gap=args.cv_gap,
      seed=args.seed,
      tune_iter=args.tune_iter,
    )
    tuned_models[model_name] = tuned_model
    tuned_rows.append(
      {
        "model": model_name,
        "tuned_cv_f1_macro": float(tuned_cv_score),
        "best_params": str(tuned_params),
      }
    )
  tuned_df = pd.DataFrame(tuned_rows).sort_values("tuned_cv_f1_macro", ascending=False).reset_index(drop=True)
  print(tuned_df.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

  best_name = tuned_df.iloc[0]["model"]
  best_model = clone(tuned_models[best_name]).fit(X_train, y_train)
  y_pred = best_model.predict(X_test)

  print("\n" + "=" * 110)
  print(f"Best model on CV: {best_name}")
  print("Holdout classification report:")
  print(classification_report(y_test, y_pred, digits=4, labels=CLASS_NAMES, zero_division=0))

  cm = confusion_matrix(y_test, y_pred, labels=CLASS_NAMES, normalize="true")
  cm_df = pd.DataFrame(cm, index=[f"true_{c}" for c in CLASS_NAMES], columns=[f"pred_{c}" for c in CLASS_NAMES])
  print("Holdout confusion matrix (row-normalized):")
  print(cm_df.to_string(float_format=lambda x: f"{x:.4f}"))
  if args.plot_confusion:
    import matplotlib.pyplot as plt

    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CLASS_NAMES)
    disp.plot(cmap=plt.cm.Blues)
    plt.title("Holdout Confusion Matrix (row-normalized)")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
  main()

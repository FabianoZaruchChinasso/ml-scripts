import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler, QuantileTransformer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
import mlflow

mlflow.set_experiment("MLflow Wifi Regressions")

mlflow.autolog(log_models=False)

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml.core.data import SITE_COLUMN, load_datasets
from ml.core.splits import outer_logo_folds

regression = 'speedtest_down_mbps'

DS_CSV = os.environ.get('DS_CSV', 'data/metrics-20260630-out.csv')
df = load_datasets(DS_CSV.split(','), target=regression)

features=["router_expected_throughput_mbps",
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
              "client_opportunity_medium_use"]

int_features = df.select_dtypes(include=['int64', 'int32']).columns
df[int_features] = df[int_features].astype("float64")

dataset_name = ','.join(
    os.path.splitext(os.path.basename(path))[0] for path in DS_CSV.split(',')
)

dataset = mlflow.data.from_pandas(
    df, source=DS_CSV, name=dataset_name, targets=regression
)

print(f"Dataset: {dataset}")

with mlflow.start_run():
        mlflow.log_input(dataset, context="dataset")

# Model configurations
model_configs = [
    {"model_type": "RandomForest", "n_estimators": 100, "max_depth": 10},
    {"model_type": "RandomForest", "n_estimators": 200, "max_depth": 20},
    {"model_type": "ExtraTreesRegressor", "n_estimators": 100, "max_depth": 10},
    {"model_type": "ExtraTreesRegressor", "n_estimators": 200, "max_depth": 20},
    {"model_type": "GradientBoostingRegressor", "n_estimators": 100, "max_depth": 10},
    {"model_type": "GradientBoostingRegressor", "n_estimators": 200, "max_depth": 20},
]

y = df[regression]
X = df[features]
# Single fold for fast experiment iteration; see regression_benchmark.py for the full per-site sweep.
fold = outer_logo_folds(X, y, df[SITE_COLUMN])[0]
X_train, X_test, y_train, y_test = fold.X_train, fold.X_test, fold.y_train, fold.y_test

for i, config in enumerate(model_configs):

    with mlflow.start_run():
        mlflow.log_input(dataset, context="training")
        for path in DS_CSV.split(','):
            mlflow.log_artifact(path, artifact_path="dataset_source")
        mlflow.log_param('test_site', fold.test_site)
        mlflow.log_param('train_sites', ','.join(fold.train_sites))

        if config["model_type"] == "RandomForest":
            model = RandomForestRegressor(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                random_state=42,
            )
            mlflow.log_param("n_estimators", config["n_estimators"])
            mlflow.log_param("max_depth", config["max_depth"])
        elif config["model_type"] == "ExtraTreesRegressor":
            model = ExtraTreesRegressor(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                random_state=42,
            )
            mlflow.log_param("n_estimators", config["n_estimators"])
            mlflow.log_param("max_depth", config["max_depth"])
        elif config["model_type"] == "GradientBoostingRegressor":
            model = GradientBoostingRegressor(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                random_state=42,
            )
            mlflow.log_param("n_estimators", config["n_estimators"])
            mlflow.log_param("max_depth", config["max_depth"])

        history=model.fit(X_train, y_train)
        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            name=config["model_type"],
            serialization_format="skops"
        )
        model_score = model.score(X_test, y_test)
        y_pred=model.predict(X_test)
        score=r2_score(y_test, y_pred)
        mean_error=pow(mean_squared_error(y_test, y_pred),0.5)
        mlflow.log_metric("score", score)
        mlflow.log_metric("Mean error", mean_error)
        print(f"-------------------------------------------------------------")
        print(f"{config["model_type"]} for {regression}: Score={score}, Mean error={mean_error}")
        print(f"Config: {config}")
        print(f"-------------------------------------------------------------")

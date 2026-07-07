import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, recall_score, f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
import mlflow

mlflow.set_experiment("MLflow Wifi Classifiers")

mlflow.autolog(log_models=False)

DS_CSV="data/metrics-20260630-qoe-speed.csv"
df = pd.read_csv(DS_CSV, sep=',', header=0)

int_features = df.select_dtypes(include=['int64', 'int32']).columns
df[int_features] = df[int_features].astype("float64")

qoe='qoe_dw_score'

dataset = mlflow.data.from_pandas(
    df, source=DS_CSV, name=DS_CSV[5:-4], targets=qoe
)

with mlflow.start_run():
    mlflow.log_input(dataset, context="dataset")
    mlflow.log_artifact(DS_CSV, artifact_path="dataset_source")

q1, q2, q3 = np.quantile(df[qoe], [0.25, 0.5, 0.75])

print(f"Quartiles: q25={q1}, q50={q2}, q75={q3}")

df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < q1 else "mid" if x < q3 else "good")

target = "qoe_class"

features=['AP_channel', 'RSSI', 'channel_width', 'client_ID',
       'distance_m', 'download_packet_loss', 'download_retrans',
       'download_tcp_rtt_ms', 'jitter_ms', 'latency_ms', 'link_speed_mbps',
       'local', 'obstacles', 'radio', 'router_expected_throughput_mbps',
       'router_noise', 'router_rx_drop_misc', 'router_rx_duration_us',
       'router_rx_rate_mbps', 'router_signal_avg_dbm', 'router_signal_dbm',
       'router_snr', 'router_tx_duration_us', 'router_tx_failed',
       'router_tx_rate_mbps', 'router_tx_retries', 'signal_level',
       'site_survey_same_channel_aps', 'site_survey_strongest_channel',
       'site_survey_strongest_rssi', 'site_survey_total_aps',
       'speedtest_down_mbps', 'speedtest_up_mbps', 'upload_packet_loss',
       'upload_retrans', 'upload_tcp_rtt_ms']
features=["router_expected_throughput_mbps", "router_noise", "router_rx_drop_misc", "router_rx_duration_us", "router_rx_rate_mbps", "router_signal_avg_dbm", "router_signal_dbm", "router_snr", "router_tx_duration_us", "router_tx_failed", "router_tx_rate_mbps", "router_tx_retries", "router_opportunity_medium_use", "client_opportunity_medium_use"]

encoder = LabelEncoder()

df[target] = encoder.fit_transform(df[target])

print(dict(zip(
    encoder.classes_,
    encoder.transform(encoder.classes_)
)))

encoder = LabelEncoder()

df[target] = encoder.fit_transform(df[target])

print(dict(zip(
    encoder.classes_,
    encoder.transform(encoder.classes_)
)))

X = df[features]
y = df[target]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

model_configs = [
    {"model_type": "RandomForest", "n_estimators": 100, "max_depth": 10},
    {"model_type": "RandomForest", "n_estimators": 200, "max_depth": 20},
    {"model_type": "LogisticRegression", "C": 0.7, "solver": "lbfgs"},
    {"model_type": "LogisticRegression", "C": 0.4, "solver": "saga"},
    {"model_type": "SVM", "kernel": "rbf", "C": 1.0},
    #{"model_type": "SVM", "kernel": "linear", "C": 0.5},
]

for i, config in enumerate(model_configs):
    with mlflow.start_run():
        # Create and train model based on type
        if config["model_type"] == "RandomForest":
            model = RandomForestClassifier(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                random_state=42,
            )
            mlflow.log_param("n_estimators", config["n_estimators"])
            mlflow.log_param("max_depth", config["max_depth"])
        elif config["model_type"] == "LogisticRegression":
            model = LogisticRegression(
                C=config["C"],
                solver=config["solver"],
                random_state=42,
                max_iter=1000,  # Increase iterations for convergence
            )
            mlflow.log_param("C", config["C"])
            mlflow.log_param("solver", config["solver"])
        else:  # SVM
            base_svc = SVC(
                kernel=config["kernel"],
                C=config["C"],
                random_state=42,
            )
            model = CalibratedClassifierCV(estimator=base_svc, ensemble=False)
            mlflow.log_param("kernel", config["kernel"])
            mlflow.log_param("C", config["C"])
        trusted_types = [
            "sklearn.calibration._CalibratedClassifier",
            "sklearn.calibration._SigmoidCalibration"
        ]
        model.fit(X_train, y_train)
        model_info = mlflow.sklearn.log_model(
                    sk_model=model,
                    name=config["model_type"],
                    serialization_format="skops",
                    skops_trusted_types=trusted_types
                )

        y_pred = model.predict(X_test)
        print(classification_report(y_test, y_pred))
        print(f"------------------------ {config["model_type"]} ------------------------")
        print(f"Config: {config}")
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Accuracy: {accuracy}")
        rscore=recall_score(y_test, y_pred, average='macro')
        print(f"Recall: {rscore}")
        f1 = f1_score(y_test, y_pred, average='macro')
        print(f"F1-score: {accuracy}")
        mlflow.log_metric("Accuracy", accuracy)
        mlflow.log_metric("Recall Score", rscore)
        mlflow.log_metric("F1-score", f1)

        if config["model_type"] == "RandomForest":
            importance = pd.DataFrame({
                "feature": features,
                "importance": model.feature_importances_
            })

            print(
                importance.sort_values(
                    by="importance",
                    ascending=False
                )
            )
        print(f"-------------------------------------------------------------------")

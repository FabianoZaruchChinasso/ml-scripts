import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt

DS_CSV="data/metrics-20260630-5g-qoe2.csv"
#DS_CSV="data/metrics-20260630-24g-qoe.csv"
DS_CSV="data/metrics-20260630-qoe.csv"
DS_CSV="data/metrics-20260630-qoe-5g-speed.csv"
DS_CSV="data/metrics-20260630-qoe-speed.csv"
DS_CSV="data/metrics-20260630-qoe-24g-speed.csv"
DS_CSV="data/metrics-20260630-qoe-24g-speed-suppress_empty.csv"
df = pd.read_csv(DS_CSV, sep=',', header=0)

qoe='qoe_dw_score'

q1, q2, q3 = np.quantile(df[qoe], [0.25, 0.5, 0.75])

print(f"Quartiles: q25={q1}, q50={q2}, q75={q3}")

#tsne_df['label']=tsne_df['label'].apply(lambda x: "bad" if x < 0.045 else "poor" if x < 0.17 else "mid" if x < 0.28 else "good")
#df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < 1.03  else "poor" if x < 1.48 else "mid" if x < 1.76 else "good")
# all qoe
#df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < 2.44 else "mid" if x < 49 else "good")
# speed 5g
df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < 0.25 else "mid" if x < 0.74 else "good")
# 5g qoe
#df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < 3.1 else "mid" if x < 31 else "good")
#df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < 22 else "mid" if x < 1397 else "good")
# 2.4g qoe
#df['qoe_class']=df[qoe].apply(lambda x: "bad" if x < 1.3 else "mid" if x < 115 else "good")


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

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    random_state=42
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)
#print(y_test)
#print(y_pred)
print(classification_report(y_test, y_pred))

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

# y_true are the actual labels, y_pred are your model's predictions
cm = confusion_matrix(y_test, y_pred, normalize='true')

# Display the matrix
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=display_labels)
disp.plot(cmap=plt.cm.Blues)
plt.show()
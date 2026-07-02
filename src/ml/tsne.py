import pandas as pd
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

DS_CSV="data/metrics-20260630-qoe-5g-speed.csv"
FEATURE="qoe_dw_score"

# read dataset
df = pd.read_csv(DS_CSV, sep=',', header=0)

# covert time to unix timestamp
#df.iloc[0:,0]=pd.to_datetime(df.iloc[0:, 0], format="%Y-%m-%d %H:%M:%S.%f%z")
#df['timestamp'] = df['timestamp'].apply(lambda x: x.timestamp())

# prepare X and y data
y = df[FEATURE]
#X = df.drop(columns=['_time', FEATURE])
features=["router_expected_throughput_mbps", "router_noise", "router_rx_drop_misc", "router_rx_duration_us", "router_rx_rate_mbps", "router_signal_avg_dbm", "router_signal_dbm", "router_snr", "router_tx_duration_us", "router_tx_failed", "router_tx_rate_mbps", "router_tx_retries", "router_opportunity_medium_use", "client_opportunity_medium_use"]
X=df[features]

# train TSNE
tsne = TSNE(n_components=2, perplexity=30, random_state=42)
X_tsne = tsne.fit_transform(X)

# get TSNE data
tsne_df = pd.DataFrame(X_tsne, columns=['TSNE-1', 'TSNE-2'])

# Inset label according feature rates
tsne_df['qoe_class']=y
#wifi
#tsne_df['label']=tsne_df['label'].apply(lambda x: "bad" if x < 0.045 else "poor" if x < 0.17 else "mid" if x < 0.28 else "good")
#tsne_df['qoe_class']=tsne_df['qoe_class'].apply(lambda x: "bad" if x < 1.03  else "poor" if x < 1.48 else "mid" if x < 1.76 else "good")
#tsne_df['qoe_class']=tsne_df['qoe_class'].apply(lambda x: "bad" if x < 2.44  else "mid" if x < 49 else "good")
#tsne_df['qoe_class']=tsne_df['qoe_class'].apply(lambda x: "bad" if x < 22  else "mid" if x < 1397 else "good")

q1, q2, q3 = np.quantile(df[FEATURE], [0.25, 0.5, 0.75])
tsne_df['qoe_class']=tsne_df['qoe_class'].apply(lambda x: "bad" if x < q1  else "mid" if x < q3 else "good")

print(f"Quartiles: q25={q1}, q50={q2}, q75={q3}")


# Plot TSNE
plt.figure(figsize=(8, 6))
sns.scatterplot(data=tsne_df, x='TSNE-1', y='TSNE-2', hue='qoe_class', palette='tab10')
plt.title('t-SNE Visualization')
plt.show()

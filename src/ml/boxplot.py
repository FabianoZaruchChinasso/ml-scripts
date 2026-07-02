import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

DS_CSV="data/metrics-20260630-5g-qoe.csv"

def plot_box(features, data, title, cut):
    cc=[]
    for f in data.columns:
        cc.append(f[:-cut])
    data.columns=cc
    df_melted = data.melt(var_name='Column', value_name='Value')
    sns.boxplot(x='Column', y='Value', data=df_melted)
    plt.title(title)
    plt.show()

# Read data set
df = pd.read_csv(DS_CSV, parse_dates=True)

# drop not useful columns
df=df.drop(columns=['_time'])

#features=["AP_channel", "RSSI", "channel_width", "client_ID", "distance_m", "download_packet_loss", "download_retrans", "download_tcp_rtt_ms", "jitter_ms", "latency_ms", "link_speed_mbps", "local", "obstacles", "radio", "router_expected_throughput_mbps", "router_noise", "router_rx_drop_misc", "router_rx_duration_us", "router_rx_rate_mbps", "router_signal_avg_dbm", "router_signal_dbm", "router_snr", "router_tx_duration_us", "router_tx_failed", "router_tx_rate_mbps", "router_tx_retries", "signal_level", "site_survey_same_channel_aps", "site_survey_strongest_channel", "site_survey_strongest_rssi", "site_survey_total_aps", "speedtest_down_mbps", "speedtest_up_mbps", "upload_packet_loss", "upload_retrans", "upload_tcp_rtt_ms",  "router_opportunity_medium_use", "client_opportunity_medium_use"]
features=df.columns
plot_box(features, df, "Wifi Metric", 14)
df.columns=features
features = ['qoe_dw_score']
for feature in features:
   df[feature]=pd.to_numeric(df[feature], errors='coerce')
   max=df[feature].max()
   min=df[feature].min()

   sns.boxplot(y=feature,data=df)
   #plt.xticks(np.arange(min, max, (max - min) / 10))
   plt.title(feature)
   plt.show()

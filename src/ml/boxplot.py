import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

DS_CSV="data/metrics-20260630-qoe.csv"
DS_CSV="data/metrics-20260630-qoe-speed-suppress_empty.csv"
DS_CSV="data/metrics-20260630-qoe-speed-suppress_empty.csv"
DS_CSV="data/metrics-local-out2.csv"
DS_CSV="data/metrics-office-20260722-stats-out.csv"

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
#df=df.drop(columns=['_time'])
#df=df.drop(columns=['Timestamp'])

#features=["AP_channel", "RSSI", "channel_width", "client_ID", "distance_m", "download_packet_loss", "download_retrans", "download_tcp_rtt_ms", "jitter_ms", "latency_ms", "link_speed_mbps", "local", "obstacles", "radio", "router_expected_throughput_mbps", "router_noise", "router_rx_drop_misc", "router_rx_duration_us", "router_rx_rate_mbps", "router_signal_avg_dbm", "router_signal_dbm", "router_snr", "router_tx_duration_us", "router_tx_failed", "router_tx_rate_mbps", "router_tx_retries", "signal_level", "site_survey_same_channel_aps", "site_survey_strongest_channel", "site_survey_strongest_rssi", "site_survey_total_aps", "speedtest_down_mbps", "speedtest_up_mbps", "upload_packet_loss", "upload_retrans", "upload_tcp_rtt_ms",  "router_opportunity_medium_use", "client_opportunity_medium_use"]
features=['router_signal',
              'router_noise',
              'router_station_signal',
              'router_bitrate',
              'router_expected_throughput_mbps',
              'router_tx_retry',
              'router_rx_failed',
              'router_rx_drop_misc', 
              'router_rx_duration_us',
              'router_tx_duration_us', 
              'router_rx_rate_mbps',
              'router_tx_rate_mbps',
              'router_opportunity_medium_use', 'Direct_Sender_TP', 'Direct_Receiver_TP', 'Direct_Receiver_Jitter', 'Direct_Receiver_Loss']
features = [  "client_opportunity_medium_use",
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
              "stats_80211_client_ampdu_avg_length",
              "stats_80211_client_ampdu_count",
              "stats_80211_client_ampdu_efficiency_pct",
              "stats_80211_client_ampdu_subframes",
              "stats_80211_client_amsdu_frames",
              #"stats_80211_client_assoc_ap",
              "stats_80211_client_beamforming",
              "stats_80211_client_block_ack_req",
              "stats_80211_client_block_ack_tx",
              "stats_80211_client_cts",
              "stats_80211_client_cts_retransmission",
              "stats_80211_client_data",
              "stats_80211_client_data_retransmission",
              "stats_80211_client_mac_bytes",
              "stats_80211_client_mpdu_bytes",
              "stats_80211_client_msdu_bytes",
              "stats_80211_client_overhead_pct",
              "stats_80211_client_payload_bytes",
              "stats_80211_client_qos_data",
              #"stats_80211_client_raw",
              "stats_80211_client_retry_bytes",
              "stats_80211_client_retry_overhead_pct",
              "stats_80211_client_rts",
              "stats_80211_client_rts_retransmission",
              "stats_80211_client_total_frames",
              "stats_80211_global_ack",
              "stats_80211_global_ampdu_avg_length",
              "stats_80211_global_ampdu_count",
              "stats_80211_global_ampdu_efficiency_pct",
              "stats_80211_global_ampdu_subframes",
              "stats_80211_global_amsdu_frames",
              "stats_80211_global_beamforming_actions",
              "stats_80211_global_beamforming_frames",
              "stats_80211_global_block_ack",
              "stats_80211_global_block_ack_req",
              "stats_80211_global_ctrl_frames",
              "stats_80211_global_cts",
              "stats_80211_global_data_frames",
              "stats_80211_global_data_frames_count",
              "stats_80211_global_data_retry_frames",
              "stats_80211_global_data_retry_pct",
              "stats_80211_global_elapsed_seconds",
              "stats_80211_global_filtered_frames",
              "stats_80211_global_mac_bytes",
              "stats_80211_global_mac_throughput_mbps",
              "stats_80211_global_mgmt_frames",
              "stats_80211_global_mpdu_bytes",
              "stats_80211_global_msdu_bytes",
              "stats_80211_global_msdu_count",
              "stats_80211_global_ndp_announce",
              "stats_80211_global_overhead_pct",
              "stats_80211_global_payload_bytes",
              "stats_80211_global_payload_throughput_mbps",
              "stats_80211_global_qos_data",
              "stats_80211_global_retry_bytes",
              "stats_80211_global_retry_frames",
              "stats_80211_global_retry_frames_pct",
              "stats_80211_global_retry_overhead_pct",
              "stats_80211_global_rts",
              "stats_80211_global_rts_retransmission",
              #"stats_80211_global_timestamp",
              "stats_80211_global_total_frames",
              "stats_80211_per_ap_count",
              "stats_80211_per_client_count",
              #"stats_80211_raw"
          ]
for feature in features:
   df[feature]=pd.to_numeric(df[feature], errors='coerce')
   max=df[feature].max()
   min=df[feature].min()

   sns.boxplot(y=feature,data=df)
   #plt.xticks(np.arange(min, max, (max - min) / 10))
   plt.title(feature)
   plt.show()

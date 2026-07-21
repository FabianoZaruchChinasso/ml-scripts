import os
from influxdb_client import InfluxDBClient
import json

# You can generate a Token from the "Tokens Tab" in the UI
token = "<INFLUX_TOKEN>"
org = "wifi_research"
bucket = "wifi_qoe"
token = os.environ.get("INFLUXDB_TOKEN")
# token = "ls2cemeUaF59cW9cgFCUMrllxft48uwvIU8fRBBU-5DXUwyuCFPlg9e_nhvumjBA2kzT3fjx35OkqgN2FNYeLQ=="


with InfluxDBClient(url="http://10.59.255.71:8086", token=token, org=org) as client:
    query = """option v = {timeRangeStart: 2026-07-13T16:55:00.000Z, timeRangeStop: 2026-07-13T16:56:00Z}

from(bucket: "wifi_qoe")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "wifi_qoe")
|> filter(
fn: (r) =>
r["_field"] == "AP_channel" or r["_field"] == "RSSI" or r["_field"] == "channel_width" or
r["_field"] == "client_mode" or r["_field"] == "distance_m" or r["_field"] == "download_packet_loss" or
r["_field"] == "download_retrans" or r["_field"] == "download_tcp_rtt_ms" or r["_field"] == "jitter_ms" or
r["_field"] == "latency_ms" or r["_field"] == "link_speed_mbps" or r["_field"] == "obstacles" or
r["_field"] == "router_connected_time_sec" or r["_field"] == "router_expected_throughput_mbps" or
r["_field"] == "router_noise" or r["_field"] == "router_rx_bytes" or r["_field"] == "router_rx_drop_misc" or
r["_field"] == "router_rx_duration_us" or r["_field"] == "router_rx_packets" or r["_field"] == "router_rx_rate_mbps" or
r["_field"] == "router_signal_avg_dbm" or r["_field"] == "router_signal_dbm" or r["_field"] == "router_site_survey_ap" or
r["_field"] == "router_snr" or r["_field"] == "router_tx_bytes" or r["_field"] == "router_tx_duration_us" or
r["_field"] == "router_tx_failed" or r["_field"] == "router_tx_packets" or r["_field"] == "router_tx_rate_mbps" or
r["_field"] == "router_tx_retries" or r["_field"] == "signal_level" or r["_field"] == "site_survey_client" or
r["_field"] == "site_survey_same_channel_aps" or r["_field"] == "site_survey_strongest_channel" or
r["_field"] == "site_survey_strongest_rssi" or r["_field"] == "site_survey_strongest_ssid" or
r["_field"] == "site_survey_total_aps" or r["_field"] == "speedtest_down_mbps" or r["_field"] == "speedtest_up_mbps" or
r["_field"] == "stats_80211_client_ampdu_avg_length" or r["_field"] == "stats_80211_client_ampdu_count" or
r["_field"] == "stats_80211_client_ampdu_efficiency_pct" or r["_field"] == "stats_80211_client_ampdu_subframes" or
r["_field"] == "stats_80211_client_amsdu_frames" or r["_field"] == "stats_80211_client_assoc_ap" or
r["_field"] == "stats_80211_client_beamforming" or r["_field"] == "stats_80211_client_block_ack_req" or
r["_field"] == "stats_80211_client_block_ack_tx" or r["_field"] == "stats_80211_client_cts" or
r["_field"] == "stats_80211_client_cts_retransmission" or r["_field"] == "stats_80211_client_data" or
r["_field"] == "stats_80211_client_data_retransmission" or r["_field"] == "stats_80211_client_mac_bytes" or
r["_field"] == "stats_80211_client_mpdu_bytes" or r["_field"] == "stats_80211_client_msdu_bytes" or
r["_field"] == "stats_80211_client_overhead_pct" or r["_field"] == "stats_80211_client_payload_bytes" or
r["_field"] == "stats_80211_client_qos_data" or r["_field"] == "stats_80211_client_raw" or
r["_field"] == "stats_80211_client_retry_bytes" or r["_field"] == "stats_80211_client_retry_overhead_pct" or
r["_field"] == "stats_80211_client_rts" or r["_field"] == "stats_80211_client_rts_retransmission" or
r["_field"] == "stats_80211_client_total_frames" or r["_field"] == "stats_80211_global_ack" or
r["_field"] == "stats_80211_global_ampdu_avg_length" or r["_field"] == "stats_80211_global_ampdu_count" or
r["_field"] == "stats_80211_global_ampdu_efficiency_pct" or r["_field"] == "stats_80211_global_ampdu_subframes" or
r["_field"] == "stats_80211_global_amsdu_frames" or r["_field"] == "stats_80211_global_beamforming_actions" or
r["_field"] == "stats_80211_global_beamforming_frames" or r["_field"] == "stats_80211_global_block_ack" or
r["_field"] == "stats_80211_global_block_ack_req" or r["_field"] == "stats_80211_global_ctrl_frames" or
r["_field"] == "stats_80211_global_cts" or r["_field"] == "stats_80211_global_data_frames" or
r["_field"] == "stats_80211_global_data_frames_count" or r["_field"] == "stats_80211_global_data_retry_frames" or
r["_field"] == "stats_80211_global_data_retry_pct" or r["_field"] == "stats_80211_global_elapsed_seconds" or
r["_field"] == "stats_80211_global_filtered_frames" or r["_field"] == "stats_80211_global_mac_bytes" or
r["_field"] == "stats_80211_global_mac_throughput_mbps" or r["_field"] == "stats_80211_global_mgmt_frames" or
r["_field"] == "stats_80211_global_mpdu_bytes" or r["_field"] == "stats_80211_global_msdu_bytes" or
r["_field"] == "stats_80211_global_msdu_count" or r["_field"] == "stats_80211_global_ndp_announce" or
r["_field"] == "stats_80211_global_overhead_pct" or r["_field"] == "stats_80211_global_payload_bytes" or
r["_field"] == "stats_80211_global_payload_throughput_mbps" or r["_field"] == "stats_80211_global_qos_data" or
r["_field"] == "stats_80211_global_retry_bytes" or r["_field"] == "stats_80211_global_retry_frames" or
r["_field"] == "stats_80211_global_retry_frames_pct" or r["_field"] == "stats_80211_global_retry_overhead_pct" or
r["_field"] == "stats_80211_global_rts" or r["_field"] == "stats_80211_global_rts_retransmission" or
r["_field"] == "stats_80211_global_timestamp" or r["_field"] == "stats_80211_global_total_frames" or
r["_field"] == "stats_80211_per_ap_count" or r["_field"] == "stats_80211_per_client_count" or
r["_field"] == "stats_80211_raw" or r["_field"] == "stored_at" or r["_field"] == "upload_packet_loss" or
r["_field"] == "upload_retrans" or r["_field"] == "upload_tcp_rtt_ms",
)
"""
    tables = client.query_api().query(query, org=org)
    print(f"Lenght: {len(tables)}")
    for table in tables:
        for record in table.records:
            #print(record)
            row_data = record.values
            print(f'{row_data.get("_time")} - {row_data.get("_field")}')
            #json=json.loads(record)

import os
import csv
import sys
import json
import argparse
import io
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
from urllib3.exceptions import ReadTimeoutError

channels_24g = { 1 : 2412, 2 : 2417, 3 : 2422, 4 : 2427, 5 : 2432, 6 : 2437, 7 : 2442, 8 : 2447, 9 : 2452, 10 : 2457, 11 : 2462, 12 : 2467, 13 : 2472 }
channels_5g = { 32:5160, 36:5180, 40:5200, 44:5220, 48:5240, 52:5260, 56:5280, 60:5300, 64:5320, 68:5340, 72:5360, 76:5380, 80:5400, 84:5420, 88:5440, 92:5460, 96:5480, 100:5500, 104:5520, 108:5540, 112:5560, 116:5580, 120:5600, 124:5620, 128:5640, 132:5660, 136:5680, 140:5700, 144:5720, 149:5745, 153:5765, 157:5785, 161:5805, 165:5825, 169:5845, 173:5865, 177:5885 }


def main():
    parser = argparse.ArgumentParser(description="Query InfluxDB in chunks and output a wide table.")
    parser.add_argument("-o", "--output", help="Path to the file to save the output (CSV format). If not provided, prints to stdout.")
    parser.add_argument("-s", "--start", default="2026-06-01T23:00:00Z", help="Start time in ISO 8601 format (e.g., 2026-06-01T23:00:00Z)")
    parser.add_argument("-e", "--end", default="2026-06-01T23:05:00Z", help="End time in ISO 8601 format (e.g., 2026-06-01T23:05:00Z)")
    parser.add_argument("-u", "--url", default="http://10.59.255.71:8086", help="InfluxDB server URL")
    parser.add_argument("-r", "--org", default="wifi_research", help="InfluxDB organization")
    parser.add_argument("-b", "--bucket", default="wifi_qoe", help="InfluxDB bucket")
    parser.add_argument("--checkpoint-every", type=int, default=1, help="Write the output file after every N successful chunks.")
    parser.add_argument("--progress-log", help="Optional file to record the last successful chunk end timestamp.")
    parser.add_argument("--debug-large-fields", action="store_true", help="On CSV parse failure, re-run the chunk as raw CSV and report the largest field.")
    args = parser.parse_args()

    # InfluxDB connection details
    url = args.url
    org = args.org
    bucket = args.bucket
    
    token = os.environ.get("INFLUXDB_TOKEN")
    if not token:
        print("Error: INFLUXDB_TOKEN environment variable is not set or empty.", file=sys.stderr)
        sys.exit(1)

    # Parse start and end times
    try:
        start_dt = datetime.fromisoformat(args.start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(args.end.replace('Z', '+00:00'))
    except ValueError as e:
        print(f"Error parsing date: {e}")
        return

    all_records = []
    all_columns = set()

    csv.field_size_limit(sys.maxsize)

    if args.checkpoint_every < 1:
        print("Error: --checkpoint-every must be at least 1.", file=sys.stderr)
        sys.exit(1)

    def normalize_time_value(value):
        if isinstance(value, datetime):
            return value.isoformat().replace('+00:00', 'Z')
        if value is None:
            return ""
        return str(value)

    def load_existing_output(output_path):
        records = []
        columns = set()

        if not output_path or not os.path.exists(output_path):
            return records, columns

        with open(output_path, mode='r', newline='', encoding='utf-8') as input_file:
            reader = csv.DictReader(input_file)
            for row in reader:
                records.append(row)
                columns.update(row.keys())

        print(f"Loaded {len(records)} existing rows from {output_path}", file=sys.stderr)
        return records, columns

    def load_progress_log(progress_log_path):
        if not progress_log_path or not os.path.exists(progress_log_path):
            return None, None, None

        values = {}
        with open(progress_log_path, mode='r', encoding='utf-8') as progress_file:
            for line in progress_file:
                line = line.strip()
                if not line or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()

        last_successful_end = values.get('last_successful_end')
        saved_rows = int(values['saved_rows']) if values.get('saved_rows', '').isdigit() else None
        saved_chunks = int(values['saved_chunks']) if values.get('saved_chunks', '').isdigit() else None
        return last_successful_end, saved_rows, saved_chunks

    def save_output_records(records, columns, output_path):
        if not output_path:
            return

        excluded = ['result', 'table', '_start', '_stop', '_measurement', 'router_site_survey_ap', 'site_survey_client']
        clean_columns = [c for c in columns if c not in excluded]

        ordered_headers = []
        if '_time' in clean_columns:
            ordered_headers.append('_time')
            clean_columns = [c for c in clean_columns if c != '_time']

        ordered_headers.extend(sorted(clean_columns))

        records.sort(key=lambda x: normalize_time_value(x.get('_time')))

        with open(output_path, mode='w', newline='', encoding='utf-8') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=ordered_headers)
            writer.writeheader()
            for row in records:
                writer.writerow({k: row.get(k, "") for k in ordered_headers})

        print(f"Saved {len(records)} rows to {output_path}", file=sys.stderr)

    def save_progress_log(progress_log_path, last_successful_end, saved_rows, saved_chunks):
        if not progress_log_path:
            return

        with open(progress_log_path, mode='w', encoding='utf-8') as progress_file:
            progress_file.write(f"last_successful_end={last_successful_end}\n")
            progress_file.write(f"saved_rows={saved_rows}\n")
            progress_file.write(f"saved_chunks={saved_chunks}\n")

        print(f"Progress updated in {progress_log_path}: {last_successful_end}", file=sys.stderr)

    def query_with_retries(query, org_name, retries=3):
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                return client.query_api().query(query, org=org_name)
            except (TimeoutError, ReadTimeoutError) as e:
                last_error = e
                print(f"Timeout on query attempt {attempt}/{retries}: {e}", file=sys.stderr)
                if attempt < retries:
                    continue
                raise
        if last_error:
            raise last_error

    def debug_largest_field(query, start_str, end_str):
        raw_csv = client.query_api().query_raw(query, org=org)
        reader = csv.reader(io.StringIO(raw_csv))

        header = None
        for row in reader:
            if row and not row[0].startswith('#'):
                header = row
                break

        if not header:
            print(f"No CSV header returned for chunk {start_str} to {end_str}.", file=sys.stderr)
            return

        max_len = -1
        max_row = None
        max_col = None
        max_value = None

        for row_num, row in enumerate(reader, start=2):
            if not row or row[0].startswith('#'):
                continue

            for idx, value in enumerate(row):
                if idx >= len(header):
                    continue
                value_len = len(value)
                if value_len > max_len:
                    max_len = value_len
                    max_row = row_num
                    max_col = header[idx]
                    max_value = value

        print(
            f"Largest field in chunk {start_str} to {end_str}: row={max_row}, column={max_col}, length={max_len}",
            file=sys.stderr,
        )
        if max_value is not None:
            print(f"Field preview: {max_value[:500]}", file=sys.stderr)

    last_successful_end = args.start

    if args.output and args.progress_log and os.path.exists(args.output):
        all_records, all_columns = load_existing_output(args.output)
        progress_end, saved_rows, saved_chunks = load_progress_log(args.progress_log)
        if progress_end:
            try:
                start_dt = datetime.fromisoformat(progress_end.replace('Z', '+00:00'))
                last_successful_end = progress_end
                print(f"Resuming from {progress_end}", file=sys.stderr)
            except ValueError:
                print(f"Warning: could not parse progress log timestamp '{progress_end}'. Starting from --start.", file=sys.stderr)

        completed_chunks = saved_chunks or 0
    else:
        completed_chunks = 0

    with InfluxDBClient(url=url, token=token, org=org) as client:
        current_start = start_dt
        while current_start < end_dt:
            current_end = min(current_start + timedelta(minutes=5), end_dt)
            
            # Convert back to ISO string for Flux
            start_str = current_start.isoformat().replace('+00:00', 'Z')
            end_str = current_end.isoformat().replace('+00:00', 'Z')
            
            print(f"Fetching chunk: {start_str} to {end_str}...", file=sys.stderr)

            query = f"""
from(bucket: "{bucket}")
|> range(start: {start_str}, stop: {end_str})
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
|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
"""
            try:
                tables = query_with_retries(query, org)
            except csv.Error as e:
                print(f"CSV parse error for chunk {start_str} to {end_str}: {e}", file=sys.stderr)
                save_output_records(all_records, all_columns, args.output)
                if args.debug_large_fields:
                    debug_largest_field(query, start_str, end_str)
                raise
            except (TimeoutError, ReadTimeoutError) as e:
                print(f"Timeout error for chunk {start_str} to {end_str}: {e}", file=sys.stderr)
                save_output_records(all_records, all_columns, args.output)
                save_progress_log(args.progress_log, last_successful_end, len(all_records), completed_chunks)
                raise
            
            for table in tables:
                for record in table.records:
                    row_data = record.values
                    row_data["_time"] = normalize_time_value(row_data.get("_time"))
                    
                    # Calculate new features representing medium usage opportunity
                    router_opp = 0
                    client_opp = 0
                    
                    channel_val = row_data.get("AP_channel")
                    if channel_val is not None:
                        try:
                            channel = int(float(channel_val))
                            radio = row_data.get("radio")
                            ch_map = channels_5g if radio == '5ghz' else channels_24g
                            
                            if channel in ch_map:
                                target_freq = ch_map[channel]
                                
                                # Process router_site_survey_ap
                                router_survey = row_data.get("router_site_survey_ap")
                                if router_survey:
                                    try:
                                        neighbors = json.loads(router_survey)
                                        for n in neighbors:
                                            if n.get("freq_mhz") == target_freq:
                                                router_opp += 1
                                    except Exception:
                                        pass
                                        
                                # Process site_survey_client
                                client_survey = row_data.get("site_survey_client")
                                if client_survey:
                                    try:
                                        neighbors = json.loads(client_survey)
                                        for n in neighbors:
                                            if n.get("frequency") == target_freq:
                                                client_opp += 1
                                    except Exception:
                                        pass
                        except (ValueError, TypeError):
                            pass
                    
                    row_data["router_opportunity_medium_use"] = router_opp
                    row_data["client_opportunity_medium_use"] = client_opp
                    
                    all_records.append(row_data)
                    all_columns.update(row_data.keys())

            completed_chunks += 1
            last_successful_end = end_str
            if args.output and (completed_chunks % args.checkpoint_every == 0):
                save_output_records(all_records, all_columns, args.output)
                save_progress_log(args.progress_log, last_successful_end, len(all_records), completed_chunks)
            
            current_start = current_end

    if not all_records:
        print("No records found.")
        return

    if args.output:
        save_output_records(all_records, all_columns, args.output)
        save_progress_log(args.progress_log, last_successful_end, len(all_records), completed_chunks)
        print(f"Final output checkpointed to {args.output}", file=sys.stderr)
        return

    excluded = ['result', 'table', '_start', '_stop', '_measurement', 'router_site_survey_ap', 'site_survey_client']
    clean_columns = [c for c in all_columns if c not in excluded]

    ordered_headers = []
    if '_time' in clean_columns:
        ordered_headers.append('_time')
        clean_columns.remove('_time')

    ordered_headers.extend(sorted(clean_columns))

    writer = csv.DictWriter(sys.stdout, fieldnames=ordered_headers)
    writer.writeheader()
    for row in all_records:
        writer.writerow({k: row.get(k, "") for k in ordered_headers})

if __name__ == "__main__":
    main()

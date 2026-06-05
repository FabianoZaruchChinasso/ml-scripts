import os
import csv
import sys
import argparse
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient

def main():
    parser = argparse.ArgumentParser(description="Query InfluxDB in chunks and output a wide table.")
    parser.add_argument("-o", "--output", help="Path to the file to save the output (CSV format). If not provided, prints to stdout.")
    parser.add_argument("-s", "--start", default="2026-06-01T23:00:00Z", help="Start time in ISO 8601 format (e.g., 2026-06-01T23:00:00Z)")
    parser.add_argument("-e", "--end", default="2026-06-01T23:05:00Z", help="End time in ISO 8601 format (e.g., 2026-06-01T23:05:00Z)")
    parser.add_argument("-u", "--url", default="http://10.59.255.71:8086", help="InfluxDB server URL")
    parser.add_argument("-r", "--org", default="wifi_research", help="InfluxDB organization")
    parser.add_argument("-b", "--bucket", default="wifi_qoe", help="InfluxDB bucket")
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
r["_field"] == "AP_channel" or r["_field"] == "RSSI" or r["_field"] == "client_mode"
or
r["_field"] == "channel_width" or r["_field"] == "distance_m" or r["_field"]
==
"download_packet_loss" or r["_field"] == "download_retrans" or r["_field"]
==
"download_tcp_rtt_ms" or r["_field"] == "jitter_ms" or r["_field"] == "latency_ms"
or
r["_field"] == "link_speed_mbps" or r["_field"] == "obstacles" or r["_field"]
==
"signal_level" or r["_field"] == "stored_at" or r["_field"] == "upload_packet_loss"
or
r["_field"] == "upload_retrans" or r["_field"] == "upload_tcp_rtt_ms"
or
r["_field"] == "router_connected_time_sec" or r["_field"]
==
"router_expected_throughput_mbps" or r["_field"] == "router_noise" or r["_field"]
==
"router_rx_bytes" or r["_field"] == "router_rx_drop_misc" or r["_field"]
==
"router_rx_duration_us" or r["_field"] == "router_rx_packets" or r["_field"]
==
"router_tx_duration_us" or r["_field"] == "router_tx_bytes" or r["_field"]
==
"router_snr" or r["_field"]
==
"router_signal_dbm" or r["_field"] == "router_rx_rate_mbps" or r["_field"]
==
"router_tx_failed" or r["_field"] == "router_tx_retries" or r["_field"]
==
"router_tx_rate_mbps" or r["_field"] == "router_tx_packets" or r["_field"]
==
"router_signal_avg_dbm" or r["_field"] == "speedtest_down_mbps" or r["_field"]
==
"speedtest_up_mbps" or r["_field"] == "site_survey_same_channel_aps"
or
r["_field"] == "site_survey_strongest_channel" or r["_field"]
==
"site_survey_strongest_rssi" or r["_field"] == "site_survey_strongest_ssid"
or
r["_field"] == "site_survey_total_aps",
)
|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
"""
            tables = client.query_api().query(query, org=org)
            
            for table in tables:
                for record in table.records:
                    row_data = record.values
                    all_records.append(row_data)
                    all_columns.update(row_data.keys())
            
            current_start = current_end

    if not all_records:
        print("No records found.")
        return

    # Exclude internal columns and the specifically requested _measurement
    excluded = ['result', 'table', '_start', '_stop', '_measurement']
    clean_columns = [c for c in all_columns if c not in excluded]
    
    # Ensure _time is the first column
    ordered_headers = []
    if '_time' in clean_columns:
        ordered_headers.append('_time')
        clean_columns.remove('_time')
    
    # Add the remaining columns (pivoted fields and tags) sorted alphabetically
    ordered_headers.extend(sorted(clean_columns))
    
    # Determine output destination
    output_file = None
    try:
        if args.output:
            output_file = open(args.output, mode='w', newline='', encoding='utf-8')
            out_stream = output_file
        else:
            out_stream = sys.stdout

        # Sort all records by time to ensure chronological order across chunks
        all_records.sort(key=lambda x: x.get('_time'))

        writer = csv.DictWriter(out_stream, fieldnames=ordered_headers)
        writer.writeheader()
        for row in all_records:
            writer.writerow({k: row.get(k, "") for k in ordered_headers})
        
        if args.output:
            print(f"Dataset consolidated and saved to {args.output}")

    finally:
        if output_file:
            output_file.close()

if __name__ == "__main__":
    main()

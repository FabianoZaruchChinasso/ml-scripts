import os
from influxdb_client import InfluxDBClient
import sys
import json
import argparse
from datetime import datetime, timedelta

# You can generate a Token from the "Tokens Tab" in the UI
token = "<INFLUX_TOKEN>"
org = "wifi_research"
bucket = "wifi_qoe"
token = os.environ.get("INFLUXDB_TOKEN")
# token = "ls2cemeUaF59cW9cgFCUMrllxft48uwvIU8fRBBU-5DXUwyuCFPlg9e_nhvumjBA2kzT3fjx35OkqgN2FNYeLQ=="

channels_24g = { 1 : 2412, 2 : 2417, 3 : 2422, 4 : 2427, 5 : 2432, 6 : 2437, 7 : 2442, 8 : 2447, 9 : 2452, 10 : 2457, 11 : 2462, 12 : 2467, 13 : 2472 }
channels_5g = { 32:5160, 36:5180, 40:5200, 44:5220, 48:5240, 52:5260, 56:5280, 60:5300, 64:5320, 68:5340, 72:5360, 76:5380, 80:5400, 84:5420, 88:5440, 92:5460, 96:5480, 100:5500, 104:5520, 108:5540, 112:5560, 116:5580, 120:5600, 124:5620, 128:5640, 132:5660, 136:5680, 140:5700, 144:5720, 149:5745, 153:5765, 157:5785, 161:5805, 165:5825, 169:5845, 173:5865, 177:5885 }

def main():
    parser = argparse.ArgumentParser(description="Query InfluxDB in chunks and output a wide table.")
    parser.add_argument("-s", "--start", default="2026-06-01T23:00:00Z", help="Start time in ISO 8601 format (e.g., 2026-06-01T23:00:00Z)")
    parser.add_argument("-e", "--end", default="2026-06-01T23:05:00Z", help="End time in ISO 8601 format (e.g., 2026-06-01T23:05:00Z)")
    args = parser.parse_args()

    # Parse start and end times
    try:
        start_dt = datetime.fromisoformat(args.start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(args.end.replace('Z', '+00:00'))
    except ValueError as e:
        print(f"Error parsing date: {e}")
        return

    with InfluxDBClient(url="http://10.59.255.71:8086", token=token, org=org) as client:
        current_start = start_dt
        while current_start < end_dt:
            current_end = min(current_start + timedelta(minutes=5), end_dt)
            
            # Convert back to ISO string for Flux
            start_str = current_start.isoformat().replace('+00:00', 'Z')
            end_str = current_end.isoformat().replace('+00:00', 'Z')
            
            print(f"Fetching chunk: {start_str} to {end_str}...", file=sys.stderr)
            query = f"""
    from(bucket: "wifi_qoe")
    |> range(start: {start_str}, stop: {end_str})
    |> filter(fn: (r) => r["_measurement"] == "wifi_qoe")
    |> filter(
    fn: (r) =>
    r["_field"] == "AP_channel" or
    r["_field"] == "router_site_survey_ap" or 
    r["_field"] == "site_survey_client",
    )
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
            tables = client.query_api().query(query, org=org)
            #print(tables)
            for table in tables:
                #print(table)
                for record in table.records:
                    print(record)
                    row_data = record.values
                    channel_val = row_data.get("AP_channel")
                    if channel_val is not None:
                        channel = int(float(channel_val))
                        radio = row_data.get("radio")
                        ch_map = channels_5g if radio == '5ghz' else channels_24g
                        print(f"=======> Channel {channel}")
                    router_survey = row_data.get("router_site_survey_ap")
                    if router_survey:
                        router_medium_contention = 0
                        found = None
                        #print(record["_value"])
                        real_v = json.loads(router_survey)
                        for v in real_v:
                            #print(v)
                            if v["freq_mhz"] == ch_map[channel]:
                                router_medium_contention += 1
                                found = real_v
                        if router_medium_contention:
                            print(f"*********** Router contention: x {router_medium_contention} ******************")
                            #print(found)
                        else:
                            print("*****************************************************************")
                    client_survey = row_data.get("site_survey_client")
                    if client_survey:
                        client_medion_contention = 0
                        found = None
                        #print(record["_value"])
                        real_v = json.loads(client_survey)
                        for v in real_v:
                            #print(v)
                            if v["frequency"] == ch_map[channel]:
                                client_medion_contention += 1
                                found = real_v
                        if client_medion_contention:
                            print(f"*********** Client contention: x {client_medion_contention} ******************")
                            #print(found)
                        else:
                            print("****************************************************************")
            current_start = current_end


if __name__ == "__main__":
    main()
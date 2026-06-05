import os
from influxdb_client import InfluxDBClient

# You can generate a Token from the "Tokens Tab" in the UI
token = "<INFLUX_TOKEN>"
org = "wifi_research"
bucket = "wifi_qoe"
token = os.environ.get("INFLUXDB_TOKEN")
# token = "ls2cemeUaF59cW9cgFCUMrllxft48uwvIU8fRBBU-5DXUwyuCFPlg9e_nhvumjBA2kzT3fjx35OkqgN2FNYeLQ=="


with InfluxDBClient(url="http://10.59.255.71:8086", token=token, org=org) as client:
    query = """option v = {timeRangeStart: 2026-06-01T23:00:00.078Z, timeRangeStop: 2026-06-01T23:05:00Z}

from(bucket: "wifi_qoe")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["_measurement"] == "wifi_qoe")
|> filter(
fn: (r) =>
r["_field"] == "router_site_survey_ap",
)
"""
    tables = client.query_api().query(query, org=org)
    for table in tables:
        for record in table.records:
            print(record)

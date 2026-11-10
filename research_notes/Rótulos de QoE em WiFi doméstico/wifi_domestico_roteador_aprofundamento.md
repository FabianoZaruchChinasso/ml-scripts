# Deepening: router-side (TR-069/TR-181) data for home Wi-Fi QoE. Which parameters, which collection mechanisms, and how the project should proceed

Access notes (read before using these notes):
- TR-181 facts come from the machine-readable Broadband Forum data model files, Device:2.21, read directly in this session. Files: `tr-181-2-21-0-cwmp-full.xml` (TR-069/CWMP variant) from [BroadbandForum/cwmp-data-models](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml) and `tr-181-2-21-0-usp-full.xml` (TR-369/USP variant) from [BroadbandForum/usp-data-models](https://github.com/BroadbandForum/usp-data-models/blob/master/tr-181-2-21-0-usp-full.xml). I parsed the XML with a script. "Introduced in" versions are the `version` attributes in the **CWMP** file. The USP file starts at 2.12, so anything older shows as "2.12" there, and I did not use those values. I did not open the HTML rendering at usp-data-models.broadband-forum.org.
- Version dates are the dates when each `tr-181-2-X-0-cwmp-full.xml` file was first committed to GitHub (via the GitHub API). They are **not** official publication dates: 2.12 = 2018-02, 2.13 = 2019-09, 2.14 = 2020-11, 2.15 = 2022-01, 2.16 = 2023-06, 2.17 = 2024-01, 2.18 = 2024-07, 2.19 = 2025-04, 2.20 = 2025-11, 2.21 = 2026-06. Versions before 2.12 are not dated here.
- TR-398 Issue 4 (September 2026): full PDF read (text extracted) from [broadband-forum.org/pdfs/tr-398-4-0-0.pdf](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf).
- da Hora et al. INFOCOM 2018 and the 2017 thesis: **still not read in full.** Routes tried this session:
  - HAL `hal-01676921/document`, the HAL thesis `tel-01670997` (incl. `/file/2017PA066599.pdf`) and hal.sorbonne-universite.fr all return the same 12.5 kB HTML bot-challenge page.
  - core.ac.uk/download/146072036.pdf returns 403 (curl and WebFetch).
  - Wayback snapshots exist (archive.org availability API: [INFOCOM PDF snapshot 2021-07-31](http://web.archive.org/web/20210731070144/https://hal.inria.fr/hal-01676921/document), [thesis snapshot 2022-08-05](http://web.archive.org/web/20220805005205/https://tel.archives-ouvertes.fr/tel-01670997/document)), but downloads timed out at 280 s, and WebFetch cannot reach web.archive.org from here.
  - arXiv: no preprint found.
  - Semantic Scholar lists only the HAL copy as open access (citationCount = 14) ([S2 API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/INFOCOM.2018.8486335?fields=title,openAccessPdf,externalIds,citationCount)).
  - A human with a browser can open the Wayback links above.
- Morshedi & Noll, Sensors 2021: full text read (PMC).
- Pefkianakis et al. INFOCOM 2015 ("The Gateway View"): full text read (PDF mirror).
- Sharma, Feamster, Richardson IMC 2024: **not read** (ACM PDF returned 403). Only search-snippet facts, flagged.
- Plume QoE white paper: only the Wi-Fi NOW news item was read. The white paper is behind a login.
- QA Cafe Bulk Data article: read.

---

## 1. Which TR-181 Device:2 parameters exist for Wi-Fi radio/AP/associated-device statistics, and in which version did each appear?

### Takeaway
TR-181 has two parallel Wi-Fi branches. The **legacy branch** (`Device.WiFi.Radio/SSID/AccessPoint.{i}.AssociatedDevice`, mostly from 2.0 to 2.8) gives per-station last-frame PHY rate, RSSI, a "retransmissions in the last 100 packets" figure, and cumulative byte/packet/retry counters. It has **no channel-utilization or medium-busy parameter at all.** The **EasyMesh/Wi-Fi Data Elements branch** (`Device.WiFi.DataElements.*`, from 2.13, 2019) adds four things a WiSe-style capacity estimate needs: total channel utilization, utilization split into own-transmit, own-BSS-receive and other-BSS-receive, per-station airtime, and an AP-side "estimated MAC throughput if 100% airtime were available" (`EstMACDataRateDownlink/Uplink`). Whether a deployed router has the DataElements branch depends on the firmware. It is optional, and nothing in the data model guarantees it.

### Cited Findings
**Legacy per-station table `Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.` (object v2.0)** — all from [cwmp-full 2.21 XML](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- `LastDataDownlinkRate` / `LastDataUplinkRate` (v2.0, kbps): "the data transmit rate ... that was most recently used for transmission from the access point to the associated device". This is the **last frame's** rate, not an average.
- `SignalStrength` (v2.0, int dBm): uplink signal "as an average of the last 100 packets received from the device".
- `Retransmissions` (v2.0, packets): "the number of packets that had to be re-transmitted, from the last 100 packets sent to the associated device. Multiple re-transmissions of the same packet count as one." In effect a retry percentage over the last 100 packets.
- `Active` (v2.0, boolean): "The ability to list inactive nodes is OPTIONAL ... The length of time an inactive node remains listed in this table is a local matter to the CPE."
- `OperatingStandard` (v2.10). `AssociationTime` (v2.12, dateTime UTC, "when the device was associated"). `Noise` (v2.12, dBm, last 100 packets, ANPI).
- `SNR` (v2.17, dB), `MaxSupportedDataDownlinkRate` / `MaxSupportedDataUplinkRate` (v2.17, kbps), `MaxSupportedBandwidth` (v2.17). `Type` and `SetStaATF` (v2.14).
- Sub-object `.Stats.`:
  - `BytesSent`, `BytesReceived`, `PacketsSent`, `PacketsReceived`, `ErrorsSent`, `RetransCount`, `FailedRetransCount`, `RetryCount`, `MultipleRetryCount` (v2.8).
  - `ErrorsReceived` (v2.14).
  - `RetransCount` counts every retransmission ("two retransmissions of the same packet results in this counter incrementing by two").

**Radio `Device.WiFi.Radio.{i}.` and `.Stats.`** — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- `Stats` Bytes/Packets/Errors/Discard counters (v2.0). `PLCPErrorCount`, `FCSErrorCount`, `InvalidMACCount`, `PacketsOtherReceived` (v2.7).
- `Stats.Noise` (v2.8, dBm): "non-IEEE 802.11 noise power ... made by sampling the channel when virtual carrier sense indicates idle".
- Channel-change counters (`TotalChannelChangeCount`, `AutoDynamicChannelChangeCount`, `AutoDFSChannelChangeCount`, etc.) and `ChannelLastChange` (seconds since the current channel came into use).
- `CtsReceived`, `NoCtsReceived`, `FrameHeaderError`, `GoodPLCPReceived`, `DPacketOtherMACReceived` / `MPacketOtherMACReceived` / `CPacketOtherMACReceived` (frames from other BSSs), `CtsOtherMACReceived`, `RtsOtherMACReceived` (v2.14).
- Radio configuration/status: `Channel`, `ChannelsInUse`, `CurrentOperatingChannelBandwidth`, `OperatingStandards`, `SupportedStandards`.
- **No `ChannelUtilization`, medium-busy or airtime parameter exists under `Device.WiFi.Radio`, `SSID` or `AccessPoint`.** A search of those subtrees in 2.21 for utiliz/busy/airtime found only the ATF *configuration* knobs `SSID.{i}.SetATF` and `AssociatedDevice.{i}.SetStaATF` (v2.14), plus `MultiAP.APDevice.{i}.BackhaulLinkUtilization` (v2.13, in the now-deleted MultiAP object). — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)

**SSID `Device.WiFi.SSID.{i}.Stats.`**
- `RetransCount`, `FailedRetransCount`, `RetryCount`, `MultipleRetryCount`, `ACKFailureCount`, `AggregatedPacketCount` (v2.7).
- `DiscardPacketsSentBufOverflow`, `DiscardPacketsSentNoAssoc` ("discarded packets due to the station not being associated"), `SentNoAck`, `DupReceived`, `AckUcastReceived` (v2.14).
- Source: [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)

**EasyMesh / Wi-Fi Data Elements branch `Device.WiFi.DataElements.` (object v2.13; "represents the Wi-Fi Alliance Data Elements")**
- `Network.Device.{i}.Radio.{i}.Utilization` (v2.13): "(Total Channel Utilization) The percentage of time (linearly scaled with 255 representing 100%) that the Access Point device sensed the medium was busy, as indicated by either the physical or virtual carrier sense". It is "calculated only for the primary channel" when more than one channel is in use. — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- Same object, v2.13: `Transmit` (own transmissions), `ReceiveSelf` ("local transmissions", i.e. from STAs of its own BSSs), `ReceiveOther` ("non-local transmissions", i.e. valid 802.11 frames from other BSSs), all scaled 0-255. `Noise` (ANPI-encoded noise plus interference on the primary channel). `ChannelUtilizationThreshold` and `ChannelUtilizationReportingThreshold` (v2.15). — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- `Radio.{i}.ScanResult...ChannelScan.{i}.Utilization` / `.Noise` (v2.14): utilization and noise of scanned 20 MHz channels. — same source
- Per-station `Network.Device.{i}.Radio.{i}.BSS.{i}.STA.{i}.`, v2.13 unless noted (same source):
  - Rates and capacity: `LastDataDownlinkRate`/`LastDataUplinkRate` (kbps); `EstMACDataRateDownlink`/`EstMACDataRateUplink` (Mbps, "Estimate of the MAC layer throughput ... achievable in the downlink direction if 100% of channel airtime and BSS operating bandwidth were available", per EasyMesh §10.3.1).
  - Airtime: `UtilizationReceive`/`UtilizationTransmit` (milliseconds of airtime spent on this STA).
  - Signal and session: `SignalStrength` (RCPI-encoded 0-220); `LastConnectTime` (seconds since association).
  - Counters: Bytes/Packets/Errors/`RetransCount`.
  - Other: `MeasurementReport` (the STA's latest 802.11k beacon report); `SleepMode` (v2.17).
- Internal inconsistency in the spec: `AssociatedDevice.SignalStrength` is int dBm, while `DataElements...STA.SignalStrength` is an unsignedInt RCPI code (0-220). Yet both descriptions say that, for the same instance, "this parameter is the same as" the other. A collector must convert RCPI to dBm (dBm ≈ RCPI/2 − 110 per 802.11; my knowledge, not verified in this session) and must not mix the two raw values. — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- TR-181 2.15 is described in trade press as the version that consolidated the Wi-Fi Data Elements fragments, alongside USP 1.2. — [The Fast Mode via search summary](https://www.thefastmode.com/technology-solutions/22849-broadband-forum-integrates-advanced-capabilities-from-wi-fi-data-elements) (not opened)

**Diagnostics**
- `Device.WiFi.NeighboringWiFiDiagnostic` (v2.7). Per neighbor `Result.{i}`: `SignalStrength` (dBm), `Noise`, `Channel`, `OperatingChannelBandwidth`, `BasicDataTransferRates`. — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- `Device.IP.Diagnostics.IPPing` (v2.0): `Host`, `NumberOfRepetitions`, `SuccessCount`, `FailureCount`, Avg/Min/Max response time, including `...Detailed` variants. — same source
- `Device.IP.Diagnostics.UDPEchoDiagnostics` (v2.9, TR-143 App. A.1), with `InterTransmissionTime` and `IndividualPacketResult` entries. — same source
- `Device.IP.Diagnostics.ServerSelectionDiagnostics` (v2.9): ICMP or UDP-echo ping to a `HostList`, returning `FastestHost` and min/avg/max RTT. — same source
- `Device.IP.Diagnostics.DownloadDiagnostics` (v2.0), with time-based test fields. `Device.IP.Diagnostics.IPLayerCapacityMetrics` (v2.14, TR-471). — same source

### Inferences
- Mapping to the literature. da Hora's best web feature set had four inputs:
  - Tx PHY rate maps to `LastDataDownlinkRate`, which is last-frame, not averaged.
  - Frame delivery ratio maps to `Retransmissions` or ΔRetransCount/ΔPacketsSent.
  - Medium busy maps to DataElements `Utilization`.
  - **MediumBusyOtherWiFi** maps to DataElements `ReceiveOther`.

  The prior notes said the Wi-Fi vs non-Wi-Fi busy split is "usually not exposed by TR-181". That holds for the legacy branch but **not for DataElements**. A rough non-Wi-Fi busy share can be derived as (Utilization − Transmit − ReceiveSelf − ReceiveOther)/255. This is my derivation, not a spec statement. It also absorbs collisions and undecodable frames.
- WiSe's `link_exp = (1 − a)(1 − c) · r` maps to DataElements as follows:
  - r = `EstMACDataRateDownlink`, or a mean of `LastDataDownlinkRate` deltas.
  - a = `ReceiveOther`/255 (plus the non-Wi-Fi residual).
  - c = share of the radio's `Transmit + ReceiveSelf` airtime spent on *other* STAs, from per-STA `UtilizationTransmit/Receive` deltas.

  Without DataElements, only r (last-frame rate) and a retry ratio are available. That is roughly WiSe's "effective rate" alone (r = 0.88 in WiSe), with no airtime term.
- `LastDataDownlinkRate` is a single last-frame sample. Pefkianakis et al. warn about exactly this (RSSI averaged over the interval vs PHY rate of the last frame; see Section 3). Sampling it every N seconds yields a noisy estimate that also depends on whether traffic was flowing. Idle stations often show low or legacy rates (my knowledge; not verified here).

### Gaps
- No public table of which commercial CPE firmwares implement DataElements over TR-069 (CWMP) rather than only over USP. Implementation coverage has to be checked device by device (see Implications).
- The exact definitions in the Wi-Fi Alliance Data Elements specification and EasyMesh §10.3.1 (how `EstMACDataRate` is computed by the AP) were not read. The WFA spec was not opened.

---

## 2. Which collection mechanisms (periodic BulkData, events, logs) can give (a) a WiSe-like capacity estimate and (b) availability/disconnections from the router side?

### Takeaway
For capacity, the standard path is a continuous periodic **BulkData** profile (TR-069 Amendment 5/6 or USP) pushing JSON/CSV of the parameters in Section 1 at a fixed interval. `PeriodicStatistics` is a fallback that buffers samples on the CPE. For disconnections, the picture is worse than expected:
- **Under TR-069/CWMP, the standard event tables for Wi-Fi association, disassociation and failed connection were deprecated in 2.17, obsoleted in 2.19 and deleted in 2.20, "because a corresponding USP event is defined instead".**
- Under USP, `Disassociated!` and `FailedConnection!` events exist (v2.15) and carry ReasonCode, InitiatedBy and final link stats.
- A pure-CWMP deployment must therefore reconstruct availability from **periodic snapshots** of the association table (AssociationTime/LastConnectTime resets, MAC presence gaps) and `Hosts.Host.ActiveLastChange`, or from vendor logs. All of these miss short drops and say nothing about clients that never reach the AP.

### Cited Findings
**BulkData and periodic statistics**
- `Device.BulkData.` (v2.5): "bulk data collection capabilities ... Bulk Data utilizes various solutions (e.g., IPDR, HTTP) to collect data from devices and transfer the data to a collection server." `Protocols` enum in 2.21: `Streaming`, `File`, `HTTP`, `MQTT`. `MinReportingInterval` is advertised by the CPE ("0 indicates no minimum"). — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- `Device.BulkData.Profile.{i}.` (v2.5): `ReportingInterval`, `TimeReference`, `Parameter.{i}.Reference` (partial paths and wildcards allowed if `ParameterWildCardSupported`).
  - `NumberOfRetainedFailedReports` (v2.10, −1 = keep as many as possible).
  - `HTTP.` (v2.10), with `RetryEnable`, `RetryMinimumWaitInterval`, `Compression`, `PersistAcrossReboot`.
  - Source: [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- USP: `Device.BulkData.Profile.{i}.Push!` event (v2.13) delivers the report inside a USP Notify. — [usp-full 2.21](https://github.com/BroadbandForum/usp-data-models/blob/master/tr-181-2-21-0-usp-full.xml)
- Practitioner description (QA Cafe):
  - Bulk Data exists because TR-069 "wasn't designed for the frequent, periodic transmission of large amounts of data".
  - An ACS/Controller "can configure an agent to periodically send a JSON or CSV formatted set of Device:2 (TR-181) information" by HTTP PUT/POST to a separate collector.
  - Failed deliveries are retried with back-off similar to CWMP.
  - Source: [QA Cafe](https://www.qacafe.com/articles/data-collection-analytics-with-tr069-tr369-usp)
- `Device.PeriodicStatistics.` (v2.0): statistics "measured over a sample interval ... made available to the Controller as a comma-separated list of the most recent <n> samples". Example: `ReportSamples` = 24 with `SampleInterval` = 3600 stores a day. The CPE may reject intervals below `MinSampleInterval`. — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)

**Association/disassociation events**
- CWMP 2.21:
  - `Device.WiFi.DataElements.AssociationEvent.AssociationEventData.{i}.` (v2.13): TimeStamp, BSSID, MACAddress, StatusCode, capabilities, OpClass, Channel.
  - `DisassociationEvent.DisassociationEventData.{i}.` (v2.13): BSSID, MACAddress, **ReasonCode**, final Bytes/Packets/Errors/RetransCount, LastDataDownlink/UplinkRate, UtilizationReceive/Transmit, EstMACDataRate, **SignalStrength**, **LastConnectTime**, Noise, **InitiatedBy**, OpClass, Channel.
  - `FailedConnectionEvent.FailedConnectionEventData.{i}.` (v2.15): BSSID, MACAddress, StatusCode, ReasonCode, TimeStamp.
  - All three are marked "{{deprecated|2.17|because a corresponding USP event is defined instead}} {{obsoleted|2.19}} {{deleted|2.20}}".
  - Source: [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- USP 2.21:
  - `Device.WiFi.DataElements.AssociationEvent.Associated!`, `DisassociationEvent.Disassociated!` and `FailedConnectionEvent.FailedConnection!` (all v2.15).
  - `Disassociated!` carries the same arguments as the old table, with `InitiatedBy` ∈ {STA, EasyMesh_Agent, EasyMesh_Controller, DE_Collector, Unknown}.
  - `FailedConnection!` carries BSSID, MACAddress, StatusCode, ReasonCode, TimeStamp.
  - Source: [usp-full 2.21](https://github.com/BroadbandForum/usp-data-models/blob/master/tr-181-2-21-0-usp-full.xml)
- There is no event under the legacy `Device.WiFi.AccessPoint.{i}.AssociatedDevice` table in either model. Generic USP alternatives: `Device.LocalAgent.Threshold.{i}.Triggered!` (v2.13) and `Device.LocalAgent.Monitor.{i}.OnChange!` (v2.16), "when the values of the parameters specified by ReferenceList change within the configured Interval". — [usp-full 2.21](https://github.com/BroadbandForum/usp-data-models/blob/master/tr-181-2-21-0-usp-full.xml)

**Presence and logs**
- `Device.Hosts.Host.{i}.Active` (v2.0). "The method of presence detection is a local matter to the CPE", and listing inactive hosts is optional.
- `Hosts.Host.{i}.ActiveLastChange` (v2.10): "The datetime when Active last changed from true to false or from false to true." This is a single timestamp, not a history.
- `Hosts.Host.{i}.AssociatedDevice` links a host to its Wi-Fi association. `Hosts.Host.{i}.WANStats.` (v2.12).
- Source for the three items above: [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- `Device.SSID.{i}.Stats.DiscardPacketsSentNoAssoc` (v2.14): "discarded packets due to the station not being associated". — same source
- `Device.ConnectionMonitoring.` (v2.20): monitors interface connectivity by ARP, ND, Ping or BFDEcho, with `MonitorInterval`, `FailInterval`, `MonitoringStatus` and `Stats.TotalNumberOfAttempts`. It is aimed at interface/upstream connectivity, not Wi-Fi stations. — same source
- `Device.Syslog.` (v2.17, based on the YANG syslog model). `Device.DeviceInfo.VendorLogFile.{i}.` (v2.1): "informational only and does not allow the Controller to operate on these files in any way". Retrieval would go through the TR-069 Upload RPC (my knowledge of TR-069; not verified this session). — same source
- TR-398 Issue 4 has a mandatory "Multiple Association/Disassociation Stability" test and a 4-hour "Long Term Stability" test in which "Throughput and connection availability are continuously monitored" (pass: packet loss ratio ≤ 0.0001 per interval). The standard therefore treats connection availability as a first-class AP property, but it measures it with test stations in a chamber, not from the data model. — [TR-398 Issue 4](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)

### Inferences
- **(a) Capacity estimate.** A continuous BulkData profile (e.g. 30-60 s, subject to the CPE's `MinReportingInterval`) gives counter deltas that are independent of the speed test. That decouples router features from the ~11 s test window, which the project memory flags as a leakage source.
  - The recipe is: ΔBytesSent/Δt (offered load), ΔRetransCount/ΔPacketsSent (retry ratio), `LastDataDownlinkRate` (sampled), `SignalStrength`/`SNR` and, if available, DataElements `Utilization`/`ReceiveOther`/`EstMACDataRateDownlink`.
  - That is enough for a WiSe-style `link_exp` without running any test.
  - Capacity is only observable when the station is associated, and the PHY-rate/retry fields are only meaningful when it carries traffic. Idle samples must be flagged, not averaged in.
- **(b) Availability over CWMP.** With CWMP only, the most defensible reconstruction combines four signals:
  - Poll the full `AssociatedDevice` table every report interval (MAC, AssociationTime or `LastConnectTime`).
  - Count a reassociation whenever AssociationTime advances or LastConnectTime resets.
  - Count an absence episode whenever a known MAC disappears from all AccessPoint/BSS tables across consecutive reports.
  - Cross-check with `Hosts.Host.Active/ActiveLastChange`.

  Time resolution equals the reporting interval. Drops shorter than one interval are seen only as a reassociation (AssociationTime jump), not as a duration. A phone that leaves coverage for good looks identical to a user walking out of the house. Router-side availability is therefore an **upper bound** on true availability and needs the collector's client-side log as ground truth.
- MAC address randomization on phones (per-SSID random MACs are usually stable, but some modes rotate them) could make a "known MAC disappears" rule produce false disconnection episodes. This is my knowledge; not verified here.
- The 2.20 deletion matters beyond this project. Routers certified only against new CWMP models have no standard disassociation reason codes. If the deployed CPEs also speak USP, or are EasyMesh controllers with a DE collector, the USP `Disassociated!` event with `ReasonCode` and `InitiatedBy` is the only standard source of *why* a station left.

### Gaps
- No public measurement of how reliably commercial CPEs populate `AssociationTime`, `Active` or inactive entries, or `ActiveLastChange`. The spec makes most of it optional or "a local matter".
- Whether TR-069 value-change notifications (passive/active) on `AssociatedDeviceNumberOfEntries` are a usable change trigger in practice was not researched. CWMP allows the CPE to refuse active notification on some parameters (my knowledge; not verified this session).
- `MinReportingInterval` values of real CPEs were not found.

---

## 3. What do TR-398, Wi-Fi Data Elements/EasyMesh, and the gateway-side measurement literature say about trusting these router metrics?

### Takeaway
TR-398 Issue 4 (September 2026) is a lab conformance test plan, not a QoE model. It is useful here because its optional "Parameter Accuracies" section tests exactly the TR-181 DataElements fields a model would use, read over TR-369. The bar is loose:
- RCPI only needs **relative** accuracy of ±2 dB.
- Channel utilization needs ±3 percentage points at 25/50/75% load.
- Noise accuracy was **moved to an appendix** (not normative).
- The whole section is only "conditionally mandatory".

Absolute RSSI and noise values are therefore not standardized to be comparable across router models. That is consistent with the project's per-building efficiency differences. The gateway literature adds one more caution: PHY rate (last frame) and RSSI (interval average) live on different timescales.

### Cited Findings
**TR-398 Issue 4**
- "Wi-Fi Residential & SOHO Performance Testing", Issue 4, September 2026. Issue 4 adds 802.11be (Wi-Fi 7) "across all bands" and an Uplink MU-MIMO test. Issue 3 added "new test cases for parameter accuracy" and Wi-Fi 6E. Issue 3 Corrigendum 1 moved the Noise Accuracy test to an appendix. — [TR-398 Issue 4](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- Section 7 "Parameter Accuracies": tests are "CONDITIONALLY MANDATORY ... either tests in this section are not run or they are all run in their entirety". They "require that the parameter values can be read from the DUT by transmitting parameters defined in TR-181 over TR-369". The parameters are `DataElements...STA.{i}.SignalStrength` (RCPI), `DataElements...Radio.{i}.Utilization` and `DataElements...Radio.{i}.Noise`. — [TR-398 Issue 4](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- RCPI test: "a simplified measurement of the accuracy of relative changes in reported RCPI ... This is a relative measurement only." It fails if any relative error exceeds 2 dB in absolute value. — [TR-398 Issue 4 §7.1.1](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- Channel utilization test: uplink UDP at 75%, 50% and 25% of measured TCP max, 120 s each, with one spatial stream. Reported utilization is compared with the actual airtime. Pass: |error| ≤ 3%. Notes: "Channel utilization also includes the airtime used by unassociated STAs and other BSS; this is not tested above", and "Channel utilization was recorded as reported by many APs in the field, and it never exceeded 90%." — [TR-398 Issue 4 §7.1.2](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- Latency test: 90th percentile < 15 ms at 1% load. At 70% load: < 70 ms for 802.11n and < 25 ms for 802.11ac. — [TR-398 Issue 4 §6.2.6](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- Roaming: dropped UDP packets per roam must be "less than 200"; roam time is "for further study". — [TR-398 Issue 4 §6.6.3](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- Other tests (outline): Receiver Sensitivity, Maximum Connection, Maximum Throughput, Airtime Fairness, Range Versus Rate, Spatial Consistency, Multiple STAs Performance, AP Coexistence, Automatic Channel Selection, Mesh Extender Throughput. There is no QoE test. — [TR-398 Issue 4](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- The TR-398 test plan was first published in 2019 (trade press). Ofcom used it for a router test report because "TR398 is freely available". — [TelecomTV](https://telecomtv.com/content/wi-fi/broadband-forum-releases-first-home-wi-fi-performance-testing-standard-defining-carrier-class-premium-wi-fi-experience-34284); [Ofcom PDF](https://www.ofcom.org.uk/__data/assets/pdf_file/0040/194899/wifi-performance-testing-of-home-broadband-routers.pdf) (both via search summary only)

**Pefkianakis et al., "Characterizing Home Wireless Performance: The Gateway View", IEEE INFOCOM 2015 (Technicolor/HP Labs; co-authors Van Doorselaer and Van Oost, also da Hora co-authors)**
- 167 homes of a large European ISP, monitored "continuously for 4 months" from commodity gateways, which reported every 30 s as 15-20 KB JSON. All gateways were 2.4 GHz only ("none of our gateways operates at the 5GHz band"). — [PDF mirror](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)
- Metrics: the "PHY rate of the last transmitted and received data frame, for each station ... every 30 seconds". Also RSSI, achieved throughput per station (30 s), and "excessive retries ... only in downlink". Neighbor scans every 2 hours. The gateways did "not expose 802.11 frame loss statistics ... and contention time", so effective throughput is only an upper bound from PHY rate and protocol overhead. — [same](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)
- Caveat stated by the authors: "the reported RSSI is an average for the reporting interval, while the PHY rate is reported only for the last frame; thus, the interpretation ... is likely to be less accurate under dynamic wireless channels." — [same](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)
- Results:
  - 7.6% of more than 6 million transmissions used PHY rates ≤ 6.5 Mbps (their "poor performance" proxy).
  - "a few homes have a disproportionate number of poor performance reports".
  - Poor coverage was ruled out as the main cause, pointing instead to interference.
  - Link performance was "largely uncorrelated with the wireless density in the neighborhood".
  - Source: [same](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)
- The study used an RSSI-to-expected-PHY-rate table built with an Azimuth channel emulator, and a "RateGap" (expected vs used rate index) to separate coverage problems from interference/rate-adaptation problems. — [same](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)

**Wi-Fi Data Elements and USP in industry**
- Trade press and vendor blogs describe Wi-Fi Data Elements as standardized Wi-Fi KPIs delivered through USP "real-time monitoring, telemetry, and bulk statistics collection". The Wi-Fi Alliance launched a Data Elements certification in 2019. — [Incognito blog](https://www.incognito.com/blog/user-service-platform-managed-wifi); [Advanced Television 2019](https://advanced-television.com/2019/06/26/wi-fi-alliance-introduces-wi-fi-certified-data-elements/) (search summaries only; not opened)

### Inferences
- TR-398 only requires *relative* RCPI accuracy, and noise accuracy is non-normative. Absolute `SignalStrength` and `Noise` thresholds learned on one router model should therefore not be expected to transfer to another. This mirrors WiSe's per-standard coefficients and the project's per-building efficiency gap. Features should be per-device-relative (e.g. change from the station's own baseline) or calibrated per AP model and band.
- Channel utilization is tested only for own-BSS uplink load. The part that matters most for interference, other-BSS and non-Wi-Fi airtime, is explicitly untested, so `ReceiveOther` and the residual non-Wi-Fi share have no accuracy guarantee.
- The TR-398 latency thresholds (p90 < 15 ms idle; < 25 ms at 70% load for ac) are lab conformance limits with one to eight stations in a shielded chamber. They are not perceptual thresholds, but they give an order of magnitude consistent with the WiFiSeer field numbers already in the main report.
- The gateway literature again finds that a few homes concentrate the problems. That supports reporting per-building results rather than pooled averages.

### Gaps
- The Wi-Fi Alliance Data Elements specification and the EasyMesh R5/R6 text on `EstMACDataRate` computation were not read.
- No published independent field audit of TR-181 Wi-Fi counter accuracy across vendors was found.

---

## 4. da Hora et al. INFOCOM 2018 / 2017 thesis: full text, second attempt

### Takeaway
Still inaccessible from this environment. Every open-access route resolves to HAL (bot challenge), CORE (403) or the Wayback Machine (timeouts; WebFetch-blocked). The open questions from the previous notes remain open: per-application RMSE, YouTube/RTC label models, sampling interval, and whether per-device effects are discussed.

### Cited Findings
- Semantic Scholar lists one open-access PDF (HAL, "GREEN"); citationCount = 14; DBLP key conf/infocom/HoraDOT18. — [S2 API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/INFOCOM.2018.8486335?fields=title,openAccessPdf,externalIds,citationCount)
- OpenAlex locations: doi.org, inria.hal.science/hal-01676921, inria.hal.science/hal-01677214. — [OpenAlex](https://api.openalex.org/works/doi:10.1109/INFOCOM.2018.8486335)
- Wayback has archived the PDF (2021-07-31) and the thesis (2022-08-05). — [archive.org availability API (INFOCOM)](https://archive.org/wayback/available?url=hal.inria.fr/hal-01676921/document); [thesis](https://archive.org/wayback/available?url=tel.archives-ouvertes.fr/tel-01670997/document)
- A CORE copy exists at core.ac.uk/download/146072036.pdf (returned 403). — [search result](https://core.ac.uk/download/146072036.pdf)
- A continuation patent, US 12074775, from the same family as US11316759B2, exists. Not read. — [USPTO 12074775](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12074775)
- A related precursor from the same Technicolor group (Pefkianakis et al. 2015; Section 3) documents what Technicolor gateways reported in that era: last-frame PHY rate, RSSI, throughput and excessive retries every 30 s, without frame-loss or contention statistics. That is plausibly the telemetry family behind da Hora's field data. — [Gateway View PDF](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)

### Inferences
- da Hora's selected web features included MediumBusy and MediumBusyOtherWi-Fi (patent). The 2015 Technicolor gateways did not expose contention. So either the 2016-2018 firmware added these counters, or the field application used a reduced feature set. This cannot be resolved without the full text, and it matters for judging whether their field predictions used the lab-validated feature set.

### Gaps
- Full text of INFOCOM 2018 and of the thesis: unread. A human should download them via a browser, either the [Wayback INFOCOM snapshot](http://web.archive.org/web/20210731070144/https://hal.inria.fr/hal-01676921/document) and [Wayback thesis snapshot](http://web.archive.org/web/20220805005205/https://tel.archives-ouvertes.fr/tel-01670997/document), or HAL directly.

---

## 5. Recent work (2019-2026) on router-telemetry QoE/ML and operator practice

### Takeaway
Peer-reviewed work since 2019 remains small and mostly lab-based:
- Morshedi & Noll (2021) train classifiers on more than 240 driver counters from two commodity APs (AirTies, Zyxel) to predict a YouTube MOS derived from player metrics. They report 91-99% accuracy on random splits, with one striking detail: Wi-Fi 6 clients disconnected so often under poor conditions that **about 43% of 2.4 GHz-ax instances were missing values**.
- Commercial systems (Plume "happy throughput", Lifemote, ASSIA CloudCheck) describe per-device baselines but publish no validation.
- The largest recent academic home study found (IMC 2024) uses joint client/AP measurements, not router telemetry, and could not be read.

Nothing found reports leave-one-home-out generalization or uses standard TR-181 parameters as the feature source.

### Cited Findings
**Morshedi & Noll, "Estimating PQoS of Video Streaming on Wi-Fi Networks Using Machine Learning", Sensors 21(2):621, 2021 (EyeNetworks AS / University of Oslo)** — [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC7829984/)
- Data collection: AirTies 4920 and Zyxel 5501 APs; a Bash script reads driver counters, more than 240 parameters per band interface and 48 per client, about every 1 s, sent over HTTP to Elastic. Named features include `client_LastTXRate`, `client_RSSILastRX`, `rxbadplcp`, `txFailures` and `rxmpdu_stbc`. TR-069/TR-181 is not mentioned.
- Label: MOS = 4.23 − 0.0672·L_ti − 0.742·L_fr − 0.106·L_tn − R, where L_ti is startup delay, L_fr the rebuffering count, L_tn the rebuffering duration and R a resolution penalty (720p 0.21 … 144p 2.07). It is computed every 3 s from browser-side YouTube metrics and rounded to integers. The model never yields 5. P.1203 is not used.
- Data: four lab-like datasets simulating home setups: 2n 13,039 instances; 2ax 12,762; 5ac 7,896; 5ax 8,897. Interference came from a signal generator. There was no field deployment.
- Results: ZeroR baseline above 47%; other models above 86%; LMT chosen, with the abstract reporting 93-99%. Confusion-matrix accuracies computed by the fetch tool: 5ax ≈ 91.3%, rising to 97% with SMOTE. Validation was a 70/30 split with an unspecified resampling, not by AP or home.
- The LMT root split was on `client_LastTXRate` at 272 Mbps. Other features in the tree were STBC use, PLCP errors, txFailures and per-antenna RSSI.
- Missing data: 802.11ax clients "often disconnected under poor channel conditions", leaving about 43% of 2ax instances missing. No imputation method is described.
- Stated limitations: RSSI varies across vendors; only YouTube was tested; the label comes from a regression model, not user ratings.

**Same group, video conferencing:** "Estimating PQoS of Video Conferencing on Wi-Fi Networks Using Machine Learning", Future Internet 13(3):63, 2021. It uses only 802.11 parameters from customer-premises APs and analyzes features linked to root causes. — [DOI 10.3390/fi13030063](https://doi.org/10.3390/fi13030063) (search summary only; not opened)

**Lifemote / BalkanCom 2023 (gradient boosting):** CatBoost R² = 0.92 for web QoE from Wi-Fi statistics; XGBoost beat the neural network for video. A search summary attributes the paper to "Argin et al." (authors not verified). — [BAU research portal](https://research.bau.edu.tr/en/publications/qoe-estimation-for-the-wi-fi-edge-with-gradient-boosting-based-ma/) (search summary only)

**Plume (2021):** QoE is defined by comparing "real-time throughput to the device's 'happy throughput'". Context inputs: hops, interference, congestion, true net throughput, device type, active/idle. No formula or validation is given. The white paper is behind a Wi-Fi NOW login. — [Wi-Fi NOW, 4 Nov 2021](https://wifinowglobal.com/news-and-blog/white-paper-defining-an-accurate-metric-for-home-wi-fi-quality-of-experience-qoe-by-plume/)

**ASSIA CloudCheck:** a home-gateway agent measuring broadband and Wi-Fi throughput and "real-time Wi-Fi QoE"; product brief only. — [ASSIA brief](https://assia-inc.com/wp-content/uploads/2016/10/Brief_CloudCheck.pdf) (search summary only)

**Sharma, Feamster, Richardson, "A Longitudinal Study of the Prevalence of WiFi Bottlenecks in Home Access Networks", ACM IMC 2024:** measures the client-to-AP hop and the AP-to-ISP hop jointly. Reported as "over 22,000 joint measurements across more than 50 broadband access networks", 52 households, September 2021 to September 2023. — [ACM DOI 10.1145/3646547.3689007](https://dl.acm.org/doi/10.1145/3646547.3689007) (search summary only; the PDF returned 403, so the numbers are unverified)

### Inferences
- Morshedi & Noll is the closest recent analogue to the project's single-device experiments. Like the project, it finds the last-frame Tx rate dominant (root split). Its random-split accuracies are not comparable to leave-one-building-out results.
- The 43% missing-instance figure is the only published number found that quantifies how much router-side data vanishes through client disconnection under poor conditions. It is direct evidence that dropping missing rows biases toward good conditions. In a lab with forced interference it is an upper bound, not a home prevalence.
- Vendor metrics (Plume, Lifemote) converge on a per-device "relative to own expected throughput" idea. That resembles the project's relative ruler, but none is published with validation, so they support the design idea only as industry practice, not as evidence.

### Gaps
- No 2019-2026 peer-reviewed paper found that uses standard TR-181/TR-369 parameters (rather than proprietary driver dumps) as features for QoE prediction, or that evaluates leave-one-home-out.
- No operator paper (Comcast, Deutsche Telekom, Orange, Vodafone, Telefonica) with router-telemetry-to-QoE validation found. Not searched exhaustively given the tool budget.
- Sharma et al. IMC 2024 details (bottleneck definition, band and distance effects) are unverified.

---

## Implicações para o projeto

### Takeaway
The project should (1) verify which TR-181 branches the deployed routers actually implement, (2) switch router features from speed-test-window deltas to a continuous BulkData stream, (3) build a WiSe-style capacity feature from DataElements where available, with per-AP-model/band calibration, and (4) treat router-side availability as a reconstruction from periodic association snapshots, validated against the collector's client-side disconnect log. On CWMP-only firmware there is no standard disassociation event after TR-181 2.20.

### Cited Findings
- No standard medium-busy parameter outside DataElements; DataElements utilization split and per-STA EstMACDataRate from 2.13 — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml)
- CWMP association/disassociation/failed-connection tables deleted in 2.20; USP events since 2.15 — [cwmp-full 2.21](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-21-0-cwmp-full.xml); [usp-full 2.21](https://github.com/BroadbandForum/usp-data-models/blob/master/tr-181-2-21-0-usp-full.xml)
- RCPI only relatively accurate (±2 dB), noise accuracy non-normative — [TR-398 Issue 4](https://www.broadband-forum.org/pdfs/tr-398-4-0-0.pdf)
- Last-frame PHY rate vs interval-averaged RSSI caveat; 30 s gateway reporting is feasible on commodity gateways — [Pefkianakis et al. 2015](https://netman.aiops.org/~peidan/ANM2016/WiFi/ReadingLists/2015INFOCOM_Characterizing%20Home%20Wireless%20Performance%20The%20Gateway%20View.pdf)
- Client disconnections removed about 43% of instances in an 802.11ax lab dataset — [Morshedi & Noll 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7829984/)

### Inferences (prioritized actions)
- **P0.1: Data-model inventory per router model (no new hardware).**
  - Action: for each AP/CPE model in the 6 buildings, run `GetParameterNames` on `Device.WiFi.` (next level false), read `Device.DeviceInfo.SupportedDataModel.{i}.` and `Device.BulkData.Protocols` / `MinReportingInterval`, and check whether `Device.WiFi.DataElements.` exists and over which protocol (CWMP vs USP).
  - Output: a coverage table with model, firmware, TR-181 version and presence of each Section 1 parameter. This is the "honest per-version TR-181 coverage" already planned.
  - Done when: the table exists, and every feature in v1-v5 is tagged "standard path / vendor path / not available".
- **P0.2: Continuous BulkData profile, decoupled from the speed test.**
  - Action: HTTP+JSON at the smallest supported interval (aim 30-60 s; fall back to `PeriodicStatistics` buffering if BulkData is absent). Reference `AssociatedDevice.{i}.` (MAC, LastDataDownlink/UplinkRate, SignalStrength, Noise/SNR, Retransmissions, Active, AssociationTime, OperatingStandard, Stats.*), `Radio.{i}.Stats.` (Noise, FCS/PLCP errors, channel-change counters), `Radio.{i}.Channel/CurrentOperatingChannelBandwidth/ChannelLastChange`, `SSID.{i}.Stats.` retry counters and `Hosts.Host.{i}.Active/ActiveLastChange`. Add, where present, `DataElements...Radio.{i}.Utilization/Transmit/ReceiveSelf/ReceiveOther/Noise` and `...STA.{i}.EstMACDataRateDownlink/Uplink/UtilizationTransmit/UtilizationReceive/LastConnectTime`.
  - Features: build them from windows *before* each test (e.g. the preceding 5-15 min) plus long-run room baselines. Tag idle vs active samples by ΔBytes. This removes the leakage of ~11 s test-window counters noted in project memory.
  - Done when: the model is retrained on pre-test-window features and the leave-one-building-out result is reported next to v5.
- **P0.3: Router-side availability reconstruction plus validation.**
  - Action: per station MAC, derive a presence timeline from consecutive BulkData snapshots: absence episodes, reassociation count from AssociationTime/LastConnectTime resets, band and BSSID changes. Compare against the collector app's logged attempts and disconnects in the same rooms (the ground truth the main report asks for).
  - Report: router-side recall of client-side disconnects, by duration bucket. Expect misses below the reporting interval.
  - Done when: a per-room table shows availability (router view vs client view) with Wilson intervals, and the "Ausente" kitchen case is checked against it.
- **P1.1: WiSe-style capacity feature with explicit calibration.**
  - With DataElements: `cap_est = EstMACDataRateDownlink × (1 − ReceiveOther/255 − nonWiFi_residual) × (1 − share_other_STAs)`.
  - Without DataElements: `LastDataDownlinkRate_median × (1 − retry_ratio)`, with retry_ratio = ΔRetransCount/ΔPacketsSent (or `Retransmissions`/100).
  - Calibration: fit one slope per AP model × band × standard (AX vs non-AX), not per building. That is the WiSe g/n analogue and the testable explanation of the per-building efficiency effect.
  - Done when: the efficiency residual by building shrinks under leave-one-building-out.
- **P1.2: Prefer relative over absolute radio features.** Given the TR-398 ±2 dB relative-only RCPI requirement and non-normative noise, express SignalStrength/Noise as deviations from the station's own baseline at the router or the best room. Convert DataElements RCPI to dBm before mixing it with `AssociatedDevice.SignalStrength`. Done when: an ablation of absolute vs relative signal features is reported per building.
- **P1.3: If any CPE supports USP 2.15+ DataElements, subscribe to `Disassociated!` and `FailedConnection!`.** Store ReasonCode, InitiatedBy, SignalStrength, LastConnectTime and final counters as the only standard "why it dropped" signal. If only CWMP is available, check whether the vendor exposes hostapd-style association logs via Syslog (v2.17) or VendorLogFile (Upload RPC). Treat these as vendor-specific and unvalidated.
- **P1.4: Low-rate LAN-side probing from the router (optional; inference, not validated in the literature found).** `IPPing` (v2.0) or `UDPEchoDiagnostics` (v2.9) aimed at a station's LAN IP would give a router-side Wi-Fi-hop RTT and loss series, close to Sundaresan's LAN-RTT signal. Client power-save will inflate RTT. Test on one building first and compare with the collector's ping.
- **P2.1: Interference context.** Run `NeighboringWiFiDiagnostic` (v2.7) periodically (e.g. a few times per day; impact on service not verified). If available, also use `DataElements...ScanResult` (v2.14) as building-level covariates. The Gateway View study found little effect of neighbor density, so treat this as a confound check, not a primary feature.
- **P2.2: Literature follow-up for a human with a browser.**
  - Download da Hora INFOCOM 2018 and the thesis via the Wayback links above, to settle the label models, RMSE per application and per-device effects.
  - Read Sharma et al. IMC 2024 for the bottleneck prevalence by band and distance.
  - Read the Wi-Fi Alliance Data Elements spec and EasyMesh §10.3.1 for how `EstMACDataRate` is computed.

### Gaps
- All P0/P1 actions depend on the unknown implementation coverage of the deployed CPEs (P0.1).
- No published validation of router-side availability reconstruction against client-side logs was found. The project would be producing that evidence itself.

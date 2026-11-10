# Measurement bias, failed tests and availability: deeper pass (V2 phone collector, failure logging, statistics)

Project context for the report writer: the kitchen `villa_res_cozinha` is rated "Ausente" by its resident but holds 43 successful tests and 0 logged failures (median 231 Mbps). Failures and disconnections are never written to the dataset. The `router_*` counters are deltas over the roughly 11 s speed-test window, so they are also gated by test success. V2 plans a phone app. Each room needs a label of bom / degradado / ruim. This note builds on `vies_medicao_falhas.md` (same folder) and on the draft report, and does not repeat what they already establish (M-Lab filter views, Padmanabhan's exposure hazard, Bauer/FCC 2012 discarding failures).

Source access log (what was actually opened in this session, 2026-11-09):
- Android developer reference pages, read in full: `ConnectivityManager.NetworkCallback`, `WifiInfo`, "Wi-Fi permissions", foreground service types, Android 15 behavior changes, `PeriodicWorkRequest`, Doze/App Standby.
- Apple developer documentation, read through the DocC JSON endpoint (the HTML page renders only with JavaScript): `NEHotspotNetwork.fetchCurrent`, `NEHotspotNetwork.signalStrength`, `NEHotspotNetwork`, `NWPathMonitor`, `BGTaskScheduler`, `BGAppRefreshTaskRequest`. The last three are abstract-level only.
- ndt7 protocol spec (m-lab/ndt-server): full text, summarized by the fetch tool.
- m-lab/ndt7-client-android `NDTTest.kt`: grepped source.
- RTR-Netztest (Open-RMBT): READMEs, the Android client source files `TestFinishReason.kt`, `TestStatus.kt`, `Requests.kt` and `MeasurementService.kt` (grepped), and the full PostgreSQL schema `schema/schema.sql` (grepped).
- MobiPerf `MeasurementResult.java`: grepped source.
- FCC MBA Thirteenth Report Technical Appendix (2023, fixed; SamKnows platform): full PDF downloaded and grepped.
- Baltrunas, Elmokashfi & Kvalbein, IMC 2014: **full PDF read** (key sections 2, 4, 5, 6), via the SIGCOMM conference mirror. The previous note marked this paper inaccessible; that gap is now closed.
- CCITT/ITU-T E.800 (**1992/1988 text**, superseded): full plain text read from an MIT mirror. **The in-force 2008 edition was NOT read.** The ITU download returned "Request Rejected".
- Belotti, Deb, Manning & Norton, Stata Journal 2015 (two-part models): full PDF, introduction read.
- Brown, Cai & DasGupta, Statistical Science 2001: **not opened.** Project Euclid returned an empty page and the Wharton mirror failed. Only search-result abstract excerpts were seen.
- Grover et al., IMC 2013: **still inaccessible.** The SIGCOMM mirror returned 404, Semantic Scholar marks it CLOSED, and only abstract-level summaries were seen.
- Ookla methodology page: **blocked** (the fetch tool cannot reach ookla.com). SamKnows' own methodology documents were not found; the MBA 2023 appendix stands in for them.
- NetMonster: **not checked.** It is a cellular-cell-info library (netmonster-core) and was judged out of scope for Wi-Fi.
- Interval numbers in section 3 are **my own computations** (Python/scipy) of standard formulas, not quotes from a paper.

## 1. Which phone APIs can log Wi-Fi state continuously and record failures (Android 13–15, iOS)?

### Takeaway
Android can do almost everything V2 needs: event callbacks for Wi-Fi loss and gain, RSSI, Tx/Rx link rate, frequency, Wi-Fi standard and, with location permission, BSSID. The binding constraints are scheduling, not data. Doze suspends network access and stops WorkManager. Periodic work cannot run more often than every 15 minutes. On Android 15 a `dataSync` foreground service is capped at 6 h per 24 h. iOS cannot serve as a radio collector: its only public current-network call returns SSID, BSSID and security type and nothing else. The practical design is therefore an Android-only collector that runs attended sessions (screen on, app in foreground) plus passive logging while plugged in. iOS is usable only to record test outcomes.

### Cited Findings
**Android: connectivity events (ConnectivityManager.NetworkCallback)**
- `onAvailable` is "Called when the framework connects and has declared a new network ready for use". From Android O on, it is "always immediately … followed by" `onCapabilitiesChanged`, `onLinkPropertiesChanged` and `onBlockedStatusChanged`. — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- `onLost` is "Called when a network disconnects or otherwise no longer satisfies this request or callback". With `registerNetworkCallback()` it fires "for each network which no longer satisfies the criteria". With `registerDefaultNetworkCallback()` it fires only when the last network is lost "and no other network satisfies the criteria". — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- `onLosing` (network about to be lost, with `maxMsToLive`) "is not guaranteed to be called before onLost … for example in case a network is suddenly disconnected." — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- `onUnavailable` (API 26) fires only for callbacks registered with `requestNetwork`, "if no network is found within the timeout … or if the requested network request cannot be fulfilled". — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- `onBlockedStatusChanged` (API 29) is "Called when access to the specified network is blocked or unblocked". This is relevant because Doze and data-saver blocking would otherwise look like a Wi-Fi outage. — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- The docs warn against calling synchronous `getNetworkCapabilities`/`getLinkProperties` inside callbacks ("prone to race conditions"). Instead, the app should wait for `onCapabilitiesChanged`, whose arguments are "guaranteed to be well-ordered". — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- `FLAG_INCLUDE_LOCATION_INFO` (API 31): "In Android 12 and above, by default the sent objects do not contain any location information, even if the app holds the necessary permissions." `WifiInfo` obtained through `NetworkCapabilities.getTransportInfo()` is named as location-sensitive. With the flag, "the system will check location permission and the location toggle state". — [NetworkCallback reference](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)

**Android: radio state (WifiInfo)**
- `getRssi()` returns RSSI in dBm (for MLO, "the highest of all associated links"). `getTxLinkSpeedMbps()` and `getRxLinkSpeedMbps()` arrived in API 29. `getFrequency()` returns MHz. `getWifiStandard()` (API 30) returns legacy / 11n / 11ac / 11ax / 11ad / 11be. `getMaxSupportedTx/RxLinkSpeedMbps()` arrived in API 30. `getSupplicantState()` exists since API 1. `getAssociatedMloLinks()` (API 34) covers Wi-Fi 7. — [WifiInfo reference](https://developer.android.com/reference/android/net/wifi/WifiInfo)
- Location-sensitive fields: without the required permission, `getSSID()` returns `UNKNOWN_SSID`, `getBSSID()` returns `"02:00:00:00:00:00"`, and `getNetworkId()` returns -1, among others. RSSI, link speed and frequency are **not** in the redacted list. — [WifiInfo reference](https://developer.android.com/reference/android/net/wifi/WifiInfo)
- `getIpAddress()` was deprecated in API 31 in favour of `LinkProperties` from `onLinkPropertiesChanged`. — [WifiInfo reference](https://developer.android.com/reference/android/net/wifi/WifiInfo)

**Android: permissions (13+)**
- Apps targeting Android 13 that "manage Wi-Fi connections" should request `NEARBY_WIFI_DEVICES`, which can be declared `neverForLocation`. However, "Several Wi-Fi APIs require the ACCESS_FINE_LOCATION permission, even when your app targets Android 13 or higher", including `WifiManager.getScanResults()` and `startScan()`. — [Wi-Fi permissions](https://developer.android.com/develop/connectivity/wifi/wifi-permissions)

**Android: background execution**
- Doze (screen off, unplugged, stationary) "Suspends network access", "Ignores wake locks", "Doesn't perform Wi-Fi scans", and does not let JobScheduler run, so "WorkManager tasks don't run". `setExactAndAllowWhileIdle()` cannot fire "more than once per nine minutes, per app". Plugging in releases standby apps. — [Doze and App Standby](https://developer.android.com/training/monitoring-device-state/doze-standby)
- Play policy "prohibit[s] apps from requesting direct exemption" from Doze "unless the core function of the app is adversely affected". — [Doze and App Standby](https://developer.android.com/training/monitoring-device-state/doze-standby)
- "Periodic work has a minimum interval of 15 minutes", and "execution may be delayed because WorkManager is subject to OS battery optimizations, such as doze mode." — [PeriodicWorkRequest](https://developer.android.com/reference/androidx/work/PeriodicWorkRequest)
- From Android 14, every foreground service must declare a type. `dataSync` needs `FOREGROUND_SERVICE_DATA_SYNC` and has no runtime prerequisite. `connectedDevice` requires declaring `CHANGE_NETWORK_STATE` or `CHANGE_WIFI_STATE` (among other options) and is described as "Interactions with external devices that require a Bluetooth, NFC, IR, USB, or network connection". `specialUse` requires a free-form justification that Play reviews. `shortService` lasts "about 3 minutes". — [Foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types)
- Android 15 (target API 35): "The system permits an app's dataSync services to run for a total of 6 hours in a 24-hour period". The timer resets when the user brings the app to the foreground. `BOOT_COMPLETED` receivers can no longer start `dataSync` services. — [Android 15 behavior changes](https://developer.android.com/about/versions/15/behavior-changes-15)

**iOS**
- `NEHotspotNetwork.fetchCurrent` (iOS 14+) yields "the current SSID, BSSID, and security type. This call doesn't populate other fields in the object." It returns non-nil only if the app has precise-location authorization, configured the network via `NEHotspotConfiguration`, has an active VPN configuration, or has an active `NEDNSSettingsManager` configuration. It also needs the `com.apple.developer.networking.wifi-info` entitlement. — [Apple: fetchCurrent](https://developer.apple.com/documentation/networkextension/nehotspotnetwork/fetchcurrent(completionhandler:))
- `signalStrength` (0.0–1.0) belongs to `NEHotspotNetwork`, whose class documentation frames it around the Hotspot Helper flow ("When the Hotspot Helper app is asked to evaluate a network…"). — [Apple: signalStrength](https://developer.apple.com/documentation/networkextension/nehotspotnetwork/signalstrength); [Apple: NEHotspotNetwork](https://developer.apple.com/documentation/networkextension/nehotspotnetwork)
- `NWPathMonitor` is "An observer that you use to monitor and react to network changes". `BGAppRefreshTaskRequest` is "A request to launch your app in the background to execute a short refresh task". Their scheduling limits were not read. — [Apple: NWPathMonitor](https://developer.apple.com/documentation/network/nwpathmonitor); [Apple: BGAppRefreshTaskRequest](https://developer.apple.com/documentation/backgroundtasks/bgapprefreshtaskrequest)

### Inferences
- **Event stream (Android).** Register a callback on a `NetworkRequest` with `TRANSPORT_WIFI`, using `NetworkCallback(FLAG_INCLUDE_LOCATION_INFO)` so that BSSID survives. Log every `onAvailable`, `onLost`, `onLosing`, `onBlockedStatusChanged` and `onCapabilitiesChanged` event with a monotonic timestamp. Also register a **default-network** callback, so the log shows when the phone silently falls back to cellular. A test launched at that moment would measure 4G, not the kitchen Wi-Fi.
- **Sampler.** During a session, poll `WifiInfo` every 1–5 s from the latest `onCapabilitiesChanged` transport info (RSSI, Tx/Rx rate, frequency, standard, BSSID). Write samples even when no test runs.
- **Why BSSID matters.** Without location permission and the flag, BSSID comes back as `02:00:00:00:00:00`, and roaming between mesh nodes or bands becomes invisible. For a per-room study, `ACCESS_FINE_LOCATION` is worth requesting despite the friction.
- **Doze kills unattended logging.** Doze stops network access, Wi-Fi scans and WorkManager, and periodic work cannot run more often than every 15 minutes. A truly unattended 24 h availability logger on an unplugged phone is not achievable under normal policy. The feasible protocol is: (a) **attended room sessions**, with the screen on and the app in the foreground, during which the foreground service and callbacks run freely; and (b) **overnight or plugged-in passive logging**, where charging lifts App Standby. Doze still requires the device to be unplugged, so plugged-in logging should be safe, but this needs a device test. The 6 h/24 h `dataSync` cap fits sessions but not round-the-clock monitoring.
- **Bind tests to Wi-Fi.** Every test should be bound to the Wi-Fi `Network` object (for example `Network.openConnection` / `bindSocket`), not to the default route. RTR treats a network change mid-test as an error (section 2), and this binding makes the failure explicit instead of hiding it in a cellular result. I did not open the `bindProcessToNetwork` / `Network.bindSocket` reference pages, so this rests on general Android knowledge.
- **iOS role.** Without RSSI or link rate, iOS can log outcomes (attempt started, completed or failed, with an error code) and path changes, but not radio context. Radio-to-QoE modelling has to come from Android phones or from the router.

### Gaps
- iOS background limits for `BGAppRefreshTask` and `NWPathMonitor` (frequency, duration) were not read past the abstracts.
- I did not verify whether Play review accepts `connectedDevice` or `specialUse` for a router-diagnostics app. That is a policy question, not a technical one.
- Android does not expose the 802.11 disassociation reason code to apps through public API, as far as these pages show. Neither callback nor `WifiInfo` carries it. The router side (hostapd or TR-181) is the only source for reason codes, which another note covers.
- Vendor-specific battery killers (Xiaomi, Samsung and others) beyond AOSP Doze were not researched. Field reports suggest they matter, but no source was opened.

## 2. How do open-source measurement clients and programs record failed attempts?

### Takeaway
The programs differ sharply. **RTR-Netztest (Open-RMBT) is the best template.** Its server creates the test row at request time with status `STARTED` before any data flows. The client reports a finish reason (SUCCESS / ERROR / ABORTED), the last phase reached, and an error cause such as "Illegal network change during the test". The **next** test request also carries the previous test's status, so a test whose app died still leaves a trace. ndt7 makes interruptions part of the result: the spec says to record them, not fail the test. The ndt7 Android client hands the error to the app and nothing more. MobiPerf keeps a boolean `success` per result. The FCC/SamKnows program keeps 0/1 success and failure fields in raw data, but its validity checks delete whitebox-hours with 10% or more failures, which by design removes periods of unavailability from the performance figures.

### Cited Findings
**RTR-Netztest / Open-RMBT** (Austrian regulator RTR; Apache 2.0; components in separate repos: Android, iOS, JS clients, measurement server, control server, statistics server). — [open-rmbt README](https://github.com/rtr-nettest/open-rmbt)
- Android client finish reasons: `enum class TestFinishReason { SUCCESS, ERROR, ABORTED }`. The client state machine is `WAIT, INIT, PING, DOWN, UP, INIT_UP, SPEEDTEST_END, QOS_TEST_RUNNING, QOS_END, END, ERROR, ABORTED, PACKET_LOSS_AND_JITTER`. — [open-rmbt-android `TestFinishReason.kt` and `TestStatus.kt`](https://github.com/rtr-nettest/open-rmbt-android)
- Result submission fields include `test_status` ("Reason of the test finishing … '0' for Success, '1' for Error, '2' for Aborted") and `last_client_status` ("Phase was the last done by the client"). They also include `test_error_cause` ("Stacktrace of IllegalNetworkChangeException … which was happened during the test") and `test_submission_retry_count` ("Count of unsuccessful submissions"). — [open-rmbt-android `control_client/.../Requests.kt`](https://github.com/rtr-nettest/open-rmbt-android)
- The test **request** carries `previousTestStatus` (default `"END"`) and `testCounter`. A test that never reported can therefore be flagged at the next attempt. — [open-rmbt-android `Requests.kt`](https://github.com/rtr-nettest/open-rmbt-android)
- `MeasurementService.kt` throws `IllegalNetworkChangeException("Illegal network change during the test")` and `IllegalNetworkChangeException("No active network detected")`, records the stack trace, and calls `onUnsuccessTest(TestFinishReason.ERROR)`. — [open-rmbt-android `core/.../MeasurementService.kt`](https://github.com/rtr-nettest/open-rmbt-android)
- Server schema: the `test` table has `status`, `client_previous_test_status`, `last_client_status`, `last_qos_status`, `test_error_cause`, `implausible`, `deleted`, `wifi_ssid`, `wifi_bssid`, `wifi_link_speed` and `signal_strength`. Signal tables hold `wifi_rssi` and `wifi_link_speed` per sample. Triggers run post-processing only on the `STARTED → FINISHED` transition. Status `SIGNAL` marks signal-only measurements, and an altered `FINISHED` row is marked `implausible`. — [open-rmbt-database `schema/schema.sql`](https://github.com/rtr-nettest/open-rmbt-database)

**M-Lab ndt7**
- "The maximum runtime of a test should be ten seconds since the WebSocket handshake completed". Both sides "SHOULD tolerate any abrupt EOF, RST, or timeout/alarm error", and such events "SHOULD be logged as warnings and SHOULD be recorded into the results" rather than failing the whole test. Clients should use a 5–10 s handshake timeout. Non-interactive clients should average about 6 h between tests (clamped to 2160–54000 s). On a locate "no-capacity" (204) response, an interactive client "SHOULD report an error to the user". — [ndt7 protocol spec](https://github.com/m-lab/ndt-server/blob/main/spec/ndt7-protocol.md)
- The spec does not require clients to report failures to any central service and sets no retention policy for interrupted tests. — [ndt7 protocol spec](https://github.com/m-lab/ndt-server/blob/main/spec/ndt7-protocol.md)
- The Android library calls `onFinished(null, e, testType)` on HTTP or locate failure. The error reaches the host app only, and whether it is stored is up to the app. — [ndt7-client-android `libndt7/.../NDTTest.kt`](https://github.com/m-lab/ndt7-client-android)

**MobiPerf** (Android, M-Lab-affiliated, legacy)
- `MeasurementResult` carries a `boolean success`. For HTTP it prints "Download failed, status code …". Failure is a per-result flag, not a dropped row. — [MobiPerf `android/src/com/mobiperf/MeasurementResult.java`](https://github.com/Mobiperf/MobiPerf)

**FCC MBA, Thirteenth Report Technical Appendix (2023, fixed; SamKnows whiteboxes)**
- The raw-data dictionaries for ping, DNS and HTTP tests carry `successes` and `failures` fields ("always 1 or 0 for this test" for single-shot tests). Failures are therefore stored per test in raw data. — [MBA 2023 Technical Appendix](https://data.fcc.gov/download/measuring-broadband-america/2023/Technical-Appendix-fixed-2023.pdf)
- Validity check 3 removed off-net servers with "a failure rate of 10 percent or greater during a specific one-hour period". Check 4 removed "measurements for any Whitebox that exhibited greater than or equal to 10 percent failures in a particular one-hour period. This removed periods when the Whitebox was unable to reach the Internet." — [MBA 2023 Technical Appendix](https://data.fcc.gov/download/measuring-broadband-america/2023/Technical-Appendix-fixed-2023.pdf)
- "No tests are performed if the Whiteboxes detect wired or wireless traffic beyond a defined bandwidth threshold." About software (non-whitebox) measurement, the appendix says "Potential bottlenecks, such as Wi-Fi networks … may result in unreliable data", and if the device uses in-home Wi-Fi, "differing locations in the home may impact measurements." Charts require at least 30 whiteboxes. — [MBA 2023 Technical Appendix](https://data.fcc.gov/download/measuring-broadband-america/2023/Technical-Appendix-fixed-2023.pdf)

**Ookla:** methodology page not reachable (fetch blocked). No claim is made about Ookla's failure handling.

### Inferences
- RTR's three mechanisms map directly onto the project's failure modes. (1) A **server-side row at test start** covers the case where the app dies and the row survives as `STARTED`. (2) A **finish reason plus last phase reached** separates "failed in DOWN" from "failed in INIT". (3) **Previous-test status on the next request** catches crashes the client could not report. The project should copy all three. The project uses an 11 s test, so a `STARTED` row older than about 60 s without a `FINISHED` update can be reclassified as `lost`.
- RTR treating "network change during the test" as an ERROR is direct precedent: a Wi-Fi drop or roam mid-test should become a failure row, not a silent restart.
- ndt7's design choice cuts the other way. Recording an interruption as a shorter result produces rows with low throughput and short duration that M-Lab's views later flag (IsShort, see the earlier note). The project must keep "interrupted" as a categorical outcome alongside bytes and duration. Otherwise a disconnection masquerades as a slow test.
- FCC/SamKnows shows the community's habit at its most explicit: availability failures are recorded, then excluded by rule from performance. For an ISP benchmark that is defensible. For room labels, check 4 is exactly the operation that produced "43 successes, 0 failures".

### Gaps
- I did not find RTR's published statistics on the share of ERROR or ABORTED tests, so I cannot say how common failed attempts are in a large crowdsourced Wi-Fi dataset.
- Ookla's and SamKnows' own documentation on failed or aborted tests was not read (blocked, or not found).
- The ndt7 server-side record for interrupted tests (whether the archive keeps a partial measurement) was not verified in the server code.

## 3. Statistical treatment: two-part models, intervals for few attempts, attempts per room

### Takeaway
Treat each room's attempts as a two-part outcome: a binary "attempt usable" part (Wilson or Jeffreys interval), plus a performance distribution conditional on success. The health-econometrics literature argues that the two-part model beats Heckman or Tobit selection models unless a credible exclusion restriction exists, and the project has none. Small samples are the hard limit. With 40 attempts, a room whose true failure rate is 20% gets flagged as "failure rate significantly above 10%" only about 56% of the time. A failure rate near 10% needs about 140 attempts for a ±5-point interval. Labels must therefore allow an explicit "indeterminate" outcome, or pool information across rooms.

### Cited Findings
**Two-part (hurdle) versus Heckman/Tobit.** Belotti, Deb, Manning & Norton, "twopm: Two-part models", *Stata Journal* 15(1):3–20, 2015. — [PDF](https://ageconsearch.umn.edu/record/271681/files/sjart_st0368.pdf)
- In a two-part model "a binary choice model is fit for the probability of observing a positive-versus-zero outcome. Then, conditional on a positive outcome, an appropriate regression model is fit for the positive outcome." Cragg (1971) developed it "as an extension of the tobit model". The count-data counterpart is the "hurdle" model. — [Belotti et al. 2015](https://ageconsearch.umn.edu/record/271681/files/sjart_st0368.pdf)
- "the two-part model should not be viewed as being nested within the Heckman selection model … The two-part model does not make any assumption about the correlation between the errors". In addition, "the zeros in the Heckman selection model denote censored values of the positive outcome, while zeros in the two-part model are true zeros." — [Belotti et al. 2015](https://ageconsearch.umn.edu/record/271681/files/sjart_st0368.pdf)
- Monte Carlo evidence: without exclusion restrictions, "the two-part model generally produces better estimates of the conditional mean and of marginal effects than the correctly specified generalized tobit model … the correlation parameter is very poorly identified." The two-part model "is almost always an adequate (if not superior on precision grounds) way" when no exclusion restrictions exist. — [Belotti et al. 2015](https://ageconsearch.umn.edu/record/271681/files/sjart_st0368.pdf)
- Secondary source: Heckman correction requires an exclusion restriction (a variable that affects selection but not the outcome). Without one, identification rests on functional form alone. — [Wikipedia: Heckman correction](https://en.wikipedia.org/wiki/Heckman_correction) (secondary)

**Binomial intervals.** Brown, Cai & DasGupta, "Interval Estimation for a Binomial Proportion", *Statistical Science* 16(2):101–133, 2001, DOI [10.1214/ss/1009213286](https://doi.org/10.1214/ss/1009213286). **Abstract-level only, via search excerpts; full text not opened.**
- The Wald interval's coverage is "chaotic" and textbook prescriptions are "misleading and defective". The authors recommend the Wilson or equal-tailed Jeffreys interval for small n and Agresti–Coull for larger n. — [search excerpt of Brown et al.](https://doi.org/10.1214/ss/1009213286) (unverified against full text)
- In the same issue, Agresti & Coull's comment describes Clopper–Pearson as inverting "an 'exact' test" and as a de facto gold standard. Its conservativeness (wider than nominal) is a widely known property, but I did not verify it in the paper. — [search excerpt](https://users.stat.ufl.edu/~aa/articles/agresti_coull_2001.pdf) (not opened)

**My computations (95% two-sided, failure proportion k/n):**

| attempts (failures / n) | Wilson | Clopper–Pearson | Jeffreys |
|---|---|---|---|
| 0/10 | 0–27.8% | 0–30.8% | 0–21.7% |
| 0/20 | 0–16.1% | 0–16.8% | 0–11.7% |
| **0/43 (kitchen if 43 were all attempts)** | **0–8.2%** | **0–8.2%** | **0–5.6%** |
| 2/20 | 2.8–30.1% | 1.2–31.7% | 2.1–28.4% |
| 4/40 | 4.0–23.1% | 2.8–23.7% | 3.5–22.0% |
| 6/30 | 9.5–37.3% | 7.7–38.6% | 8.8–36.7% |
| 10/100 | 5.5–17.4% | 4.9–17.6% | 5.3–17.0% |

- Attempts needed for a Wilson 95% half-width of ±10 points: 24 (p = 5%), 34 (10%), 60 (20%), 78 (30%). For ±5 points: 82, 141, 245 and 320. — own computation
- Detection power of the rule "label `ruim` if the Wilson lower bound of failure rate exceeds 10%". At true p = 20%, power is 0.37 at n = 20, 0.56 at n = 40, 0.68 at n = 60 and 0.87 at n = 100. At true p = 30%, power is 0.76 at n = 20 and 0.94 at n = 40. The false-alarm rate at true p = 2% is at most 0.001 for all n ≥ 10. — own computation (exact binomial)
- Padmanabhan et al.'s reporting rule (n ≥ 40 and nλ̂(1−λ̂) ≥ 10) gives about 110 attempts at a 10% rate. This is the same order as the Wilson ±5-point figure. — [Padmanabhan et al., SIGCOMM 2019](https://thunderping.cs.umd.edu/papers/sigcomm19-weather.pdf) (from the earlier note)

### Inferences
- **The kitchen case, quantified.** If the 43 successes really were all the attempts, the failure rate is below 8.2% with 95% confidence, so the data positively contradict "Ausente". Either the denominator is missing (failures not logged), or the resident's "Ausente" describes times and activities at which no test was ever attempted. That would be an accessibility failure in E.800 terms (section 4), invisible to any test-gated log. Both explanations point to the same fix: scheduled attempts, where "no Wi-Fi at the scheduled time" is itself an outcome, plus a time-based connected fraction from the event stream.
- **Recommended structure** (two-part, following Belotti et al.): part 1 is P(attempt usable | room), where usable means started, completed and not interrupted. Part 2 is the throughput or latency distribution | completed. The unconditional quantity that maps to experience is P(usable AND performance ≥ floor) = P(usable) × P(perf ≥ floor | usable). This is exactly Baltrunas' pair of metrics (section 4).
- **Why not Heckman or Tobit.** There is no exclusion restriction. A Heckman variable would have to change completion without changing link throughput. A candidate such as "OS killed the app" (Doze or battery saver) is plausible but would be very weak. Belotti's argument therefore favours the two-part model. Tobit at a floor is acceptable only for the `timeout_partial` outcome code, where bytes did flow.
- **Few attempts.** Use Wilson (or Jeffreys) intervals and a three-way decision: ruim if the lower bound exceeds the cut, bom if the upper bound falls below the cut, and indeterminate otherwise. Per-building partial pooling (for example a beta-binomial with a building-level prior) would shrink rooms with few attempts toward their building's rate. This is a standard technique, but no source on it was opened in this session.
- **Attempts per room.** Separating 5% from 20% failure rates reliably takes roughly 40–60 usable attempts per room and condition. Ruling out a 10% failure rate when the true rate is 0 needs at least 35 attempts (the Wilson upper bound at 0/30 is 11.4% and at 0/35 is 9.9%, own computation). Sessions should therefore schedule many short attempts (for example a 3 s probe every 30–60 s) rather than a few 11 s tests.

### Gaps
- The full text of Brown et al. 2001 was not read; the recommendations above are from abstract excerpts.
- No source was opened on hierarchical or beta-binomial pooling, or on sequential stopping rules (how to stop a session early once the label is clear).
- I found no network-measurement paper that applies a two-part model to speed-test outcomes. The structure is borrowed from health econometrics plus Baltrunas' metric pair.

## 4. Filling the gaps: Baltrunas IMC 2014, E.800 definitions, Grover IMC 2013, Heckman/Tobit in network data

### Takeaway
Baltrunas et al. (full text now read) is the closest published template. It measures reliability at three levels (connection, data plane, application). It logs **every** reconnection attempt. It merges flapping into events with a 3-minute rule. Its application metrics are P(download completes) and P(rate ≥ 1 Mbps) over hourly attempts with error codes. Radio quality explains much but not all downtime. E.800's vocabulary of accessibility, retainability and integrity gives the project a formal split for "could I get service / did it last / how good was it". Grover IMC 2013 remains closed-access. No network-measurement use of Heckman or Tobit on failed tests was found.

### Cited Findings
**Baltrunas, Elmokashfi, Kvalbein, "Measuring the Reliability of Mobile Broadband Networks", ACM IMC 2014, pp. 45–58** — [PDF (SIGCOMM mirror)](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Framework: reliability "must be assessed at several levels, from the availability of the network connection to the stability of application performance". The levels are network (failures, availability, radio conditions), data plane (packet loss, loss runs, large events) and application (HTTP throughput, SIP success rate). — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Setup: Norway's NNE, several hundred stationary indoor nodes, 5 operators, 10 months. — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Connection failures: the node "continuously monitors the status of the" connection, retries immediately with no hold time, and "we log all these attempts". Consecutive attempts spaced by less than M minutes are grouped into one event, so "a connection must keep its PDP context for at least M minutes before the reconnection was deemed successful". They detected 154,772 failures at M = 1 min. The count dropped only 0.019% at M = 3 but 3% at M = 4 and 4.9% at M = 5, so they chose M = 3, which "captures well what the user perceives as a usable connection, since a connection is not worth much if it flaps at a high frequency." — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Artifact control: they "discard all failure events that were rectified either by rebooting the node or actively resetting the USB modem". They also keep only failures "that have well defined starting and ending points". — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Metrics: MTBF, MTTR and downtime percentage per connection. "15-38% of connections are unavailable more than 10 minutes per day on average." One operator has "frequent but short-lived failures", while others have longer time between failures "but a higher overall downtime". — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Radio explains part of the downtime only. Downtime is higher at one signal bar, but "we experience downtime in 5% of the hours characterized by a good Ec/Io. This indicates that radio quality can not alone explain all connection failures." RSSI correlates less than Ec/Io because RSSI "include[s] all received components (i.e. signal and noise)". — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Data plane: one UDP packet per second to an echo server. A "loss run" of k packets therefore lasts about k seconds without traffic. Runs of 5–6 s were traced to RRC state demotions. — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Application: a 1 MB HTTP GET once per hour for 3 weeks ("up to 504 runs per connection"). "For each test iteration, we record the time it took to start the data transfer, the total time to complete the download (if successful), throughput, and any error code." The reported metrics are "the probability of successfully completing the transfer, and the probability of achieving a download rate of at least 1 Mbps." For Telenor, "55% … experience a failure rate higher than 5%, and 12% … higher than 10%". — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Failure causes come from error codes. For most operators the dominant cause was "the failure to establish the connection", and these failed handshakes coincided with high packet loss. For Telenor, "the connection broke after the initial TCP handshake in 74% of the failing attempts". For VoIP, 13–34% of failures occurred at call setup (SIP INVITE) and the rest were dropped calls. — [Baltrunas et al. 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)

**CCITT E.800 (1988 Blue Book text, republished 1992; superseded; the in-force edition is 09/2008)** — [MIT mirror of E.800 text](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc); [ITU-T E.800 listing](https://www.itu.int/rec/T-REC-E.800)
- Serveability "may be subdivided into the service accessibility performance and the service retainability performance". — [E.800 (1988/1992)](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc)
- 5301, service accessibility: "The probability that a service can be obtained within specified tolerances and other given operating conditions when requested by the user." — [E.800 (1988/1992)](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc)
- 5401, service retainability: "The probability that a service, once obtained, will continue to be provided under given conditions for a given time duration." 5404, premature release probability: "The probability that an established connection will be released for a reason other than intentionally by any of the parties". — [E.800 (1988/1992)](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc)
- 3107, service integrity: "The degree to which a service is provided without excessive impairments, once obtained." — [E.800 (1988/1992)](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc)
- Dependability "relates to the ability of an item to be in a state to perform a required function" and is quantified as availability, reliability and maintainability performance. Measures "may be related to an instant of time … or expressed as a mean value over a time interval". The section 4 terms include interruption, interruption duration, mean time between interruptions (MTBI) and mean interruption duration (MID). — [E.800 (1988/1992)](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc)
- Caveat: whether the 2008 edition kept this wording was not verified. A search summary says the 2008 edition (09/08) is the one in force. — [ITU-T E.800 listing](https://www.itu.int/rec/T-REC-E.800)

**Grover et al., "Peeking Behind the NAT: An Empirical Study of Home Networks", ACM IMC 2013, pp. 377–390, DOI [10.1145/2504730.2504736](https://doi.org/10.1145/2504730.2504736)**
- Still not accessible: open access is CLOSED per Semantic Scholar, and the SIGCOMM mirror returns 404. A search-level summary says it is the first empirical study of home network **availability**, infrastructure and usage via custom-firmware routers, and that downtime is "more frequent and longer" in developing countries. No numbers were verified. — [Semantic Scholar record](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/2504730.2504736); [Princeton record](https://collaborate.princeton.edu/en/publications/peeking-behind-the-nat-an-empirical-study-of-home-networks/)

**Heckman/Tobit as applied to network data**
- Searches found no network-measurement study that applies Heckman selection or Tobit to failed speed tests. The results were generic econometrics pages only. The methodological case against them for this setting is in section 3 (Belotti et al.). — [search result: Wikipedia, Heckman correction](https://en.wikipedia.org/wiki/Heckman_correction) (secondary)

### Inferences
- **E.800 mapped to the project.** *Accessibility*: when a scheduled attempt fires, the phone is associated to the home Wi-Fi with a working gateway path (associated, IP, DNS, test started). *Retainability*: a started attempt finishes without loss of association or a stall. *Integrity*: throughput, latency or loss given completion. The current dataset measures only integrity, conditional on accessibility and retainability both succeeding. That is exactly why the kitchen looks good.
- **Baltrunas' grouping rule applies to Wi-Fi.** Merge `onLost`/`onAvailable` flaps closer than M (try 1–3 min, with a sensitivity table like theirs) into one outage event. Report MTBF, MTTR and downtime per room-hour. Their artifact rule translates to discarding outages caused by the collector itself, such as app restarts, OS kills, or a user toggling Wi-Fi. These need logging, so that they can be excluded rather than confused with the room.
- **The 1-packet-per-second probe is cheap and decisive.** A 1 Hz UDP or ICMP echo to the gateway during sessions yields loss runs, and Baltrunas shows that runs of several seconds matter for interactive apps. An 11 s TCP test averages them away.
- **"Radio does not explain everything"** (5% of good-Ec/Io hours with downtime) supports keeping availability as its own label component instead of inferring it from RSSI.

### Gaps
- The exact 2008 E.800 wording, and any newer ITU or ETSI Wi-Fi or Internet-access QoS definitions (for example ITU-T E.804 or ETSI TS 102 250 for mobile), were not read.
- Grover IMC 2013 numbers (downtime frequency, Wi-Fi spectrum crowding) remain unverified.
- Baltrunas' dataset is cellular with stationary nodes. Transfer to home Wi-Fi is by analogy, and their PDP-context failure is not the same mechanism as 802.11 disassociation.

## Implicações para o projeto

### Takeaway
The V2 collector should be an Android-first, attempt-logging, event-logging instrument built on RTR's and Baltrunas' patterns. A room label should be a two-part decision: usable-attempt probability, with a Wilson interval, gating performance floors. An explicit "indeterminate" outcome is needed when attempts are too few. Until that data exists, the kitchen cannot be labelled from the current data. Its 43/0 record either lacks the denominator or describes moments that were never tested.

### Cited Findings
- Row at start, finish reason, last phase, previous-test status on the next request: [open-rmbt-android](https://github.com/rtr-nettest/open-rmbt-android); [open-rmbt-database schema](https://github.com/rtr-nettest/open-rmbt-database)
- Log every attempt; group flaps with M = 3 min; report P(complete) and P(rate ≥ floor) with error codes: [Baltrunas et al., IMC 2014](https://conferences.sigcomm.org/imc/2014/papers/p45.pdf)
- Accessibility, retainability and integrity as separate probabilities: [E.800 (1988/1992 text)](https://stuff.mit.edu/afs/net/dev/reference/ccitt/1992/e/e800.asc)
- Two-part over Heckman without an exclusion restriction: [Belotti et al. 2015](https://ageconsearch.umn.edu/record/271681/files/sjart_st0368.pdf)
- Android callbacks, WifiInfo fields, location redaction, Doze, WorkManager 15 min, dataSync 6 h/24 h: [NetworkCallback](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback); [WifiInfo](https://developer.android.com/reference/android/net/wifi/WifiInfo); [Doze](https://developer.android.com/training/monitoring-device-state/doze-standby); [PeriodicWorkRequest](https://developer.android.com/reference/androidx/work/PeriodicWorkRequest); [Android 15 changes](https://developer.android.com/about/versions/15/behavior-changes-15)
- iOS gives only SSID, BSSID and security type: [Apple fetchCurrent](https://developer.apple.com/documentation/networkextension/nehotspotnetwork/fetchcurrent(completionhandler:))
- FCC/SamKnows removes whitebox-hours with 10% or more failures from performance: [MBA 2023 Technical Appendix](https://data.fcc.gov/download/measuring-broadband-america/2023/Technical-Appendix-fixed-2023.pdf)

### Inferences
Prioritized actions. P0 needs no new hardware, P1 is the V2 build, and P2 comes after V2 data exists.

**P0: before any V2 collection**
1. **Freeze the kitchen.** Mark `villa_res_cozinha` as "not labelable from current data" and remove it from ruler comparisons. Write down the reason: 0/43 implies a failure rate below 8.2% if complete, which contradicts "Ausente", so the denominator or the tested moments are missing. Search router or DHCP or association logs for attempts in that period. If none exist, the decision stands.
2. **Pre-register the label rule (written before data), using a two-part, E.800-style rule per room and condition:**
   - Accessibility A = share of *scheduled* attempts that found the phone on home Wi-Fi with a working gateway path.
   - Retainability R = share of started attempts that completed without `onLost`, roam-loss or stall.
   - Usable U = A × R, with a Wilson interval on the attempt-level U.
   - Integrity = performance among completed attempts (p10 and median throughput, gateway RTT p90, 1 Hz loss runs), judged against absolute floors from the application-label note.
   - **ruim** if the Wilson upper bound of U is below 0.90, **or** if P(perf ≥ call/video floor | completed) has an upper bound below 0.80. **bom** if the Wilson lower bound of U is at least 0.95 **and** the performance floors pass with lower bound at least 0.90. **degradado** if both are well estimated and neither ruim nor bom applies. **indeterminado** otherwise.
   - The cut values here are placeholders for the team to set. The structure is what this research supports.
3. **Adopt Baltrunas' combined metric as the headline number per room:** P(attempt completes AND throughput ≥ floor), with a Wilson interval. It is one number that a failed attempt can no longer improve.

**P1: V2 collector specification (Android)**
4. **Attempt table, written at start.** Create a local row and a server row with status `STARTED` before the first byte. Fields: attempt id, scheduled or user trigger, room, device, app version. On finish, update with status, `last_phase` (init, ping, down, up), an outcome enum (`ok`, `no_wifi_at_start`, `fell_back_to_cellular`, `dns_fail`, `connect_fail`, `disconnect_mid_test`, `stall_timeout_partial`, `server_error`, `app_killed`), bytes, elapsed ms and error text. The next request carries `previous_attempt_status`, and server-side `STARTED` rows older than 60 s become `lost`.
5. **Event stream, independent of tests.** A Wi-Fi-transport `NetworkCallback` (with `FLAG_INCLUDE_LOCATION_INFO`) plus a default-network callback. Log `onAvailable`, `onLost`, `onLosing`, `onBlockedStatusChanged` and `onCapabilitiesChanged`, together with screen, charging and Doze state. Also log app lifecycle events, so collector artifacts can be excluded as Baltrunas did.
6. **Radio sampler at 1–5 s during sessions:** RSSI, Tx/Rx link rate, frequency, Wi-Fi standard, BSSID and max supported rate. Request `ACCESS_FINE_LOCATION`, because BSSID is otherwise `02:00:00:00:00:00`.
7. **1 Hz gateway echo during sessions** gives loss runs and RTT. Bind all probes and tests to the Wi-Fi `Network`, so a cellular fallback becomes a failure instead of a fast result.
8. **Session protocol shaped by OS limits.** Run attended room sessions in a foreground service, with the screen on, for example 15–20 minutes per room: a short probe (about 3 s) every 30–60 s plus a few full tests. Run optional plugged-in overnight passive logging. Do not rely on WorkManager (15 min minimum, deferred in Doze) or on an unplugged background `dataSync` service (6 h/24 h on Android 15).
9. **Attempts per room and condition: at least 40, ideally 60.** At 40 attempts a 30% failure room is caught 94% of the time, but a 20% room only 56% of the time. Report Wilson intervals and the indeterminate class, never point rates alone.
10. **iOS:** outcomes and path changes only. Do not use iOS rows to train radio features.

**P2: after V2 data exists**
11. **Fit the two-part model:** logistic P(usable | room features, radio, building), plus a performance model conditional on completion. Report both parts. Do not use Heckman or Tobit unless a defensible exclusion restriction appears; Tobit is acceptable only for `stall_timeout_partial`.
12. **Sensitivity checks:** vary the flap-merge window M (1–5 min) and the cuts, and publish a table like Baltrunas'. If labels flip under small changes, the label is not robust.
13. **Map phone-side outcomes to router-side TR-181 features later** (association and disassociation counters, for example) so that the deployed model can predict availability without the phone. This is the open item in the TR-069 note.

### Gaps
- None of the cut values (0.90, 0.95, 0.80) comes from a validated source; they are placeholders for pre-registration.
- Whether residents' "Ausente" judgments track A (accessibility) or R (retainability) more closely is untested. The V2 subjective-label protocol should ask about *what failed* (couldn't connect, or dropped during use) to tell the two apart.
- Battery cost of a 1 Hz echo plus a 1–5 s radio sampler on mid-range Android phones was not measured or researched.

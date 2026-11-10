# Objective application-level QoE labels: going deeper, toward a buildable V2 test harness

Scope note: these notes extend `rotulos_objetivos_aplicacao.md` (not modified) and the draft report `reports/Rótulos de QoE em WiFi doméstico.md`. The aim is a V2 harness that a phone app can run per room and that yields bom/degradado/ruim labels with failures logged. Every item says how deeply I read it: full text, relevant sections, abstract only, or snippet. Research date: 2026-11-09. Downloads went only to the session scratchpad. No browser automation was used.

---

## 1. Player-side measurement APIs: what still works on YouTube and what replaces it

### Takeaway
The YouTube IFrame API **can no longer set or read playback quality**. The English revision history dates the change to **24 Oct 2019**, and it says the change had already been in effect "for over a year". So the plan from the earlier notes, "forced-resolution YouTube sessions via the API", **cannot be built with the API**.

What remains in the IFrame API:
- player states, including buffering (3);
- `onPlaybackQualityChange`, which reports a coarse label (`small` … `hd1080`, `highres`);
- `getVideoLoadedFraction` and `getCurrentTime`;
- `onAutoplayBlocked`, added in 2023.

Frame-level and pixel-level data, such as `getVideoPlaybackQuality()` (dropped and total frames) and `videoHeight`, come from the HTML `<video>` element. They are only reachable when the harness runs JavaScript *inside* the page that owns the video. YoMoApp did this by injecting JS into an Android WebView that loads m.youtube.com. A self-hosted player (ExoPlayer/Media3, dash.js) also qualifies.

### Cited Findings
- **The IFrame API reference no longer lists `getPlaybackQuality`, `setPlaybackQuality` or `getAvailableQualityLevels`.**
  - It still documents `onPlaybackQualityChange`: "fires whenever the video playback quality changes", with values `small, medium, large, hd720, hd1080, highres`.
  - Player states: −1 unstarted, 0 ended, 1 playing, 2 paused, 3 buffering, 5 cued.
  - `getVideoLoadedFraction`: the fraction "the player shows as buffered".
  - `setPlaybackRate`: "does not guarantee that the playback rate will actually change".
  - Minimum embed viewport: 200×200 px.
  - `onAutoplayBlocked` fires when "the browser blocks autoplay or scripted video playback".
  - (Page read, 2026-11-09.) — [YouTube IFrame Player API reference](https://developers.google.com/youtube/iframe_api_reference)
- **Revision history, 24 Oct 2019 entry** (the English page; translated pages give conflicting dates, so I used the English one):
  - "The documentation has been updated to reflect the fact that the API no longer supports functions for setting or retrieving playback quality."
  - "The getPlaybackQuality, setPlaybackQuality, and getAvailableQualityLevels functions are no longer supported."
  - The queueing functions "no longer support the suggestedQuality argument".
  - "The onPlaybackQualityChange event is still supported".
  - A second entry, 20 Nov 2023: "The new onAutoplayBlocked event API is now available." — [IFrame API revision history](https://developers.google.com/youtube/iframe_api_revision_history)
- **The YouTube embedded-player parameters page has no quality (`vq`) parameter.** It documents `enablejsapi=1` (enables API control) and recommends always setting `origin`. — [Player parameters](https://developers.google.com/youtube/player_parameters)
- **`HTMLVideoElement.getVideoPlaybackQuality()`** returns a `VideoPlaybackQuality` object with "metrics including how many frames have been lost".
  - `totalVideoFrames` "includes any dropped or corrupted frames".
  - MDN status: "Baseline: Widely available … since February 2020".
  - Spec: W3C Media Playback Quality. — [MDN getVideoPlaybackQuality](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/getVideoPlaybackQuality)
- **YoMoApp shows how to get `<video>`-level data on a phone** (Wamser et al., EuCNC 2015, DOI 10.1109/EuCNC.2015.7194076; full text read from the Augsburg repository).
  - The app loads the mobile YouTube website in an Android WebView. It injects JavaScript that "analyzes the HTML video content", polling the player element "every second".
  - Logged fields: `buffered`, `played`, `currentTime`, height/width, `totalVideoFrames`, `droppedVideoFrames`, `corruptedVideoFrames`, plus device and network data.
  - The authors warn that JavaScript "can sometimes introduce inconsistencies and obvious errors, e.g., missed player events, non-equidistant" samples, so post-processing is needed. With that, the tool was accurate "on a sufficiently small time scale (~1 s)". — [YoMoApp EuCNC 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107427/107427.pdf)
- **YouQ (Zagreb) took the IFrame route on Android** and logged quality-change events (`hd1080`, `hd720`, `large`=480p, `medium`, `small`, `tiny`), a per-second buffer log and the HTTP request URLs (2016). This was possible while quality events still carried the label, and the event still exists. — [Orsolic et al., QoEMC 2016 PDF](https://www.fer.unizg.hr/images/50020698/YouTube_QOEMC_2016.pdf)
- **"Stats for nerds"** is a user-facing overlay with a "Copy debug info" option. I found no documentation for any programmatic interface. Searches for the internal `getStatsForNerds` method returned nothing authoritative. — [YouTube Help 7519898 (search snippet)](https://support.google.com/youtube/answer/7519898)
- **Chrome DevTools Media panel:** Properties, Events, Messages, and a Timeline that shows "media playback and buffer status live". The page says nothing about resolution or dropped frames, and nothing on whether it replaces `chrome://media-internals`. — [Chrome DevTools Media panel](https://developer.chrome.com/docs/devtools/media-panel)
- **ExoPlayer/Media3 `PlaybackStats`**, marked `@UnstableApi`, gives session QoE directly:
  - `getMeanJoinTimeMs()` (startup);
  - `totalRebufferCount`;
  - `getTotalRebufferTimeMs()` and `getMeanRebufferTimeMs()`;
  - `getMeanVideoFormatHeight()`;
  - `totalDroppedFrames`;
  - `abandonedBeforeReadyCount`, "playbacks which were abandoned before they were ready to play";
  - a playback-state history with an explicit `PLAYBACK_STATE_ABANDONED`. — [Media3 PlaybackStats reference](https://developer.android.com/reference/androidx/media3/exoplayer/analytics/PlaybackStats)

### Inferences
- **Forcing a resolution is no longer possible through YouTube's public API.** There are three ways to get a "known-bitrate capacity probe":
  - (a) Script the quality menu in the YouTube UI. This is brittle, breaks with UI changes, and may conflict with YouTube's terms (not checked).
  - (b) Use **self-hosted DASH/HLS content** in ExoPlayer (Android) or dash.js/hls.js (browser), pinning one representation, e.g., 1080p at a known bitrate. You then control the bitrate, have no ads, and get `PlaybackStats` for free.
  - (c) Use plain progressive MP4 files at fixed bitrates.

  Option (b) is the most reproducible. It also removes the confounders the literature flags: ads, CDN choice, and per-location ad strategies (see Section 2).
- **Keep a YouTube session as well, for ecological validity, in observation mode only.** Use an unlisted video the project uploads itself, so the content is fixed. Run it in auto-ABR and read states, buffering and the coarse quality label from the IFrame API (a single fixed URL works). Better still, use a YoMoApp-style WebView with injected JS so that `videoHeight`, `buffered` and `getVideoPlaybackQuality()` are available every second.
- **An IFrame embed is cross-origin**, so the host page cannot read the inner `<video>`. Pixel-level data therefore needs the WebView/injection route or an extension (standard same-origin policy; I did not re-check it in a source this pass).
- The quality-change event maps 1440p and 2160p to a single `highres` label. Resolution from the IFrame API is therefore coarse at the top end. On phones this barely matters (Section 2: YoMoApp image MOS ≥ 4.17 in all conditions).

### Gaps
- I could not open the CDP `Media` domain reference page (it only returned a redirect stub). So I could not confirm which events (e.g., `playerPropertiesChanged`, `playerEventsAdded`) are exposed or whether the domain is experimental.
- YouTube's Terms of Service and API policies on automated playback and scripted UI interaction were not checked.
- I did not test whether m.youtube.com still exposes a plain `<video>` element reachable by injected JS inside an Android WebView in 2026, or whether it shows ads on unlisted uploads. YoMoApp's evidence is from 2015.

---

## 2. Open-source and research tools for automated video QoE on phones and PCs

### Takeaway
A reusable lineage exists:
- **YoMo** (Firefox add-on);
- **YoMoApp** (Android WebView with injected JS, validated in a 52-person lab study);
- **MONROE YoMo** (headless Firefox in Docker);
- **YouQ** (Android app on the IFrame API, rule-based 3-class labels);
- **Orsolic & Seufert 2021** (Selenium and Chrome at two sites).

Two results matter most for this project. First, on smartphones, resolution adaptation barely moves perceived image quality, and stalls are only disturbing under outages. Second, every collection campaign lost a share of sessions to failures, which most papers drop. I found no public code for the Bronzino/Princeton Chrome extension. The same group's public repository (vcaml) covers WebRTC only.

### Cited Findings
- **YoMoApp, EuCNC 2015 full paper and MobiCom 2015 poster (DOI 10.1145/2789168.2795176), both read.**
  - Lab study: **52 participants** (29 female, 23 male, mean age 32), Samsung Galaxy S4 on Android 4.4, on Wi-Fi APs, with NetEm shaping.
  - Conditions: constant 1, 2 and 4 Mbps; "var" (1→3 Mbps bursts, mean 1.5 Mbps); "out" (4 Mbps with 10 s outages twice per minute, mean 2.7 Mbps).
  - Share of sessions with no stalling: 93.48% at 4 Mbps, 95.12% at 2 Mbps, 85.00% at 1 Mbps (one 22 s outlier). Stalling occurred in 14.63% of var sessions and 78.57% of out sessions (mean 25 s, max 41 s).
  - Stalling-disturbance MOS: ≥ 4.4 for 1, 2, 4 Mbps and var; **2.83 only for the outage condition**.
  - **Image-quality MOS was ≥ 4.17 in every condition.** The authors note that resolution adaptation "does not have a big impact on the subjectively perceived image quality, which is most probably linked to the small display size of smartphones".
  - The maximum quality was 720p because of the device. — [YoMoApp poster PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107494/107494.pdf); [YoMoApp EuCNC PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107427/107427.pdf)
- **Schwind, Seufert, Alay, Casas, Tran-Gia, Wamser, "Concept and Implementation of Video QoE Measurements in a Mobile Broadband Testbed", TMA 2017 MNM workshop (full text read).**
  - The YoMo Firefox add-on records a snapshot every second (playback time, buffered playtime, resolution) plus player events. It runs headless in MONROE nodes, always with the same baseline video, which is available up to 2160p.
  - "Measurements of 13 video streaming sessions could not" be completed "for unknown reasons", so "only the results of 89 successful measurements" were analysed.
  - Mean initial delay was 6.43 s (1.32–18.09 s). 77.58% of sessions had no stalling.
  - A precedent for logging failures, and also for losing them. — [MNM 2017 PDF](https://dl.ifip.org/db/conf/tma/tma2017/mnm2017_paper10.pdf)
- **Orsolic, Pevec, Suznjevic, Skorin-Kapov, "YouTube QoE Estimation Based on the Analysis of Encrypted Network Traffic Using Machine Learning" (full text read).** QoEMC 2016 workshop; I take Globecom 2016 from the filename and search snippets, and did not verify it on the paper.
  - The YouQ Android app plays videos through the **IFrame API** and logs the event, buffer and URL logs. Data: 1,060 videos over 39 bandwidth scenarios.
  - **Rule-based 3-class label (high/medium/low).** "High" needs `checkHigh < 1`, built from the normalised share of time on high quality (hd1080/hd720/large) and the stall duration. The normalisation is 0 if PHQ > 90% and 1 if PHQ < 80%; for stall duration, 0 if SD < 3 s and 1 if SD > 5 s. The condition on stall count is garbled in the PDF text; it appears to require at most one stall.
  - "Low" holds if the sum of four normalised factors is ≥ 1, or if any single factor saturates:
    - PLQ: time on low quality, from 50% to 60%;
    - SC: stall count, from 4 to 6;
    - OR: overhead ratio, from 0.08 to 0.12;
    - ASD: average stall duration, from 3 s to 5 s.
  - Everything else is "medium". Result: 333 low, 310 medium, 417 high.
  - The authors caution that these classes "cannot be expressed as a range of MOS values" and are "proposed only for proof-of-concept purposes".
  - Random Forest reached 80.18% on the full set; Naïve Bayes reached 83.94% on the constant-bandwidth subset.
  - Mobile YouTube often never chose hd720 or hd1080: "YouTube assumes that quality level large is good enough … on a small screen". — [YouQ QoEMC 2016 PDF](https://www.fer.unizg.hr/images/50020698/YouTube_QOEMC_2016.pdf)
- **Orsolic & Seufert, "On machine learning based video QoE estimation across different networks", ConTEL 2021, DOI 10.23919/contel52528.2021.9495971 (sections read).**
  - Same Selenium and Chrome framework at Würzburg (campus fibre) and Zagreb (ISP cable), on a laptop behind a Raspberry Pi doing `tc`. Conditions: no limit, 1 Mbps, and an exponential process with mean 1 Mbps. The full list of 2,000 videos was run with and without an ad-blocker.
  - Class splits:
    - MOS from P.1203, high > 3.5;
    - average resolution, ≥ 700p / 400–700p / < 400p;
    - stalling, yes/no;
    - initial delay, < 2 s / 2–10 s / ≥ 10 s.
  - Ad-blocker samples were removed "due to potential impact of different ad strategies enforced by YouTube at different locations", leaving 2,142 samples.
  - Network-specific models lost performance when tested across networks. — [Orsolic & Seufert 2021 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107344/107344.pdf)
- **Orsolic et al., MTAP 2017 (DOI 10.1007/s11042-017-4728-4)**: still inaccessible behind a Springer login. The QoEMC 2016 paper above is its documented precursor. — [Springer DOI](https://doi.org/10.1007/s11042-017-4728-4)
- **Panahi, Jalilvand, Diyanat, arXiv 2406.08564v2, 2024 (preprint, not peer-reviewed; sections read).** An open-source Selenium/Firefox framework. It exports a HAR file, detects stalls by polling the player's on-screen stall indicator every second, and computes ITU-T P.1203 scores. Selenium is also used to skip ads. Methodologically weak (UI-indicator polling), but a usable P.1203 plumbing reference. — [arXiv 2406.08564](https://arxiv.org/pdf/2406.08564v2)
- **noise-lab/vcaml (IMC 2023, DOI 10.1145/3618257.3624828; README read).**
  - Ground-truth labels come from **`chrome://webrtc-internals` JSON dumps**, paired with `tcpdump` pcaps, for Meet, Teams and Webex.
  - Metrics: `framesReceivedPerSecond`, bitrate, frame jitter, `frameHeight`. FPS accuracy is scored at ±2 fps.
  - The repository was last pushed in June 2026. No video-streaming (Bronzino) extension appears in the noise-lab organisation's repository list (GitHub API listing, 2026-11-09). — [vcaml](https://github.com/noise-lab/vcaml)
- **Hoßfeld, Seufert, Sieber, Zinner, "Assessing effect sizes of influence factors towards a QoE model for HTTP adaptive streaming", QoMEX 2014, DOI 10.1109/qomex.2014.6982305 (full text skimmed).** A crowdsourced study. Their simplified HAS QoE model "only relies on the switch amplitude and the playback time of each layer". They conclude that "the number of switches needs not be optimized in first place", and that up-switching early raises time on the highest layer. — [Hoßfeld 2014 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107445/107445.pdf)

### Inferences
- **For a phone-based V2, YoMoApp is the closest validated template.** It uses a WebView, injects JS that polls `<video>` every second (`currentTime`, `buffered`, `videoHeight`, `getVideoPlaybackQuality()`), and post-processes the samples.
- **Its own subjective result suggests resolution is a weak label component on phones.** Under realistic constant bandwidths, people barely noticed adaptation or the short stalls. Only outages (10 s drops) produced a clearly bad MOS (2.83). This matches the draft report's "instability" hypothesis: an outage-like pattern in a room is what users perceive as bad. It also argues for weighting stalls, outages and failed sessions over resolution.
- **YouQ's rule is a published precedent for exactly what the project needs.** It is a deterministic 3-class label from player KPIs with linear ramps between thresholds (3–5 s stall duration, 4–6 stalls, 80–90% time on high quality). Its thresholds are ad hoc, as the authors admit, but the ramp structure is reusable.
- Neither the MONROE paper nor most others count failed sessions as an outcome, though failures are common (13 of 102 attempts in MONROE). The V2 harness should count them, as the draft report already recommends.

### Gaps
- I did not locate Bronzino et al.'s Chrome extension code or the technical report with their rebuffering models.
- YoMoApp's validation is from 2015 (Android 4.4, ≤ 720p). Whether the WebView/m.youtube.com approach still works was not tested.
- No open-source Playwright or Puppeteer YouTube QoE harness with a published validation turned up. The search found only Selenium-based ones.

---

## 3. WebRTC getStats for video calls, and mappings to user ratings

### Takeaway
W3C webrtc-stats (Candidate Recommendation Draft, 25 Sep 2025) now standardises freeze and pause counters:
- a freeze is a gap ≥ max(3·avg frame duration, avg + 150 ms) over the last 30 frames;
- a pause is more than 5 s without a rendered frame.

It also standardises dropped frames, FPS, jitter-buffer delay and inter-frame delay sums. These can be logged per second at both ends of a self-made call.

There is **no standard mapping** from these counters to MOS. The evidence available:
- Microsoft's documented operational thresholds (CQD: video "poor" if average FPS < 7, frame loss > 50%, or post-FEC loss > 0.15; a learned freeze classifier);
- an older subjective study (van Kester et al., SPIE 2011, 23 viewers): a single freeze longer than about **0.36 s** drops MOS below 3.5;
- one Wi-Fi video-telephony study (Mallesham et al., arXiv 2019, 200+ raters), whose 3-class thresholds were tuned on the test labels.

Via (SIGCOMM 2016) links network metrics to Skype poor-call rate (PCR) only for audio calls, and its thresholds are distribution-based, not perceptual.

### Cited Findings
- **W3C "Identifiers for WebRTC's Statistics API", CRD 2025-09-25 (relevant definitions read).**
  - `freezeCount`: "It is a freeze if frame duration … is equal or exceeds Max(3 * avg_frame_duration_ms, avg_frame_duration_ms + 150)", with the average over the last 30 rendered frames.
  - `totalFreezesDuration`: total duration of rendered frames considered frozen, in seconds.
  - `pauseCount`: video is considered paused "if time passed since last rendered frame exceeds 5 seconds". `totalPausesDuration` is the matching total.
  - `framesDropped`: frames dropped before decode or for missing their display deadline. `framesPerSecond`: decoded frames in the last second.
  - `jitterBufferDelay` / `jitterBufferEmittedCount`: average jitter-buffer delay. `jitterBufferTargetDelay` is the target.
  - `totalInterFrameDelay` and `totalSquaredInterFrameDelay` give the variance of inter-frame delay.
  - `concealedSamples` / `totalSamplesReceived`: audio concealment.
  - The fetched part did not include `qualityLimitationReason`. — [W3C webrtc-stats](https://www.w3.org/TR/webrtc-stats/)
- **Microsoft Teams CQD stream classification (page dated 2026-06).**
  - Video "Poor" is decided by the first available metric: local frame loss > 50%, else average frame rate < 7, else post-FEC packet loss > 0.15. Packet utilisation must exceed 500 packets.
  - A separate "Video Poor Due to Freeze Classifier" gives a score from 0 to 1 "generated based on a combination of user experience, freeze duration statistics, and overall call experience". Poor means > 0.246 (client:server) or > 0.524 (client:client).
  - Audio poor: RTT > 500 ms, loss > 0.1, jitter > 30 ms. Microsoft says of these: "this doesn't mean the audio stream was actually of poor quality, nor does it mean the user perceived a quality issue".
  - Streams are "Unclassified" when ICE fails or when the QoE report never arrives (e.g., "because of a network outage"). — [Teams CQD stream classification](https://learn.microsoft.com/en-us/microsoftteams/stream-classification-in-call-quality-dashboard)
- **Microsoft Teams real-time telemetry (page dated 2026-05).**
  - Video "good" thresholds: 25–30 FPS at ≥ 360p, 7–15 FPS at ≤ 270p; RTT < 500 ms.
  - "Source Freeze Count" < 2, defined as "the number of times the camera didn't generate a new frame for more than one second". This is a capture-side metric, not a network one.
  - For application sharing: "Normalized Freeze Duration" < 25 ms of freeze per minute ("Loss-free networks should have a value of 0").
  - The page also classifies Wi-Fi RSSI as Excellent ≥ −50 dBm, Good −51 to −64, and Poor ≤ −65. — [Teams real-time telemetry](https://learn.microsoft.com/en-us/microsoftteams/use-real-time-telemetry-to-troubleshoot-poor-meeting-quality)
- **van Kester, Xiao, Kooij, Brunnström, Ahmed, "Estimating the impact of single and multiple freezes on video quality", Proc. SPIE 7865, 2011, DOI 10.1117/12.873390 (full text skimmed).**
  - 20 s sequences, four content types, **23 subjects**. No perceived difference between frame-halt and frame-drop freezes.
  - "The acceptable freezing time (MOS>3.5) is 0.36 seconds". Other models in their comparison cross MOS 3.5 below 0.53 s.
  - Multiple-freeze model: correlation "higher than 0.9" on the test data. The text also reports Pearson 0.81–0.88 in places.
  - This is IPTV-style viewing, not a two-way call. — [van Kester 2011 PDF](https://nas-new.ewi.tudelft.nl/Publications/2011_vanKester.pdf)
- **Mallesham, Vlachou, Sanadhya, Sahu, Qiu, Kim, Das (Stony Brook / HPE Labs / Facebook), "Handcrafted vs Deep Learning Classification for Scalable Video QoE Modeling", arXiv 1901.03404, 2019 (no venue on arXiv; sections read).**
  - Video telephony (Skype, FaceTime, Hangouts) from a mobile device on enterprise **Wi-Fi**, with `tc` impairments: delay, 10–20% loss, 2–10 Mbps.
  - Metrics: perceptual bitrate, **freeze ratio, freeze length, number of freezes**.
  - MOS from **> 200 users** (two labs plus MTurk) on **800+ samples**, mapped to 3 classes (bad < m1 ≤ average < m2 ≤ good). About 90% median accuracy, about 95% with a CNN-LSTM.
  - Critical point: m1 and m2 were chosen by sliding-window search "to maximize the accuracy", comparing true and predicted labels on test data. That is optimistic, the same "choose cut-offs after seeing labels" problem the draft report flags. — [arXiv 1901.03404](https://arxiv.org/abs/1901.03404)
- **Jiang et al., "Via: Improving Internet Telephony Call Quality Using Predictive Relay Selection", ACM SIGCOMM 2016, DOI 10.1145/2934872.2934907 (full text, relevant sections read).**
  - Data: 430 M sampled Skype **audio** calls over 7 months, 1,905 ASes, 126 countries; 83% wireless, 46.6% international.
  - "For a small random fraction of calls", users rate 1–5. Ratings of 1–2 are "poor", and PCR is the poor-call share. PCR is shown only normalised to its maximum, so absolute PCR is not reported.
  - Binned PCR increases with RTT, loss and jitter, with correlation coefficients 0.97, 0.95 and 0.91. Each bin has at least 1,000 calls.
  - Thresholds RTT 320 ms, loss 1.2% and jitter 12 ms were picked because "over 15%" of calls exceed them. The authors call them "in line with" standards (150 ms one-way, 1% loss). They are averages over the call and can hide bursts. — [Via PDF](https://cs.cmu.edu/~junchenj/via.pdf)
- **Sharma et al. (vcaml), IMC 2023**: FPS and resolution inferred from IP/UDP headers for Meet, Teams and Webex, with WebRTC-internals as ground truth (venue confirmed via the repository README). — [vcaml README](https://github.com/noise-lab/vcaml)
- A vendor blog suggests a freeze ratio under 1% as "production-grade" and over 10% as unacceptable. This is not peer-reviewed and appeared only as a search snippet. — [Fora Soft blog (snippet)](https://www.forasoft.com/blog/article/how-to-test-webrtc-stream)

### Inferences
- **For calls, the V2 should run a self-made WebRTC call:** phone in the room ↔ fixed wired peer, with a fixed pre-recorded video source (as in MacMillan et al.). Poll `getStats()` once per second at **both ends**:
  - the inbound stats at the wired peer give the phone's **uplink**;
  - the inbound stats at the phone give its **downlink**.

  Log `freezeCount`, `totalFreezesDuration`, `pauseCount`, `framesPerSecond`, `framesDropped`, `frameHeight`, jitter-buffer delay (as `jitterBufferDelay/jitterBufferEmittedCount`), `packetsLost`, RTT from `remote-inbound-rtp`, and audio `concealedSamples/totalSamplesReceived`.
- Derive per call:
  - normalised freeze duration (ms of freeze per minute);
  - freezes per minute;
  - the longest freeze;
  - mean FPS, and the share of seconds below 15 FPS;
  - any pause (> 5 s without a frame);
  - call-setup failure (ICE failure or timeout), logged as an outcome.
- **Thresholds with the best available sourcing** (to be pre-registered; none has been validated in homes):
  - **ruim**: call setup failed, or any pause (> 5 s, W3C definition), or mean FPS < 7 (Microsoft CQD video "poor").
  - **degradado**: at least one freeze longer than 0.36 s per minute on average (van Kester: one freeze > 0.36 s already brings MOS below 3.5), or FPS below the Teams "good" band (< 25 at ≥ 360p).
  - **bom**: otherwise.

  The 25 ms/min "normalized freeze" target is Microsoft's figure for **screen sharing**, not camera video, so do not use it for video.
- Via's thresholds come from the call distribution, not from perception. Its 0.9+ correlations are on bins of ≥ 1,000 calls, which hides per-call noise. They support "PCR rises monotonically with RTT, loss and jitter" and nothing more precise.

### Gaps
- I found no peer-reviewed study mapping the W3C `freezeCount`/`totalFreezesDuration` counters themselves to two-way call MOS. ITU-T P.1305 and P.1301 (videoconferencing) were not opened.
- Browser support for `freezeCount` and related stats outside Chromium (Safari, Firefox, Android WebView) was not verified.
- How Microsoft's freeze classifier is built (training ratings, features) is not public beyond the one-line description.

---

## 4. Web QoE on mobile: Lighthouse, SpeedIndex, ByteIndex, G.1030

### Takeaway
Lighthouse's defaults are **unsuitable** for a room label. It uses *simulated* throttling (Slow 4G: 150 ms RTT, 1.6 Mbps down, 4x CPU), so its numbers describe a modelled network, not the room's Wi-Fi. For a real phone, the Lighthouse README prescribes running it over adb against Chrome on Android with `--throttling-method=provided --screenEmulation.disabled --throttling.cpuSlowdownMultiplier=1`.

Lighthouse's Speed Index thresholds (mobile good ≤ 3.4 s, poor > 5.8 s) come from HTTP Archive distributions, not from user ratings. ITU-T G.1030 is the only perceptual anchor, and it was fitted on a simple search task. In the 60 s context: MOS = 5.72 − 0.936·ln(session time), R = 0.95, with session times under about 2 s giving MOS 5.

### Cited Findings
- **Lighthouse Speed Index.** Lighthouse "records a video of the page loading … and compares the visual change between frames", computed with the Speedline module.
  - Mobile: 0–3.4 s good, 3.4–5.8 s needs improvement, > 5.8 s poor.
  - Desktop: 0–1.3 s, 1.3–2.3 s, > 2.3 s.
  - The scores "are based on how the page compares with real websites, using HTTP Archive data". — [Lighthouse Speed Index](https://developer.chrome.com/docs/lighthouse/performance/speed-index)
- **Lighthouse 10 performance weights:** FCP 10%, SI 10%, LCP 25%, TBT 30%, CLS 25%. "A lot of the variability in your overall Performance score and metric values is not due to Lighthouse" (A/B tests, ads, routing). — [Lighthouse performance scoring](https://developer.chrome.com/docs/lighthouse/performance/performance-scoring)
- **Lighthouse throttling.**
  - "Simulated throttling, which Lighthouse uses by default, uses a simulation of a page load." Mobile preset: 150 ms RTT, 1.6 Mbps down / 750 kbps up, 4x CPU ("Slow 4G").
  - DevTools request-level throttling is "not a sufficient model of a slow connection". — [Lighthouse throttling.md](https://github.com/GoogleChrome/lighthouse/blob/main/docs/throttling.md)
- **Lighthouse README.** "Lighthouse can run against a real mobile device" via `adb forward tcp:9222 localabstract:chrome_devtools_remote`, using `--screenEmulation.disabled --throttling.cpuSlowdownMultiplier=1 --throttling-method=provided` "to disable any additional emulation". — [Lighthouse docs/readme.md](https://github.com/GoogleChrome/lighthouse/blob/main/docs/readme.md)
- **ITU-T G.1030 (02/2014) Appendix II (full text of the appendix read; PDF freely downloadable).**
  - Subjects retrieved a search page and then a result page. Session time T1+T2+T3+T4 was manipulated, with 49 sessions per experiment, at time scales of 6, 15 and 60 s.
  - 60 s context (12+17 = 29 subjects): MOS = 5.72 − 0.936·ln(ST), R = 0.95, "session times below about 2 seconds lead to the maximum MOS value of 5", valid from 2.16 to 155 s.
  - 6 s context: naïve-subject correlation "far too low (0.72)", so a weighted session time is used, in which the final download time T4 weighs most.
  - The recommendation itself warns: "this simple web search task does not reflect the dynamics of real web browsing".
  - It cites Nielsen's 0.1 / 1 / 10 s limits, and notes that "subjects tend to adapt their quality judgment towards the expected download time". — [ITU-T G.1030 (02/2014) PDF](https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-G.1030-201402-I!!PDF-E&type=items)
- Bocchi et al.'s ByteIndex and ObjectIndex (CCR 2016) were covered in the earlier notes. They can be computed from Resource Timing without video capture, and they correlate with SpeedIndex. — [Bocchi 2016 PDF](https://c3lab.poliba.it/sites/default/files/2026-05/ccr16-webQoE.pdf)

### Inferences
- **For an in-room phone, Lighthouse via adb needs a tethered PC**, which is impractical as the app's default. The practical in-app option is a WebView loading a fixed page set (cache cleared) and recording:
  - Navigation Timing (`loadEventEnd`, `responseStart`);
  - Resource Timing for a ByteIndex/ObjectIndex approximation;
  - FCP/LCP through `PerformanceObserver`, where the WebView supports them (not verified here);
  - load failures and timeouts as outcomes.

  Lighthouse-on-adb is then a periodic calibration run in a few rooms.
- In homes with hundreds of Mbps, web page-load time is dominated by RTT, DNS and server time, not Wi-Fi throughput. A web label will discriminate mainly through **failures and latency spikes** (the 10 s attention limit in G.1030 and G.1010), not through median PLT.
- Proposed web cut-offs (to pre-register):
  - **bom**: median PLT ≤ 2 s (G.1030 MOS 5 region);
  - **degradado**: p90 PLT above about 5.8 s (Lighthouse "poor" SI band, which is distribution-based) or above the G.1030 MOS < 3 point (about 13 s in the 60 s context, from MOS = 5.72 − 0.936·ln ST; my own calculation);
  - **ruim**: any timeout over 10 s, or a load failure.

### Gaps
- I found no study of Lighthouse or SpeedIndex variance on real phones over Wi-Fi, and nothing on how many runs are needed.
- No subjective validation of ByteIndex/ObjectIndex on mobile was found.
- G.1031 (web QoE influence factors) was not opened.

---

## 5. Filling the gaps from the earlier notes (Hossfeld 2012, Orsolic, Via, YoMoApp, G.1030/G.1072)

### Takeaway
- **Closed:** YoMoApp (full text: 52 subjects, numbers above); Via (full text); G.1030 (appendix model and coefficients); G.1072 (application range and validation: PLCC 0.82 default / 0.90 extended, RMSE 0.47 / 0.33 MOS on a held-out set that the ITU itself calls possibly optimistic); Orsolic (YouQ 2016 and the 2021 cross-network paper read; MTAP 2017 still paywalled).
- **Still open:** Hossfeld QoMEX 2012. No open-access copy was found, so the "16 s" and "90%" figures remain second-hand via Seufert 2015.

### Cited Findings
- **ITU-T G.1072 (01/2020), freely downloadable (sections 6 and 9 read).**
  - Built from P.809 interactive tests (90 s, 24" screen, mouse and keyboard, 1080p) and passive tests (30 s, 720p or 1080p). H.264 via NVENC, CBR.
  - Ranges: bitrate 1–50 Mbps (interactive) or 0.3–50 (passive); frame rate 10–60; **uniform** loss 0–5% or 0–2%; delay 0–400 ms.
  - Note 2: uniform loss "does not reflect the situation in real-life networks, where losses would typically occur in bursts … an item for further study".
  - Out of scope: VP9, AV1 and HEVC; "display size lower/higher than 24""; delay distributions.
  - Structure: R_QoE = R_max − weighted impairments, mapped to MOS with MOS_max 4.64.
  - Performance on an unseen test set: default mode PLCC 0.82, RMSE 0.47 MOS; extended mode PLCC 0.90, RMSE 0.33. Caveat: "due to the same range of parameters used in the training and test set, the result could be optimistic". — [ITU-T G.1072 PDF](https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-G.1072-202001-I!!PDF-E&type=items); [G.1072 record page](https://www.itu.int/rec/T-REC-G.1072-202001-I/en)
- **Hossfeld, Egger, Schatz, Fiedler, Masuch, Lorentzen, QoMEX 2012, DOI 10.1109/QoMEX.2012.6263849.** Again only the abstract and metadata were found: "users are extremely sensitive to interruptions". Neither the Augsburg OPUS repository nor searches turned up the PDF. — [researchr record](https://researchr.org/publication/HossfeldESFML12)
- Via, YoMoApp and Orsolic findings are in Sections 2 and 3 above.

### Inferences
- G.1072's out-of-scope list (no VP9/AV1, 24" only, uniform loss, no jitter input) excludes phones on bursty Wi-Fi. It confirms the draft report's position: a G.1072 MOS can only ever be an auxiliary feature in this project, never ground truth.
- Startup delay stays a weak label component. The evidence: the 16 s figure (second-hand); YoMoApp/MONROE mean startup of 6.4 s in mobile broadband with no reported dissatisfaction; and Orsolic 2021's splits at 2 s and 10 s. The literature supports only a coarse "ruim if startup ≥ 10 s or never started" rule.

### Gaps
- Hossfeld QoMEX 2012 full text (IEEE paywall).
- Orsolic MTAP 2017 full text (Springer paywall).
- The Dimopoulos IMC 2016 and Requet full texts were not re-attempted in this pass.

---

## 6. Answer to the key question: what exactly the V2 harness should measure per room, with which tools, how many runs, and which rule

### Takeaway
Per room, run a fixed, scheduled **test battery from the phone app**. Every attempt is logged at its start, with an outcome code:
- **(A) video capacity probe:** self-hosted DASH content, a pinned representation at a known bitrate, played by ExoPlayer with `PlaybackStats`;
- **(B) YouTube observation run:** a project-owned unlisted URL in auto-ABR, played in a YoMoApp-style WebView with injected JS (or the IFrame API as a fallback);
- **(C) WebRTC call:** to a fixed wired peer, with `getStats()` read at both ends every second;
- **(D) web page set:** in a WebView, with Navigation and Resource Timing.

The room label is the **worst** of the per-application classes, combined with an availability class computed from failed attempts. Thresholds come from the sources below and are written down before collection. Since no source gives a sample size, use at least 10 scheduled batteries per room spread over different times of day. With 30 attempts, rare-event rates (stalls, failures) can be bounded at about 10% (rule of three; my own calculation).

### Cited Findings
- Stall tolerance: one stall under 3 s per clip is tolerated. — [Hossfeld 2011 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107463/107463.pdf)
- A phone-specific subjective result: outages (10 s drops) give stall MOS 2.83, while constant 1–4 Mbps gives ≥ 4.4, and image MOS stays ≥ 4.17 everywhere. — [YoMoApp EuCNC PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107427/107427.pdf)
- A ramped 3-class rule from player KPIs: time on high quality 80–90%; stall duration 3–5 s; stall count 4–6; average stall 3–5 s; overhead 8–12%. — [YouQ QoEMC 2016 PDF](https://www.fer.unizg.hr/images/50020698/YouTube_QOEMC_2016.pdf)
- Initial delay splits of 2 s and 10 s; resolution classes ≥ 700p and 400–700p; P.1203 MOS cut at 3.5. — [Orsolic & Seufert 2021 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107344/107344.pdf)
- The ExoPlayer session fields for join time, rebuffers, mean height, dropped frames, and abandoned-before-ready. — [Media3 PlaybackStats](https://developer.android.com/reference/androidx/media3/exoplayer/analytics/PlaybackStats)
- The W3C freeze and pause definitions. — [W3C webrtc-stats](https://www.w3.org/TR/webrtc-stats/)
- Microsoft CQD video poor if FPS < 7; Teams good FPS 25–30 at ≥ 360p. — [CQD](https://learn.microsoft.com/en-us/microsoftteams/stream-classification-in-call-quality-dashboard); [Teams RTA](https://learn.microsoft.com/en-us/microsoftteams/use-real-time-telemetry-to-troubleshoot-poor-meeting-quality)
- A single freeze over 0.36 s puts MOS below 3.5. — [van Kester 2011 PDF](https://nas-new.ewi.tudelft.nl/Publications/2011_vanKester.pdf)
- G.1030 web: MOS 5 when ST < about 2 s; MOS = 5.72 − 0.936·ln ST. — [G.1030 PDF](https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-G.1030-201402-I!!PDF-E&type=items)
- The YouTube API can no longer force quality (24 Oct 2019). — [Revision history](https://developers.google.com/youtube/iframe_api_revision_history)
- Ads differ by location and were removed from the cross-network study. — [Orsolic & Seufert 2021 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107344/107344.pdf)

### Inferences

**Per-room battery** (my synthesis; each element is tied to a source above):

| Test | Tool or API | Per-attempt measures | Outcome codes logged even on failure |
|---|---|---|---|
| A. Video probe, about 120 s, pinned at 1080p (e.g., about 5 Mbps) and a second at 2160p (e.g., about 15–20 Mbps); own DASH server or CDN | ExoPlayer/Media3 `PlaybackStatsListener` | join time; rebuffer count; total and longest rebuffer; dropped frames; abandoned before ready | `never_started`, `fatal_error`, `abandoned` |
| B. YouTube observation, about 120 s, auto-ABR, own unlisted video | WebView with injected JS polling `<video>` at 1 Hz (`currentTime`, `buffered`, `videoHeight`, `getVideoPlaybackQuality()`) plus IFrame states and quality events as fallback | startup; stall count and duration (excluding initial buffering); time at ≥ 720p (on phones, informative only); ad present (yes/no) | `autoplay_blocked`, `no_playback` |
| C. WebRTC call, about 60 s, fixed clip | `RTCPeerConnection.getStats()` at 1 Hz, both ends | freezes/min; normalised freeze ms/min; longest freeze; pauses; mean FPS; share of seconds with FPS < 15; RTT; audio concealment ratio | `ice_failed`, `setup_timeout`, `dropped_mid_call` |
| D. Web, 5–10 fixed pages, cache cleared | WebView Navigation and Resource Timing (Lighthouse on adb only for calibration) | PLT per page; ByteIndex | `timeout_10s`, `dns_fail`, `http_error` |
| Context, every attempt | Android Wi-Fi APIs plus router TR-181 snapshot | band, channel, RSSI, link rate, BSSID at start and end; other household activity if known | `not_associated_at_start` |

**Proposed pre-registered classification per room** (worst-of, applied to the distribution over attempts):
- **ruim** if any of:
  - (i) the attempt-failure rate is ≥ 10% across all tests (the cut is my proposal);
  - (ii) in A at 1080p, ≥ 20% of sessions have a stall > 3 s or more than 1 stall (Hossfeld), or any session `never_started`;
  - (iii) in C, any pause or mean FPS < 7 in ≥ 20% of calls (W3C, CQD);
  - (iv) in D, any timeout in ≥ 20% of page loads.
- **degradado** if not ruim and any of:
  - A at 2160p fails the stall rule in ≥ 20% of sessions;
  - B shows a stall in ≥ 10% of sessions;
  - C averages ≥ 1 freeze > 0.36 s per minute (van Kester), or FPS < 25 for most of the call (Teams band);
  - D median PLT > 2 s, or p90 > about 5.8 s.
- **bom** otherwise.

The 10% and 20% shares are placeholders to fix *before* data collection, not literature values.

**Runs.** No source gives a rule. With n attempts and zero events, the 95% upper bound on the event rate is about 3/n: 10 attempts give 30%, 30 give 10%. Telling a 20% stall rate from 5% with reasonable power needs roughly 30+ sessions per room per test (my own calculation). So at least 10 batteries per room over at least 3 different days and times, and preferably 30 for the A and B video tests. This lands in the 10–30 range of the earlier notes, and it now applies per test type.

**Validity caveat.** These thresholds come from lab and crowdsourcing work on PCs, older phones and IPTV. YoMoApp's own phone result implies that most of these "degradado" triggers may go unnoticed by users on small screens. The human ratings must therefore be used to check whether the objective "degradado" boundary orders rooms the way residents do, as the draft report's within-building metric proposes.

### Gaps
- No study validates any of these cut-offs inside homes or for room-level aggregation, i.e., what share of bad sessions makes a room "ruim".
- I did not verify whether a self-hosted pinned-bitrate probe is perceptually comparable to YouTube. Only YouTube carries ecological validity, which is why test B is kept.

---

## Implicações para o projeto

### Takeaway
The V2 plan must change in one concrete place: **YouTube can no longer be forced to a resolution through its API**. The capacity probe has to use self-hosted content in ExoPlayer, and YouTube becomes an observation-only test. The rest of the plan holds, with sharper tools: YoMoApp-style injected JS, W3C freeze stats, Lighthouse only for calibration, and G.1030 as the web anchor.

### Cited Findings
- API removal: [Revision history](https://developers.google.com/youtube/iframe_api_revision_history).
- Phone-specific perception: [YoMoApp](https://opus.bibliothek.uni-augsburg.de/opus4/files/107427/107427.pdf).
- Rule precedent: [YouQ](https://www.fer.unizg.hr/images/50020698/YouTube_QOEMC_2016.pdf).
- Call stats: [W3C](https://www.w3.org/TR/webrtc-stats/), [CQD](https://learn.microsoft.com/en-us/microsoftteams/stream-classification-in-call-quality-dashboard).
- Lighthouse on a real device: [Lighthouse readme](https://github.com/GoogleChrome/lighthouse/blob/main/docs/readme.md).

### Inferences: prioritised actions
1. **P0: correct the plan.** Remove "forced resolution via the YouTube API" from the V2 spec (it was in the draft report's P1.1). Replace it with an ExoPlayer pinned-bitrate probe on project-hosted DASH content (1080p and 2160p ladders). Keep YouTube as an auto-ABR observation test on a project-owned unlisted URL.
2. **P0: write the label rule before collecting.** Freeze the Section 6 table and thresholds in a dated pre-registration, including the placeholder 10% and 20% shares. The draft report's P0.1 already requires pre-registration.
3. **P0: log every attempt.** Each test of the battery writes a row at start, with outcome codes (`never_started`, `ice_failed`, `timeout_10s`, `autoplay_blocked`, `not_associated_at_start` …), bytes and elapsed time, and a radio snapshot. ExoPlayer's `abandonedBeforeReadyCount` and CQD's "Unclassified when the QoE report never arrives" show that mature tools treat these as outcomes.
4. **P1: build the in-app instrumentation.**
   - WebView with JS injection polling `<video>` at 1 Hz (YoMoApp pattern), with the IFrame API events as a fallback.
   - Media3 `PlaybackStatsListener` for the probe.
   - WebRTC loopback to a wired peer with `getStats()` at both ends; the wired peer's inbound stats measure the phone's uplink.
   - WebView Navigation and Resource Timing for the page set.
5. **P1: dry-run in 2–3 rooms of one building**, at least 10 batteries per room, before rollout. Check stall and freeze base rates. If the 1080p and 2160p probes never stall anywhere, raise the pinned bitrate or lengthen sessions. The labels must have variance.
6. **P1: calibrate the web test.** In a few rooms, run Lighthouse over adb with `--throttling-method=provided` next to the in-app timings to confirm that the cheap in-app metric tracks SpeedIndex. Never use Lighthouse's default simulated scores as labels.
7. **P2: compute continuous companions.** P.1203 Mode 0 for test B (the open-source plumbing exists, e.g., the Panahi 2024 framework). G.1030 MOS for web. These are auxiliary features only; G.1072 is out of scope for phones and VP9/AV1.
8. **P2: validate against people.** Compare the objective room ordering with resident ratings within each building, as in the draft report's P0.6. Expect weak agreement on resolution-driven "degradado" for phone users (YoMoApp), and stronger agreement on outages and failures.

### Gaps
- Risks I could not settle from sources:
  - YouTube ToS for automated playback;
  - whether m.youtube.com in a 2026 Android WebView still allows the YoMoApp injection;
  - `freezeCount` availability in Android WebView;
  - hosting cost and CDN placement of the self-hosted probe, which needs to be close enough that the Wi-Fi, not the WAN, is the bottleneck.

**Source access log (this pass):**
- **Full or relevant sections read:**
  - YouTube IFrame API reference, revision history and player parameters
  - MDN `getVideoPlaybackQuality`
  - W3C webrtc-stats (first 100k characters)
  - Media3 `PlaybackStats`
  - YoMoApp EuCNC 2015 and MobiCom 2015 poster
  - MONROE TMA/MNM 2017
  - YouQ QoEMC 2016
  - Orsolic & Seufert ConTEL 2021
  - Hoßfeld QoMEX 2014
  - Panahi arXiv 2024
  - vcaml README
  - Via SIGCOMM 2016
  - van Kester SPIE 2011
  - Mallesham arXiv 2019
  - Teams CQD and RTA documentation
  - Lighthouse Speed Index, scoring, throttling and readme
  - ITU-T G.1030 (2014) Appendix II
  - ITU-T G.1072 (2020) sections 6 and 9
- **Partial:** Chrome DevTools Media panel page (short page, no API detail).
- **Snippet only:** YouTube "Stats for nerds" help page; Fora Soft blog.
- **Inaccessible:**
  - Hossfeld QoMEX 2012 (paywall, no OA copy)
  - Orsolic MTAP 2017 (Springer login)
  - CDP Media domain reference (redirect stub only)
  - Bronzino Chrome extension code (not found)

# Objective, application-level QoE labels (video stalling, video calls, web, cloud gaming)

Scope note: these notes cover methods that produce QoE "ground truth" automatically from application behaviour (player events, WebRTC stats, page-load timings, standardised parametric models) instead of user surveys or fixed QoS thresholds. They also cover how well those labels track subjective ratings. Every item says whether I read the full text, only the abstract, or only a search snippet. A source access log is at the end, in the Gaps of the last section.

---

## 1. Stalling/rebuffering as QoE: which features matter (stall count, duration, startup delay, resolution switches) and how strongly

### Takeaway
The subjective literature agrees that stalling dominates video QoE. MOS falls roughly exponentially with the number of stalls, and the drop is steeper for longer stalls. Users tolerate about one short stall (under about 3 s) per clip. Initial delay matters far less: delays up to about 16 s reduce perceived quality only marginally, and about 90% of users prefer a longer initial delay to a stall. Among adaptation effects, switch amplitude matters most, and time spent at low quality also counts. So a stall-based V2 label has a strong basis, but on ABR players it needs a resolution or quality component, because ABR turns most capacity shortfalls into quality drops rather than stalls.

### Cited Findings
- **Hossfeld et al., "Quantification of YouTube QoE via Crowdsourcing", IEEE ISM 2011, DOI 10.1109/ISM.2011.87 (full text read).** A crowdsourced test on the Microworkers platform with consistency and gold-standard questions to filter unreliable workers. Conclusions: YouTube QoE "is mainly determined by stalling and both stalling parameters, i.e. frequency and length". The authors found no significant effect of age, level of Internet usage or content type. "Users tolerate one stalling event per clip as long as stalling event duration remains below 3 s". — [Hossfeld 2011 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107463/107463.pdf)
- Hossfeld 2011 fitted exponential mappings from the number of stalls N to MOS. For 1 s stalls: f1(N) = 3.26·e^(−0.37·N) + 1.65, R² = 0.941. For 3 s stalls: f3(N) = 2.99·e^(−0.96·N) + 2.01, R² = 0.997. Each extra stall therefore costs much more when stalls are long. I took these from the figure text in the PDF; the total number of raters was not extracted. — [Hossfeld 2011 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107463/107463.pdf)
- **Hossfeld, Egger, Schatz, Fiedler, Masuch, Lorentzen, "Initial delay vs. interruptions: between the devil and the deep blue sea", QoMEX 2012, DOI 10.1109/QoMEX.2012.6263849 (full text not accessible; abstract-level only).** Lab and crowdsourcing studies of initial delay across application scenarios, then initial delay compared with stalling on YouTube. Users are very sensitive to interruptions, so trading a longer initial delay (prebuffering) for fewer stalls is a valid strategy. — [researchr record](https://researchr.org/publication/HossfeldESFML12)
- As summarised by the Seufert survey, this QoMEX 2012 study (survey ref. [17]) found that "initial delays up to 16 s reduce the perceived quality only marginally" and that "initial delays are preferred to stalling by around 90% of users". — [Seufert et al. 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107128/107128.pdf)
- **Seufert, Egger, Slanina, Zinner, Hossfeld, Tran-Gia, "A Survey on Quality of Experience of HTTP Adaptive Streaming", IEEE COMST 17(1), 2015, DOI 10.1109/COMST.2014.2360940 (full text read).** Main findings:
  - Stalling is "perceived much worse" than initial delay because it is an unexpected interruption.
  - Studies it reviews report an exponential relationship between stalling parameters and MOS.
  - One long stall is preferred to frequent short ones (ref. [26], Qi & Dai 2006).
  - Whether stall position matters is disputed (ref. [26] says no; ref. [27], Minhas & Fiedler, says yes).
  - Irregular stalling is worse than periodic stalling, and stalling is worse than frame-rate reduction (ref. [28]).
  - Waiting times for other services (web PLT, IPTV zapping) are usually modelled as logarithmic in MOS, but those results "cannot easily be transferred" to video. — [Seufert 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107128/107128.pdf)
- Seufert 2015 on adaptation:
  - "The most dominant adaptation factor is the adaptation amplitude."
  - Switching faster than about every 1 s is more annoying than constant low quality.
  - At low switching frequency (intervals over 2 s), switching beats constant low quality.
  - Low-amplitude switches go undetected by most participants, and half of users did not notice 15 vs 30 fps changes.
  - Recency effects (last quality level, time since the last switch) matter.
  - Recommendation: "Algorithms should play out the highest possible quality" (i.e., time on the highest layer counts). — [Seufert 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107128/107128.pdf)
- **Duanmu, Zeng, Ma, Rehman, Wang, "A Quality-of-Experience Index for Streaming Video" (SQI), IEEE JSTSP 11(1):154–166, 2017, DOI 10.1109/JSTSP.2016.2608329 (full text read).**
  - Subjective database built with 25 naïve subjects, single-stimulus scoring, videos with compression, initial buffering and stalling.
  - SQI adds explicit penalties for initial buffering and stalling to a frame-level presentation-quality model (e.g., SSIM-family VQA).
  - The proposed SQI models "significantly outperform their baseline presentation VQA models".
  - The authors call existing QoE models' predictions "somewhat disappointing".
  - They note that the stalling impact "tends to saturate with the increase of the number of stalling events at a constant quality setting". — [Duanmu 2017 PDF](https://ece.uwaterloo.ca/~z70wang/publications/JSTSP_Streaming_QoE.pdf)
- **Duanmu et al., "A Quality-of-Experience Database for Adaptive Video Streaming" (Waterloo SQoE-III), IEEE Trans. Broadcasting 2018, DOI 10.1109/TBC.2018.2822870 (abstract read).** 450 streaming videos, 6 ABR algorithms, 13 network conditions, 34 subjects; 15 objective QoE models compared against MOS. Per-model correlation values were not extracted. — [DOI](https://doi.org/10.1109/TBC.2018.2822870)
- **ITU-T P.1203 (open reference implementation, README read; Robitza et al. MMSys 2018 abstract read, DOI 10.1145/3204949.3208124).**
  - P.1203 is the "first standardized QoE model for audiovisual HTTP Adaptive Streaming", "trained and validated on over a thousand audiovisual sequences" with stalling, coding artefacts and quality switches, from 30 official subjective databases.
  - The authors show bitstream-based modes clearly beat metadata-based ones for video quality.
  - Combining classical models with ML is robust. — [Robitza 2018 DOI](https://doi.org/10.1145/3204949.3208124)
- P.1203 modes, per the reference implementation:
  - Mode 0: metadata only (bitrate, frame rate, resolution).
  - Mode 1: plus frame types and sizes.
  - Mode 2: plus 2% of QP values.
  - Mode 3: plus all QP values. "The higher the mode, the higher the accuracy".
  - The output is per-second audio and video scores plus an integrated audiovisual MOS (P.1203.3) that includes stalling.
  - The official scope is H.264 up to 1920x1080 at 25 fps.
  - Amendment 1 adjusts the score for long stalling events. — [itu-p1203 GitHub README](https://github.com/itu-p1203/itu-p1203)

### Inferences
- For a room-level good/degraded/bad label, the subjective evidence supports this ranking: stall count and stall duration first, then sustained low resolution and the amplitude of quality drops, with startup delay last. A rule of the form "more than one stall, or any stall over about 3 s, means degraded" has direct support from Hossfeld 2011.
- Startup delay is a weak discriminator by subjective standards (marginal effect up to about 16 s). Weighting it heavily in a label would contradict the literature, unless delays are extreme or the service is short-form.
- On an ABR YouTube player in a home with tens of Mbps, stalls will be rare. The informative signal will often be resolution and bitrate selection, not stalls. A stall-only V2 label is likely to collapse to almost all "good", with heavy class imbalance (see also the Bronzino finding in Section 2 that speed barely moves startup delay and resolution).
- The proposed fixed-URL YouTube tests at forced resolutions (e.g., forcing 1080p or 2160p) turn the ABR player into something close to progressive download at a fixed bitrate. Stalling then becomes the main impairment, and the Hossfeld-style exponential stall-to-MOS curves apply more directly. This is arguably the cleanest way to make stalls appear and carry information about room capacity. In effect, it is a capacity probe at known bitrates.
- P.1203 Mode 0 needs only player-observable metadata: per-segment bitrate, resolution and frame rate, plus stall events. It could serve as a standardised, citable continuous label that is then thresholded into 3 classes. Caveats: Mode 0 is the least accurate mode, scope is H.264 ≤1080p (YouTube mostly serves VP9/AV1, which is out of official scope), and screen size matters.

### Gaps
- Full text of Hossfeld QoMEX 2012 was not accessible (IEEE paywall; no OA copy found). The "16 s" and "90%" figures come from the Seufert survey's summary, not the original.
- I did not extract the number of raters in Hossfeld 2011, or the PLCC/SRCC values for SQI and the 15 models in SQoE-III.
- I found no study that validates these stall-to-MOS curves specifically for home Wi-Fi viewing on phones or laptops of the kind in this project. All are lab or crowdsourcing studies with controlled impairments.
- P.1203's official per-database correlation numbers were not extracted, since the ITU-T recommendation itself was not opened.

---

## 2. Inferring video QoE from (encrypted) network traffic: accuracy, labels, home Wi-Fi relevance

### Takeaway
Every encrypted-traffic study uses the same labelling method: drive a player automatically, read QoE ground truth from the player (YouTube IFrame API, a Chrome extension scraping player stats or overlays), and train a classifier on traffic features. Reported accuracies are 72–92% for coarse classes. Rebuffering is the hardest metric and often dropped or class-imbalanced. Results are service- and threshold-specific. For this project, the useful part is the labelling method (player-reported events), not the traffic models.

### Cited Findings
- **Dimopoulos, Leontiadis, Barlet-Ros, Papagiannaki, "Measuring Video QoE from Encrypted Traffic", ACM IMC 2016, pp. 513–526, DOI 10.1145/2987443.2987459 (abstract read).** Predictive models for "different levels of QoE degradation" caused by three factors: stalling, average video quality and quality variations. Evaluated on a large mobile operator's production network. Encrypted-traffic detection reaches "72%–92% accuracy", higher for cleartext. — [DOI](https://doi.org/10.1145/2987443.2987459); [UPC handle](http://hdl.handle.net/2117/105252)
- A later Zagreb paper credits Dimopoulos with showing that changes in segment size and inter-arrival times are among the strongest signals of impairment. This is a secondary description; the paper could not be opened (HTTP 403). — [Orsolic et al. QEEMS paper (search snippet only)](https://www.fer.unizg.hr/_news/71871/qeems_paper.pdf)
- **Mazhar & Shafiq, "Real-time Video Quality of Experience Monitoring for HTTPS and QUIC", IEEE INFOCOM 2018, pp. 1331–1339, DOI 10.1109/INFOCOM.2018.8486321 (full text read).**
  - Data: a controlled lab testbed collected YouTube data over four months from March 2017: 5,488 QUIC sessions and 5,375 HTTPS/TCP sessions.
  - Sessions ran up to 4 minutes each.
  - Ground truth came from the YouTube IFrame API player states (not started, paused, playing, completed, buffering).
  - Startup delay was binarised at 3.3 s ("Started" vs "Not Started").
  - Inference runs on 10 s windows. Accuracy is "up to 90%" for HTTPS and "up to 85%" for QUIC. — [Mazhar 2018 PDF](http://hammadmazhar1.github.io/files/real-time-infocom18.pdf)
- **Bronzino, Schmitt, Ayoubi, Martins, Teixeira, Feamster, "Inferring Streaming Video Quality from Encrypted Traffic: Practical Models and Deployment Experience", POMACS/SIGMETRICS 2020, DOI 10.1145/3366704 (arXiv 1901.05800 full text read).** The arXiv listing shows Schmitt as first author; the published version is commonly cited as Bronzino et al.
  - Labels: a Chrome extension collected ground truth per service. Netflix was scraped by "parsing overlay text" updated once per second; for YouTube, the extension logged playback position and the HTTPS requests.
  - Collection setup: sessions were generated automatically with ChromeDriver and played for 8–12 minutes, with network conditions varied by `tc`.
  - Machines: six laptops in residences on home Wi-Fi (three homes at 100, 18 and 6 Mbps, a student residence, a US campus apartment and a rural US home), four lab laptops on Wi-Fi and one Ethernet desktop.
  - Sessions where Netflix refused to play (e.g., 50 kbps) were removed.
  - Final labelled set: 13,765 sessions (Netflix, YouTube, Amazon, Twitch). — [arXiv 1901.05800](https://arxiv.org/abs/1901.05800)
- Bronzino results:
  - Resolution is inferred per 10 s bin over 240p–1080p, with precision and recall above 81% and FPR below 12% across services. Average precision is 0.98 for YouTube and Twitch and lower for Netflix and Amazon, which switch more.
  - Startup delay was regressed: Netflix RMSE was 1.24 s for the service-specific model and 1.45 s for the composite, with errors mostly within 1 s for 2–10 s delays.
  - Rebuffering models were omitted from the paper and moved to a technical report. — [arXiv 1901.05800](https://arxiv.org/abs/1901.05800)
- Bronzino on the earlier method: applied to their data, the Mazhar & Shafiq models gave about 20% FPR for detecting startup over 5 s on Netflix, and more on Amazon. 99% of Twitch sessions start after 5 s, so a fixed 5 s threshold is meaningless there. The thresholds are service-specific. — [arXiv 1901.05800](https://arxiv.org/abs/1901.05800)
- Bronzino deployment: 66 homes over 16 months, 216,173 video sessions. "Higher speeds provide only minimal improvements to startup delay and resolution." — [POMACS abstract / DOI](https://doi.org/10.1145/3366704)
- **Gutterman et al., "Requet: Real-time QoE detection for encrypted YouTube traffic", ACM MMSys 2019, DOI 10.1145/3304109.3306226; extended in ACM TOMM 2020, DOI 10.1145/3394498 (abstract read).** Requet detects chunks from IP headers and predicts three labels: buffer warning (low/high), video state (buffer increase, buffer decay, steady, stall) and resolution. Data: "a large YouTube dataset… over various WiFi network conditions". Requet beats a prior-work baseline by 1.12x, 1.53x and 3.14x on those labels. Absolute accuracies and session counts were not seen. — [DOI](https://doi.org/10.1145/3304109.3306226); [Nokia Bell Labs listing](https://www.nokia.com/bell-labs/publications-and-media/publications/requet-real-time-qoe-detection-for-encrypted-youtube-traffic)
- **Orsolic, Pevec, Suznjevic, Skorin-Kapov, "A machine learning approach to classifying YouTube QoE based on encrypted network traffic", Multimedia Tools and Applications 2017, DOI 10.1007/s11042-017-4728-4.** Inaccessible: the Springer page redirects to login and no OA copy was found. Label construction, class definitions and accuracy are not verified here. — [DOI](https://doi.org/10.1007/s11042-017-4728-4)

### Inferences
- The methodological template the project can reuse is the ground-truth side, not the traffic-ML side. It has three parts:
  - Automate a browser (ChromeDriver or Playwright).
  - Read player state from the YouTube IFrame API (buffering events → stall count and duration; playback quality → resolution) or from an extension.
  - Log per-second or per-10 s bins.
- Mazhar and Bronzino both show that this produces labels for tens of thousands of sessions without humans.
- Bronzino's in-home collection ran on home Wi-Fi laptops with `tc` shaping. That is the closest prior setup to a home Wi-Fi room study, but its goal was ISP-side inference, not room comparison.
- The "minimal improvement with higher speed" finding implies that, above a modest threshold, video labels saturate at "good". Room-level discrimination will come mainly from the weakest rooms or from forced high-bitrate tests.
- The study-specific binarisation thresholds (3.3 s, 5 s) show that any fixed cut-off for startup delay or stall must be justified per service. For the project, anchor thresholds to subjective findings (Section 1) rather than copying ML-paper thresholds.
- Accuracies of 72–92% for traffic inference are the accuracy of predicting the player label from packets. They say nothing about how well the label tracks user opinion. None of these encrypted-traffic papers ran subjective tests; their "QoE" is player QoS (startup, stalls, resolution).

### Gaps
- Dimopoulos IMC 2016 full text not read: I could not verify session counts, label definitions (they map to "QoE degradation levels") or whether labels were tied to subjective models.
- Orsolic 2017 not accessible.
- Requet absolute accuracies and dataset size not seen; only relative gains.
- Bronzino's rebuffering results are in a separate technical report that I did not locate.

---

## 3. Video conferencing QoE: how labels are built (Microsoft call ratings, Zoom/Teams/Meet measurement)

### Takeaway
Two labelling traditions exist:
- **(a) Large-scale subjective telemetry.** Skype/Teams end-of-call star ratings: "poor call" means a rating of 1–2, and the poor call rate (PCR) is the share of such calls. This needs real users and has strong response bias.
- **(b) Objective application metrics from WebRTC stats.** Per-second FPS, resolution, QP and freeze duration. Measurement papers use these as quality indicators without mapping them to MOS.

Header-only ML can estimate FPS within 2 fps about 83% of the time in real homes. I found no peer-reviewed mapping from WebRTC freeze/FPS metrics to subjective ratings.

### Cited Findings
- **Gupchup, Hosseinkashi, Ellis, Johnson, Cutler (Microsoft), "Analysis of Problem Tokens to Rank Factors Impacting Quality in VoIP Applications", QoMEX 2017, Erfurt (arXiv 1805.00373, full text read).**
  - Data: over 700,000 Skype end-of-call surveys.
  - Calls rated 1 or 2 are "poor calls", and PCR is their share of all calls.
  - Users are much more likely to fill in the problem-token questionnaire after poor calls, so there is response bias. For example, the "I could not hear any sound" token has about 3x the response rate among poor calls.
  - Only about 54% of poor calls carry any token.
  - Problem tokens give a "73% reduction in entropy (information gain) of the poor call label", computed on a balanced set. — [arXiv 1805.00373](https://arxiv.org/abs/1805.00373)
- Trade-press analysis of Skype for Business data from more than 100,000 users:
  - Network MOS only weakly influences perceived call quality.
  - Calls flagged "poor" by the CQM tool were rated "bad/really bad" only 47% of the time, and "excellent" 28% of the time.
  - The CQD poor-call definition is threshold-based (e.g., packet loss over 10%).
  - This is not peer-reviewed and was seen only as a search snippet. — [No Jitter, "Good MOS does not make a good call" (snippet)](https://www.nojitter.com/video-conferencing/sophisticated-skype-good-mos-does-not-make-a-good-call)
- **MacMillan, Mangla, Saxon, Feamster, "Measuring the Performance and Network Utilization of Popular Video Conferencing Applications", arXiv 2105.13478, 2021 (full text read; commonly cited as IMC 2021, venue not verified on the arXiv page).**
  - Testbed: calls between two clients, link shaped with `tc`, and a pre-recorded 1280x720 talking-head video fed via ffmpeg for reproducibility.
  - Application metrics come from the Chrome WebRTC stats API at per-second granularity: FPS, quantization parameter, frame width/resolution and freeze duration.
  - Freeze definition used: frame inter-arrival > max(3δ, δ + 150 ms), with δ the average inter-frame time.
  - Zoom in Chrome could not be measured this way because it uses DataChannels, not RTP media streams. Zoom's native-client logs were too coarse.
  - Freeze stats exist only for the received stream, so the uplink was proxied by counting Full Intra Requests (FIR).
  - Under the same constraints, the apps adapt differently: Teams-Chrome lowers FPS, while Meet raises QP first and only lowers resolution and FPS at about 0.4 Mbps.
  - The paper builds no QoE labels. — [arXiv 2105.13478](https://arxiv.org/abs/2105.13478)
- **Sharma, Mangla, Gupta, Jiang, Feamster, "Estimating WebRTC Video QoE Metrics Without Using Application Headers", arXiv 2306.01194, 2023 (abstract read; venue not stated on the page).** Per-second FPS and resolution for Meet, Teams and Webex, estimated from IP/UDP headers only. Data: 54,696 seconds from lab conditions and from 15 households. FPS is within 2 fps for up to 83.05% of 1 s intervals in real-world data, 1.76% below RTP-header methods. — [arXiv 2306.01194](https://arxiv.org/abs/2306.01194)

### Inferences
- For a home Wi-Fi room label, the practical objective proxy for video-call quality is a scripted WebRTC call between two of your own endpoints (e.g., in Chrome) that logs received FPS, freeze count and duration (WebRTC `freezeCount`/`totalFreezesDuration`-style stats), resolution and QP. MacMillan's testbed is a direct template.
- Uplink matters for calls and is not visible in received-stream freeze stats. The phone's uplink in each room would need the far-end receiver's stats.
- The Microsoft evidence warns that network-threshold "poor call" flags agree poorly with user ratings (47% vs 28% in the trade-press number). That supports the project's move away from fixed QoS thresholds, and it also warns that objective application metrics are not equal to opinion.
- PCR-style labels need thousands of rated calls and suffer response bias. They are not reproducible at the scale of a small home dataset.

### Gaps
- "Via" (Jiang et al., SIGCOMM 2016, DOI 10.1145/2934872.2934907), which used Skype PCR with network metrics at large scale, was not read. Its network-metric-to-PCR relationship is unverified here.
- I found no peer-reviewed study mapping WebRTC freeze/FPS stats to MOS for Teams, Zoom or Meet. ITU-T P.1305 and related standards for videoconferencing were not checked.
- I did not find a Microsoft Teams-era (post-2020) peer-reviewed paper on predicting call ratings from telemetry. Search returned only Skype-era work.

---

## 4. Web QoE (ITU-T G.1030, PLT vs SpeedIndex, Bocchi et al.) and cloud gaming QoE (ITU-T G.1072, Schmidt/Möller)

### Takeaway
**Web:**
- Standard models (G.1030) map waiting or session time to MOS with a logarithmic law fitted on simple tasks.
- onLoad/PLT is easy to measure but a known poor proxy.
- SpeedIndex-type time-integral metrics track experience better.
- Bocchi et al. propose cheaper ByteIndex and ObjectIndex metrics that correlate highly with SpeedIndex.

**Cloud gaming:** ITU-T G.1072 is a parametric opinion model (E-model style) that takes bitrate, frame rate, resolution, packet loss and delay and outputs MOS 1–5. Its training ratings come from non-expert gamers, and inputs must stay within the training ranges.

### Cited Findings
- **Bocchi, De Cicco, Rossi, "Measuring the Quality of Experience of Web users", ACM SIGCOMM CCR 46(4):8–13, 2016, DOI 10.1145/3027947.3027949 (full text read).**
  - onLoad is "simple to measure though knowingly inaccurate". SpeedIndex is "better correlated with the actual user experience" but complex, "relegated to lab experiments".
  - They propose ByteIndex and ObjectIndex (time-integrals over bytes or objects).
  - On the Alexa top-100, these remain "highly correlated to the SpeedIndex". The Pearson correlation matrix shows only values ≥ 0.4; exact values were not extracted.
  - Computing SpeedIndex (video capture) inflates the very timings it measures, an "indetermination principle". — [Bocchi 2016 PDF](https://c3lab.poliba.it/sites/default/files/2026-05/ccr16-webQoE.pdf)
- Seufert 2015 notes that web PLT and similar waiting-time models presume a logarithmic waiting-time-to-MOS relationship. — [Seufert 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107128/107128.pdf)
- **ITU-T G.1030 (2005 v1 Annex A; 2014 v2).** A web-browsing opinion model based on experiments rating MOS against session time on a simple web-search task. QoE is approximated as the logarithm of normalised session time, with case-dependent parameters. Several authors argue that logarithmic models fit simple waiting tasks, but interactive browsing is more complex, and that PLT is a poor proxy of perceived loading time. These points come from search snippets; the recommendation text and coefficients were not opened. — [ITU-T G.1030 TOC](https://www.itu.int/dms_pubrec/itu-t/rec/g/T-REC-G.1030-200511-S!!TOC-HTM-E.htm); [ITC23 paper (snippet)](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf); [Rossi et al. WWW 2019 Wikipedia QoE (snippet)](https://nonsns.github.io/paper/rossi19www.pdf)
- **Egger, Hossfeld, Schatz, Fiedler, "Waiting times in quality of experience for web based services", QoMEX 2012, DOI 10.1109/QoMEX.2012.6263888.** Metadata only, not read. — [DOI](https://doi.org/10.1109/QoMEX.2012.6263888)
- **ITU-T G.1072 (01/2020; Corrigendum 1, 10/2020).**
  - An opinion model "predicting gaming quality of experience for cloud gaming services" for non-expert gamers, intended as a network planning tool.
  - It uses an impairment-factor approach inspired by the E-model (G.107).
  - Default mode assumes a delay- and frame-loss-sensitive game with high encoding complexity; an extended mode uses game-class-specific coefficients.
  - Out of scope: VR and non-keyboard/mouse input. — [ITU work programme](https://www.itu.int/ITU-T/workprog/wp_item.aspx?isn=13778); [GlobalSpec scope (snippet)](https://standards.globalspec.com/std/14350384/itu-t-g-1072); [Corrigendum summary](https://itu.int/dms_pubrec/itu-t/rec/g/T-REC-G.1072-202010-I!Cor1!SUM-HTM-E.htm)
- G.1072 reference implementation by Zadtootaghaj (README read):
  - Inputs: bitrate (0.3 kbps–50 Mbps), frame rate (10–60 fps), resolution (1080p/720p/480p only), video complexity and interaction-sensitivity classes, packet loss (0–5% freezing effect; 0–2% slicing effect) and delay (0–400 ms).
  - "The model only works based on the range of parameters used for training".
  - Outputs: overall quality plus input (interaction) quality due to delay and due to packet loss, and video quality. — [ITU-G1072 GitHub](https://github.com/stootaghaj/ITU-G1072)
- Related cloud-gaming findings (search snippets, not read in full):
  - A UCC 2020 study found frame age the most important QoS metric for in-game performance and QoE. — [liu.se UCC 2020 (snippet)](https://www.ida.liu.se/~nikca89/papers/ucc20.pdf)
  - Wahab et al. (2021) found overall cloud-gaming QoE depends more on playability than on video quality. — [MDPI J 4(3):31 (snippet)](https://mdpi.com/2571-8800/4/3/31)
  - Schmidt, Zadtootaghaj, Möller ran a P.809-style test showing packet loss significantly affects audio and overall gaming QoE. — [Zenodo (snippet)](https://zenodo.org/records/5176127/files/Towards_the_Influence_of_Audio_Quality_on_Gaming_Quality_of_Experience_CRV.pdf)

### Inferences
- For web, an automated room test can log navigation-timing onLoad plus a SpeedIndex-like visual metric (or Bocchi's ByteIndex/ObjectIndex from resource timings) for a fixed page set. Map these through a logarithmic G.1030-style curve only as a rough guide, since the coefficients were fitted on old, simple tasks.
- For cloud gaming, G.1072 lets you turn measured delay, loss and achievable bitrate in a room into a predicted MOS without running a game. It is a planning model driven by network parameters, though, so it reintroduces the "fixed QoS mapping" the project wants to avoid. It is also not validated on Wi-Fi jitter or bursty loss. It is best seen as an extra derived feature, not ground truth.
- Delay up to 400 ms and loss up to 5% are inside G.1072's range. Wi-Fi bufferbloat spikes above 400 ms are outside it.

### Gaps
- I did not open the G.1030 or G.1072 recommendation texts, so I have no coefficients and no G.1072 validation correlation (RMSE/PCC against subjective databases).
- No Schmidt/Möller G.1072 validation paper was found in this pass.
- Bocchi's exact correlation values were not extracted, and I found no Bocchi user-study MOS correlation for ByteIndex/ObjectIndex in this paper. The link to user opinion is via SpeedIndex, not direct.

---

## 5. Practical: automated YouTube/Netflix test harnesses, pitfalls, how many sessions

### Takeaway
Research harnesses are browser automation (ChromeDriver), YouTube IFrame API player-state polling, Chrome extensions scraping player overlays and stats, and Android WebView apps (YoMoApp). Studies run 4–12 minute sessions, shape networks with `tc`, and collect about 5,000 to about 14,000 sessions to train traffic models. Pitfalls:
- player APIs differ per service;
- ads and pre-roll;
- players that refuse to start at very low bandwidth (biases the dataset);
- coarse logging granularity;
- service-specific startup norms;
- received-only stats for calls.

### Cited Findings
- **Mazhar & Shafiq 2018.** YouTube IFrame API player-state events (not started, paused, playing, completed, buffering) used as ground truth. Sessions up to 4 min, collected over 4 months, about 5.4k sessions per protocol. — [Mazhar 2018 PDF](http://hammadmazhar1.github.io/files/real-time-infocom18.pdf)
- **Bronzino et al. 2020.**
  - Harness: Chrome extension plus ChromeDriver, with per-service collection; Netflix's quality overlay text was parsed once per second.
  - Ads at session start were deliberately left in to mimic real use. Sessions lasted 8–12 min.
  - `tc` shaping was used, and sessions where Netflix refused to play at extreme constraints were dropped.
  - Data was aggregated into 10 s bins as a trade-off between precision and the chance of covering complete segment downloads.
  - About 13.8k labelled sessions. — [arXiv 1901.05800](https://arxiv.org/abs/1901.05800)
- **YoMoApp (Wamser et al., EuCNC 2015, DOI 10.1109/EuCNC.2015.7194076; search snippet only).** An Android app that runs the mobile YouTube site in a WebView and monitors buffer level and resolution to derive stalling and quality, plus network and context data. The authors report validation in subjective lab tests and later field studies (Seufert et al. 2016/2017). Full text not opened; Augsburg repository downloads were refused. — [YoMoApp PDF (not opened)](https://opus.bibliothek.uni-augsburg.de/opus4/files/107427/107427.pdf); [DOI](https://doi.org/10.1109/EuCNC.2015.7194076)
- **MacMillan et al. 2021.** WebRTC stats are available per second in Chrome but not for Zoom-in-browser (DataChannels). The harness used a fixed pre-recorded video source for reproducibility. — [arXiv 2105.13478](https://arxiv.org/abs/2105.13478)
- **Hossfeld 2011.** Crowdsourced subjective tests need gold-standard and consistency questions; many workers are unreliable. Relevant if the project's phone app adds a subjective label. — [Hossfeld 2011 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107463/107463.pdf)

### Inferences
- **Recommended V2 video label design.** Use a fixed set of YouTube URLs (fixed content avoids content-dependent bitrate). For each room, run:
  - (a) an auto-ABR session, which logs resolution over time and stalls;
  - (b) forced-resolution sessions (e.g., 720p / 1080p / 2160p), where the main outcome is stalls.

  Then derive these features:
  - stall count, total stall time, and longest stall;
  - startup delay;
  - fraction of time below a target resolution;
  - number and amplitude of downswitches.

  Map them to classes with literature-anchored rules: no stalls and sustained target resolution = good; ≥ 1 stall over 3 s, more than 1 stall, or sustained low resolution = degraded; repeated stalls or failure to sustain the lowest forced level = bad. Optionally compute P.1203 Mode 0 MOS as a continuous companion score.
- **Logging pitfalls (my inference, partly from memory; verify).**
  - IFrame API state events give buffering transitions. Initial buffering must be separated from mid-playback stalls.
  - The quality getter in the IFrame API has been deprecated or neutered in recent years (not verified in this pass), so resolution may need to come from "Stats for nerds" scraping or HTMLVideoElement `getVideoPlaybackQuality()` and `videoHeight`.
  - Ads change startup and stall statistics; use URLs without ads or a premium account, or detect ads.
  - Browser cache and CDN warm-up bias repeated runs of the same URL; clear the cache between runs.
  - Background traffic from other household devices is a confounder that must be logged.
- **How many sessions.** The thousands of sessions in the ML papers were needed to train packet-to-label models. Reading labels directly from the player needs far fewer runs; the binding constraint is how rare stalls are. If a room produces stalls in only a few percent of auto-ABR runs, distinguishing "degraded" from "good" needs many repeats per room (on the order of 10–30+ runs per room per condition). Forced high-resolution runs raise the base rate and cut that number. This is my own reasoning; I found no source giving a sample-size rule for player-derived labels.
- **Applicability to a small home Wi-Fi dataset.** None of the encrypted-traffic models transfer as-is: they target ISP vantage points, services, and years of player behaviour that have since changed. The lasting contributions are:
  - the ground-truth harness pattern;
  - the evidence that speed beyond a modest level barely changes video QoE;
  - the subjective weighting (stalls ≫ quality switches ≫ startup delay).

  Labels from player QoS are objective and reproducible, but validated against MOS only through the lab and crowdsourcing models above (Hossfeld, Duanmu, P.1203), not in-home.

### Gaps
- No source found giving a minimum number of sessions for player-derived (non-ML) QoE labels.
- Current (2025–2026) YouTube IFrame API capabilities for reading resolution were not verified. The deprecation statement above is from memory and must be checked before building the harness.
- The YoMoApp paper itself was not read (repository refused automated download). Its validation numbers are unknown.
- Netflix's current debug overlay (Ctrl+Alt+Shift+D) behaviour and automation terms of service were not checked.

#### Source access log
- **Full text read:**
  - Hossfeld ISM 2011
  - Seufert COMST 2015
  - Duanmu JSTSP 2017
  - Mazhar & Shafiq INFOCOM 2018
  - Bronzino/Schmitt arXiv 1901.05800
  - MacMillan arXiv 2105.13478
  - Gupchup QoMEX 2017 (arXiv 1805.00373)
  - Bocchi CCR 2016
  - P.1203 reference implementation README
  - G.1072 reference implementation README
- **Abstract only:**
  - Dimopoulos IMC 2016
  - Requet MMSys 2019
  - SQoE-III TBC 2018
  - Robitza MMSys 2018
  - Bronzino POMACS 2020 (published abstract)
  - Sharma arXiv 2306.01194
- **Metadata or snippet only:**
  - Hossfeld QoMEX 2012 (findings via the Seufert summary)
  - G.1030 and G.1072 recommendation texts
  - Egger QoMEX 2012
  - YoMoApp EuCNC 2015
  - No Jitter Skype for Business article
  - UCC 2020 and MDPI cloud-gaming papers
  - Schmidt et al. audio gaming paper
- **Inaccessible:**
  - Orsolic MTAP 2017 (Springer login)
  - Via SIGCOMM 2016 (not attempted beyond metadata)
  - Orsolic/Zagreb QEEMS PDF (HTTP 403)

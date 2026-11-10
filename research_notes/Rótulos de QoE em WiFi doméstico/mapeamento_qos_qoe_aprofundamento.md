# QoS-to-QoE mapping, deeper pass: standards in full text, multi-application aggregation, contextual thresholds

Scope note: this file extends `mapeamento_qos_qoe.md` (same folder) and the draft report `reports/Rótulos de QoE em WiFi doméstico.md`. It does not repeat their content except where a full-text reading changes or sharpens it. Guiding question: how should the home Wi-Fi QoE project (27 rooms, 6 buildings, one rater per building, rulers vs labels around 0.5 balanced accuracy, failed tests not logged, deployment on router TR-181 metrics, V2 phone app with YouTube/call/web tests) proceed?

Access legend: **[full text]** means I downloaded the PDF and read the relevant sections myself. **[fetched summary]** means a page read through WebFetch, where a small model summarised the page; quotes from those are as returned and should be spot-checked. **[not accessed]** means I could not open it; anything said about it comes from metadata only.

Work was cut short by the coordinator before the planned searches on 2018-2026 acceptability-threshold studies were done. See the Gaps sections and the "not done" list at the end.

---

## 1. Which standardized or well-validated QoS-to-QoE mapping should the project adopt per application, with which parameters, and how should applications be combined into one room class?

### Takeaway
There is a defensible standard per application: G.1030 Appendix II for web waiting time, P.1203 mode 0 for adaptive video up to 1080p H.264, and G.1072 for cloud-gaming delay and loss. Each has a narrow validated range, and none takes Wi-Fi metrics or jitter as input. No ITU-T recommendation combines applications into one score. The two published combination methods are ETSI TR 103 559 and the IETF Quality-of-Outcome draft:

- **ETSI TR 103 559** (2019) is a weighted sum of per-KPI scores. Each KPI scores linearly between a "bad limit" and a "good limit" and saturates outside them. **Success ratios carry most of the weight**, and failures must be counted.
- **The IETF Quality-of-Outcome draft** (2026) takes the minimum across latency percentiles, loss and throughput.

Neither combination method is validated against user ratings. Both are explicit that their limits are examples or subjective choices.

### Cited Findings

**ITU-T G.1011 (07/2016), "Reference guide to quality of experience assessment methodologies"** [full text] — [ITU record](https://www.itu.int/rec/T-REC-G.1011/en)
- G.1011 is a catalogue, not a model. Its scope says "there is no single document available that describes methods for assessing QoE" and that it "provides a reference guide to existing standardized methods in ITU".
- It states the epistemic hierarchy plainly: "Since QoE, i.e., perceived quality, is internal to the user, perceptual quality tests are ultimately the only means of validly and reliably assessing quality". Objective methods "can be used as a replacement for or a complement to subjective tests" only "within the range of system configurations [they] have been designed for, and proven to provide, valid and reliable quality predictions".
- Its taxonomy (Table 10-1) maps applications to standards:
  - **Web browsing:** subjective method P.1501, model G.1030, usage "PLN" (planning) only, not monitoring.
  - **Video telephony:** G.1070 (planning).
  - **Telephony:** G.107 (planning) and P.563/P.564 (monitoring).
  - **Adaptive streaming over TCP:** P.1201 Amd. 2 App. III; P.1203 appeared later.
- It uses the P.10 definition. QoE is "The overall acceptability of an application or service, as perceived subjectively by the end-user", with Note 2: "Overall acceptability may be influenced by user expectations and context."
- It contains **no method for combining applications** into one score.

**ITU-T G.1030 (02/2014), Appendix II "Opinion model for a simple web search task"** (informative, "does not form an integral part of this Recommendation") [full text] — [ITU record](https://www.itu.int/rec/T-REC-G.1030/en)
- **Basis.** The model is built on lab experiments (Beerends et al. 2004; Van der Gaast et al.) of a two-step search session: a search page, then a results page, with timers T1 to T4 and 49 sessions per experiment. Three experiments used time-scales of about 6, 15 and 60 s, "corresponding to fast, medium and slow network contexts". The 60 s context had 29 subjects (12+17). The 6 s context had 7 naïve and 18 expert subjects.
- **Shape.** "The perceived quality goes down linearly with the logarithm of the session time." General form:

  MOS = 4·(ln(ST) − ln(Min)) / ln(Min/Max) + 5, clipped to [1, 5].
- **Standardized mappings** (WST is the weighted session time, WT1·T1 + … + WT4·T4, with weights normalised to sum 4):

  | Context | Mapping | Weights WT1–WT4 | Min / Max (s) | Correlation |
  |---|---|---|---|---|
  | Short (6 s) | MOS = 4.38 − 1.30·ln(WST) | 0.47 / 0.60 / 0.71 / 2.22 | 0.62 / 13.5 | 0.95 |
  | Medium (15 s) | MOS = 4.79 − 1.03·ln(WST) | 0.54 / 0.72 / 0.98 / 1.76 | 0.81 / 39 | 0.97 |
  | Long (60 s) | MOS = 5.76 − 0.948·ln(WST) | 0.73 / 0.90 / 1.16 / 1.22 | 2.22 / 151 | 0.98 |
  | Long, no weighting | MOS = 5.72 − 0.936·ln(ST) | 1 / 1 / 1 / 1 | 2.16 / 155 | 0.95 |

- **Recency.** In short contexts the last download time dominates. For naïve subjects its weight is "more than four times as large as the impact of the other download and response times".
- **Background thresholds** (cited from Nielsen): about 0.1 s for "instantaneous", about 1.0 s for "uninterrupted" flow of thought, and about 10 s for "loss of attention".
- **Self-declared limits.** The appendix "does not reflect the dynamics of real web browsing such as flow experience, interaction with the web site and consecutive load time patterns throughout a real web browsing session" (it refers to G.1031 for those factors). Section II.5 adds a single-page and single-timing-event extension. I did not extract its coefficients.

**ITU-T P.1203 (10/2017), adaptive and progressive streaming** [full text of the umbrella recommendation; P.1203.1/.2/.3 not read] — [ITU record](https://www.itu.int/rec/T-REC-P.1203/en)
- **Output.** The model predicts "a mean opinion score (MOS) on a 5-point absolute category rating (ACR) scale". O.46 is the "Final media session quality score … Includes initial loading delay and stalling aspects". O.35 is the final audiovisual coding quality. O.23 is a "Perceptual stalling indication". This confirms the O.46 label left open in the first notes.
- **Intended use.** Modes 0 and 1 are intended for monitoring "encrypted HTTP/TCP based VoD/Live streaming", assuming the required metadata is available. Mode 0 needs only metadata such as bitrate, resolution, frame rate and stalling events. Primary application: "monitoring of transmission quality for operations and maintenance".
- **Validated range** (Table 1):
  - video: "H.264/AVC High profile, 75 kbit/s – 12.5 Mbit/s", "Full HD (1920x1080)", "8-30 frames per second";
  - audio: AAC-LC 32–196 kbit/s;
  - devices: PC/TV monitors and one phone (Samsung Galaxy S5);
  - sessions: 1–5 min.
- **Performance** (Appendix I):

  | | Mode 0 | Mode 1 | Mode 2 | Mode 3 |
  |---|---|---|---|---|
  | RMSE | 0.465 | 0.415 | 0.381 | 0.333 |
  | Pearson | 0.814 | 0.842 | 0.868 | 0.892 |

  The figures were computed "after final training of the model on all available subjective test databases … slightly optimistic", and scores were mapped "with a linear mapping applied per each database" to remove between-test bias.

**ITU-T G.1072 (01/2020), cloud gaming opinion model** [full text] — [ITU record](https://www.itu.int/rec/T-REC-G.1072/en)
- **Core model.** R_QoE = 100 − 0.788·I_VQcod − 0.896·I_VQtrans − 0.227·I_TVQ − 0.625·I_IPQframes − 0.848·I_IPQdelay. R is converted to MOS with the P.1201.2 transform, where MOS_max is 4.64 and MOS_min is 1.3.
- **Delay impairment.** I_IPQdelay = f1/(1+exp(f2 − f3·Delay)) + f4. Default (high-sensitivity) coefficients: f1 = 90, f2 = 1.191, f3 = 0.009775, f4 = −18.73. Low sensitivity: f1 = 47.97, f2 = 2.097, f3 = 0.01073, f4 = −4.567.
- **Definition of delay.** Round-trip time of the video and command streams, "excluding additional delays such as system tick rate, rendering delay, encoding/decoding time, refresh rate of the display".
- **Application range** (Table 1): 1080p interactive; H.264 NVENC at 1–50 Mbit/s; 10–60 fps; mouse and keyboard; 24" screen; 90 s sequences; uniform packet loss 0–5%; delay 0–400 ms.
- **Not modelled:** "Packet loss and delay distribution", bursty loss (which "does not reflect the situation in real-life networks … is an item for further study"), VP9, HEVC and AV1. **There is no jitter input.**
- **Performance** (Table 7), "could be optimistic" because train and test share parameter ranges:

  | Mode | RMSE (MOS) | PLCC |
  |---|---|---|
  | Default | 0.47 | 0.82 |
  | Extended (game classified) | 0.33 | 0.90 |

- **My calculation, delay term only** (default mode, all other impairments set to zero; not a G.1072 table):

  | Delay (ms) | 0 | 50 | 80 | 100 | 150 | 200 | 300 | 400 |
  |---|---|---|---|---|---|---|---|---|
  | MOS | 4.33 | 4.21 | 4.07 | 3.96 | 3.60 | 3.19 | 2.54 | 2.21 |

  This is a smooth sigmoid with no cliff at 80 ms. It is consistent with the WPI linear result cited in the first notes.

**ITU-T Y.1541 (12/2011), IP network QoS classes** [full text] — [ITU record](https://www.itu.int/rec/T-REC-Y.1541/en)
- **Table 1** (all values "stable"):

  | Class | Mean IPTD | IPDV | IPLR |
  |---|---|---|---|
  | 0 | 100 ms | 50 ms | 1×10⁻³ |
  | 1 | 400 ms | 50 ms | 1×10⁻³ |
  | 2 | 100 ms | unspecified | 1×10⁻³ |
  | 3 | 400 ms | unspecified | 1×10⁻³ |
  | 4 | 1 s | unspecified | 1×10⁻³ |
  | 5 | unspecified | unspecified | unspecified |

  - IPER is 1×10⁻⁴ for classes 0–4.
  - IPDV is defined as the "upper bound on the 1 − 10⁻³ quantile of IPTD minus the minimum IPTD".
  - "An evaluation interval of 1 minute is suggested … Any minute observed should meet these objectives."
  - Provisional classes 6 and 7 tighten IPLR to 1×10⁻⁵, with IPDV 50 ms at the 1 − 10⁻⁵ quantile.
- **Table 2 guidance.** Classes 0 and 1 are for "Real-time, jitter sensitive … (VoIP, VTC)". Class 4 is "Low loss only (short transactions, bulk data, video streaming)".
- **Critical scope point.** These are UNI-to-UNI objectives for public IP networks. Figure 1 places the **customer installation (terminal and LAN) outside** the scope: "specifications for TE and the user-to-user connection are beyond the scope of this Recommendation". Y.1541 values therefore say nothing directly about the in-home Wi-Fi hop. They are network classes, not user acceptability thresholds.

**ETSI TR 103 559 V1.1.1 (2019-08), "Best practices for robust network QoS benchmark testing and scoring"** [full text] — [ETSI PDF](https://www.etsi.org/deliver/etsi_tr/103500_103599/103559/01.01.01_60/tr_103559v010101p.pdf)
- **Structure.** Results are "aggregated individually", then "weighted and further aggregated for each application like telephony, video and data services", and finally weighted across areas into one overall score.
- **Scoring function.** Metrics have "a bad limit to saturation area in which the experience of the customer does not deteriorate significantly and a good limit to saturation area above which the customers experience does not improve further". The score is 0% beyond the bad limit, rises linearly to 100% at the good limit, and stays at 100% beyond it. Non-linear functions ("square root or logistic sigmoid") are allowed. Because averages under-represent extremes, it adds percentile and "ratio of tests exceeding a threshold" terms.
- **Failures must be scored.** "Failures occurring due to lack of coverage should always be included in scoring calculations and weighted appropriately to reflect the true customer experience."
- **Annex A example limits and weights** (presented as examples, not normative):

  | Group (weight) | KPI | Bad limit | Good limit | KPI weight |
  |---|---|---|---|---|
  | Telephony (40% of services) | Call setup success | 85% | 100% | 31.25% |
  | | Call drop | 10% | 0% | 37.5% |
  | | MOS | 2.0 | 4.3 | 4.38% |
  | | MOS < 1.6 | 10% | 0% | 5.62% |
  | | Call setup time | 12 s | 4.5 s | 6.25% |
  | Data services (60% of services) | Video streaming / Data testing / Browsing / Social media | | | 22% / 25% / 38% / 15% of data |
  | Video streaming | Service success ratio | 80% | 100% | **58%** |
  | | Video MOS | 3.0 | 4.5 | 16.5% |
  | | 10th-percentile MOS | 2.0 | 4.0 | 16.5% |
  | | Access time | 7 s | 2 s | 4.5% |
  | | Access time > 10 s | 5% | 0% | 4.5% |
  | Data testing | DL average throughput | 1 Mbit/s | **100 Mbit/s** | |
  | | DL 10th percentile | 1 Mbit/s | **40 Mbit/s** | **18%** |
  | | DL 90th percentile | 10 Mbit/s | 240 Mbit/s | |
  | | UL average | 0.5 Mbit/s | 50 Mbit/s | |
  | | UL 10th percentile | 0.5 Mbit/s | 30 Mbit/s | |
  | | Transfer success DL / UL | 80% | 100% | 11% each |
  | Browsing | Activity success | 80% | 100% | **66.67%** |
  | | Average duration | 6 s | 1 s | 28.57% |
  | | Share > 6 s | 15% | 0% | 4.76% |
  | Social media and messaging | Average duration | 15 s | 3 s | |

- **What it is not.** It is a mobile-network benchmarking best practice, not a perceptual model. The document gives no subjective validation of the limits or weights. Annex B gives a second, non-linear example set, which I did not extract.

**IETF draft-ietf-ippm-qoo-11 (19 May 2026), "Quality of Outcome"** (Informational, CUJO AI authors) [fetched summary] — [Datatracker](https://datatracker.ietf.org/doc/draft-ietf-ippm-qoo/)
- **Score.** Each application gets Requirements for Optimal Performance (ROP) and Conditions at the Point of Unacceptable Performance (CPUP), both expressed on latency percentiles and loss.
  - Latency: per percentile, m = 1 − (ML − ROP)/(CPUP − ROP), clamped to [0, 1]; QoO_latency is the **minimum across percentiles**.
  - Loss: the same interpolation on the mean loss ratio.
  - Throughput: binary pass/fail against a minimum.
  - Overall: **QoO = min(latency, loss, throughput)**.
- **Percentiles.** The draft recommends 0/10/25/50/75/90/95/99/99.9/100 (from BITAG).
- **Example requirement:** ROP {p99 100 ms, p99.9 200 ms, 0.1% loss}; CPUP {p99 200 ms, p99.9 300 ms, 2% loss}; throughput ≥ 4 Mbit/s.
- **Self-assessment.** The draft "does not define a standardized approach" for setting requirements. Its threshold-setting approach is "admittingly subjective", and "direct use … in production scenarios is discouraged". It says "More comprehensive and large-scale testing are needed", and that interactivity "cannot be modeled by a linear scale" (citing G.1051).
- **User test.** Appendix C reports a preliminary user test with 25 participants using instrumented home routers for 10 days. They found the scores "more intuitive and actionable" than speed tests, and the authors acknowledge the design "might have introduced different forms of bias".
- **Combination.** The draft does **not** define how to combine applications. Requirements are per application, per application type, or per SLA.
- **Lineage.** It is conceptually based on Broadband Forum TR-452.1 "Quality Attenuation" (2020), which I did not read.

**Inaccessible primary sources**
- **IQX** (Fiedler, Hossfeld, Tran-Gia, IEEE Network 24(2), 2010, DOI 10.1109/MNET.2010.5430142). Semantic Scholar lists a green open-access copy at BTH DiVA (urn:nbn:se:bth-7791, record diva2:835453) and 886 citations, but the DiVA server refused connections from this environment. [not accessed] — [Semantic Scholar API record](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/MNET.2010.5430142)
- **Reichl, Egger, Schatz, D'Alconzo, ICC 2010** (DOI 10.1109/ICC.2010.5501894). Closed access (319 citations). [not accessed]
- **Reichl, Tuffin, Schatz, Telecommunication Systems** (2013 issue, online 2011). The Zenodo copy (record 3413352) shows "Record deleted … take-down request" (2019-12-13). [not accessed] — [Zenodo API](https://zenodo.org/api/records/3413352)

### Inferences
- **Per-application adoption.** These are the standards' validated ranges laid against what V2 will measure.
  - **Web:** G.1030 Appendix II on measured page-load or session times, with the context chosen a priori (see section 2).
  - **YouTube:** P.1203 mode 0 O.46. Its validated range matches only H.264 at 1080p or below. YouTube usually serves VP9/AV1, so V2 should either force avc1/≤1080p in test sessions or treat P.1203 output as an out-of-range feature. P.1204.3 covers 4K, but I did not read it.
  - **Gaming:** G.1072 on measured RTT and loss, with jitter folded into a latency percentile rather than entered directly.
  - **Video call:** no read standard fits a WebRTC call measured on a phone. G.1070 (planning model) was not read. G.1010 targets (150 ms preferred and 400 ms limit one-way, <1% loss) remain the only sourced numbers.
- **The 10 ms jitter limit has no support in any standard read.** None of G.1010, G.1030, G.1072, P.1203, Y.1541, ETSI TR 103 559 or QoO contains it. The closest standardized quantity is Y.1541's IPDV: the p99.9 delay minus the minimum, over one minute, with a 50 ms bound for real-time classes, and on the operator network rather than the LAN. QoO likewise expresses jitter as high latency percentiles. This confirms recommendation P0.2 of the draft report and gives a sourced replacement: express delay variation as (p99 or p99.9) − min over a window of at least 1 min.
- **Throughput saturates far below the project's rooms.** ETSI's example good limits are 100 Mbit/s for average DL and 40 Mbit/s for the 10th percentile. A room at 231 or 442 Mbit/s scores 100% on every throughput term. Under the only published multi-service scoring scheme, throughput cannot make such rooms bad. Only success ratios, access times, low percentiles and latency can. This is an independent, standards-based version of the "pisos de suficiência" argument in the draft report.
- **Two aggregation philosophies, and the one to pick.**
  - ETSI is **compensatory**: a weighted sum. Good browsing can offset bad video.
  - QoO is **non-compensatory**: the minimum. The project's "pior-de" rule is of this family.
  - For a per-room class meant to answer "can the resident do what they need here?", the minimum is easier to defend. One unusable application makes the room bad for its user. The weighted sum suits ranking operators across a population.
  - A hybrid is consistent with both documents: take the minimum across *applications*, while each application's score is a small weighted set (success ratio, low percentile, typical value), as ETSI does.
  - Whatever the weights, ETSI's allocation of 58–67% to *success ratios* means a room's failure rate should dominate its class. The project currently cannot compute that.
- **The output of all these models is a MOS or a score, not a class.** Class cut points must be chosen. The only sourced cut points are ETSI's bad and good limits (video MOS 3.0 and 4.5; telephony MOS 2.0 and 4.3) and the E-model GoB/PoW tradition from the first notes (MOS about 3.1 and 2.3). None of them was validated as a class boundary against home users.

### Gaps
- I could not read the IQX and Reichl full texts, so fitted coefficients and sample sizes are still unverified.
- I did not read P.1203.3 (Pq integration), P.1204 (the ITU download returned HTML), G.1070, G.107, P.1501, G.1031, G.1051 or BBF TR-452.1.
- I did not read ETSI TR 103 559 Annex B or the worked example in detail.
- I found no subjective validation of the ETSI limits or weights.
- I did not read the QoO user study (QoOUserStudy) itself.
- I did not read "Deriving QoE in systems: from fundamental relationships to a QoE-based Service-level Quality Index" (Hossfeld et al., QUX 2020, DOI 10.1007/s41233-020-00035-0, CC-BY), which is the most relevant academic multi-session aggregation paper. Springer's cookie wall and the Würzburg OPUS bot wall blocked it.
- Searches for other multi-service aggregation turned up only vendor scorecards (MedUX, Rohde & Schwarz NPS, which says it derives from the ETSI work) and patents. I did not read these and excluded them.

---

## 2. Is there any validated way to make thresholds relative or contextual, or should the project drop the relative ruler?

### Takeaway
Yes, there is one standardized, lab-validated contextual mapping: G.1030's web model. The same session time maps to very different MOS depending on the user's expected time scale ("fast/medium/slow network context"). The context is a property of the **whole range of conditions the user is exposed to**, fixed in advance. It is **not the best single condition**, and it applies to waiting-time tasks only. Nothing I read validates "relative to the best room". The project should drop the best-room ruler as the class definition. If it wants context, it should use a G.1030-style household context class chosen a priori and applied identically to every room, for web waiting times only.

### Cited Findings
- **G.1030 Appendix II, the context dependence.** "An important observation in modelling the perceived quality in web browsing is the fact that the expected maximal session time will dominate the perceived quality. If one expects a session time of 100 seconds, the perceived quality of a 10-second session will be much higher than if one expects a session time of 1 second. Therefore, the model takes a context-dependent approach by using three different time-scales: 6, 15 and 60 seconds, corresponding to fast, medium and slow network contexts". Also: "subjects tend to adapt their quality judgment towards the expected download time [Dellaert & Kahn 1998]. When subjects are informed about the expected download time, they are willing to accept longer download times." [full text] — [ITU-T G.1030](https://www.itu.int/rec/T-REC-G.1030/en)
- **G.1030, how the context was produced.** In each experiment "different combinations of T1 through T4 are configured, varying … the session time, from 0 to the time-scale for this set of experiments". The context is therefore operationalised as the **range** of the stimulus set, which is the range effect noted in the draft report. Correlations are lower in short contexts, and for naïve subjects in the 6 s context "the correlation is too low to allow for accurate MOS predictions" before weighting. [full text] — [ITU-T G.1030](https://www.itu.int/rec/T-REC-G.1030/en)
- **Y.1541 Table 2 note** on the best-effort class: applications can use class 5 "as long as the users are willing to accept the level of performance prevalent during their session". This is a passing acknowledgement that acceptance is tied to prevailing conditions; it is not a model. [full text] — [ITU-T Y.1541](https://www.itu.int/rec/T-REC-Y.1541/en)
- **The other models are absolute.** ETSI TR 103 559 uses fixed bad and good limits per KPI. QoO uses fixed ROP/CPUP per application. G.1072 and P.1203 take absolute inputs. None takes a reference condition as input. [full text / fetched summary] — [ETSI TR 103 559](https://www.etsi.org/deliver/etsi_tr/103500_103599/103559/01.01.01_60/tr_103559v010101p.pdf); [IETF QoO draft](https://datatracker.ietf.org/doc/draft-ietf-ippm-qoo/)
- **G.1011 and P.10 Note 2** say acceptability "may be influenced by user expectations and context", but give no method to quantify it. [full text] — [ITU-T G.1011](https://www.itu.int/rec/T-REC-G.1011/en)
- **Reference dependence and prospect theory.** A search found:
  - a 2021 survey (Luo et al., Frontiers in Communications and Networking, DOI 10.3389/frcmn.2021.634950);
  - a prospect-theoretic streaming QoE metric (arXiv 2608.10625);
  - a prospect-theory pricing paper evaluated by simulation (NSF PAR 10316423).

  None of these was read, and the search snippets show no controlled user study of a network-quality reference point. [not accessed] — [Frontiers survey](https://www.frontiersin.org/articles/10.3389/frcmn.2021.634950/full); [arXiv 2608.10625](https://arxiv.org/pdf/2608.10625)
- **Earlier evidence.** The first notes found the labelling effect (Sackl) faded between 2011 and 2013, that the memory effect is temporal, and that no study tests a best-room anchor. — see `mapeamento_qos_qoe.md`, sections 3 and 4.

### Inferences
- **A worked illustration of how big context is** (my calculation from G.1030 eq. II-5 and II-7, assuming WST = 3 s): a 3 s session gives MOS ≈ 4.38 − 1.30·ln 3 ≈ **2.95** in the fast (6 s) context and ≈ 5.76 − 0.948·ln 3 ≈ **4.72** in the slow (60 s) context. A contextual effect of almost two MOS points is in the standard. So the intuition behind the relative ruler, that users in fast homes are stricter, has **lab support for waiting times**, contrary to the weaker picture in the first notes. The support is for a context set by the overall expected time scale, not by an internal comparison.
- **Why G.1030's context does not rescue the best-room ruler.**
  1. The context is a coarse class (three time scales) chosen *before* scoring. It does not change when one more room is measured. The project's current rule fails this stationarity test.
  2. It comes from the *range* the user experiences across a session set. In a home, that maps more naturally to the household's typical or subscribed performance than to its single best room.
  3. It is validated only for waiting time (web). For capped-rate applications (streaming, calls, gaming), the absolute models (P.1203, G.1072, G.1010) remain the reference, and above saturation there is no perceptible stimulus left to be relative about.
  4. It is computable at the router: the household context class can come from the WAN plan or from the long-run household median page-load time, without knowing which room is best.
- **Recommended stance.** Drop "relative to the best room" as part of the class. Optionally replace it with a **household context class** that only selects which G.1030 mapping (6, 15 or 60 s) is used for web. Keep "gap to the home's typical performance" as a separate, non-class output (as in report action P1.5). Treat any per-user or per-home calibration beyond this as unvalidated.
- **Caveats on G.1030.** The evidence is old (2004 experiments), small (tens of subjects), lab-based, uses a single search task, and counts experts and naïve subjects differently. It shows that context matters. It does not provide current calibrated values for 2026 homes with hundreds of Mbit/s, where all page loads may fall below the 6 s context's Min of 0.62 s and saturate at MOS 5.

### Gaps
- No user study found that validates a spatial (within-home, best-room) reference. The 2018–2026 search for contextual or relative QoE was not completed because the coordinator asked to wrap up.
- The prospect-theory and reference-dependence QoE papers found by search were not read.
- I did not search for studies deriving acceptability thresholds from user data (for example binary acceptance questions in field apps, or abandonment-based thresholds). The θ-acceptability, %GoB and acceptance definitions from Hossfeld et al. (arXiv 1607.00321, in the first notes) remain the methodological basis. The main "QoE beyond the MOS" article (QUX 2016, DOI 10.1007/s41233-016-0002-1) was again blocked by Springer's cookie wall; Semantic Scholar lists it as bronze open access, with an NTNU copy at handle 11250/2418025 that now redirects to an NVA registration page without a PDF link.

---

## 3. Implicações para o projeto

### Takeaway
Define the room class as the **worst of per-application scores**, each built from standard mappings in their validated ranges plus a **success ratio** that requires logging failed attempts. Express delay variation as a latency percentile over at least 1 min, not as a 10 ms jitter cut. Retire the best-room ruler as a class. Context, if used at all, enters only as a pre-declared household time-scale class for web.

### Cited Findings
- Success ratio carries 58–67% of the ETSI service scores, and "failures … should always be included" — [ETSI TR 103 559](https://www.etsi.org/deliver/etsi_tr/103500_103599/103559/01.01.01_60/tr_103559v010101p.pdf)
- The QoO score is the minimum over latency percentiles, loss and throughput. Its thresholds are self-described as "subjective". — [IETF QoO draft-11](https://datatracker.ietf.org/doc/draft-ietf-ippm-qoo/)
- IPDV is p99.9 minus min over 1 min, bounded at 50 ms for real-time classes, and the LAN is out of scope — [ITU-T Y.1541](https://www.itu.int/rec/T-REC-Y.1541/en)
- G.1072 has no jitter input; MOS falls smoothly with RTT; loss is assumed uniform — [ITU-T G.1072](https://www.itu.int/rec/T-REC-G.1072/en)
- P.1203 is validated for H.264 at ≤1080p, 75 kbit/s to 12.5 Mbit/s, with RMSE 0.465 in mode 0 — [ITU-T P.1203](https://www.itu.int/rec/T-REC-P.1203/en)
- G.1030 maps web time to MOS logarithmically and depends on context — [ITU-T G.1030](https://www.itu.int/rec/T-REC-G.1030/en)
- Objective models are valid only within their tested range; subjective tests are "ultimately the only means" — [ITU-T G.1011](https://www.itu.int/rec/T-REC-G.1011/en)

### Inferences (prioritized actions)
These complement, and partly re-ground, the P0–P2 table of the draft report.

1. **P0. Log every attempt and make the success ratio a first-class component.** This is now backed by a standards body document, not only by measurement-practice papers. Per room and per application, compute the success ratio with a Wilson interval and score it between ETSI-style limits (bad 80%, good 100%, as sourced example values). Until failures are logged, document that no ruler can see the dominant ETSI component.
2. **P0. Remove the 10 ms jitter rule and replace it with a latency-percentile term.** Use (p99 − min) or p99 RTT over windows of at least 60 s, following Y.1541 and QoO. Score it linearly between pre-declared ROP and CPUP. QoO's example values (ROP p99 100 ms, CPUP p99 200 ms) are illustrations, not validated limits. Feed gaming RTT into G.1072's delay curve: MOS ≈ 4.2 at 50 ms, 3.96 at 100 ms, 3.19 at 200 ms (my calculation).
3. **P0. Stop treating throughput above saturation as information for the class.** Cap throughput terms at ETSI-like good limits (example values: DL average 100 Mbit/s, DL 10th percentile 40 Mbit/s, UL 10th percentile 30 Mbit/s). Use the 10th percentile, which needs multiple tests per room, rather than the median.
4. **P0. Pre-register the aggregation rule.** Room class = min over applications (QoO-style, matching the current "pior-de"). Each application score is a small ETSI-style weighted set: success ratio, low percentile, typical value. Fix the class cut points on the 0–100 score before any V2 data is collected, and record which source each limit comes from.
5. **P0. Retire "relative to best room" from the class.** It fails stationarity, it is not computable at the router, and no source validates it. If the team wants context, declare a household context class (fast, medium or slow, from the WAN plan or the long-run household median) that only selects the G.1030 web mapping.
6. **P1 (V2 app).** Compute standard model outputs as *labels-by-model*, inside their validated ranges:
   - web: G.1030 Appendix II (or its II.5 single-page extension) on measured load times;
   - YouTube: P.1203 mode 0 O.46 on sessions forced to H.264 ≤1080p (outside that range, keep as a feature only);
   - gaming probe: G.1072 on RTT and loss;
   - call: G.1010 one-way delay and loss targets.

   Keep the raw application metrics as well, because the models will be out of range for VP9/AV1 and for 4K.
7. **P1. Do not apply Y.1541 class values to the Wi-Fi hop.** They are UNI-to-UNI operator objectives. At the router, TR-181 metrics describe only the in-home segment. Any per-hop budget, such as giving the Wi-Fi hop a share of a 100 ms end-to-end target, is an engineering assumption the project must state as such.
8. **P2. Validate limits with residents, not only from standards.** Add a binary acceptance question ("was this good enough?") to the V2 app next to the 5-level rating. That lets θ-acceptability and %GoB-style curves be estimated per application score, which is what ETSI and QoO lack. With 6 buildings, report this as descriptive calibration, not as a test.

### Gaps
Not done because the coordinator asked to wrap up:
- full texts of IQX (DiVA copy exists but refused connection), Reichl ICC 2010 (closed) and Reichl–Tuffin–Schatz 2013 (Zenodo copy taken down);
- the "QoE beyond the MOS" main article and "Deriving QoE in systems … SQI" (QUX 2020; both open access on Springer but blocked from this environment);
- P.1203.3, P.1204, G.1070, G.107, P.1501, G.1031, G.1051, BBF TR-452.1, and ETSI TR 103 559 Annex B;
- the QoO user study and QoOSimStudy;
- the 2018–2026 literature on acceptability thresholds derived from user data, on multi-application per-user scores beyond ETSI/QoO, and on validated relative or contextual QoE beyond G.1030; only one prospect-theory search was run and none of its results were read;
- mapping each proposed term to specific TR-181 parameters per data-model version.

Downloaded full texts used here are in `/tmp/claude-1000/-home-venko-ml-TR069-ml-scripts/d2886c8a-85a8-4d2b-9a33-24f270113833/scratchpad/dl/itu/` (G.1011, G.1030, G.1072, P.1203, Y.1541) and `/tmp/claude-1000/-home-venko-ml-TR069-ml-scripts/d2886c8a-85a8-4d2b-9a33-24f270113833/scratchpad/dl/etsi/` (TR 103 559).

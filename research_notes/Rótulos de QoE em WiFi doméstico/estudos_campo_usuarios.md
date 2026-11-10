# Field and in-the-wild user studies linking reported experience (ratings, satisfaction, complaints) to measured Wi-Fi / home / mobile network metrics

Scope note: written for a project that labels home Wi-Fi QoE per room (good/degraded/bad) from ~11 s speed tests and router (TR-069/TR-181) metrics. In that project, labels from one rater per building agree poorly (~0.5) with both fixed per-application thresholds and a ruler relative to the best room. Rooms that pass every app threshold in fast homes are still rated bad, and disconnections are not logged.

Access status per source ("full text" = I opened and read the document text; "abstract/secondary" = only the abstract, a search snippet, or a summary page):

| Source | Year / venue | Access |
|---|---|---|
| Ickin, Wac, Fiedler, Janowski, Hong, Dey, "Factors influencing QoE of commonly used mobile applications" | 2012, IEEE Commun. Mag. 50(4):48-56, DOI 10.1109/MCOM.2012.6178833 | Full text (UNIGE open archive) |
| Boz, Finley, Oulasvirta, Kilkki, Manner, "Mobile QoE prediction in the field" | 2019, Pervasive and Mobile Computing 59:101039, DOI 10.1016/j.pmcj.2019.101039 | Full text (Aalto repository, CC BY-NC-ND) |
| Finley, Boz, Kilkki, Manner, Oulasvirta, Hämmäinen, "Does network quality matter? A field study of mobile user satisfaction" | 2017, Pervasive and Mobile Computing 39:80-99 (arXiv 1809.03918) | Full text via ar5iv (read through a summarising fetch tool, so numbers were checked only as extracted) |
| Casas, Seufert, Egger, Schatz et al., RAIM 2015 paper (lab + field trial, YouTube/Facebook/Maps) | 2015, IRTF RAIM workshop; extended as "Next to You", IEEE eTNSM 2016 | RAIM paper: full text. eTNSM version: abstract/secondary only |
| Jiang et al., "Via: Improving Internet Telephony Call Quality Using Predictive Relay Selection" | 2016, ACM SIGCOMM, DOI 10.1145/2934872.2934907 | Full text (author copy) |
| Gupchup, Hosseinkashi, Ellis, Johnson, Cutler, "Analysis of Problem Tokens to Rank Factors Impacting Quality in VoIP Applications" | 2017, QoMEX (arXiv 1805.00373) | Full text via ar5iv (through a summarising fetch tool) |
| Chetty, Haslem, Baird, Ofoha, Sumner, Grinter, "Why Is My Internet Slow?: Making Network Speeds Visible" | 2011, ACM CHI, DOI 10.1145/1978942.1979217 | Full text (author copy) |
| Sackl, "Investigations on the Role of Expectations and Individual Decisions in Quality Perception" (PhD thesis, TU Wien/FTW); includes Sackl & Schatz, "Got what you want?", QoMEX 2014, DOI 10.1109/QoMEX.2014.6982291 | 2016/2017 thesis | Thesis: full text (relevant chapters). QoMEX paper: abstract only |
| Jin et al., "NEVERMIND, the Problem Is Already Fixed: Proactively Detecting and Troubleshooting Customer DSL Problems" | 2010, ACM CoNEXT, DOI 10.1145/1921168.1921178 | Abstract/secondary only (author PDF 404, ACM 403) |
| da Hora, van Doorselaer, van Oost, Teixeira, "Predicting the effect of home Wi-Fi quality on QoE" | 2018, IEEE INFOCOM | Abstract/secondary only (HAL blocked by bot protection, ResearchGate and Semantic Scholar 403) |
| Ofcom, "UK Broadband Speeds" annex 6 (SamKnows panel + satisfaction survey) | ~2009-2010 data | Secondary only (PDF 403); figures come from a search-engine summary |
| Sharma, Richardson, Martins, Feamster, "Measuring the Prevalence of WiFi Bottlenecks in Home Access Networks" | arXiv 2311.05499 (2023); longitudinal version at IMC 2024, DOI 10.1145/3646547.3689007 | Abstract only |
| Schwind, Wamser, Wunderer, Gassner, Hoßfeld, "Mobile Internet Experience: Urban vs. Rural" | arXiv 1909.07617 (2019) | Abstract only |
| De Masi & Wac, "Less annoying" replication of Ickin 2012 | 2022, Quality and User Experience (Springer) | Search snippet only (Springer redirected to login) |
| Industry polls on per-room Wi-Fi "dead zones" (TechSee 2025; Uswitch/OnePoll 2026; Zen Internet) | 2025-2026 press releases | Search snippets only; not peer reviewed |
| Rural household throughput + satisfaction (Telecommunications Policy 2024, ScienceDirect S0308596124000594) | 2024 | Search snippet only (403) |

---

## 1. Experience-sampling / in-situ rating studies on mobile and Wi-Fi: sample sizes, rating methods, metrics that predicted ratings, accuracy

### Takeaway
Every in-the-wild study with real users found the same pattern. Ratings are heavily skewed toward "good", network metrics explain little of the variance when the network is reasonably good, and the best field classifier (Boz 2019, 292 users, 64k ratings, tested on held-out users) reached only G-Mean ≈ 0.60 (sensitivity 55%, specificity 66%), about 20% above chance. In the field, the network features that carry signal are the extremes (minimum throughput, loss, delay), not averages. Studies that report much higher accuracy either used lab ratings or did not split by user.

### Cited Findings

**Ickin et al. 2012 (IEEE Commun. Mag.) — 29 Android users, 4 weeks, 7,804 ratings**
- Design: 31 recruited (from 430 online-survey candidates), 2 dropped out. Four consecutive weeks in Feb–Mar 2011, own phones and own US carriers. Three data streams: passive on-phone sensing (Wi-Fi/cellular, RSSI, throughput, location, running apps, plus a 64-byte RTT probe every 3 min and a server-response-time probe); an Experience Sampling Method (ESM) questionnaire after random app uses, "maximum of 8–12 surveys per day", taking "approximately 5 s"; and weekly Day Reconstruction Method interviews in which users explained their ESM ratings against plotted logs — [Ickin et al. 2012, UNIGE full text](https://archive-ouverte.unige.ch/unige:55830)
- Rating: ITU MOS 1 (poor) to 5 (excellent), plus location (home, office/school, street, other indoor, other outdoor), social context and mobility. Users were asked to give "independent ratings" for each episode — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- 7,804 ratings, an average of 9.29 per participant per day. "The high ratings (4, 5) are much more frequent than low ones (1, 2)." Per-user counts of MOS 1 and 2 were mostly in single digits (e.g., S3: 3 and 0 out of 181), with a few outliers (S28: 34 and 15 out of 251) — [Ickin et al. 2012, Table 1](https://archive-ouverte.unige.ch/unige:55830)
- Adaptation: "participants find their QoE acceptable; they have explained that they learned how to maximize their mobile application usage along their routine activities. The participants exhibited knowledge on circumstances that they can expect particular QoE depending on network coverage." — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- Network influence was weak: "we do not have much evidence of the influence of QoS on the user's QoE. There are low QoE ratings in our data, but there is no strong evidence for a low QoS." On Wi-Fi: "We have attempted to investigate the influence of the WiFi signal strength on MOS; however, no clear trends were observed." — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- Mean RTT and mean server response time fall as MOS rises (overall RTT mean 231 ms, SD 73 ms). The authors read off ~950 ms SRT for MOS 3 and ~850 ms for MOS 5. Mean throughput rises with MOS, but with wide confidence intervals: "many different throughput ranges resulting in the same MOS level." — [Ickin et al. 2012, Figs. 4–5](https://archive-ouverte.unige.ch/unige:55830)
- Low ratings concentrated on streaming apps (Listen, YouTube, Pandora), and occurred "mostly when a person is at home or school while being alone and sitting". Some users rated 1 while others were "tolerant, knowing that they gain possibility of accessing these applications while being mobile" — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- Expectation effect: "for mobile applications users previously experienced on a fixed PC, the expectations for performance were high, which resulted in low QoE." Users also "regularly mixed network performance with application performance" — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- A 2022 replication (De Masi & Wac) reportedly found that the factors influencing smartphone app QoE "were similar to the 2012 findings". Snippet only; not read — [search result: Springer s41233-020-00039-w / UNIGE 158545](https://archive-ouverte.unige.ch/unige:158545)

**Boz et al. 2019 (Pervasive and Mobile Computing) — 292 users, 64,036 ratings, Finland, summer 2017**
- Collection: a "QoE-Client" Android app measured network quality whenever the screen was on (UDP delay/loss probes, DL throughput, signal strength, network type). It "occasionally shows a notification prompting the user to rate their experience with the specific app" on a star scale. Prompts are biased toward network-intensive apps because these trigger active latency measurements. Reward: two movie tickets for ≥2 weeks installed, ≥60 ratings, ≥50% of prompts answered, and an exit survey — [Boz et al. 2019, full text](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Network mix of ratings: LTE 41%, Wi-Fi 34%, HSPA+ 21%. Median DL throughput 13.09 Mbps, median delay 51 ms, median loss 0% — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Quality filtering: dropped ratings given long after the session, and ratings more than 4 weeks after the first one (otherwise a few users would have >1,000 ratings vs a median of 167) — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- **Label = personal baseline.** "the user (experience) rating ... is first normalized for each user by subtracting the median rating of that user. This normalization helps mitigate differences in usage of the scale between users." Normalized ratings in [−4, −2] = Bad-QoE ("a significant degradation from the user's normal experience"); [−1, 4] = Normal. Normalizing by user×app median "did not find substantial differences". Class imbalance ≈ 26:1 — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- "over 70% of the ratings are at the given user's median value" — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Correlations: "the correlation magnitudes between the numeric features and the normalized ratings are low (all ρ < 0.08)". Per user, for each network feature only "between 5% and 16% of users have both the intuitively correct correlation sign and a statistically significant correlation (p < 0.05)" — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Accuracy (group splits by user, 50 splits): RF G-Mean 0.598 [0.534, 0.662], GBF 0.597, SVM 0.586, vs uniform-dummy 0.497, stratified-dummy 0.182 and isolation forest 0.338. F1 ≈ 0.11. RF TPR 55%, TNR 66% — [Boz et al. 2019, Table 4](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Why earlier work looked better: a prior study reported ~95% rates, but "does not explicitly mention group cross-validation, suggesting user's ratings might be in both the training and test sets ... [which] is substantially easier because a user's ratings over time are fairly static." That study also had median DL < 1 Mbps vs ~13 Mbps here: "in networks with high quality the importance of network features in QoE modeling likely decreases and the importance of non-network ... features likely increases." — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Features kept after backward elimination: device memory, DL bulk max, delay, echo loss ratio, Play-store review score, Play-store downloads, years of smartphone use, app meta-category. The most important was years of smartphone use (read as a proxy for expectations). Echo loss ratio was among the most important network features: "a significant connection loss is the most egregious network problem." Per-category models (Social, Communication, Entertainment, Other, Games) all reached G-Mean 0.597–0.632 — [Boz et al. 2019, Fig. 12, Tables 5–6](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- Dataset is public (less processed version) — [Aalto QoE app rating page](https://userinterfaces.aalto.fi/qoeapprating)

**Casas et al. (RAIM 2015; extended in IEEE eTNSM 2016 "Next to You")**
- Lab: 52 participants, Android phones, NetEm downlink 0.5–16 Mbps. Continuous ACR MOS plus a binary acceptability question. Max lab MOS never reached 5 ("between 4.2 and 4.6", scale saturation). Reported thresholds: ~4 Mbps (YouTube) and ~1 Mbps (Facebook) "high enough to reach near optimal results"; 2 Mbps is enough for good QoE and near-full acceptability in one app condition — [Casas et al., RAIM 2015 full text](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)
- Field: "30 participants using their own smartphones and cellular ISPs" for 2 weeks in Vienna, with vouchers, on-device passive flow monitoring (throughput, RSSI, RAT, cell) and a QoE-feedback app per session. "In total, almost 700 ratings". Home was the most common location. MOS distributions were "rather similar" across apps and locations, because coverage in Vienna was very good — [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)
- Field vs lab: sessions with mean flow throughput >5 Mbps had good QoE (matching the lab optimum above 4 Mbps), and most MOS = 1 sessions had very low throughput. "However ... the picture becomes very fuzzy in the most relevant MFT gap, between 1 Mbps and 4 Mbps, having MOS scores between 2 and 5." — [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)
- eTNSM version abstract: five services (YouTube, Facebook, Chrome, Google Maps, WhatsApp), bandwidth plus latency plus network stability. It says lab mappings "track the QoE provided by users in real networks" and gives bandwidth thresholds — [search summary of eTNSM/Augsburg OPUS record](https://opus.bibliothek.uni-augsburg.de/opus4/files/107031/107031.pdf) (abstract-level only)

**Finley et al. 2017 (Pervasive and Mobile Computing) — 2,224 users with ~290k measurements, one-shot satisfaction survey**
- Netradar crowdsourced speed-test app (Finland). After a user-initiated cellular test, a pop-up asked five 5-point Likert statements: device satisfaction, availability ("My mobile connection is available when I need it"), speed satisfaction, good enough for video, would recommend. 5,550 completed; 2,224 analysed; per-user response rate ≈ 15%. Cronbach's α (Q2–Q5) = 0.897 — [Finley et al., arXiv 1809.03918 / ar5iv](https://ar5iv.labs.arxiv.org/html/1809.03918)
- Model: partial proportional-odds ordinal logit on features computed from up to one year of each user's tests. Fit is low: adjusted McFadden pseudo-R² 0.035 (availability) and 0.052 (speed); binary versions 0.067 and 0.100, which the authors equate to roughly OLS R² 0.10 and 0.22 — [Finley et al.](https://ar5iv.labs.arxiv.org/html/1809.03918)
- Significant predictors of speed satisfaction: **minimum** TCP download, **last** TCP download, median TCP download, and the count of invalid (failed) user-initiated tests (negative). For availability: minimum download, number of frequent locations, operator, tablet vs phone. Upload and most latency features were not significant. The authors conclude "both the peak-end effect and integration over measurements" shape satisfaction — [Finley et al.](https://ar5iv.labs.arxiv.org/html/1809.03918)
- Caveat (authors'): respondents might compare speeds with the "marketed speed for their data plan". The sample is biased toward technically advanced users — [Finley et al.](https://ar5iv.labs.arxiv.org/html/1809.03918)

**Skype at scale (Jiang et al. 2016; Gupchup et al. 2017)**
- Skype asks "a small random fraction of calls" for a 1–5 rating, and 1–2 counts as "poor". Across 430M calls (135M users, 126 countries, Nov 2015–May 2016), Poor Call Rate rises with RTT, loss and jitter (correlations of binned PCR with the metric: 0.97, 0.95, 0.91, bins ≥1,000 calls). "PCR is sensitive to the entire spectrum of network metrics". Chosen "poor network" thresholds: RTT 320 ms, loss 1.2%, jitter 12 ms — [Jiang et al., SIGCOMM 2016](https://cs.cmu.edu/~junchenj/via.pdf)
- Caveat: these are aggregate correlations over millions of calls in bins. They say nothing about how well a single call's rating can be predicted.
- Gupchup et al.: ~700k one-to-one calls from >100k users over 2 weeks. A "problem token" questionnaire was shown only after ratings below 5. Response bias: users answer more after poor calls (the "I could not hear any sound" response rate was about 3× higher for poor calls), and only ~54% of poor-call respondents ticked any token. A logistic model from tokens to poor call reached AUC 0.95 — [Gupchup et al., QoMEX 2017 / arXiv 1805.00373](https://ar5iv.labs.arxiv.org/html/1805.00373). Related work cited there says perceived quality *decreases* as users get familiar with a system (Pessemier et al., 120 days) — [Gupchup et al.](https://ar5iv.labs.arxiv.org/html/1805.00373) (secondary citation)

### Inferences
- The project's ~0.5 agreement between labels and metric rulers is in the same range as the best published in-the-wild results (Boz: TPR 0.55 / TNR 0.66 on held-out users). Poor agreement is the norm for field subjective labels, not a sign that the project's metrics are broken.
- Field studies share three properties: ratings saturate at "good", the minority "bad" class is rare (26:1 in Boz), and signal sits in extremes and failures (minimum throughput, loss, failed tests), not in means. A per-room label built from medians of *successful* ~11 s speed tests discards exactly the evidence these studies found predictive.
- Wi-Fi RSSI alone showed "no clear trend" with MOS in the one study that tried it (Ickin). Router RSSI/PHY rate should not be expected to separate ratings cleanly.
- Any accuracy number from this project's data must be computed with group splits by rater/building. Boz shows that leaking a user's ratings into training inflates accuracy dramatically (~95% vs ~60%).

### Gaps
- No full text read for the eTNSM 2016 "Next to You" paper or the 2017 Casas/Seufert ML follow-up, so their exact field n and per-feature accuracy are unverified.
- Wac et al. 2011 (the methodology paper behind Ickin) and Schwind et al. (only the abstract was seen; no n) were not read.
- "QoE Doctor" (Chen et al., IMC 2014) was not opened. From memory it is an automated UI-replay measurement tool, not a user-rating study, so it was left out as a source.
- I found no peer-reviewed in-the-wild study in which users rated *home Wi-Fi specifically* (as opposed to mobile apps over Wi-Fi/cellular) and the ratings were paired with AP/router telemetry.

---

## 2. Studies pairing home broadband / Wi-Fi measurements with satisfaction surveys, HCI home-network studies, and ISP studies using complaints/tickets as labels

### Takeaway
Fixed-broadband evidence is thinner and older than mobile evidence. Regulator panels (Ofcom ~2010) show that measured speed correlates with satisfaction *on average*, but households often do not know their own plan speed. HCI field work (Chetty 2011) shows users cannot tell where slowdowns come from. ISP work treats customer tickets as labels (NEVERMIND 2010), and these labels are sparse and reactive. The most cited home-Wi-Fi→QoE work (da Hora/Teixeira 2018) used lab-derived predictors, not ratings from people at home. No study found pairs per-room ratings with router telemetry.

### Cited Findings

**Regulator / survey studies**
- Ofcom UK Broadband Speeds annex (SamKnows-era panel, ~2009–2010): among "8Mb" customers, "those who receive higher actual connection speeds are significantly more satisfied (overall) than those who receive slower connection speeds". The link was stronger for satisfaction *with speed* than for overall satisfaction. "Only 57% of respondents could accurately remember the headline speed of their broadband service" vs 96% who knew their ISP — [Ofcom annex 6 (secondary; PDF returned 403)](https://www.ofcom.org.uk/siteassets/resources/documents/research-and-data/telecoms-research/other-telecoms/annex_6.pdf?v=330783)
- FCC survey (~2009): only 24% of broadband users say they always get the promised download speed, while 67% say they should — [FCC DOC-298516A1 (secondary snippet)](https://docs.fcc.gov/public/attachments/DOC-298516A1.pdf)
- Consumer Reports/NORC 2021 (nationally representative, no measurements): 77% satisfied overall, 54% rate speed excellent/very good — [Consumer Reports broadband survey 2021 (snippet)](https://advocacy.consumerreports.org/wp-content/uploads/2021/08/CR_Broadband-Survey_8_2021_VF.pdf)
- Rural households (Telecommunications Policy 2024): household-level throughput tied to satisfaction surveys. Fiber > satellite and cable > DSL on speed satisfaction — [ScienceDirect S0308596124000594 (snippet only, 403)](https://www.sciencedirect.com/science/article/pii/S0308596124000594)
- I did not find a SamKnows/FCC/Ofcom publication that models per-household satisfaction from the household's own measured speed with reported effect sizes. Only the dated Ofcom annex above comes close.

**HCI home-network field studies**
- Chetty et al., CHI 2011 (Best Paper): 10 households, 21 adults + 2 teens. The Kermit probe ran ~12 days on average, with a mean of 21 automated plus user-run speed tests per day; interviews before and after, diaries, surveys. Baseline: "Our users had very little prior knowledge about factors causing their varying connection speed ... households suspected internal hogs or external service providers ... Just under half of the respondents had never performed a speed test before ... half the participants did not know what speed they were paying for." Users distrusted ISPs' claims. After seeing data, beliefs changed (e.g., a father found he, not his son, was the "biggest hog") — [Chetty et al. 2011, author PDF](https://faculty.cc.gatech.edu/~beki/c53.pdf)
- No rating of experience was paired with metrics in this study. It is qualitative, and its evidence concerns attribution and awareness, not prediction.

**ISP tickets / complaints as labels**
- NEVERMIND (AT&T, CoNEXT 2010): DSL troubleshooting is "reactive, relying mainly on customers to report problems". A ticket predictor and a trouble locator are trained with supervised ML on "existing sparse line measurements" (weekly line tests). They were evaluated on "an entire year worth of customer tickets and measurement data from a large network" and "can predict thousands of future tickets per week with high accuracy" — [Jin et al. 2010 (abstract/secondary via search; author PDF 404)](https://www-users.cse.umn.edu/~zhang089/Papers/Jin-CoNext10-NEVERMIND.pdf). Precision/recall figures and label-noise discussion were not verified.
- Cloud Wi-Fi vendor patents (Plume-style systems) describe a "call-in rate" predictor trained on past support calls vs the network state at the time, with alarms for offline nodes, congestion, poor coverage and speed. No evaluation numbers — [USPTO 12231924](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12231924); [USPTO 12634720](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12634720)
- A complaint-prediction review notes that research is scarce partly because call-center databases are hard to obtain — [Purdue thesis (snippet)](https://docs.lib.purdue.edu/cgi/viewcontent.cgi?article=2432&context=open_access_theses)

**Home Wi-Fi metrics → QoE without in-home ratings**
- da Hora et al., INFOCOM 2018: passive commodity-AP metrics (e.g., PHY rate) → per-app QoE via support vector regression, with K-means combining apps. Predictors were trained in a controlled testbed sweeping Wi-Fi conditions for web, YouTube, and audio/video RTC. Applied to 3,479 APs of an Asia-Pacific ISP: "approximately 21% of stations have more than 25% poor QoE samples". Poor-QoE events were usually short, but some lasted hours. An earlier web-only version used 4,880 APs — [HAL/abstract via search](https://hal.science/hal-01676921/document) (full text blocked). Whether the lab ground truth was human MOS or standardised objective models could not be verified here.
- Sharma, Richardson, Martins, Feamster (arXiv 2023 / IMC 2024): >50 homes, ~2 years, >13,000 joint Wi-Fi + access-link throughput measurements. "For access links above 800 Mbps, the WiFi network was the bottleneck 100% of the time." No satisfaction data; a Qualtrics survey covered setup only — [arXiv 2311.05499](https://arxiv.org/abs/2311.05499); [IMC 2024](https://dl.acm.org/doi/abs/10.1145/3646547.3689007)

### Inferences
- In fast homes Wi-Fi is the bottleneck almost always (Sharma et al.). A user who knows (or was sold) a fast plan and gets a fraction of it in some rooms has a concrete reference point for judging those rooms "bad" even when absolute app thresholds pass. This fits the project's observation, but no study tested it directly at room level.
- Ticket/complaint labels are reactive and sparse, and they come from the customers who call. They work for "something is broken" (outages, line faults), not for graded per-room quality.
- Users frequently do not know their contracted speed (Ofcom 57%, Chetty ~half). Asking raters for their plan speed and expectation is cheap, and its answer is itself informative about how they rate.

### Gaps
- Not found: Schatz/Egger home broadband field trials with satisfaction under controlled bandwidth (the "Vienna surfing" style studies). Searches returned only second-hand mentions that Schatz & Egger collected MOS/acceptability for download speeds in lab+field. Unverified.
- No full text for NEVERMIND, da Hora 2018, the Ofcom annex, or the 2024 rural study. Exact accuracy numbers and label definitions are therefore unverified.
- No Comcast, Plume, Lifemote or other operator publication was found that pairs home Wi-Fi telemetry with customer feedback and reports accuracy.
- Other HCI home-network studies (Grinter et al. "The work to make a home network work"; Chetty "You're capped") were not opened.

---

## 3. Studies where users rated individual rooms or locations, or reported "dead zones"

### Takeaway
No peer-reviewed study was found in which users rated individual rooms of their home and the ratings were paired with measurements. Location exists in ESM studies only as a coarse category (home, office, street...). Room-level evidence comes only from consumer polls, which show that per-room complaints are common, with bedrooms first.

### Cited Findings
- Ickin 2012 recorded location per rating (home/office/street/...). Low QoE ratings occurred "mostly when a person is at home or school while being alone and sitting" — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- Casas 2015 field trial: "The preferred location was home", but MOS distributions were "rather similar" across locations — [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)
- TechSee (US, ~4,000 consumers, census-weighted, 2025): 68% of households had Wi-Fi issues in the past 12 months; weak rooms were bedrooms (35%) and home offices (24%); 31% have dead zones. The base of the "76% weak in specific rooms" figure is inconsistent between the press release and the blog. The poll is run by a vendor of support software, so possibly promotional — [TechSee blog](https://techsee.com/blog/the-hidden-cost-of-broadband-customer-experience/); [PR Newswire](https://www.prnewswire.com/il/news-releases/techsee-survey-reveals-connectivity-gaps-still-plague-us-households-driving-frustration-and-churn-302569453.html)
- Uswitch/OnePoll (UK, 2026): 36% "struggle with their Wi-Fi connection"; worst rooms were main bedroom (24%), guest bedroom (23%), kitchen (22%) — [ISPreview 2026](https://www.ispreview.co.uk/index.php/2026/08/study-claims-36-percent-of-uk-adults-with-home-wi-fi-suffer-poor-connection.html)
- Zen Internet (UK, 2,000 people): 33% of households have signal blackspots; nearly 1 in 5 moved their router — [DJS Research summary](https://www.djsresearch.co.uk/TelecommunicationsMarketResearchInsightsAndFindings/article/Third-of-people-report-WiFi-blackspots-in-their-homes-04500)

### Inferences
- A per-room subjective label is a novel design with no published validation. The project cannot borrow a validated protocol and should treat its label procedure as something to validate (inter-rater agreement, test-retest).
- Polls suggest people readily name a "bad room". A forced *ranking* of rooms within a home may be more natural and reliable than an absolute grade per room. This is an inference, not tested in the sources.

### Gaps
- No academic paper found on user-reported dead zones paired with RSSI/throughput heat maps.
- No study was found on test-retest reliability of a household member's room ratings.

---

## 4. What these studies say about personal baselines, habituation/adaptation and relative vs absolute judgment

### Takeaway
The evidence consistently favours relative, person-specific judgment. The largest field study defined "bad" as a drop of ≥2 points below the user's own median rating. Users with chronically low throughput did not rate worse relative to their own baseline (adaptation), while delay showed a significant user-level relationship. Labelling the same connection "wireless" made users more tolerant in the lab. Measured individual expectations improved QoE model accuracy by up to 12%. Satisfaction integrates the worst moments and the most recent one (peak-end) rather than averages.

### Cited Findings
- **Personal baseline as label:** Boz et al. normalized each rating by the user's median, and called "Bad" only "a significant degradation from the user's normal experience". Older users gave lower absolute ratings but the same normalized ratings, "suggesting older users might be using the rating scale differently (potentially using the center three-star rating as a baseline rather than the five-star rating)" — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- **Adaptation to low throughput:** at user level, the correlation between DL throughput and normalized rating showed "no clear significant relationship (ρ = −0.04, p = 0.53), even for users with low mean DL throughputs of less than 8 Mbps (ρ = 0.06, p = 0.79). One possible explanation is that these low DL throughput users adapt their usage (and expectations)". For delay the relationship was "clearly stronger and more significant (ρ = −0.22, p = 0.0002)", because delay-sensitive apps are harder to adapt. Users also shifted sessions to Wi-Fi when Wi-Fi/cellular throughput ratios were higher — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)
- **Learned expectations:** Ickin's participants "learned how to maximize their mobile application usage" and knew which QoE to expect given coverage. Expectations carried over from PC use produced low QoE on mobile — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830)
- **Labelling/expectation effect (lab):** Sackl's 2011 "ConnectionSwitcher" study: identical connections labelled "3G" vs "ADSL". For web browsing at low QoS, users were more tolerant of the "wireless" label, and 71% of DiffRatings were significantly positive vs 17% opposite. At high bandwidth, a positive effect occurred for only ~33% of users. With "LTE" vs "ADSL" in 2013 (1–45 Mbit/s), the effect vanished, which the author attributes to changed expectations of wireless — [Sackl PhD thesis, ch. 2.2.1.1](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- **Measuring expectations helps:** questionnaires on "desired" and "adequate" expectations, added as linear factors to exponential (IQX) web-QoE models, raised prediction accuracy "up to 12%". The author recommends including the two short questionnaires (Annex A of the thesis) in user studies — [Sackl thesis, Conclusions](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf); [Sackl & Schatz QoMEX 2014 (abstract)](https://manuscript.isc.ac/Inventory/49/185078.htm)
- **Range/context bias:** "when a set of stimuli is presented that has a specific quality range, the usage of the quality scale will be different for an individual stimulus than when that stimulus is presented with a different set of stimuli" (range-equalization bias) — [Sackl thesis, §2](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- **Peak-end and integration:** minimum, last and median download were all significant for speed satisfaction — [Finley et al. 2017](https://ar5iv.labs.arxiv.org/html/1809.03918)
- **Reference to marketed speed:** respondents may compare with the "marketed speed for their data plan" — [Finley et al. 2017](https://ar5iv.labs.arxiv.org/html/1809.03918). Expected vs delivered: 67% think they should always get the promised speed, 24% say they do — [FCC (snippet)](https://docs.fcc.gov/public/attachments/DOC-298516A1.pdf)
- **Familiarity lowers perceived quality over time** (Pessemier et al., 120 days, cited as related work) — [Gupchup et al. 2017](https://ar5iv.labs.arxiv.org/html/1805.00373) (secondary)
- **Absolute thresholds do work in aggregate when the network is poor:** Skype PCR rises across the whole RTT/loss/jitter range — [Jiang et al. 2016](https://cs.cmu.edu/~junchenj/via.pdf). The lab bandwidth thresholds of Casas et al. matched field ratings at the extremes (<1 and >5 Mbps), but not in the 1–4 Mbps middle — [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)

### Inferences
- Combining these points: absolute thresholds predict ratings near the extremes (very poor or very good networks) and in aggregate. In the middle band, and in high-capacity networks, ratings depend on a person-specific reference (own median, plan speed, prior experience, what other rooms deliver). This is exactly where the project's disagreement sits (rooms that pass app thresholds in fast homes rated bad).
- The project's best-room ruler is a *home* baseline, not a *rater* baseline. With one rater per building, the two are fully confounded: one cannot tell whether a "bad" label in a fast building reflects that home's best room (relative judgment) or that rater's harsh use of the scale (scale bias). Boz's design separated them only because each user rated many sessions under varying conditions.
- Adaptation (Boz) and the labelling effect (Sackl) imply that the same 100 Mbps room can be "good" for a rater used to 50 Mbps and "bad" for one used to 500 Mbps. Contracted plan speed and the best room's speed are reasonable proxies for that reference point, and both are measurable.

### Gaps
- No field study tested "relative-to-best-location" vs "absolute" labels head-to-head on home Wi-Fi.
- No study quantified habituation within a single home over weeks with repeated room ratings.

---

## Implicações para o projeto

Prioritized, concrete actions. Each is tied to the evidence above. Items marked (inference) are my extrapolation, not tested in the sources.

1. **Separate rater bias from home baseline before anything else (highest priority).** With one rater per building, a "rater effect" and a "building/relative effect" cannot be identified. In V2:
   - get ≥2 raters per building (residents of the same home rating the same rooms independently); and/or
   - have a few raters (e.g., the field team) rate rooms in *several* buildings as an anchor panel.

   Then measure inter-rater agreement (weighted kappa / Krippendorff's α) per building. Agreement between humans is the ceiling a model can hope to hit. Boz's normalization only worked because each user contributed ~167 ratings across varying conditions — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)

2. **Switch the label from one-off room grades to in-situ experience sampling tied to real use.** Use a short prompt (≈5 s, like Ickin's ESM) right after a real session (video, call, game) in a given room: "How was it? 1–5" plus a binary "acceptable for this use? yes/no" (Casas used acceptability alongside MOS). Cap prompts (Ickin: max 8–12/day). Record room and activity, and drop ratings given long after the session (Boz filter) — [Ickin et al. 2012](https://archive-ouverte.unige.ch/unige:55830); [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf); [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf). This fits the phone-app MVP already agreed for the collection app. Prompts should be random as well as user-initiated, because people volunteer feedback mainly after bad experiences — [Gupchup et al. 2017](https://ar5iv.labs.arxiv.org/html/1805.00373)

3. **Model "bad" as a drop relative to the rater's own baseline, and keep the absolute label too.** Following Boz, define a second target as rating ≤ (rater median − 2). Compare this with the absolute label and with the best-room ruler. Report both. Requires enough ratings per rater to estimate a median: Boz's median was 167 per user. (Inference: a stable per-rater median plausibly needs at least ~20–30 ratings spanning several rooms.)

4. **Log failures and extremes; stop labelling from medians of successful tests.**
   - Field evidence points to minimum throughput, last value, failed tests and loss as predictors: Finley (min/last download, invalid tests); Boz (echo loss among the top features); Via (loss, jitter, RTT).
   - Collect from the phone/collector side: failed/aborted speed tests, association drops/roams, ping loss/timeouts during the session, and per-session minimum/p10 throughput, not only medians. This is the project's known blind spot (disconnections not logged) — [Finley et al. 2017](https://ar5iv.labs.arxiv.org/html/1809.03918); [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf); [Jiang et al. 2016](https://cs.cmu.edu/~junchenj/via.pdf)

5. **Capture each rater's reference point cheaply.** At enrolment, record:
   - contracted plan speed, and whether the rater knows it (Ofcom: only 57% remember it);
   - the two Sackl expectation questions ("desired" and "adequate" quality), which improved model accuracy by up to 12%;
   - what the rater considers their "good room".

   Use these, and the home's best-room speed, as features or as normalizers instead of fixed app thresholds — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf); [Ofcom annex (secondary)](https://www.ofcom.org.uk/siteassets/resources/documents/research-and-data/telecoms-research/other-telecoms/annex_6.pdf?v=330783)

6. **Set realistic accuracy expectations and validate correctly.** Always split by building/rater (group CV). Report balanced metrics (G-Mean, balanced accuracy, per-class recall) against dummy baselines. Boz's best held-out-user G-Mean was ~0.60, about 20% above a uniform dummy. Studies that did not group-split reported ~95%. Treat the current ~0.5 as "near the field norm", and treat any jump above ~0.8 on random splits as suspicious leakage — [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)

7. **Sample sizes seen in the literature (for planning V2):**

   | Study | Users | Duration | Ratings |
   |---|---|---|---|
   | Ickin | 29 | 4 weeks | 7,804 (~9 per user per day) |
   | Casas field | 30 | 2 weeks | ~700 |
   | Boz | 292 | 2–4 weeks | 64,036 (bad class ≈ 1/27) |
   | Finley | 2,224 | one-shot | one survey each |

   (Inference: with ~6 buildings and 1 rater each, the project is far below these. Even 2–3 raters × 6–10 buildings × 2 weeks of ESM at ~5 prompts/day would give ~1,000–3,000 ratings. That would be enough to estimate per-rater baselines and inter-rater agreement, though still few "bad" events if the network is good.)

8. **Expect saturation and plan for the rare class.** Ratings skew to 4–5 (Ickin, Boz, Casas), and lab maxima stop at 4.2–4.6. Oversample conditions likely to be bad (far rooms, 2.4 GHz, busy hours), or deliberately degrade conditions in a controlled sub-study, so that "bad" examples exist — [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf); [Boz et al. 2019](https://acris.aalto.fi/ws/portalfiles/portal/35746767/ELEC_Boz_Mobile_QoE_PaMC.pdf)

9. **Consider within-home ranking as a complementary label (inference).** Since judgments appear relative and room-level ratings have no validated protocol, ask raters to order rooms from best to worst for a given activity. Rankings are immune to scale-use differences between raters, and they directly test the best-room-ruler hypothesis against the absolute-threshold hypothesis.

10. **Use absolute per-app thresholds only where they are supported: at the extremes.** Lab-to-field mappings hold for very low (<1 Mbps) and comfortably high throughput, and for loss, latency and jitter at gross levels (e.g., Via's 320 ms / 1.2% / 12 ms). In the middle band, combine thresholds with the relative/personal features above rather than relying on thresholds alone — [Casas et al. 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf); [Jiang et al. 2016](https://cs.cmu.edu/~junchenj/via.pdf)

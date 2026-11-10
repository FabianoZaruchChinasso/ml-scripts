# Subjective user tests: how throughput, latency, jitter and loss affect perceived quality per application (video calls, cloud gaming, video streaming, web), and whether fixed vendor thresholds are user-validated

Scope note: only results from tests with human raters count as evidence here. Vendor thresholds (Microsoft Teams CQD, and the Zoom, Netflix and GeForce Now numbers the project used) are listed so they can be compared with the user evidence, not as evidence. Each item says how deeply I read it: **[full text]** means I extracted and read the PDF text, **[abstract/snippet]** means I only saw an abstract or search-result text, and **[secondary]** means another paper describes it. Downloaded PDFs are in `/tmp/claude-1000/-home-venko-ml-TR069-ml-scripts/d2886c8a-85a8-4d2b-9a33-24f270113833/scratchpad/pdfs/` (via.txt, xu_mmsys24.txt, claypool_jitter26.txt, schmitt1mbps.txt, casas_raim15.txt, egger_thesis.txt, sabet_mmve20.txt).

Project context: a fixed-threshold ruler applied a 10 ms jitter limit for cloud gaming. That limit drove most of the ruler's verdicts, yet rooms that users rated "Excelente" had 10–25 ms of jitter, as measured by speed tests.

---

## 1. Video calls (WebRTC / Zoom / Teams / Skype): what delay, jitter, loss and bitrate users notice or reject

### Takeaway
User-rated evidence on video calls exists, but none of it supports a sharp jitter cutoff near 10 ms.
- **Skype (430 M calls, user ratings):** the poor-call rate rises smoothly with RTT, loss and jitter. The "12 ms jitter" in that paper was picked as a distribution tail (calls worse than it make up about 15%), not found as a user tolerance knee.
- **Multiparty video, lab:** quality saturates at about 1 Mbit/s of H.264 per stream, and 0.5% random loss bothered only a few participants.
- **Delay:** untrained participants often do not notice one-way delays of several hundred ms. Ratings still drop by 0.4–1.0 MOS at 125–250 ms in highly interactive tasks.
- **Microsoft's own operational "poor" thresholds** (jitter >30 ms, loss >10%, RTT >500 ms) are far looser than 10 ms, and Microsoft gives no user-rating basis for them.

### Cited Findings
- **Skype / VIA (Jiang et al., SIGCOMM 2016, DOI 10.1145/2934872.2934907) [full text].**
  - The dataset is 430 million sampled Skype *audio* calls over seven months, from 1,905 ASes in 126 countries.
  - "For a small random fraction of calls in Skype, users label the call quality on a discrete 5-point scale". Calls rated 1 or 2 count as "poor", and the share of such calls is the Poor Call Rate (PCR).
  - Each bin holds ≥1000 calls. PCR "significantly increases with all the three network metrics (correlation coefficients of 0.97, 0.95, 0.91)". The authors add that "PCR is sensitive to the entire spectrum of network metrics", meaning there is no plateau or knee.
  - The thresholds come from the distribution, not from a user knee: "A significant fraction of calls (over 15%) occur on paths with RTT over 320ms, or loss over 1.2%, or jitter more than 12ms, which we pick as our thresholds for poor performance". The thresholds apply to per-call averages.
  - Source: [Jiang et al., VIA, CMU PDF](https://cs.cmu.edu/~junchenj/via.pdf); [Microsoft Research page](https://www.microsoft.com/en-us/research/publication/via-improving-internet-telephony-call-quality-using-predictive-relay-selection/)
- **Microsoft Teams Call Quality Dashboard (vendor operational rule, not a user study) [full page].**
  - A stream counts as poor if any one of these is exceeded: jitter >30 ms, packet loss >10%, or RTT >500 ms.
  - On jitter, the page says "Teams can adapt to some levels of jitter through buffering. It's only when the jitter exceeds the buffering that a participant notices the effects of jitter."
  - The page cites no user-rating study for these values.
  - Source: [Microsoft Learn, Use CQD to manage call and meeting quality](https://learn.microsoft.com/en-us/microsoftteams/quality-of-experience-review-guide)
- **Multiparty video conferencing, CWI / TU Delft (Schmitt, Redi, Cesar) [full text of the follow-up paper, which summarizes the earlier study].**
  - Setup: 7 groups of 4 people, 28 subjects in total (18 female, mean age 31.9). The groups built a Lego model collaboratively over desktop video.
  - Only the video stream was impaired: H.264 at 256, 1024 and 4096 kbit/s, with 0% or 0.5% random loss. Audio stayed unimpaired.
  - Result: "at 1Mbit encoded H.264 streams the quality perception seemed to saturate. Increasing the bitrate to 4Mbit was noticed by only very few participants, whereas lowering it to 256Kbit severely decreased the QoE."
  - Also: "The packet loss at 0.5% … was disturbing only few participants."
  - In the mixed models, the fixed system factors (bitrate, loss) explained only 8.45% of the variance in perceived audio quality, against 73.69% when group and user random effects were included. Individual and group differences dominated.
  - Source: [Schmitt, Redi, Cesar, "Towards context-aware interactive QoE evaluation for audiovisual multiparty conferencing" (CWI PDF)](https://ir.cwi.nl/pub/24757/24757B.pdf). The earlier study, "1Mbps is enough", has a [TU Delft record](https://research.tudelft.nl/en/publications/1mbps-is-enough-video-quality-and-individual-idiosyncrasies-in-mu/). The later journal paper, "Towards individual QoE for multiparty videoconferencing" (IEEE TMM 20(7):1781–1795, 2018, DOI 10.1109/TMM.2017.2777466), uses the same 4-person Lego paradigm with bitrate and loss; I saw only its abstract: [TU Delft record](https://repository.tudelft.nl/record/uuid:47fc29ef-3180-4d4a-aff9-3846c7357c95).
- **Mobile multiparty WebRTC, Univ. Zagreb (Vučić & Skorin-Kapov) [abstract/snippet].**
  - Study 1 (MMM 2019): 30 participants in three-party audiovisual calls on mobile devices, with packet loss and Google Congestion Control. "In most cases it took approximately 25 seconds for the video stream to recover to an acceptable quality level after the temporary occurrence of network packet loss."
  - Study 2 (PQS 2016): 27 participants, three-party WebRTC calls with bandwidth limits, run following the ITU-T P.1301 procedure.
  - I did not extract any MOS-versus-QoS numbers.
  - Sources: [Springer chapter, MMM 2019](https://rd.springer.com/chapter/10.1007/978-3-030-05710-7_38); [PQS 2016 PDF](https://www.fer.unizg.hr/_news/66200/pqsvucic.pdf); [CROSBI record](https://www.bib.irb.hr/1014967)
- **Conversational delay (speech) [full text of Egger's PhD thesis, its review chapter plus its own studies].**
  - Egger summarizes Kitawaki & Itoh: "delay detectability thresholds of untrained participants were up to 1120 ms (one-way delays) depending on the conversational scenario". Yet perceived conversational quality in highly interactive scenarios dropped "by 0.4 MOS points up to 1.0 MOS for moderate transmission delays of 125 ms and 250 ms already".
  - Egger's own lab studies ran one-way delays from 100 to 1600 ms and found MOS drops of up to 1.6 (free conversation at 1600 ms).
  - Egger, Schatz & Scherer (Interspeech 2010): "one-way delay values up to 400 ms did not have any significant impact on untrained participants' perception of overall speech quality" [abstract/snippet].
  - Sources: [Egger, PhD thesis, "QoE Analysis for Interactive Internet Applications in the Presence of Delay" (EURASIP)](https://theses.eurasip.org/wp-content/uploads/egger-sebastian-qoe-analysis-for-interactive-internet-applications-in-the-presence-of-delay.pdf); [Interspeech 2010 abstract](https://www.isca-archive.org/interspeech_2010/egger10_interspeech.html)
- **Delay changes behaviour more than ratings.** Schoenenberg, Raake et al. (Speech Communication) show that delay alters conversational rhythm and turn-taking, and that the adaptation needed co-determines the quality impact [abstract/snippet]. A 1991 mobile conversation test with 0, 600 and 1200 ms round-trip delay found no change in subjective quality but more interruptions [abstract/snippet]. — [Schoenenberg et al. record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1677923645); [Bell Labs/Nokia publication page](https://www.nokia.com/bell-labs/publications-and-media/publications/subjective-evaluation-of-transmission-delay-in-telephone-conversations)

### Inferences
- The one large user-rated dataset that links network jitter to call ratings (Skype/VIA) shows a *monotone* PCR curve. Its 12 ms cut is the edge of the worst ~15% of calls. Using 12 ms as a "users reject above this" threshold misreads the paper. It also covers audio only, and the jitter is a per-call average measured inside Skype's media path, not a speed-test ping jitter.
- The vendor's own operational rule (Teams, jitter >30 ms counts as poor) is three times looser than 10 ms. It also states explicitly that jitter below the playout buffer's capacity is not noticed. For video calls, then, 10–25 ms of speed-test jitter should usually be absorbed.
- For throughput, video-call quality per stream saturates around 1 Mbit/s (720p-class desktop video, 2016 codecs). A home Wi-Fi link that delivers tens of Mbit/s is not the limit for calls. Loss bursts and delay spikes are.

### Gaps
- I found no peer-reviewed user study of Zoom, Teams or Google Meet that publishes MOS (or acceptability) against network jitter with participant counts. Search led only to vendor documentation. The Microsoft CQD thresholds have no published rating basis.
- ITU-T P.1305/P.1301/P.1310 (multiparty test methods and the delay/jitter effects behind them): I did not open the recommendation texts.
- Vučić & Skorin-Kapov: I have no numeric MOS-versus-bandwidth or MOS-versus-loss curves (I did not open the full texts).
- Schmitt et al. TMM 2018: I did not read the delay/jitter results (the CWI preprint `ir.cwi.nl/pub/26702` was not fetched).
- I did not verify Zoom's published network requirements in this session.

---

## 2. Cloud gaming: acceptable latency and jitter, delay-sensitivity classes, G.1072, and whether any user test supports a 10 ms jitter limit

### Takeaway
No user test I found supports 10 ms of *network* jitter as an acceptability limit for cloud gaming.
- **Frame jitter:** the most direct evidence pools 4 WPI user studies (132 players, 11 games). It models QoE as *linear* in frame-time standard deviation: QoE ≈ 4.6 − 0.056·FTSD(ms). At 10 ms of frame-time SD that predicts ≈4.0, and at 25 ms ≈3.2. That is a gradual slope, not a cliff at 10 ms. FTSD is also measured at the display, after the client's playout buffer, so it is not the speed-test ping jitter.
- **Delay versus frame interrupts:** a 2026 WPI study (25 players, not peer-reviewed) found added delay of 0–100 ms barely changed QoE, while frame interrupts of 30–120 ms clearly did.
- **Delay sensitivity:** the TU Berlin / G.1072 line of work treats delay sensitivity as game-dependent. It derives the sensitivity classes from the quality drop between 0 and 200 ms of delay, not from any jitter threshold.
- **G.1072 inputs:** as far as I could see, the recommendation's input parameters are delay, frame loss, packet loss and encoding. It has no jitter input.

### Cited Findings
- **Xu & Claypool, "User Study-based Models of Game Player QoE with Frame Display Time Variation", ACM MMSys 2024 (Bari) [full text].**
  - The paper pools 4 user studies with 28, 35, 31 and 38 players (132 total, ages 18–26, mostly CS/game-development students).
  - 11 games: CS:GO, Valorant, Hades, Hollow Knight, Rocket League, SuperTuxKart and others.
  - Frame jitter was induced either by a network middlebox (a Raspberry Pi router) or in the game engine, at low, medium and high levels. The pilots set "low" at the perceptibility point and "high" at the maximum tolerance.
  - Baseline QoE without jitter: means of 4.2–4.3.
  - Linear fit across all studies: QoE = −0.056·FTSD(ms) + 4.6 (R² 0.92; 10-fold CV R² 0.84).
  - Interrupt magnitude fits almost as well (R² 0.93), while interrupt frequency does not (R² 0.18): "the size of the interrupt matters to the QoE more than how often an interrupt happens".
  - Source: [Xu & Claypool, MMSys 2024 PDF](https://web.cs.wpi.edu/~claypool/papers/frame-variation-mmsys-24/paper.pdf)
- **Cilley, Dong, Le, Soni (advisor Claypool), WPI IQP report, 7 March 2026 [full text; undergraduate report, "published without editorial or peer review"].**
  - Modified Unity FPS game. 25 valid participants (26 recruited), 25 rounds of 30 s each.
  - Conditions: added delay of 0/25/50/75/100 ms on top of ≈36 ms base system latency, and frame "interrupts" (their jitter proxy) of 0/30/60/90/120 ms.
  - Overall QoE "remains relatively stable as delay increases from 0 to 100 ms", with overlapping confidence intervals. With delay held at 0, overall QoE "declines more consistently as jitter increases from 0 to 120 ms".
  - They estimate that 100 ms of added delay ≈ 30–35 ms of jitter in perceived overall QoE.
  - The report's related work describes a Lead-Rush FPS study with 31 participants in which the sharpest QoE drops came from 0→50 ms of latency and 0→30 ms of jitter [secondary; original reference not identified].
  - Source: [WPI IQP final report PDF](https://web.cs.wpi.edu/~claypool/iqp/delay-jitter-cloud-26/final-report.pdf); [project page](https://web.cs.wpi.edu/~claypool/iqp/delay-jitter-cloud-26/)
- **Sabet, Schmidt, Zadtootaghaj, Griwodz, Möller, "Delay Sensitivity Classification of Cloud Gaming Content", ACM MMVE 2020 (DOI 10.1145/3386293.3397116) [full text].**
  - A focus group of 9 participants played 12 game scenarios at 0, 150 and 300 ms of delay to identify game characteristics.
  - 14 experts rated the characteristics.
  - The classes come from k-means on the drop in input quality (IQ) between 0 and 200 ms of delay, across 40 games (30 for training, 10 for testing). They chose 200 ms because earlier work found it the most diverging delay.
  - The decision tree reached ~86.6–90% accuracy.
  - The paper contains no jitter condition.
  - Source: [arXiv 2004.05609](https://arxiv.org/pdf/2004.05609)
- **ITU-T G.1072 (01/2020), "Opinion model predicting gaming quality of experience for cloud gaming services".**
  - It uses impairment factors for video quality and input quality. Its table of contents lists input-quality factors for network delay and frame-rate reduction, and a video transmission-error factor for packet loss.
  - Default mode assumes a game "highly sensitive to delay and frame loss". The training ratings come "primarily from non-expert gamers".
  - [abstract/TOC; recommendation text not opened]
  - Sources: [ITU-T G.1072 summary](https://itu.int/dms_pubrec/itu-t/rec/g/T-REC-G.1072-202001-I!!SUM-HTM-E.htm); [TOC](https://www.itu.int/dms_pubrec/itu-t/rec/g/T-REC-G.1072-202001-I!!TOC-HTM-E.htm); [reference implementation (GitHub)](https://github.com/stootaghaj/ITU-G1072)
- **Jarschel, Schlosser, Scheuring, Hoßfeld, "An Evaluation of QoE in Cloud Gaming Based on Subjective Tests", IMIS 2011, pp. 330–335 [secondary only; full text not accessed].** Later papers summarize it as a subjective study showing that delay hurts most, and that users tolerate packet loss more in fast-paced games than in slower games such as RPGs. — [dblp record](https://dblp.org/rec/conf/imis/JarschelSSH11); [Linköping UCC'20 paper citing it](https://www.ida.liu.se/~nikca89/papers/ucc20.pdf)
- **Wahab et al., "Subjective Quality Assessment for Cloud Gaming", J (MDPI) 4(3):31, 2021 [abstract/snippet].** They varied delay (lognormal distributions) and packet loss, with ACR ratings of video quality, playability and overall QoE. Overall QoE depended more on playability than on video quality, and the most complex, fast-paced game was hit hardest. Full text was blocked (HTTP 403 from MDPI; Kingston eprints DNS failure). — [Kingston record](https://eprints.kingston.ac.uk/49794); [MDPI](https://www.mdpi.com/2571-8800/4/3/31/htm)

### Inferences
- **Is a 10 ms jitter limit supported by any user test? No, as far as this search reached.**
  - The closest user-derived numbers are these: a linear QoE slope of ~0.056 MOS per ms of *frame-time SD* (so 10 ms costs ≈0.56 MOS from the 4.6 intercept, not a pass/fail); "noticeable" frame interrupts of tens of ms; and a 0→30 ms jump in an unidentified secondary study.
  - None of these is ping jitter from a speed test. Cloud gaming clients run a jitter buffer that turns network jitter into extra delay or frame drops.
  - The likely origin of "10 ms" is vendor guidance (see Section 6 Gaps), not a user study.
- Where the studies compare them, delay (tens of ms) affects game QoE more weakly than the frame-delivery irregularity it causes. Delay sensitivity depends on the game (G.1072 classes, Sabet 2020). A single fixed per-application threshold therefore ignores what users actually play.
- All gaming evidence here comes from students and young gamers on wired lab PCs. None of it covers home Wi-Fi.

### Gaps
- I did not access the full texts of Jarschel 2011, Wahab 2021 or the G.1072 training-data papers (Schmidt et al., Zadtootaghaj et al.), so I have no MOS-at-50/100 ms values from them.
- I found no subjective study that maps *network* RTT jitter (ms, as reported by Ookla/M-Lab speed tests) to cloud-gaming MOS through a real streaming client such as GeForce Now, xCloud or Stadia.
- Clincy & Wilgor (Kennesaw, "Qualitative Evaluation of Latency and Packet Loss in a Cloud-based Games") appeared only as a record link and was not read: [record](https://digitalcommons.kennesaw.edu/facpubs/3893).
- Claypool & Finkel (NetGames 2014) appear here only through the IQP report's paraphrase ("for every 100 ms of added latency, player performance and QoE drop by approximately 25%") [secondary; not verified].

---

## 3. Web browsing: waiting-time studies with users

### Takeaway
Lab and field studies with 75 participants in total (Egger/Hoßfeld/Schatz/Reichl, FTW Vienna) show three things:
- **Shape of the curve:** web QoE falls *logarithmically* with page-load time (the WQL hypothesis).
- **Saturation:** ratings saturate below ~0.5 s, so times under 0.5 s are all equally fine.
- **Example values:** for a search task the fit QoE = −0.88·ln(t) + 4.72 gives ≈4.7 at 1 s, ≈4.1 at 2 s, ≈3.5 at 4 s and ≈2.9 at 8 s.
Older industry guidelines (8 s → 4 s → 2 s) changed over the years without published data behind them.

### Cited Findings
- **Egger PhD thesis, chapter 4 (Studies A, B and C) [full text].**
  - Study A (2009): lab, 26 subjects, downlink bandwidth (DL-BW) varied.
  - Study B (2011): lab, 32 subjects, both DL-BW and page-load time (PLT) varied.
  - Study C (2010): field on Vienna 3G HSPA, 17 subjects, DL-BW varied.
  - All used ACR MOS ratings.
  - Page-load fits: "Picture Load 1" QoE(t) = −0.80 ln(t) + 3.77; "Picture Load 2" −0.63 ln(t) + 3.58; "Search Task" −0.88 ln(t) + 4.72; "Picture Load Task" −1.00 ln(t) + 4.73 (coefficient of determination 0.98–1.00).
  - File-download fits: 2.5 MB −1.14 ln(t) + 6.83; 10 MB −1.68 ln(t) + 9.61.
  - On saturation: "QoE reaches saturation for small waiting times and … the WQL hypothesis only applies above the saturation point". The two shortest times, 0.18 s and 0.44 s, were rated alike, so the fits exclude times below 0.5 s.
  - Field users were more relaxed about download times than lab users.
  - Source: [Egger thesis PDF (EURASIP)](https://theses.eurasip.org/wp-content/uploads/egger-sebastian-qoe-analysis-for-interactive-internet-applications-in-the-presence-of-delay.pdf)
- **On guidelines:** guidelines "postulated waiting times of 8 s as acceptable in 1999 and adapted this threshold to 4 s in 2006 and furthermore down to 2 s in 2009", and "neither the data used deriving them nor the methodologies used to derive this data are known". — [Egger thesis](https://theses.eurasip.org/wp-content/uploads/egger-sebastian-qoe-analysis-for-interactive-internet-applications-in-the-presence-of-delay.pdf)
- **Related papers.** Egger, Reichl, Hoßfeld, Schatz, "'Time is bandwidth'? …", IEEE ICC 2012 (DOI 10.1109/ICC.2012.6363769), formalizes WQL as QoE = a − b·ln(t) via the Weber–Fechner law [abstract/snippet]. Egger, Hoßfeld, Schatz, Fiedler, "Waiting times in QoE for web based services", QoMEX 2012, pp. 86–96 (DOI 10.1109/QoMEX.2012.6263888), is listed by some sources as a tutorial [snippet; not opened]. — [ITC23 paper citing WQL](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf); [bibsonomy record](https://bibsonomy.org/bibtex/34414f4b1597d8762075e6c2f55271f9)
- **Casas et al. mobile lab (also Section 5) [full text]:** Facebook and Google Maps acceptability against downlink bandwidth. — [Casas et al., RAIM 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)

### Inferences
- What matters for web QoE is page-load *time*, which depends mostly on RTT × round trips plus server and rendering time once bandwidth exceeds a few Mbit/s. A Wi-Fi room ruler for web should therefore weigh latency and loss under load above raw throughput, and use a log curve rather than a step.
- The log form means each doubling of load time costs roughly the same MOS (≈0.6–0.9 points per doubling in the PLT tasks). There is no single "acceptable" time.

### Gaps
- I did not fetch Nielsen's 0.1 s / 1 s / 10 s response-time limits. They are, in any case, expert guidelines rather than rating studies.
- I did not open Arapakis et al. (SIGIR 2014, search latency perception), the Google "Speed matters" (Brutlag 2009) field experiment, or the Akamai/Amazon abandonment studies. Those measure behaviour (abandonment, searches), not ratings, and I could not verify their numbers here.

---

## 4. Video streaming: resolution and bitrate against MOS; 1080p versus 4K

### Takeaway
I verified no subjective study showing that a ≥25 Mbit/s "4K" bandwidth requirement is needed for users to rate a stream highly on typical home screens and distances.
- Recent psychophysics (Cambridge/Meta, Nature Communications 2025, n=18) measured a foveal resolution limit of ~94 pixels per degree. Press summaries of that work conclude that at normal viewing distances 4K beyond 1080p/1440p is often not resolvable.
- A broadcast test reported 1080p "just under a half point" below native UHD at the design viewing distance, and less than half a point at 2.7 m [secondary].
- On mobile, YouTube ratings saturate at 4 Mbit/s with DASH. What drives streaming QoE is stalling, not resolution (see the sibling note rotulos_objetivos_aplicacao.md).

### Cited Findings
- **Ashraf, Chapiro, Mantiuk, "Resolution limit of the eye: how many pixels can we see?", Nature Communications 2025, DOI 10.1038/s41467-025-64679-2 [abstract/snippet].**
  - 18 participants judged fine line patterns on a display.
  - Limits: 94 ppd for achromatic foveal vision, 89 ppd for red-green and 53 ppd for yellow-violet. These exceed the traditional 60 ppd ("20/20") figure.
  - Sources: [DOAJ record](https://doaj.org/article/f01680f7077448d2a59a8b0247626335); [Cambridge project page](https://www.cl.cam.ac.uk/research/rainbow/projects/resolution_limit/); [Cambridge news](https://www.cam.ac.uk/research/news/is-your-ultra-hd-tv-worth-it-scientists-measure-the-resolution-limit-of-the-human-eye)
  - Press reading: "at the advised viewing distance of eight feet, a 2K set is enough for a 44-inch display" [press, secondary]. — [T3](https://www.t3.com/tech/tvs/boffins-claim-we-cant-see-the-difference-between-4k-and-1080p-on-our-tvs-and-forget-about-8k)
- **Broadcast UHD test reported in TV Technology [secondary].** "at the proper viewing distance, 720p and 1080i content was perceived to have over a half point worse quality on the ITU 5-point scale compared with native UHD, and even 1080p was viewed as just under a half point worse. At 2.7 meters, all three HD upconverted versions showed less than a half point difference." I could not identify the original study or its n. — [TV Technology, "4K for Broadcast: Is it Worth the Expense?"](https://www.tvtechnology.com/broadcast-engineering/4k-for-broadcast-is-it-worth-the-expense)
- **Hammond et al. 2024 (Cambridge):** pairwise comparisons of 4K HDR streaming distortions at several viewing distances and luminances. High-frequency distortions become less visible as distance increases [abstract/snippet]. — [Hammond 2024 PDF](https://www.cl.cam.ac.uk/~rkm38/pdfs/hammond2024_hdr_vdc.pdf)
- **Casas et al. (mobile YouTube, 52 participants, Section 5) [full text].**
  - Content: 720p with an average video bitrate of ~1.6 Mbit/s.
  - At 1 Mbit/s the standard (non-adaptive) player stalled heavily and only 23% accepted it, against ~99% with DASH.
  - With DASH, image quality was rated "almost excellent" even at the lowest bandwidth.
  - Source: [Casas et al., RAIM 2015](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf)
- **Mackin et al. (ICIP 2018):** "spatial resolution has a significant impact on MOS" [snippet only; numbers not seen]. — [core.ac.uk PDF](https://core.ac.uk/download/158371656.pdf)

### Inferences
- A per-room rule of the form "4K needs ≥ X Mbit/s, otherwise not Excelente" rests on a codec bitrate ladder, not on user ratings. The user evidence says the visible gain from 1080p to 4K is about ≤0.5 MOS and depends on screen size and distance. Stalling, which follows throughput *dips* below the selected bitrate, drives ratings far more strongly.
- For a Wi-Fi ruler, "sustained throughput comfortably above the bitrate the user's device will select" plus "no deep dips" makes a better proxy than a fixed 4K figure.

### Gaps
- I did not open the Netflix VMAF training data, the Waterloo SQoE-III/IV databases, LIVE databases, or ITU-T P.1203 training data. I have no numbers from them on MOS saturation against bitrate.
- I found no subjective test that directly isolates 1080p versus 4K MOS on typical living-room setups with participant counts I could verify.
- I did not verify Netflix's published per-resolution bandwidth recommendations in this session.

---

## 5. Throughput satisfaction curves (bandwidth against MOS, saturation points)

### Takeaway
User-rated bandwidth curves saturate at low rates for every application tested:
- **Mobile lab:** ~1 Mbit/s for Facebook, ~2–4 Mbit/s for Google Maps, ~4 Mbit/s for YouTube.
- **Video calls:** ~1 Mbit/s per video stream (Section 1).
- **Web and file downloads:** QoE follows the log of waiting time (Section 3).
Above these points, more bandwidth adds little measured satisfaction. This supports a relative or saturating ruler more than ever-higher fixed thresholds.

### Cited Findings
- **Casas, Gardlo, Seufert, Wamser, Schatz, "Taming QoE in Cellular Networks: from Subjective Lab Studies to Measurements in the Field", RAIM 2015 [full text].**
  - Lab compliant with standard QoE test procedures. 52 participants (29 female, 23 male, mean age 32).
  - Smartphones, with downlink bandwidth (DBW) shaped by NetEm at logarithmic steps from 0.5 to 16 Mbit/s. Ratings on a continuous ACR MOS scale plus a yes/no acceptability question.
  - Results: "a downlink bandwidth of 4 Mbps/1 Mbps respectively is high enough to reach near optimal results in terms of overall quality and acceptability" (YouTube / Facebook).
  - Google Maps: 2 Mbit/s gives good QoE and almost full acceptability; 4 Mbit/s is better.
  - Facebook: "A DBW of 500 kbps is not high" enough. 1 Mbit/s gives good QoE.
  - Max MOS "never 5".
  - The authors' slides say 50 participants and "excellent QoE for DBW > 4 Mbps", so the slides and the paper disagree slightly on n (50 vs 52).
  - Sources: [paper PDF](https://irtf.org/raim-2015-papers/raim-2015-paper7.pdf); [slides](https://www.irtf.org/raim-2015-slides/fman/casas.pdf)
  - The companion paper is Casas et al., "Exploring QoE in cellular networks: how much bandwidth do you need for popular smartphone apps?", ACM All Things Cellular 2015, which also covered Chrome web browsing and WhatsApp [abstract/snippet]. — [bibsonomy](https://www.bibsonomy.org/bibtex/c2c012b5c333f8503ff13a06891722c9)
- **Egger thesis, studies A, B and C (Section 3) [full text]:** DL-BW was manipulated; for downloads, QoE is logarithmic in download time, which equals size/throughput. — [Egger thesis](https://theses.eurasip.org/wp-content/uploads/egger-sebastian-qoe-analysis-for-interactive-internet-applications-in-the-presence-of-delay.pdf)
- **Schmitt et al. (Section 1):** video-conference quality saturates at 1 Mbit/s per H.264 stream (28 participants). — [CWI PDF](https://ir.cwi.nl/pub/24757/24757B.pdf)

### Inferences
- These saturation points are 2015–2016 values on phones and 720p video. Higher-resolution screens and newer codecs shift them, but only by small multiples. Speed-test throughput in the tens to hundreds of Mbit/s is far above where the measured curves flatten.
- Because the curves are logarithmic or saturating (Weber–Fechner, IQX), ratings depend on *relative* changes in QoS. This matches the project's finding that a relative ruler does better than a fixed one.

### Gaps
- I did not open Sackl / Hoßfeld / Ameigeiras bandwidth-versus-MOS curves for wireline web (e.g., "Got what you expected?" / expectation effects).
- I found no user study of throughput satisfaction on home Wi-Fi with speed-test-level measurements.

---

## 6. Overall verdict: are the fixed per-application vendor thresholds validated by user data?

### Takeaway
Mostly not.
- **Video calls:** Skype's large user-rated data show monotone degradation with no knee. Microsoft's own "poor" thresholds (30 ms jitter, 10% loss, 500 ms RTT) are loose and have no published rating basis.
- **Cloud gaming:** no user test validates a 10 ms *network*-jitter limit. The user-derived frame-jitter model is linear and moderate.
- **Video streaming:** 4K bandwidth requirements come from encoding ladders. User studies show small resolution gains at normal distances.
- **Web:** user studies show log curves with saturation below 0.5 s, not fixed cut-offs.

### Cited Findings
- Skype PCR "is sensitive to the entire spectrum of network metrics"; the 12 ms jitter cut comes from the >15% tail. — [VIA](https://cs.cmu.edu/~junchenj/via.pdf)
- Teams CQD: jitter >30 ms, loss >10%, RTT >500 ms; jitter is noticed only beyond the buffer. — [Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/quality-of-experience-review-guide)
- Game QoE = 4.6 − 0.056·FTSD(ms), 132 players, 11 games. — [Xu & Claypool MMSys 2024](https://web.cs.wpi.edu/~claypool/papers/frame-variation-mmsys-24/paper.pdf)
- Web QoE = −0.88·ln(t) + 4.72 (search task), saturation below ~0.5 s. — [Egger thesis](https://theses.eurasip.org/wp-content/uploads/egger-sebastian-qoe-analysis-for-interactive-internet-applications-in-the-presence-of-delay.pdf)

### Inferences
- The project's own observation fits the literature: rooms rated "Excelente" while showing 10–25 ms of speed-test jitter.
  - Microsoft treats ≤30 ms as fine for calls.
  - The frame-jitter model predicts ≈3.2–4.0 even if all of that jitter reached the display, and a playout buffer normally absorbs most of it.
  - Skype's curve gives only a small PCR change across that range. That last point is an inference: VIA plots normalized PCR, and I could not read the exact values in that range.
- Speed-test jitter is a different quantity from the in-app jitter these studies use.
  - Ookla/M-Lab report variation in ping RTT over a short test.
  - RTP interarrival jitter (Teams/Skype) is a smoothed one-way metric.
  - Frame-time SD is measured at the display after buffering.
  - Mapping between them needs care, which strengthens the case against a hard 10 ms cut on speed-test jitter.

### Gaps
- I did not verify NVIDIA GeForce Now's published requirements (the support page returned 403), so I cannot confirm here where "10 ms jitter" comes from. Zoom's and Netflix's published numbers were not fetched either.
- I found no study that measures speed-test jitter and in-app jitter on the same links, so that conversion remains unquantified.

---

## Implicações para o projeto

Prioritized actions, ordered by how strongly the evidence above supports them.

1. **Remove the 10 ms jitter limit for cloud gaming as a hard pass/fail rule.** Supported by Sections 2 and 6: no user test found supports it, the user-derived model is linear and moderate, and a playout buffer sits between network jitter and the player.
   - If a cloud-gaming check is kept, turn jitter into a *graded penalty*. A defensible, sourced anchor is the Teams CQD "poor" boundary of 30 ms, which is vendor-sourced but at least published and 3× looser.
   - Optionally add a soft slope inspired by Xu & Claypool (−0.056 MOS per ms of frame-time SD), labelled clearly as a frame-jitter (not ping-jitter) model and therefore an upper bound on the penalty.
   - Do not cite VIA's 12 ms as a user tolerance threshold: it is a distribution tail for audio calls.
   - Document in the Studio/ruler code that the old 10 ms value had no user-validated source.
2. **Replace binary per-application thresholds with saturating or log curves per application.** These match the relative-ruler direction the project already found better.
   - Web: QoE ≈ a − b·ln(PLT) with saturation below 0.5 s (Egger); feed it an estimated page-load time (RTT × round trips plus transfer) rather than raw Mbit/s.
   - Video calls: saturating in throughput at ~1 Mbit/s per stream (Schmitt); penalty for loss above ~1% and RTT above ~300 ms (VIA's tails, as soft knees).
   - Gaming: delay penalty graded by game delay sensitivity (G.1072 default = high sensitivity), plus the graded jitter term from item 1.
   - Streaming: driven by throughput dips relative to the selected bitrate (stalling) rather than a 4K bandwidth gate.
3. **Do not give the 4K/Netflix bandwidth gate the power to drive "Excelente" verdicts.** User evidence shows small (≤~0.5 MOS) gains from 1080p to 4K at normal distances (Section 4). Bandwidth curves saturate at a few Mbit/s for mobile apps (Section 5).
4. **Treat speed-test jitter as a different metric from in-app jitter.**
   - Before any threshold is applied to the ~11 s speed-test window, check on a few rooms how speed-test ping jitter relates to WebRTC `jitter` (chrome://webrtc-internals) or the frame-time SD of a cloud-gaming client.
   - This links to the existing note that router counters are speed-test-window deltas.
5. **Use the planned phone collection app (the 2026-10-28 meeting MVP) to make the thresholds the project's own.**
   - Collect ACR 1–5 plus a yes/no acceptability question per application and room, as Casas and Egger did. With a modest per-condition n (the cited lab studies used 25–52 people), fit per-application curves on the project's own Wi-Fi data.
   - Prioritize the gaming and video-call conditions with 10–30 ms jitter, which is exactly where the old fixed ruler and the users disagree.
6. **Keep the relative ruler as the default and report fixed vendor numbers only as context.** The literature consistently finds monotone, saturating QoS-to-QoE curves (Weber–Fechner/IQX), and in Schmitt et al. user and group factors explained far more variance than system factors (8.45% vs 73.69%). Both point to relative, per-user or per-building framing rather than universal fixed cut-offs.

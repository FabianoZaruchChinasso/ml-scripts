# Temporal and context effects in subjective QoE: recency, peak-end, memory, anchoring/range, expectations, intermittent failures

Project context for the report writer: in fast homes, some rooms get a "bad" rating from users even though every ~11 s speed test there passes all application thresholds. Disconnections are not logged. The question is which of two approaches better matches how people rate: a per-home relative ruler (each room compared to the home's best room) or a time-based metric (worst moments, dropouts, minimum speed). This note covers only experiments with human participants.

Source access log (what was actually read in this session):
- Hoßfeld et al., "The Memory Effect and Its Implications on Web QoE Modeling", ITC 2011: full text read (ITC archive PDF).
- Bampis et al., "Study of Temporal Effects on Subjective Video QoE", IEEE TIP 2017: full text read (LIVE PDF).
- Seshadrinathan & Bovik, "Temporal hysteresis model of time varying subjective video quality", ICASSP 2011: full text read in part (LIVE PDF).
- Tran, Ngoc, Hoßfeld, Seufert, Thang, "Cumulative Quality Modeling for HTTP Adaptive Streaming", arXiv 1909.02772v3 (2020): full text read in part.
- Hoßfeld, Seufert, Sieber, Zinner, "Assessing effect sizes of influence factors towards a QoE model for HTTP adaptive streaming", QoMEX 2014: full text read (Augsburg postprint).
- Hoßfeld et al., "Quantification of YouTube QoE via crowdsourcing", IEEE ISM 2011: full text read.
- Seufert et al., "A survey on QoE of HTTP adaptive streaming", IEEE COMST 2015: full text read (relevant sections).
- Guse, Hohlfeld, Wunderlich, Weiss, Möller, "Multi-episodic Perceived Quality of an Audio-on-Demand Service", QoMEX 2020: full text read (arXiv 2005.00400).
- A. Sackl, PhD thesis on user expectations and QoE (netidee-hosted PDF, 2017): chapter 2 read (expectation-trigger studies Trigger 1–4 and "Measuring" studies).
- Cooper & Yamagishi, "Investigating Range-Equalizing Bias in MOS Ratings of Synthesized Speech", Interspeech 2023: full text read in part (arXiv 2305.10608).
- Redelmeier & Kahneman 1996 (Pain): PubMed abstract read.
- Oliver 1980 (JMR): abstract read via the Semantic Scholar API.
- Hands & Avons 2001 (Applied Cognitive Psychology): NOT accessible. Wiley returned 403 and the Semantic Scholar abstract field is elided. Only a search-engine summary of the abstract was seen, so claims are marked as abstract-level via secondary.
- Zielinski, Rumsey & Bech 2008 (JAES): NOT accessible (AES 403). Only search-engine summaries of the abstract were seen.
- Sackl, Egger & Schatz, QoMEX 2014 (Web QoE fluctuations/outages): only an abstract summary from a bibliographic index.
- Hoßfeld et al., "Initial delay vs. interruptions", QoMEX 2012: only search-result summaries. Its DOI is unverified.
- Guse et al. 2017 (QUEX, telephony multi-episodic): abstract-level via search, plus the summary inside Guse et al. 2020.
- Tavakoli et al. 2016 (JSAC): metadata only (not read).
- Kahneman et al. 1993 ("When more pain is preferred to less"): metadata only (not read).
- Moorthy et al. 2012 (LIVE Mobile, IEEE JSTSP): abstract-level via search only.
- Ghadiyaram, Pan & Bovik 2018 (IEEE TIP): skimmed. It is a modeling paper that cites the hysteresis effect.

## 1. Recency, peak-end and duration neglect: do worst moments or last moments drive overall ratings?

### Takeaway
Across medicine, TV picture quality and video streaming, retrospective judgments follow the worst moment ("peak") and, in short single sequences, the last moments ("end"). Duration is largely neglected. The peak/minimum effect is the most robust one across timescales. The recency effect is strong within one 30 s to 5 min sequence. It becomes small or non-significant when there are many quality switches (Cohen's d ≈ 0.10) or when the judgment spans several days (n.s. in a 6-day, n=93 field study). Rebuffering/stalling (interruptions) dominates ratings. An early severe event keeps depressing ratings even when it is followed by good quality.

### Cited Findings
**Peak-end and duration neglect (psychology baseline)**
- Redelmeier & Kahneman 1996, *Pain* 66(1):3–8, DOI 10.1016/0304-3959(96)02994-6. Patients' pain was recorded in real time during colonoscopy (n = 154) and lithotripsy (n = 133). Retrospective total-pain judgments correlated strongly with the peak intensity (P < 0.005) and with the intensity of the last 3 min (P < 0.005). "Despite substantial variation in the duration of the experience, lengthy procedures were not remembered as particularly aversive." — [PubMed 8857625](https://pubmed.ncbi.nlm.nih.gov/8857625/)

**Recency and peak in TV picture quality (abstract-level, secondary)**
- Hands & Avons 2001, "Recency and duration neglect in subjective assessment of television picture quality", *Applied Cognitive Psychology*, DOI 10.1002/acp.731. Five experiments with 30 s sequences. Retrospective quality ratings were lower when the worst segment came at the end rather than the beginning (recency). The recency effect disappeared when viewers rated continuously. Impairment duration had little effect (duration neglect). In regression, peak impairment intensity was the best predictor of ratings. n per experiment and effect sizes were not accessible. — [zendy record / search summary](https://zendy.io/title/10.1002/acp.731); full text inaccessible ([Wiley](https://doi.org/10.1002/acp.731) returned 403)
- An earlier study, Aldridge et al. 1995 (IEE conference, DOI 10.1049/cp:19950676), reportedly found that impairments near the end of 30 s sequences got more weight, with a rating difference of about half a point on a 5-point scale. This comes from a search-engine summary only and was not verified. — [doi.org record](https://www.doi.org/10.1049/CP:19950676)

**Hysteresis: drops are punished fast, recovery is slow**
- Seshadrinathan & Bovik, ICASSP 2011. 38 subjects (32 retained after screening) gave continuous ratings of time-varying video quality. "Subjects react sharply to drops in video quality and provide poor quality scores for such regions and do not react as sharply to improvements in quality thereon." The authors call this a hysteresis effect: "the memory of poor quality elements in the past causes subjects to provide lower quality scores immediately af[ter]". — [LIVE PDF](https://www.live.ece.utexas.edu/publications/2011/ks_icassp_2011.pdf)
- Ghadiyaram, Pan & Bovik 2018 (IEEE TIP 27(5)) build a continuous-time streaming QoE model around a "hysteresis or recency 'aftereffect'". This is a modeling paper and adds no new participant data on the effect itself. — [LIVE PDF](https://www.live.ece.utexas.edu/publications/2018/ghadiyaram2018learning.pdf)

**Long streaming sessions with rebuffering (LIVE-Netflix)**
- Bampis et al. 2017, IEEE TIP 26(11):5217, DOI 10.1109/TIP.2017.2729891. 112 distorted videos from 14 contents, each at least 1 min long, rated by more than 55 subjects on a mobile device, with both continuous and retrospective scores. — [PDF](https://www.colorado.edu/lab/live/publications/bampis2017study.pdf)
  - "Rebuffering is always obvious and unpleasant to subjects." A constant low bitrate chosen to avoid rebuffering "was not tolerated by subjects". — [Bampis 2017](https://www.colorado.edu/lab/live/publications/bampis2017study.pdf)
  - Rebuffering vs an equal-bandwidth low bitrate depended on content. Out of 14 contents, subjects preferred the very low bitrate in 4, rebuffering in 3, and 7 were statistically equivalent. — [Bampis 2017](https://www.colorado.edu/lab/live/publications/bampis2017study.pdf)
  - Recency: the SROCC between 10 s windowed averages of the continuous scores and the retrospective score was higher for more recent windows. Retrospective scores often failed to separate the playout patterns statistically, which the authors attribute to recency plus duration neglect. — [Bampis 2017](https://www.colorado.edu/lab/live/publications/bampis2017study.pdf)
  - Primacy/memory of bad events: "recency by itself is not enough to explain subject QoE when a very negative QoE experience has occurred in the past". With two rebuffering events, even recent windows correlated poorly with the retrospective score. A second rebuffering event caused a larger drop, which the authors attribute to "memory of a recent rebuffering event". — [Bampis 2017](https://www.colorado.edu/lab/live/publications/bampis2017study.pdf)
- Moorthy et al. 2012 (LIVE Mobile VQA, IEEE JSTSP) has 200 distorted videos from 10 references, including time-varying distortions and frame freezes, rated on phones and tablets. Only abstract-level details were seen, and the hysteresis claim attributed to it in the assignment was not verified in the text. — [record](https://ersearch2.cvtisr.sk/vufind/SummonRecord/FETCH-LOGICAL-c267t-39e9fc5fa0a83d26f76e055c280eafe1799fb62cf7be66c39e3d347bf7f4085c3/Details)

**Minimum-window quality as a pooling component**
- Tran et al. (arXiv 1909.02772v3, 2020). 71 subjects (2 rejected under ITU-T P.913, about 23 valid ratings per sequence) gave a 1–5 retrospective rating at the end of long HAS sequences. Statistical analysis identified three components of cumulative quality: minimum window quality, last window quality and average window quality. The first window (primacy) had no significant effect for any window size (10–60 s). The last window was significant but with a small effect (η²p < 0.06) only for 50–60 s windows. — [arXiv](https://arxiv.org/pdf/1909.02772)

**Recency is weak once there are several switches (large crowdsourcing study)**
- Hoßfeld, Seufert, Sieber & Zinner, QoMEX 2014, DOI 10.1109/QoMEX.2014.6982305. About 710 unique crowd workers, each pattern rated by at least 82 (on average 106) participants, short adaptive-streaming clips. — [Augsburg postprint](https://opus.bibliothek.uni-augsburg.de/opus4/frontdoor/deliver/index/docId/107445/file/107445.pdf)
  - Switch amplitude was the main effect, with Cohen's d = 0.70 (low vs high amplitude). — [Hoßfeld 2014](https://opus.bibliothek.uni-augsburg.de/opus4/frontdoor/deliver/index/docId/107445/file/107445.pdf)
  - Ending on low vs high quality gave Cohen's d = 0.10. With 3 or 5 switches the confidence intervals overlapped, and only the single-switch pattern showed a slight high-end advantage. Recency time (time since the last switch) was not significant (d = 0.07). Time spent on the highest layer, not switching frequency, drove QoE. — [Hoßfeld 2014](https://opus.bibliothek.uni-augsburg.de/opus4/frontdoor/deliver/index/docId/107445/file/107445.pdf)
- The Seufert et al. 2015 survey (IEEE COMST) summarizes this and other studies. One study ([102] in the survey) found "a strong recency effect, i.e., higher quality in the end of a video clip leads to higher QoE". The survey concludes that stalling "is the worst degradation and has to be avoided". — [Seufert 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107475/107475.pdf)
- Tavakoli et al. 2016 (IEEE JSAC, DOI 10.1109/JSAC.2016.2577361) is a multi-lab plus crowdsourcing cross-analysis of switching and recency. Only a search summary was seen: higher switching frequencies are not penalized if enough time is spent at high quality. Its recency numbers were not read. — [metadata](https://publications.ait.ac.at/en/publications/perceptual-quality-of-http-adaptive-streaming-strategies-cross-ex/)

### Inferences
- The strongest and most consistent finding is "worst part dominates, duration does not". This is evidence for a time-based metric based on the minimum or worst episode, not on medians or means of successful tests. An ~11 s median throughput is close to the opposite of what these studies say people remember.
- Duration neglect means that a short dropout can count almost as much as a long one in memory. So a room with rare but severe events (dropouts that are never logged) can be rated "bad" even if 95%+ of its successful samples are excellent.
- Recency is fragile beyond single short sequences. A model should not count on "last test in the room" as the main explanatory variable.

### Gaps
- n, effect sizes and the exact regression results of Hands & Avons 2001 were not accessible.
- Kahneman et al. 1993 (cold-water study) was not opened. Only metadata was seen.
- I found no human-participant study of peak-end specifically for Wi-Fi or home broadband rooms. All evidence comes from video, TV, speech and web transfer.

## 2. Memory of past sessions and multi-episodic judgments

### Takeaway
Ratings of the current condition depend on what came just before. On the web, the same 480 ms page-load time got MOS 3.3 after a better condition and 3.8 after a worse one, a difference of 0.5 points (95% CI 0.26–0.76). Over days, a single bad usage day out of six lowered the overall judgment from 4.7 to 3.6. The judgment saturated after about two bad days, and later good days did not significantly repair it (recency n.s.).

### Cited Findings
- Hoßfeld, Biedermann, Schatz, Platzer, Egger & Fiedler, "The Memory Effect and Its Implications on Web QoE Modeling", ITC 23, 2011. — [ITC archive PDF](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf)
  - Design: one local lab test (29 users) and two online tests (72 and 26 users). Each user viewed 40 web pages in fixed, identical PLT sequences and rated each page on a 5-point ACR scale ("Are you satisfied with this download speed?"). — [Hoßfeld ITC 2011](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf)
  - PLT and MOS were tightly coupled (Pearson r = −0.957 in online test #1), but the current PLT alone did not explain MOS. — [Hoßfeld ITC 2011](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf)
  - Contrast effect: in online test #2, sections A1 and A5 both had PLT 480 ms. A1 followed 240 ms and was rated μ1 = 3.3. A5 followed 720 ms and was rated μ5 = 3.8. The difference had a 95% CI of [0.26; 0.76]. "The perception of the current QoS level is strongly biased by the preceding quality levels experienced." In another pair (A2 vs A4) the difference was only about 0.11. — [Hoßfeld ITC 2011](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf)
  - After a quality drop, MOS "strongly decays and this decay continues" over the next pages of the same section. In an SVM over past ratings, the previous rating OS₁ had a strong weight. — [Hoßfeld ITC 2011](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf)
  - Caveat: all PLTs were sub-second to about 1.2 s on a simple photo page. This is a short-term, within-session memory effect, not a multi-day one.
- Guse et al., QoMEX 2020 (arXiv 2005.00400). Audio-on-demand used twice a day for 6 days by 93 participants at home on their own equipment, between-subject design, HP (MP3 192 kbit/s) vs LP (heavily degraded) days. — [arXiv PDF](https://arxiv.org/pdf/2005.00400)
  - Multi-episodic judgment after day 6: HP only 4.7 (SD 0.6), LP on day 6 3.6 (0.6), LP on days 5–6 2.5 (1.0), LP on days 4–6 2.4 (0.7). Conditions differed significantly (H(3) = 68.37, p < 0.001), but days 5–6 vs 4–6 did not (p = 0.366), so the effect saturates. — [Guse 2020](https://arxiv.org/pdf/2005.00400)
  - Recency: LP on day 4 followed by HP days gave 4.1 vs 3.6 for LP on day 6, which was not significant (W = 138.5, p = 0.136, one-sided). LP on days 4–5 vs 5–6 gave 3.0 vs 2.5 (p = 0.087). The authors' conclusion: "LP usage episodes should thus be avoided as the subsequent HP usage episodes do not make up for prior LP experiences." — [Guse 2020](https://arxiv.org/pdf/2005.00400)
  - The multi-episodic judgment stayed about 1 point above the episodic LP ratings, so the overall impression is not just the worst episode. — [Guse 2020](https://arxiv.org/pdf/2005.00400)
  - Ambiguity: the text says "approximately 1 pt per LP usage episode for up to two episodes", while the table manipulates LP days (two episodes per day). The episodic MOS range (0.9–5.0) suggests the scale is not a plain 1–5 ACR.
- Guse et al. 2017 (Quality and User Experience 2:8) studied one telephony session of up to 45 min, with about 205 participants over two experiments according to Guse 2020. More low-performance episodes lowered the overall judgment until it levelled off. The position of the LP episode mattered only for two-party conversations. Seen at abstract level only. — [bibbase record](https://bibbase.org/network/publication/guse-weiss-haase-wunderlich-mller-multiepisodicperceivedqualityforonesessionofconsecutiveusageepisodeswithaspeechtelephonyservice-2017); [Guse 2020 related work](https://arxiv.org/pdf/2005.00400)
- Earlier multi-day Skype field study (12 days, 2 calls per day, cited in Guse 2020 as [8]): "the results were rather limited". — [Guse 2020](https://arxiv.org/pdf/2005.00400)

### Inferences
- For a home, one bad usage episode in a room (for example a call that dropped) can lower that room's remembered quality by about one point on a 5-point-like scale for days. Later good speed tests in that room will not "repair" the label. This matches the project symptom: good recent tests, bad label.
- The contrast effect (0.5 MOS for the identical condition) is the mechanism that would make a relative ruler match ratings. People rate relative to the reference they have just experienced.

### Gaps
- No multi-episodic study of Wi-Fi or home broadband with real outages was found.
- Guse 2017's exact numbers were not read.

## 3. Anchoring, range and context effects; relative judgments

### Takeaway
MOS is a "rubber ruler": listeners stretch their ratings over the whole scale for whatever range of stimuli they are shown. Restricting a test to the top 6% of systems produced many "1" ratings for systems that never got a 1 in the full test, and shifted some systems down by about 1 MOS point. Reviews put such biases at up to 22% (MUSHRA) and up to 40% of the scale. Listeners still keep some absolute sense. This strongly supports the idea that occupants of a fast home will call their worst room "bad" relative to the home's own range.

### Cited Findings
- Cooper & Yamagishi, Interspeech 2023 (DOI 10.21437/Interspeech.2023-1076, arXiv 2305.10608). They re-ran MOS tests on progressively "zoomed-in" subsets of the 187 BVCC synthesis systems (top 50%, 25%, 12%, 6%). The test was designed for 200 unique listeners. — [arXiv PDF](https://arxiv.org/pdf/2305.10608)
  - "While no samples from the top 11 systems (6% zoom) received ratings of 1 in the original BVCC listening test, we nevertheless observe many '1' ratings in the new test where listeners only heard samples from the top 6% of systems." — [Cooper & Yamagishi](https://arxiv.org/pdf/2305.10608)
  - "A substantial decrease of about one MOS point in scores for some systems". Listeners "nevertheless maintain some sense of absolute quality", shown by the skew of the score distributions. — [Cooper & Yamagishi](https://arxiv.org/pdf/2305.10608)
  - Narrower ranges let more pairwise differences reach significance. For the top 12% of systems, the 25% test found 117 significant pairs vs 61 in the original BVCC test. — [Cooper & Yamagishi](https://arxiv.org/pdf/2305.10608)
- Zielinski, Rumsey & Bech 2008, "On some biases encountered in modern audio quality listening tests: a review", JAES 56(6):427–451. Per search summaries of the abstract: errors from affective judgments, response mapping and interface biases can reach up to 40% of the full scale, and results should be treated as relative rather than absolute. Full text not accessible. — [AES E-Library](https://aes2.org/publications/elibrary-page/?id=14393) (403 on fetch; search summary only)
- Zielinski et al. 2007 (AES convention, MUSHRA) found systematic discrepancies up to 22% from stimulus spacing and range-equalizing biases. Part 2 (JAES 2016) covers five systematic errors, including range equalization. Search summaries only. — [AES 2007](https://aes2.org/publications/elibrary-page/?id=14237); [AES 2016](https://aes2.org/publications/elibrary-page/?id=18105)
- The Sackl thesis links range-equalization to expectation adaptation: "when a set of stimuli is presented that has a specific quality range, the usage of the quality scale will be different for an individual stimulus than when that stimulus is presented with a different set of stimuli." — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- Within-session contrast on the web: identical 480 ms PLT rated 3.3 vs 3.8 depending on the preceding condition (see section 2). — [Hoßfeld ITC 2011](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/papers/1569411677.pdf)

### Inferences
- If occupants rate all rooms of their own home in one sitting (or from memory of that home), range-equalizing bias predicts that the worst room in an excellent home gets a low score even when it is objectively adequate. A per-home relative ruler would then fit the labels better than absolute thresholds. That fit would reflect how the ratings were produced, not necessarily whether the room is unusable.
- Cooper's "some sense of absolute quality" finding means the relative effect is partial. A model mixing absolute level with within-home position should beat either pure form.

### Gaps
- I found no study of "relative QoE across devices or locations" with human participants (for example rating rooms or locations in one's own home). The transfer from listening-test range effects to home rooms is an inference.
- ITU-T P.800/P.910 context-effect quantifications (for example from the P.800 Annex or Möller's work) were not retrieved in this session.

## 4. Expectations and habituation from usual service; customer satisfaction theory

### Takeaway
Evidence that people's usual home connection changes how they rate a given condition is weak and inconsistent. In a crowdsourcing study with 1,349 users, YouTube ratings were statistically independent of the user's own access speed. Labeling an identical line as "3G" made users more tolerant of low QoS in 2011 (n=49; 71% of within-subject rating differences favored the wireless label). The effect vanished in 2013 with an "LTE" label (n=45). A price/contract manipulation (n=44) had no significant effect. Measured individual expectations improved model fit by only 4–12%. Oliver's expectation-disconfirmation model supplies the theory. In QoE, within-session context (section 3) is far stronger than long-term habituation.

### Cited Findings
- Hoßfeld et al., "Quantification of YouTube QoE via crowdsourcing", IEEE ISM 2011, DOI 10.1109/ISM.2011.87. 1,349 Microworkers users rated stalling patterns on a 54 s clip. "The user ratings are statistically independent from the video parameters ..., the usage pattern of the user, as well as its access speed to reflect the user's expectations." Stalling parameters dominated. — [Augsburg PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107463/107463.pdf)
- Sackl PhD thesis, expectation-trigger studies (Table 2.1). — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
  - Trigger 1 (2011, within-subjects, n = 49): users browsed (news site, Google Maps, video) over a mock "ConnectionSwitcher" that pretended to switch between ADSL and 3G. Both connections were technically identical. For low QoS, wireless-labeled connections were rated more tolerantly: 71% of the per-user DiffRatings were significantly positive and 17% showed the opposite. The effect was weak at mid/high QoS and absent for video. This was published as Sackl, Masuch, Egger & Schatz 2012, "Wireless vs. wireline shootout: how user expectations influence QoE". — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
  - Trigger 2 (2013, n = 45, "LTE" label): no significant labeling effect except one condition. The questionnaire showed expectations for fixed vs mobile had converged. Correlations: home download bandwidth vs "Fixed high-speed Internet access is very important", Kendall τ = 0.46. Months of mobile-Internet use vs "I expect 100% stability from my fixed Internet access", r = −0.67 (more mobile experience, lower stability expectation at home). The author calls these "preliminary". — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
  - Trigger 3 (2012, n = 26): a "standard TV quality" text hint before a video lowered its rating. An "HD" hint did not raise ratings as expected. — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
  - Trigger 4 (2011, between-subjects, n = 44): an imagined bronze/silver/gold VoD contract had no significant effect on video ratings. — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
  - "Measuring" studies: adding each participant's stated adequate or desired expectation (for example "How long should it take to download a 50 MB file at home?") to a QoS→MOS model improved fit by +4.44% to +12.42%. One example is the 50 MB download at 4/14/45 Mbit/s, +9.41%. — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
  - The thesis notes that related work assumes "users with a high-speed Internet connection at home might be less tolerant regarding long page loading times" and that "no explicit empirical evidence is presented" for similar claims. — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- Oliver 1980, JMR 17(4):460–469, DOI 10.1177/002224378001700405: "consumer satisfaction as a function of expectation and expectancy disconfirmation", supported by "a two-stage field study ... of a flu inoculation". This is a health-service field study, not a network one. n was not given in the abstract. — [SAGE](https://journals.sagepub.com/doi/10.1177/002224378001700405); abstract via [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1177/002224378001700405)
- A mobile YouTube study reports that opinion-survey MOS was about 20% higher than a model built from wired scenarios, which suggests more lenience on wireless. Search snippet only. Treat it as weak. — [arXiv 1405.4709](https://arxiv.org/pdf/1405.4709)

### Inferences
- "Fast-home users are spoiled" (long-term habituation) is not well supported as a strong, stable effect. The robust mechanisms are within-session contrast and range equalization (section 3), plus worst-episode memory (sections 1–2).
- Expectation of reliability may matter more than expectation of speed. The Trigger 2 correlation (r = −0.67) concerns stability expectations, which fits the project's unlogged disconnections.

### Gaps
- No study was found where participants with different usual home speeds rated the same Wi-Fi condition in their own homes.
- Oliver's sample size and effect sizes were not read.

## 5. Intermittent failures: interruptions/outages vs steady low quality

### Takeaway
Interruptions are the dominant impairment in streaming and interactive web use. One 3 s stall in a 54 s YouTube clip dropped MOS from about 5.0 to about 3.2, and three such stalls to about 2.2. Stalling consistently outweighs bitrate reductions, though a constant very low bitrate is also not tolerated. Interactive web apps (Google Maps) were "heavily impaired by outages" while a news site was tolerant. Uncontrolled degradations (loss, stalls) hurt more than controlled ones (lower resolution).

### Cited Findings
- Hoßfeld et al., ISM 2011 (n = 1,349 crowd users). Exponential mappings: for 3 s stalls, MOS = 2.99·e^(−0.96·N) + 2.01 (R² = 0.997). For 1 s stalls, MOS = 3.26·e^(−0.37·N) + 1.65 (R² = 0.941). Computed from these: N = 0 gives about 5.0, one 3 s stall about 3.15, three 3 s stalls about 2.18, one 1 s stall about 3.90. — [Augsburg PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107463/107463.pdf)
- Bampis et al. 2017 (more than 55 subjects): rebuffering "always obvious and unpleasant". Earlier rebuffering keeps lowering later ratings, and a second rebuffer causes larger drops (see section 1). — [Bampis 2017](https://www.colorado.edu/lab/live/publications/bampis2017study.pdf)
- Seufert et al. 2015 survey: users "are more sensitive to stalling than to an increase of quantization parameter". The provisioning–delivery hysteresis (Zinner et al. 2010) "confirms that it is better to control the quality than to suffer from uncontrolled effects like stalling", because packet-loss impairments were "much more severe" than controlled resolution reduction. — [Seufert 2015 PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107475/107475.pdf)
- Sackl, Egger & Schatz, "The influence of network quality fluctuations on Web QoE", QoMEX 2014, pp. 123–128, DOI 10.1109/QoMEX.2014.6982307. Two lab experiments on outages, throughput alternations and increasing/decreasing throughput. Interactive applications like Google Maps were "heavily impaired by outages", browsing a news site was more tolerant, and alternation frequency had no significant effect. Abstract-level only, with no n or durations. — [ISC record](https://search.isc.ac/inventory/49/185109.htm)
- Sackl, Casas, Schatz, Janowski & Irmer, "Quantifying the impact of network bandwidth fluctuations and outages on Web QoE", QoMEX 2015, DOI 10.1109/QOMEX.2015.7148078. Title and metadata only. — [OpenAlex](https://api.openalex.org/works/doi:10.1109%2FQOMEX.2015.7148078)
- Hoßfeld, Egger, Schatz, Fiedler, Masuch & Lorentzen, "Initial delay vs. interruptions: between the devil and the deep blue sea", QoMEX 2012. Per search summaries, lab and crowd studies show users are far more sensitive to interruptions than to initial delay of comparable length. Numbers and DOI not verified. — [researchr record](https://researchr.org/publication/HossfeldESFML12)
- Guse 2020: one degraded day among six lowered the 6-day judgment from 4.7 to 3.6 (see section 2). This is the closest available analogue to "occasional bad episodes in a room". — [Guse 2020](https://arxiv.org/pdf/2005.00400)

### Inferences
- In this project, an unlogged Wi-Fi disconnection is the home analogue of a stall or outage. The literature says it is the most damaging single event, and it is remembered (peak, hysteresis, multi-episodic persistence). A room can thus be "bad" for occupants because of events the ~11 s successful-test dataset structurally cannot contain.
- The dominance of the outage effect for interactive apps over passive ones suggests the label depends on what the room is used for (calls or video calls vs browsing).

### Gaps
- No human-participant study of Wi-Fi association loss or roaming dropouts and their rating impact was found. Call-drop rating studies (for example Chen et al. on Skype) were not retrieved in this session.
- n and outage-duration curves for Sackl 2014/2015 were not accessible. The Augsburg repository refused connections late in the session.

## Implicações para o projeto

Prioritized actions, each tied to the evidence above.

1. **Log and model failures and worst moments first (highest priority).** Peak-end (Redelmeier & Kahneman, n=287), "peak impairment best predictor" (Hands & Avons), minimum-window quality (Tran, n=71), stalling dominance (Hoßfeld 2011, n=1,349: one 3 s stall costs about 1.8 MOS) and hysteresis (Seshadrinathan, n=38) all point to the same conclusion: users remember the worst episode, not the median. Labels and features should use per-room worst-case statistics:
   - minimum or low-percentile (p5/p10) throughput;
   - fraction of failed or aborted tests;
   - disconnect, association-loss and roaming counts and time since the last one, from router or collector logs, not from successful tests.

   This is impossible today because failures are dropped. Instrumenting them is the prerequisite. Duration neglect implies that a count of severe events matters more than total bad time.
2. **Treat the per-home relative ruler as a rating-calibration effect, not as the ground truth of usability.** Range equalization (about 1 MOS shift, the "rubber ruler"; Cooper & Yamagishi) and within-session contrast (0.5 MOS for the identical condition; Hoßfeld ITC 2011) explain why the worst room in a fast home gets "bad". Recommendation: model the label as f(absolute worst-moment features) + g(position of the room within its home's range). Compare three models on held-out homes: absolute-only, relative-only and mixed. Cooper's finding that listeners keep "some sense of absolute quality" predicts the mixed model wins. Report per-home results.
3. **Do not over-weight "usual service" habituation.** Evidence that a fast home connection makes users harsher is weak or null: ISM 2011 found ratings independent of access speed, Sackl's Trigger 2 and Trigger 4 found nothing, and expectations add only about 4–12% fit. Do not add "home plan speed" as a proxy for expectations unless the data shows it. Within-home range (action 2) is the better-supported mechanism.
4. **Change how ratings are collected (for the phone collection app) to separate the effects.**
   - Ask per-episode ratings right after each use (episodic) plus a periodic per-room retrospective rating (multi-episodic). Guse shows these differ: multi-episodic is about 1 pt above the bad episodes and saturates after about two bad days.
   - Ask an absolute, anchored question in addition to the MOS-like scale. Sackl's thesis used a binary "Would you accept this quality at home?". Examples here: "Could you make a video call here without problems?" or "Did the connection drop?". This reduces the rubber-ruler effect.
   - Record the event the user remembers ("dropped", "froze", "slow to load") and when it happened. Peak/hysteresis predicts this event explains the rating.
   - Randomize or record the order in which rooms are rated, and avoid asking for all rooms of a home in one sitting without fixed anchors. Otherwise the ratings measure position within that home's range. Show the same anchor descriptions in every home.
   - If rooms must be rated in one sitting, also collect one "reference" condition common to all homes (for example a fixed description of good and bad call quality) to allow cross-home normalization.
5. **Prefer recency-robust summaries over "last test".** Recency was small with several switches (d = 0.10, Hoßfeld 2014) and n.s. across days (Guse 2020), while worst-episode effects persisted. Use "worst of the last N days" plus "event count" windows, not the most recent ~11 s test.
6. **Weight by usage type.** Outages heavily impair interactive apps (Google Maps) but not news browsing (Sackl 2014). Rooms used for calls or video calls should get stronger dropout penalties. Record the main use per room in the app.
7. **Stated limitation for the report.** None of the cited experiments is about Wi-Fi rooms. The transfer from video, speech and web lab or crowd tests to home rooms is an inference that the project's own collection data (actions 1 and 4) must validate.

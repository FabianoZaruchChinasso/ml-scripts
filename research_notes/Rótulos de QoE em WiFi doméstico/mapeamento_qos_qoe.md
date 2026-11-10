# Mapping network QoS (throughput, latency, jitter, loss) to QoE classes: fixed per-application thresholds vs relative/expectation-based judgments

Scope note: written for a project that labels home Wi-Fi QoE per room (good/degraded/bad) from ~11 s speed tests and router metrics. It weighs fixed per-application thresholds (video call, 4K streaming, cloud gaming) against a ruler relative to the best room of the same home. Access status is given for every source. "Full text" means I opened and read the document. "Abstract/secondary" means I saw only the abstract, a search snippet, or a description written by the same authors elsewhere.

---

## 1. IQX hypothesis, Weber-Fechner law and logarithmic laws: what they are and what they imply for absolute vs relative thresholds

### Takeaway
The two canonical QoS-to-QoE functions are the IQX exponential (QoE = a*exp(-b*x) + c, for impairments such as loss or reordering) and the Weber-Fechner logarithm (QoE = a*ln(b*x), for waiting time and for throughput as a stimulus). Both predict diminishing returns. The logarithm is the relative one: equal *ratios* of the stimulus give equal steps in QoE. Neither is an absolute threshold law, and their own authors later showed that the same QoS gives different QoE depending on what the user experienced just before (the memory effect).

### Cited Findings
- **IQX hypothesis (Fiedler, Hossfeld, Tran-Gia, "A generic quantitative relationship between quality of experience and quality of service", IEEE Network 24(2), 2010, DOI 10.1109/MNET.2010.5430142).** It proposes an exponential link between QoE and one QoS impairment. The rationale is that the change in QoE per unit of QoS depends on the current QoE level. It was validated on streaming (MOS vs loss and vs reordering ratio, the latter caused by jitter) and on web surfing, where "matchings provided by the IQX hypothesis are shown to outperform previously published logarithmic functions". Access: abstract/secondary only; the IEEE full text was not opened. — [search record / abstract](https://typeset.io/papers/a-generic-quantitative-relationship-between-quality-of-3btyt2c2i5); [Mitra, Zaslavsky, Åhlund, "QoE Modelling, Measurement and Prediction: A Review", arXiv 1410.6952 (full text read)](https://arxiv.org/pdf/1410.6952)
- The functional form, as the authors themselves give it: "IQX hypothesis when using network parameters like bandwidth [Hoßfeld, Fiedler, Tran-Gia, ITC 2007]: QoE(x) = a exp(-b x) + c". It sits alongside "Weber-Fechner law from psychophysics when using page load time as QoS parameter [Reichl et al., ICC 2010]: QoE(x) = a ln(b x)". — [Hoßfeld, Biedermann, Schatz, Egger, Egger, Fiedler, "The Memory Effect and Its Implications on Web QoE Modeling", ITC 23, 2011, slides (full text read)](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/slides/TS3_4_TheMemoryEffectAndItsImplictionsOnWebQoEModeling.pdf)
- Criticism of IQX: "The main drawback of IQX hypothesis is that it only considers one QoS parameter to predict the corresponding QoE value. The authors did not consider the problem of integrating additional context and QoE parameters." The review also notes that IQX was tested for VoIP (PESQ MOS vs loss and jitter) and for web, using "weighted session time and delivered bandwidth". — [Mitra et al., arXiv 1410.6952 (full text)](https://arxiv.org/pdf/1410.6952)
- An early IQX test on voice codecs iLBC and G.711 dates from 2008. — [univie eprint record](https://eprints.cs.univie.ac.at/375)
- **Weber-Fechner law in QoE (Reichl, Egger, Schatz, D'Alconzo, "The Logarithmic Nature of QoE and the Role of the Weber-Fechner Law in QoE Assessment", IEEE ICC 2010, Cape Town, DOI 10.1109/ICC.2010.5501894).** It starts from the psychophysical law that perceived intensity is logarithmic in physical stimulus magnitude, and reports user trials (VoIP and data/bitrate) showing a logarithmic QoS-to-QoE relationship. It also reviews the IQX hypothesis. Access: abstract/secondary only. — [univie record](https://ucrisportal.univie.ac.at/de/publications/the-logarithmic-nature-of-qoe-and-the-role-of-the-weber-fechner-l/)
- The extended journal version is Reichl, Tuffin, Schatz, "Logarithmic laws in service quality perception: where microeconomics meets psychophysics and quality of experience", Telecommunication Systems 52 (2013) 587–600, DOI 10.1007/s11235-011-9503-7. Access: title and bibliographic data only; the abstract was not obtained. — [unpaywall record](https://unpaywall.org/10.1007%2Fs11235-011-9503-7)
- **Memory effect.** "Web pages with same page load time have different QoE, depending on previous QoS conditions." The study saw "exponential decays/increase after quality changes" and "strong deviations from model" when only current QoS is used. The authors conclude: "Memory has to be included in QoE models", "Consider previous experiences as own variables", and model with "Weber-Fechner law with iterative exponential regressions" or a Hidden Memory Markov Model. Studies were run in the lab (traffic shaper) and online (crowd); the slides give no N. — [Hoßfeld et al., ITC 23, 2011 (slides, full text)](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/slides/TS3_4_TheMemoryEffectAndItsImplictionsOnWebQoEModeling.pdf)
- In a later system-level paper the exponential (IQX) web mapping from speed index to MOS has sensitivity β ≈ 0.25. The same paper shows that the GoB/PoW ratios in a system depend on the *variance* of the QoS distribution, not only on its mean ("a sinking PoW ratio as the variance of the waiting time increases"). — [Hoßfeld, Heegaard, Varela, Skorin-Kapov, Fiedler, "From QoS Distributions to QoE Distributions: a System's Perspective", arXiv 2003.12742 (2020; full text read)](https://arxiv.org/pdf/2003.12742)

### Inferences
- In its differential form, the Weber-Fechner law (dQoE ∝ dS/S) is a *relative* law. Halving throughput from 500 to 250 Mbps costs the same QoE as halving from 20 to 10 Mbps, *as long as throughput is the stimulus the user perceives*. This is the strongest theoretical argument for a "relative to best room" ruler. Throughput is not directly perceived, though. Users perceive page load, startup delay, resolution and stalls. Adaptive applications cap their rate (Netflix 4K needs ~15 Mbps; see section 5), so above the cap the perceived stimulus stops changing. The logarithm then turns into a flat line, which is an absolute saturation. Taken together, the theory predicts relative judgments below an application's saturation point and indifference above it. A best-room ruler applied at 300 vs 600 Mbps would therefore call rooms "bad" that users cannot tell apart through any application. The exception is bulk downloads or speed tests themselves, where the speed-test number becomes the stimulus.
- IQX's "change depends on current level" premise means a fixed impairment matters more when quality is already high. This is consistent with users in fast homes being more sensitive to the same absolute drop. That reading is my inference; the papers do not state it.
- The memory effect means a single ~11 s speed-test snapshot per room cannot capture what drives a user's rating. Ratings integrate the user's recent history (see also Finley et al., section 4).

### Gaps
- I did not open the full IEEE Network 2010 paper or the full ICC 2010 paper (paywalled). Fitted coefficients and sample sizes are not reported here.
- I did not find a published, validated logarithmic law with *throughput* (Mbps) as the direct stimulus for a modern adaptive application at broadband speeds (>100 Mbps). Reichl's trials used much lower bitrates (VoIP/early data); exact values were not verified.
- No source tested whether the Weber-Fechner ratio holds *across rooms of the same home*.

---

## 2. What ITU-T and other standards say (G.1011, G.1010, G.1030, G.1072, P.1203, P.1201, P.1401, Y.1541, ETSI/BBF), and how they treat acceptability vs MOS

### Takeaway
ITU-T gives two kinds of tools. G.1010 sets *absolute, user-centric acceptability bounds* per application category (delay and loss boxes, with upper bounds for "unsatisfactory" and lower bounds below which resources are "wasteful"). Parametric opinion models (G.1072, P.1203) map QoS to a MOS on a 5-point ACR scale. None of them defines "good/medium/bad" classes from a home-relative reference. P.10/G.100 defines QoE as "acceptability ... influenced by user expectations and context", but no standard model takes expectations as an input.

### Cited Findings
- **ITU-T G.1010 (11/2001), "End-user multimedia QoS categories", in force.** (Full text read.)
  - It defines eight categories by tolerance to loss and delay, under four delay labels: "Interactive (delay <<1 s)", "Responsive (~2 s)", "Timely (~10 s)", "Non-critical (>>10 s)".
  - "The model provides an indication of the upper and lower boundaries for applications to be perceived as essentially acceptable to the user. Exceed an upper boundary (in loss or delay) and the service will be considered unsatisfactory; exceed a lower boundary, and the service will still be considered acceptable but may be wasteful from a network resource point of view."
  - It groups impairments "without implying that one class is 'better' than another (as in categorisations that use Gold, Silver, etc.)".
  - Table I.1 targets:
    - Conversational voice: one-way delay <150 ms preferred, <400 ms limit; delay variation <1 ms; <3% packet loss ratio (PLR).
    - Videophone: <150 ms preferred, <400 ms limit; <1% PLR; lip-sync <80 ms.
    - One-way video: <10 s delay; <1% PLR.
    - High-quality streaming audio: <10 s; <1% PLR.
  - Web browsing: "Delays of several seconds are acceptable, but not more than about 10 seconds". Interactive games: "very short delays of the order of a fraction of a second". Data must have "essentially zero loss".
  - Note 4 says the videophone values are "long-term target values which may not be met by current technology" (in 2001).
  - — [ITU-T G.1010 record](https://www.itu.int/rec/T-REC-G.1010-200111-I/en); PDF read via the ITU download link for T-REC-G.1010-200111-I.
- **ITU-T G.1011, "Reference guide to quality of experience assessment methodologies".** Versions 06/10, 05/13, 06/15 and 07/16; 07/16 is in force. Access: record page only; content not read. — [ITU-T G.1011 record](https://www.itu.int/rec/T-REC-G.1011/en)
- **ITU-T G.1030, "Estimating end-to-end performance in IP networks for data applications".** 11/05 (superseded) and 02/14 (in force). Access: record page only. I could not confirm the logarithmic page-load-time to MOS formula from the text. — [ITU-T G.1030 record](https://www.itu.int/rec/T-REC-G.1030/en)
- **ITU-T G.1072 (01/2020) + Corrigendum 1 (10/2020), "Opinion model predicting gaming quality of experience for cloud gaming services", in force.** (Summary read.)
  - It predicts "the overall gaming QoE of non-expert gamers for cloud gaming services" with an impairment-factor approach.
  - Inputs are IP network parameters (packet loss, delay) and encoding parameters (framerate, resolution, bitrate). It estimates impacts on video quality and input quality/interactivity.
  - Default mode assumes a game that is highly delay- and frame-loss-sensitive and has high encoding complexity. Extended mode needs the game type.
  - It builds on G.1032 and P.809 and is intended as a "network planning tool".
  - Scope limits: ratings came from non-expert gamers, so predictions may be less accurate for experienced gamers. VR, 3D rendering devices, mobile input and input devices beyond keyboard and mouse are out of scope.
  - An open implementation exists (non-commercial use).
  - — [G.1072 summary](https://itu.int/dms_pubrec/itu-t/rec/g/T-REC-G.1072-202001-I!!SUM-HTM-E.htm); [G.1072 record](https://www.itu.int/rec/T-REC-G.1072/en); [open implementation, GitHub stootaghaj/ITU-G1072](https://github.com/stootaghaj/ITU-G1072)
- **ITU-T P.1203 (11/16; 10/17 in force), "Parametric bitstream-based quality assessment of progressive download and adaptive audiovisual streaming services over reliable transport".**
  - Sessions are 1–5 min. Pv (P.1203.1) video, in modes 0–3, from metadata up to full bitstream. Pa (P.1203.2) audio. Pq (P.1203.3) integrates per-second scores into a session score that accounts for "quality switches, initial loading delay, and stalling".
  - Built for H.264 (HEVC/VP9 by extension). Secondary sources say it was validated up to Full HD, on >1000 sequences, with 5-point ACR MOS as ground truth.
  - The successor, P.1204.3, covers up to UHD/4K and was trained on >600 subjects and ~5,000 sequences.
  - — [ITU-T P.1203 record](https://www.itu.int/rec/T-REC-P.1203/en); [P.1203/P.1204 development page (TU Ilmenau group)](https://telecommunication-telemedia-assessment.github.io/bitstream_based_models); [Robitza et al., MMSys 2018 open dataset/software, DOI 10.1145/3204949.3208124 (Crossref)](https://api.crossref.org/works/10.1145%2F3204949.3208124)
- **ITU-T P.10/G.100 definition (as quoted by Sackl 2016):** QoE is "the overall acceptability of an application or service, as perceived subjectively by the end user [which] may be influenced by user expectations and context." The Qualinet definition was adopted into P.10/G.100 in 2016 (secondary: Wikipedia). — [Sackl PhD thesis, TU Berlin 2016 (full text)](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf); [Wikipedia, Quality of experience](https://www.Wikipedia.com/wiki/Quality_of_experience)
- **Acceptability vs MOS in the E-model (G.107) tradition.** %GoB = P(U ≥ 60) and %PoW = P(U ≤ 45) on the R scale (0–100), with %TME (terminate early) at 36. On the 1–5 scale the thresholds are about 3.1 (GoB) and 2.3 (PoW). Example: MOS 4.0 ↔ R 79.37 ↔ PoW 1.6% ↔ GoB 88.7%. The authors stress that these links "mostly stem from the 1970-1980s" lab data, that "there is ... no guarantee that similar numbers would be observed with the real service in the field", and that the mapping is specific to the E-model. — [Hoßfeld, Heegaard, Varela, Möller, "Formal Definition of QoE Metrics", arXiv 1607.00321 (2016; full text)](https://export.arxiv.org/pdf/1607.00321)

### Inferences
- The standard closest to the project's "fixed per-application thresholds" option is G.1010, and G.1010 itself frames thresholds as a *band*: below the lower bound is "wasteful", above the upper bound is "unsatisfactory". That gives a 3-class structure (more-than-enough / acceptable / unacceptable) defined absolutely per application. It does not accommodate "bad but above every threshold".
- G.1072 and P.1203 output MOS, not classes. Turning their MOS into good/degraded/bad requires choosing cut points (for example GoB-like θ ≥ 4, PoW-like ≤ 2). Section 3 explains why such cut points on MOS do not give the share of users who are satisfied.
- None of these models is validated on Wi-Fi room-level conditions. They take *end-to-end* delay, loss and bitrate as inputs. Room-level Wi-Fi metrics (RSSI, PHY rate, retries) would need a chain such as Wi-Fi metrics → application QoS → MOS. That is what da Hora et al. do (section 4).

### Gaps
- Not accessed: the full texts of G.1011, G.1030, G.1072, P.1203 and P.10/G.100; P.1201; P.1401 (statistical evaluation of objective models); Y.1541 (IP network QoS classes); G.1028 and G.1051 (not checked whether they exist under those numbers); ETSI and Broadband Forum documents on QoE (for example BBF TR-numbers for Wi-Fi/QoE). I cannot report their contents. Y.1541 class values (e.g., class 0 delay/jitter/loss bounds) are not stated here because I did not verify them.
- I could not confirm the exact P.1203 output scale label (O.46) or its resolution ceiling from a primary page.

---

## 3. Literature on expectations, context, acceptability and "QoE beyond the MOS"

### Takeaway
The QoE community agrees on paper that expectations and context shape ratings. Qualinet *defines* QoE as fulfilment of expectations. Empirical evidence for strong expectation effects on network-quality ratings is thin and inconsistent: labelling effects appeared in one lab study (2011) and largely vanished in its replication (2013). Expectation information improved model accuracy by at most 12%. Hoßfeld et al. show that MOS hides user diversity. Acceptance and GoB/PoW must be measured directly, not derived from MOS.

### Cited Findings
- **Qualinet White Paper v1.2 (Novi Sad, 12 March 2013):** "Quality of Experience QoE is the degree of delight or annoyance of the user of an application or service. It results from the fulfillment of his or her expectations with respect to the utility and/or enjoyment of the application or service in the light of the user's personality and current state." Access: the white paper PDF download failed; definition taken verbatim as quoted in the Sackl thesis. — [Qualinet record (HAL)](https://hal.archives-ouvertes.fr/hal-00977812); [Sackl thesis quoting it](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- **Sackl, "Investigations on the Role of Expectations and Individual Decisions in Quality Perception", PhD thesis, TU Berlin, 2016 (full text read).**
  - Abstract: user expectations and decisions "have been neglected so far in QoE related research". Questionnaires based on Zeithaml's "desired and adequate expectations" were used "to enhance the prediction accuracy of quantitative QoE models up to 12%".
  - **Zone of tolerance:** desired expectations are stable. Adequate expectations are context-dependent and get *higher* when "service alternatives" are available, giving "a smaller zone of tolerance". Service is accepted if it lies between adequate and desired.
  - **Labelling studies (n=49 in 2011, n=45 in 2013, within-subject).** Users browsed a news site and Google Maps on technically identical connections labelled "ADSL/wireline" or "3G" (2011) / "LTE" (2013).
    - 2011: a significant labelling effect at *low* QoS. Users were "more tolerant if a wireless-labeled connection was used"; 71% of individual DiffRatings were positive, 17% opposite. At mid/high QoS the effect was "relatively weak", and there was no effect on video ratings.
    - 2013: "no significant labeling effect occurred except for browsing Google Maps and high QoS conditions". Sackl attributes the change to evolving expectations; users had had mobile internet for 15 months on average in 2011 vs 28 months in 2013.
  - **Home bandwidth and expectations (2013, n=45).** Download bandwidth used at home correlated with agreeing that "Fixed high-speed Internet access is very important" (Kendall τ = 0.46, Spearman ρ = 0.53, p<0.05). Users who remembered LTE TV ads rated labelled-LTE browsing more critically (r = 0.39). Sackl calls these "preliminary, initial attempts".
  - **Crucially for this project**, Sackl notes that the claim "users with a high-speed Internet connection at home might be less tolerant regarding long page loading times" is something the cited authors "assume". He says the same of the claim that users used to low-resolution video rate differently ("no explicit empirical evidence is presented").
  - He also cites the range-equalization bias: the same stimulus is rated differently depending on the range of stimuli presented with it.
  - — [Sackl thesis (full text)](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- The journal article from the same line of work is Sackl, Schatz, Raake, Quality and User Experience (Springer), 2017, DOI 10.1007/s41233-016-0004-z. It argues that "for the user it is often not easy to verbalize expectations", for example what a "fast" connection means. Access: abstract/secondary snippet only; the Springer full text was blocked. — [Springer DOI](https://link.springer.com/doi/10.1007/s41233-016-0004-z)
- **"QoE beyond the MOS: an in-depth look at QoE via better metrics and their relation to MOS" (Hoßfeld, Heegaard, Varela, Möller), Quality and User Experience 1:2, 2016, DOI 10.1007/s41233-016-0002-1.** Access: the main article was blocked (Springer); I read the companion technical report in full.
  - The report defines MOS, SOS (standard deviation of opinion scores, S² = a·(−U² + (N+1)U − N) for an N-point scale, with SOS parameter a), quantiles, θ-acceptability Aθ = P(U ≥ θ), acceptance as a binary {0,1} measure, and %GoB = P(U ≥ 4), %PoW = P(U ≤ 2) and %TME.
  - Their web QoE example has R = 72 subjects × 40 page loads.
  - Motivation: "For service providers, acceptance is an important metric to plan, dimension and operate their services" and they want "a link between opinion measurements ... and behavioral measurements".
  - — [Formal Definition of QoE Metrics, arXiv 1607.00321 (full text)](https://export.arxiv.org/pdf/1607.00321); [VTT record of the main article](https://cris.vtt.fi/en/publications/qoe-beyond-the-mos-an-in-depth-look-at-qoe-via-better-metrics-and/)
- Follow-up: "if only a QoS-to-MOS mapping function is available, it is not possible to derive the expected GoB in the system". The fix is to approximate per-condition rating distributions (Beta/binomial) from the MOS mapping plus SOS, then combine them with the observed QoS distribution. In their video-stall example at 4.8% loss, GoB dominates (~82% top ratings); at higher loss PoW is above 60–80%. — [Hoßfeld et al., arXiv 2003.12742 (full text)](https://arxiv.org/pdf/2003.12742)
- Expectation-related influencing factors listed for web QoE: "Usage History", "Expectations", "Memory Effects" (user), "Task/purpose" (context), and device, browser and network (system). — [Hoßfeld et al., ITC 23 slides](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/slides/TS3_4_TheMemoryEffectAndItsImplictionsOnWebQoEModeling.pdf)

### Inferences
- The project's poor agreement with user ratings is what this literature predicts. User diversity (SOS) is large, so a single threshold, absolute or relative, will misclassify a sizeable share of individual ratings even when the threshold is "right" for the mean. Per-room labels should be judged against the *rating distribution* (GoB/PoW-like agreement), not as a deterministic target.
- Zeithaml's zone of tolerance fits the project's situation. A home's best room is a salient "service alternative" that raises the adequate level and narrows the zone of tolerance. This gives a principled (though not directly tested) reason why rooms above every application threshold can be called "bad" in fast homes. The evidence is conceptual plus weak correlations (τ=0.46), not a causal test.
- The 2011 → 2013 reversal in Sackl's labelling results warns that expectation effects drift over time and population. A ruler calibrated on expectations is not stable.

### Gaps
- I could not read the "QoE beyond the MOS" main article. Its specific empirical numbers on how acceptance relates to MOS (e.g., the share accepting at a given MOS) are not reported here.
- I found no study on "QoE fairness" (Hoßfeld et al., TNSM 2018) or "user-perceived bandwidth adaptation" within budget. Not covered.

---

## 4. Evidence that perceived quality depends on relative degradation, history or context rather than absolute values; contextual and personalized QoE; home Wi-Fi QoE prediction

### Takeaway
There is solid evidence that ratings depend on the user's *history*: the memory effect, and peak-end and minimum-throughput effects in field satisfaction. There is also evidence that context (labels, expectations) can shift ratings, mainly at low QoS. I found **no** peer-reviewed study that directly tests "rating relative to the best room of the same home" or "fast-connection users are stricter" with field data. That remains an assumption. The one home Wi-Fi QoE predictor I found (da Hora et al.) maps Wi-Fi metrics to *application* QoE models, which is the absolute approach.

### Cited Findings
- **Finley, Boz, Kilkki, Manner, Oulasvirta, Hämmäinen, "Does network quality matter? A field study of mobile user satisfaction", Pervasive and Mobile Computing 39 (2017) 80–99, DOI 10.1016/j.pmcj.2016.08.014.**
  - It combines satisfaction questionnaires with Netradar device measurements. "Minimum download goodput and device type predict satisfaction with network availability, whereas for network speed only download factors predicted satisfaction."
  - Users "integrate over many measurements and exhibit a known peak-end effect in their ratings."
  - The Aalto press summary says operators "cannot significantly improve users' mobile experience by ... merely increasing the top speed".
  - Context: mobile (Finland), not home Wi-Fi.
  - Access: abstract and press release; full text not read.
  - — [arXiv 1809.03918](https://arxiv.org/pdf/1809.03918); [Aalto research portal](https://research.aalto.fi/en/publications/does-network-quality-matter-a-field-study-of-mobile-user-satisfac/); [Aalto news](https://www.aalto.fi/en/news/most-finns-very-satisfied-with-4g-network-quality)
- Secondary restatement by Würzburg/Nokia authors: "the minimum, median, and current measured download throughput are highly significant in predicting user satisfaction". The same paper treats "stable DSL network connections" as guaranteeing good QoE. It is a small LTE measurement study (urban Berlin vs a rural site) that maps throughput to app QoE: 4K streaming was not possible in the rural area; Maps and WhatsApp were fine everywhere. — [Schwind, Wamser, Hoßfeld, Wunderer, Gassner, "Mobile Internet Experience: Urban vs. Rural – Saturation vs. Starving?", arXiv 1909.07617 (2019; full text)](https://arxiv.org/pdf/1909.07617)
- Memory effect: same page load time, different QoE depending on prior QoS (section 1). — [Hoßfeld et al., ITC 23, 2011](https://archive.itc-conference.org/itc23/fileadmin/ITC23_files/slides/TS3_4_TheMemoryEffectAndItsImplictionsOnWebQoEModeling.pdf)
- Labelling and expectation effects: present at low QoS in 2011 (n=49), mostly absent in 2013 (n=45). Expectation questionnaires improve models by "up to 12%". The claim that fast home connections make users less tolerant is described as an assumption without empirical evidence. — [Sackl thesis 2016](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- Range-equalization bias: ratings of a stimulus depend on the set of stimuli presented with it (cited in Sackl 2016). — [Sackl thesis](https://www.netidee.at/sites/default/files/2017-08/stip%20879-%20dissertation.pdf)
- **da Hora, Van Doorselaer, Van Oost, Teixeira, "Predicting the effect of home Wi-Fi quality on QoE", IEEE INFOCOM 2018.**
  - It passively collects Wi-Fi metrics that commodity APs expose (e.g., PHY rate). It uses support vector regression to predict QoE for popular applications, then K-means to find Wi-Fi quality regions where QoE is poor across applications.
  - About 21% of stations had >25% poor-QoE samples. Most poor-QoE events were short, but some lasted hours.
  - The earlier workshop paper ("... on Web QoE", Internet-QoE@SIGCOMM 2016) applied a web predictor to 4,880 APs in real homes.
  - Access: abstract/secondary only; HAL blocked the full text.
  - — [record](https://katalog.lib.cas.cz/KNAV/EdsRecord/edsair,edsair.doi.dedup.....9e3d7f0e55c471606c55e7c8d1fa8bb6); [dblp, SIGCOMM workshop 2016](https://dblp.uni-trier.de/rec/conf/sigcomm/HoraTDO16.html)
- Casas, Seufert, Wamser, Gardlo, Sackl, Schatz, "Next to you: monitoring quality of experience in cellular networks from the end-devices", IEEE TNSM 13(2), 2016, 181–196, DOI 10.1109/TNSM.2016.2537645. It studies how access bandwidth and latency affect QoE for YouTube, Facebook, Chrome, Google Maps and WhatsApp. Access: PDF downloaded, only the title page checked; numbers not extracted. — [Augsburg OPUS PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/107031/107031.pdf)

### Inferences
- The best-supported "relative" mechanism is *temporal*: a user's own history, minimum, and peaks and ends. A *spatial* comparison against the best room is not directly supported. For home Wi-Fi labels, this suggests a room is judged "bad" when it is *unreliable* (low minimum, dropouts, peak-end episodes), not when its mean is lower than another room's. An ~11 s speed-test window (which the project already notes the router counters reflect) mostly measures the mean and misses the minimum and the dropouts. That is a plausible reason both rulers agree poorly with users in fast homes: high capacity, poor consistency.
- A hybrid is consistent with the literature, though no paper tested it as a labeling rule:
  - absolute per-application floors in the G.1010 sense (below = bad);
  - relative or variability terms (history, minimum, ratio to the home's typical level) as a secondary axis inside the "acceptable" band, framed as Zeithaml's zone of tolerance.
- da Hora et al. is the closest prior art. It predicts QoE from AP-side Wi-Fi metrics via *application models*, i.e., absolute. If the project's direct classifier on radio-only features outperforms application-threshold rulers, that is consistent with treating application QoE models as one input rather than as the label definition.

### Gaps
- No study found on "relative QoE", "contextual QoE" or "personalized QoE thresholds" that compares rooms within a home or uses the user's best-experienced condition as the anchor. Searches for this returned only industry white papers and patents, which I excluded as non-peer-reviewed.
- No empirical study found that measures whether users with faster subscriptions give lower ratings to the *same* condition. Sackl 2016 explicitly flags this as unproven.
- da Hora INFOCOM 2018 full text (applications, rating source, thresholds) not read.

---

## 5. Concrete published thresholds: video calls, 4K streaming, cloud gaming, web browsing

### Takeaway
Vendor numbers are bandwidth floors, mostly for downstream: Zoom 1080p 3.8/3.0 Mbps; Teams 1080p "recommended" 1.5 Mbps (1:1) or 2.5/4.0 Mbps (meetings); Netflix 4K ≥15 Mbps; GeForce Now 1080p60 25 Mbps, 4K120 45 Mbps, <80 ms latency. Most omit jitter and loss. Academic work finds smooth, roughly linear degradation with latency for cloud gaming (≈14% lower QoE per 100 ms), not a cliff. All of these thresholds sit far below typical fast-home Wi-Fi throughput, so they cannot explain "bad" ratings in rooms with hundreds of Mbps.

### Cited Findings
- **Zoom (support article KB0060748, accessed 2026-11-09).**
  - 1:1 video: 600 kbps (high quality), 1.2 Mbps (720p), 3.8/3.0 Mbps up/down (1080p).
  - Group: 1.0 Mbps/600 kbps; 2.6/1.8 Mbps (720p); 3.8/3.0 Mbps (1080p). Gallery receive: 2.0 Mbps (25 views), 4.0 Mbps (49 views).
  - Screen share 50–150 kbps; audio 60–80 kbps.
  - **No latency, jitter or loss recommendations on this page.**
  - — [Zoom bandwidth requirements](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748)
- **Microsoft Teams ("Prepare your organization's network for Teams", ms.date 2026-05-26).**
  - Per-endpoint kbps up/down, as Minimum / Recommended / Best:

    | Modality | Minimum | Recommended | Best |
    |---|---|---|---|
    | Audio | 10/10 | 58/58 | 76/76 |
    | Video, 1:1 | 150/150 | 1,500/1,500 | 4,000/4,000 |
    | Video, meetings | 150/200 | 2,500/4,000 | 4,000/4,000 |
    | Screen share, 1:1 | 200/200 | 1,500/1,500 | 4,000/4,000 |
    | Screen share, meetings | 250/250 | 2,500/2,500 | 4,000/4,000 |

  - "Minimum" corresponds to up to 240p and "Recommended" to up to 1080p. "Teams ... can deliver HD video quality in under 1.5 Mbps."
  - Wi-Fi advice: WMM/QoS; 5 GHz is "better suited to real-time media"; band steering; non-overlapping channels.
  - — [Microsoft Learn, prepare-network](https://learn.microsoft.com/en-us/microsoftteams/prepare-network)
- **Netflix (help article 306):** HD 720p "3 Mbps or higher"; Full HD "5 Mbps or higher"; 4K/Ultra HD "15 Mbps or higher". — [Netflix internet speed recommendations](https://help.netflix.com/en/node/306)
- **NVIDIA GeForce Now (system requirements page):**
  - Desktop: 720p60 15 Mbps; 1080p60 25 Mbps; 1440p120 35 Mbps; 4K120 45 Mbps; 240/360 fps 55 Mbps; 5K120 65 Mbps.
  - "We also require less than 80ms of network latency from an NVIDIA data center."
  - "We recommend a hardwired Ethernet connection, or a router with a 5 GHz WiFi connection."
  - No jitter or loss figures.
  - — [GeForce Now system requirements](https://www.nvidia.com/en-us/geforce-now/system-reqs/)
- **ITU-T G.1010 targets** (section 2): conversational video <150 ms preferred / <400 ms limit one-way and <1% PLR; web "not more than about 10 seconds"; games "fraction of a second". — [G.1010](https://www.itu.int/rec/T-REC-G.1010-200111-I/en)
- **Cloud gaming, academic.** Dabrowski, Manuel, Smieja (advisors Claypool, Finkel), WPI Interactive Qualifying Project, 2014, OnLive: "QoE ratings decreased linearly as latency was added"; each 100 ms reduced QoE ratings by 14% on average; player scores also fell linearly. N and game not stated on the page. It is an undergraduate project, not peer-reviewed. — [WPI project page](https://web.cs.wpi.edu/~claypool/iqp/onlive/)
- Jarschel et al. (cloud gaming QoE): users are more tolerant to packet loss in fast-paced games than in slower RPGs, and delay is among the most influential factors. Access: secondary description in search results only. — [search pointer, Linköping UCC 2020 paper](https://www.ida.liu.se/~nikca89/papers/ucc20.pdf)
- **Adaptive streaming QoE drivers** (standardized in P.1203.3): initial loading delay, stalling, and quality switches, on top of per-second audiovisual quality. — [P.1203 development page](https://telecommunication-telemedia-assessment.github.io/bitstream_based_models)

### Inferences
- Vendor thresholds are *sufficiency floors under good latency and loss*. They are not QoE scales, and none of them were validated against user ratings in the cited pages. In a home with hundreds of Mbps, every room with Wi-Fi throughput above ~45 Mbps clears all of them. That is exactly where the project sees "bad" user ratings. The discriminating variables in such homes are therefore likely latency under load, jitter, loss and retries, and intermittency (Wi-Fi contention, roaming, 2.4 GHz fallback), not throughput. Teams, NVIDIA and G.1010 all point to latency, loss and band (5 GHz), not Mbps, as the critical factors for real-time applications.
- A rule that treats a room as bad when its throughput falls below the home's best room will flag rooms whose application experience may be identical. Unless the user's rating reflects the speed test itself or coverage and stability perceptions, the relative ruler measures capacity headroom, not experienced quality.
- The linear latency-QoE result for cloud gaming argues against a hard 80 ms cliff. A graded "degraded" class between, say, 40 and 80 ms is more consistent with that evidence than a binary pass/fail. The specific cut values here are my illustration, not a sourced recommendation.

### Gaps
- Microsoft's numeric latency, jitter and loss targets for Teams (published on a separate Microsoft 365 network page) were not accessed. Zoom, Netflix and NVIDIA give no jitter or loss targets on the pages read.
- I found no peer-reviewed academic validation of the Zoom, Teams, Netflix or GeForce Now bandwidth numbers against subjective ratings. The Jarschel 2011 and Claypool and Finkel peer-reviewed papers were not opened, so their sample sizes and exact thresholds are not reported here.
- Web-browsing thresholds from G.1030 (formula and parameters) were not verified.

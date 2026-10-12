# Model 1 analysis plan (pre-registration)

**Status:** Written 2026-10-11 before any posting score was computed. Elizabeth approved it ("go") on 2026-10-11 at 16:16 MST. The corpus, family counts and sample titles were added afterward without changing any rule; every later deviation is logged in section 10. Results: `outputs/model1_results.json`.

**Label on every output:** OBSERVED MEASUREMENT — posting text; describes wording, not intent.

## 1. Thesis alignment

Model 1 serves Research Thesis Version C 3.0 (Human-AI Employment Intelligence & Governance). It works on the *recruiting* stage, the first stage named in RQ3 and the only one public data can observe.

| Question | Hypothesis / component | What Model 1 contributes | What it cannot answer |
|---|---|---|---|
| Primary | H1, H2 | Measures one place where recruiting could contribute: what postings signal, and who they show | Whether postings contributed to the disparity |
| RQ1 Representation | H1, H2 | Tests one candidate upstream explanation | "Why", which needs applicant data |
| RQ2 Algorithmic influence | T7 scores | Measures the posting text any matching system would receive | Whether any system uses it, or how |
| RQ3 Stages | H3 (gated) | Observes the recruiting stage directly; H3 tests a link to outcomes | Screening, interviewing, hiring, or advancement |
| RQ4 Long-term AI risk | T7c | Tracks whether posting signals persist across Fellows versions | Feedback into AI systems (Model 2's question) |
| RQ5 Governance | Model 1b | The evaluation method, ready for internal data; the posting audit as a repeatable control | Accountability design |

## 2. Hypotheses

- **H1 (T7, RQ1/RQ2):** Fellows and research-titled postings use more masculine-coded words per 1,000 words than other role families. Null: no difference. This is Elizabeth's stated view; it is tested, not assumed.
- **H2 (T6, RQ1):** Women's share among people named in Fellows postings differs from (a) parity, 50%, and (b) women's share of Fellows hires, 36.4% (8 of 22 known sex). Direction-agnostic.
- **H3 (RQ3):** Across role families, posting signals are associated with women's share of hires. Run only if the estimability gate passes.

## 3. Inputs (located, never invented)

| # | Input | Location | Status |
|---|---|---|---|
| 1 | Posting text corpus, every captured version | The three sources `version_d/01_fellows_named_people.py` reads: `job_postings/snapshots/20260929T061625Z_greenhouse_anthropic_current_records.json` (629), `job_postings/historical_outputs/20260929T074631Z_historical_greenhouse_deduplicated.json` (1,246; the Version C source run), `job_postings/missing_archive_outputs/20260930T024433000000Z_missing_archived_pages_recovered.json` (932) | Received 2026-10-11 as `job_postings.zip` from the Desktop copy `AnthropicBiasData-copy-2026-10-11_15-40-17`; originals untouched; not committed to GitHub |
| 2 | April 26 captures (Economics 5183053008; RL 5183052008) | Project evidence doc gives a summary only; full OCR text is with the PDFs | **Not provided.** Named people from the evidence note are included in T6; the Economics April 26 wording is not scored |
| 3 | Named-people list (person, version, role) | `version_d/outputs/fellows_named_people.csv` and `fellows_posting_versions.csv` from `01_fellows_named_people.py` | Read from the Desktop copy; kept in git-ignored `outputs/private/inputs/` |
| 4 | Hire outcomes | Findings doc; `config.yaml → outcome_link.source_groups` | Available |
| 5 | Word lists | gender-decoder @ `7cb4a6d6a3b0a84a46eae8a6a312b5732cb363fd`, `app/wordlists.py`, vendored verbatim (MIT) | Available: 52 masculine, 50 feminine, 7 hyphenated stems |

The corpus will not be rebuilt from fresh web scraping or from memory.

## 4. Unit of analysis and exclusions

- **Primary unit:** one record per posting ID, its latest captured version. All distinct versions are used for sensitivity checks and the Fellows change-over-time table (T7c).
- **Cleaning:** strip HTML; normalize whitespace; SHA-256 of normalized text; drop exact duplicates (same posting ID, identical text).
- **Boilerplate:** remove every sentence that appears in ≥ 50% of primary records (shared "About Anthropic", benefits, logistics, EEO text). Report each removed sentence with its record share, and the share of words removed.
- **Short records:** exclude records under 150 words after boilerplate removal; report the count.

## 5. Role families

Applied in order to the title; the first match wins (case-insensitive):

1. **Fellows**: title contains "Fellow"
2. **Research-titled**: title contains "Research"
3. **Engineering**: title contains Engineer, Developer, Software, Infrastructure, or Reliability
4. **Other**: everything else

Version C carries a `posting_classification` field (title + department rules, plus a description-based research signal). **Proposed decision for review:** use the title rules above as primary, because they match the pre-registered definition and are reproducible from titles alone; report agreement with Version C's field (`role_family.py → family_report`) as a robustness table. Elizabeth can choose Version C's field instead at the "go" step.

**Decision applied:** the three source files do not carry Version C's `posting_classification` field (it was added in the R2 analytical master), so the title rules are primary, as proposed.

| Family | Postings (latest version) |
|---|---|
| Fellows | 7 |
| Research-titled | 101 |
| Engineering | 334 |
| Other | 784 |

Sample titles (20 per family, seed 20261011; Fellows has only 7):

- **Fellows:** Anthropic AI Safety Fellow; Anthropic AI Security Fellow; Anthropic Fellows Program, AI Safety & Security; Anthropic Fellows Program, ML Systems & Reinforcement Learning; Anthropic Fellows Program, Reinforcement Learning; Anthropic Fellows Program, The Anthropic Institute (Economics & Policy); Anthropic STEM Fellow
- **Research-titled:** Applied AI, Research Engineer; Communications Manager, Research; Engineering Manager, Research Data Platform; Engineering Manager, Research Productivity; Research & Education Sales Lead, Beneficial Deployments; Research Economist, Economic Research; Research Engineer / Scientist, Societal Impacts; Research Engineer, Code RL (Reinforcement Learning); Research Engineer, Cybersecurity RL (Reinforcement Learning); Research Engineer, Discovery; Research Engineer, Pretraining Scaling - London; Research Engineer, Production Model Post-Training; Research Lead, Training Insights; Research Manager, Biological Safety; Research Product Manager, Labs; Researcher, Education Labs; Staff+ Research Scientist, Multi-Agent; Staff+ Researcher, Cybersecurity Products; Transformative AI Research Economist, Economic Research; User Experience Researcher, Platform
- **Engineering:** Applied AI Engineer, Enterprise; Director, Compute Infrastructure Procurement Operations; Engineering Manager, Inference Infrastructure; Finance Systems Engineer, Revenue; IT Support Engineer; Manager, Web Engineering; Platform Security Engineer, OpenBMC; Security Labs Engineer; Senior Software Engineer, Systems; Silicon Engineer; Software Engineer, Systems - Claude Code; Software Engineer, Tokens and Prompt Structures; Sr. Software Engineer, Inference; Staff + Senior Software Engineer, Inference Infrastructure; Staff Engineer, Datacenter Server Lifecycle; Staff Software Engineer, Observability & Profiling; Staff+ Software Engineer, Backend; Staff+ Software Engineer, Capacity Engineering; Staff+ Software Engineer, Distributed Systems; Staff+ Software Engineer, Platform Connectivity
- **Other:** Analytics, Finance & Strategy; Art Director, Enterprise; Customer Success Manager, Beneficial Deployments - Global Development; Enterprise Account Executive - Industries Generalist; Executive Communications Writer; Executive Escalations Manager; Field Marketing Manager, APAC; Finance & Strategy, Deal Velocity; GTM Strategy & Operations, Frontier; Head of Compute Supply Chain; Head of EMEA Partner Success; Head of Logistics; IP Counsel, Copyright; Manager Applied AI Architecture, Healthcare & Life Sciences; Manager, Applied AI (Startups); Partner Enablement Lead, System Integrators; Product Manager, New Markets and Monetization; Regional Manager APAC, Data Center Capacity Delivery; Sales Strategy, Operational Excellence; Supplier Security & Assurance, Security GRC

**Mismatches with function (kept, per the pre-registered rule):** "Research" in a title puts non-research roles in Research-titled (for example "Communications Manager, Research", "Research & Education Sales Lead", "User Experience Researcher", "Research Product Manager"); "Infrastructure" and "Engineer" put "Director, Compute Infrastructure Procurement Operations" and "IT Support Engineer" in Engineering. Hire groups (People Data Labs titles) are a different classification: the 32 Fellows hires map to the Fellows posting family, but "AI researchers" and "Engineering (general/unspecified)" do not correspond one-to-one to these posting families.

## 6. Wording score (T7)

- Lowercase; transliterate to ASCII; tokenize on non-letters, keeping hyphenated forms for the hyphenated list (other hyphenated tokens are split into parts, as gender-decoder does).
- A stem matches a token only at the token's start; each token counts at most once per list.
- Per record: `masc_per_1k`, `fem_per_1k`, `net_per_1k` = masculine − feminine, and gender-decoder's categorical label (applied to these token counts).
- The word lists include additions to Gaucher et al. (2011). Gaucher et al.'s appendix has not been obtained; if it is, an original-stems-only variant is scored as a further robustness check.

## 7. Validity checks

**Sense audit (step 4).** Keyword-in-context sample of 200 matches, stratified by stem (maximum 10 per stem) and by family, drawn with seed 20261011. Each match is labeled:

- **Trait sense:** describes a person's disposition ("ambitious", "supportive teammate", "a confident communicator").
- **Other sense:** technical term, proper noun, product or team name, or section heading ("dependencies", "Trust & Safety", "Responsibilities", "Responsible Scaling Policy", "lead engineer" as a job level, "analysis", "commit" in version control, "customer support").

Precision per stem = trait-sense labels ÷ labels. **Fixed rule:** the sense-filtered score drops every stem with precision < 0.50 in the audit. Primary analysis = raw score; robustness = sense-filtered score. The labeler (Claude) records every label with its context in `labels/sense_audit_labels.csv`.

**Convergent check (step 5).** 300 sentences, stratified by family, seed 20261011. Each is coded agentic (independence, competition, dominance, assertiveness), communal (collaboration, care, support, interpersonal warmth) or neutral, blind to the lexicon's label. Compare with the lexicon's sentence label (masculine > feminine → agentic; feminine > masculine → communal; else neutral). Report Cohen's κ and the confusion matrix. **Fixed rule:** κ < 0.40 → the lexicon is flagged weakly valid in this domain, in the findings.

## 8. Tests and thresholds

| Test | Method | Threshold / reporting |
|---|---|---|
| T7a family differences | Each family vs. Other, for `masc_per_1k` and `fem_per_1k`; permutation test on the mean difference (10,000 permutations, two-sided); bootstrap 95% CI (10,000 resamples); Cliff's delta; Holm correction across all comparisons; raw and sense-filtered | α = .05 after Holm; effect sizes always reported |
| T7b Fellows power | Effect sizes and intervals for Fellows (about 9 records) | Low power stated plainly; p > .05 is not evidence of no difference |
| T7c change over time | Score deltas between Fellows versions (Economics Apr 26 → Jun 7; AI Safety Apr 3 → combined) | Described only, no test |
| T6a named people | Women among known (distinct persons), Wilson 95% CI, Unknown bounds | Unknown stays Unknown |
| T6b listing-weighted | Each appearance counts (63 mentor + 42 credit listings), by version | Descriptive |
| T6c comparisons | vs. 50% (exact binomial); vs. Fellows hires 8/22 (Fisher's exact) | α = .05, two-sided |
| T6d roles | Mentors and past-project credits reported separately | Descriptive |
| H3 gate | ≥ 10 non-overlapping cells, each ≥ 10 known-sex hires, both sexes in ≥ 5 cells | Otherwise `estimable: false` with cell counts; never fit on fewer cells |
| Model 1b | Binomial GLM on applicant counts per posting, SEs clustered by posting ID | Estimator test: 95% CI covers the true β in ≥ 90% of 200 simulated data sets |

**Gender of named people (T6):** public self-identification only (pronouns or explicit self-description in an official bio, faculty page, personal site, or published interview), with URL, exact quote and date accessed. Never inferred from names, photos or voice. If nothing is found, Unknown. Person-level codes are written only to `outputs/private/named_people_gender.csv`, which is git-ignored; every public output carries aggregates only.

## 9. Run before the corpus arrived (no posting scores involved)

- **Estimability gate (H3), 2026-10-11:** `estimable: false`. Four non-overlapping cells (Fellows 14 M / 8 F / 10 U; non-Fellows researchers 5 / 0 / 3; Engineering 235 / 51 / 72; Other 352 / 217 / 128) < 10 required; one cell has < 10 known-sex hires; both sexes appear in 3 cells < 5. The Engineering/research overlap cannot be verified from aggregate counts.
- **Model 1b estimator test on simulated data, 2026-10-11:** 95% CI coverage of the true β = 0.96 across 200 simulated data sets (target ≥ 0.90); mean estimate −0.0295 vs. true −0.030. An estimator test, not a result.

## 10. Deviation log

| Date | Deviation | Reason |
|---|---|---|
| 2026-10-11 | Test 1's first draft asserted the fixture sentence had 7 words; it has 6. The test fixture was corrected; the scoring code was not changed. | Miscount in the test itself, caught on first run |
| 2026-10-11 | "Go" was given on the 10-line summary before family counts and sample titles were shown; they were computed afterward and are recorded in section 5. No rule changed. | Elizabeth approved early to keep work moving |
| 2026-10-11 | Version C's `posting_classification` field is not in the source files, so the title rules are primary (the plan's proposed default). | Field exists only in the R2 master |
| 2026-10-11 | The April 26 OCR text was not provided: T7c's Economics comparison is not scored; its named people are taken from the project evidence note. | Input not available |
| 2026-10-11 | Sense-audit rubric clarified before any label: task verbs, job levels, technical terms, proper nouns and headings = other sense; person qualities, including desired candidate qualities phrased as skills, = trait sense. | The pre-registered rubric did not say how to treat task verbs such as "lead the design of" |
| 2026-10-11 | With 62 matched stems, stratifying 200 matches gave 1–4 per stem (not up to 10). The 0.50 drop rule was applied unchanged, so stem-level precision rests on very few labels. | Arithmetic of the pre-registered sample size |
| 2026-10-11 | Convergent-check sentences: at least 4 tokens, leading bullet characters stripped, deduplicated within family; 75 per family. Fixed before labeling. | Headings such as "Responsibilities" are not sentences |
| 2026-10-11 | Both label sets were produced by Claude subagents with the written rubrics (one rater each; the convergent rater was blind to lexicon labels). | No second human rater available; single-rater limitation reported |
| 2026-10-11 | Gender coding by Claude subagents using web search under the public self-identification rule; three known codes were re-verified by direct fetch; two personal pages could not be fetched, so those people stay Unknown. Code "nonbinary" was allowed (none found). | Scale (50 people) |
| 2026-10-11 | Added a bootstrap 95% CI for κ and Wilson CIs for audit precision and Model 1b coverage. | Reporting only; every finding needs an interval |

## References (APA 7)

Gaucher, D., Friesen, J., & Kay, A. C. (2011). Evidence that gendered wording in job advertisements exists and sustains gender inequality. *Journal of Personality and Social Psychology, 101*(1), 109–128.

Matfield, K. (n.d.). *Gender decoder for job ads* [Computer software]. GitHub. https://github.com/lovedaybrooke/gender-decoder

Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *Proceedings of the National Academy of Sciences, 115*(11), 2600–2606.

Robinson, W. S. (1950). Ecological correlations and the behavior of individuals. *American Sociological Review, 15*(3), 351–357.

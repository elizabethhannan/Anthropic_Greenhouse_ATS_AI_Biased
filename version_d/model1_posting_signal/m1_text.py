"""Findings, thesis alignment, research layers, limitations and references for Model 1,
generated from the numbers in the results dictionary. Aggregates only; no names.
OBSERVED MEASUREMENT — posting text; describes wording, not intent.
"""

from __future__ import annotations

THESIS = {
    "Primary": "What is driving the observed gender disparity in Anthropic’s 2026 hiring environment, where might "
               "AI-assisted recruiting and human decision-making contribute to that disparity, and who should be "
               "responsible for identifying, measuring, and correcting potential systemic bias?",
    "RQ1 Representation": "1. Representation: Why do men account for 68.7% of observed hires with known sex, compared "
                          "with 31.3% women?",
    "RQ2 Algorithmic influence": "2. Algorithmic influence: Could AI-assisted screening, candidate matching, or "
                                 "historical hiring patterns reinforce existing demographic disparities?",
    "RQ3 Human decision-making": "3. Human decision-making: At which stages—recruiting, screening, interviewing, "
                                 "hiring, or advancement—might disparities emerge or compound?",
    "RQ4 Long-term AI risk": "4. Long-term AI risk: Could repeated employment outcomes become feedback signals that "
                             "lead future AI systems to reproduce historical hiring preferences?",
    "RQ5 Governance": "5. Governance: What internal data, evaluation methods, and executive accountability are "
                      "required to distinguish algorithmic bias from human, structural, and applicant-pool factors?",
}

REFERENCES = [
    "Anthropic. (2026). Job postings, April–September 2026 [Greenhouse job board captures]. Greenhouse. "
    "https://job-boards.greenhouse.io/anthropic",
    "Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions. Psychological Bulletin, "
    "114(3), 494–509.",
    "Cohen, J. (1960). A coefficient of agreement for nominal scales. Educational and Psychological Measurement, "
    "20(1), 37–46.",
    "Dewey & People Data Labs. (2026). Observed Anthropic starts, April–July 2026 [Unpublished data set extract].",
    "Gaucher, D., Friesen, J., & Kay, A. C. (2011). Evidence that gendered wording in job advertisements exists and "
    "sustains gender inequality. Journal of Personality and Social Psychology, 101(1), 109–128.",
    "Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, "
    "6(2), 65–70.",
    "Matfield, K. (n.d.). Gender decoder for job ads [Computer software]. GitHub. "
    "https://github.com/lovedaybrooke/gender-decoder",
    "Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & "
    "Gebru, T. (2019). Model cards for model reporting. In Proceedings of the Conference on Fairness, "
    "Accountability, and Transparency (pp. 220–229).",
    "Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. "
    "Proceedings of the National Academy of Sciences, 115(11), 2600–2606.",
    "Robinson, W. S. (1950). Ecological correlations and the behavior of individuals. American Sociological Review, "
    "15(3), 351–357.",
    "Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. Journal of the "
    "American Statistical Association, 22(158), 209–212.",
]


def f2(x):
    return f"{x:.2f}"


def pct(x):
    return f"{100 * x:.1f}%"


def pfmt(p):
    if p < 0.001:
        return "p < .001"
    s = f"{p:.3f}".lstrip("0")
    return f"p = {s}"


def fam(core, name, variant="raw"):
    key = "by_family" if variant == "raw" else "by_family_sense_filtered"
    return next(x for x in core["wording"][key] if x["family"] == name)


def test(core, comp, metric, variant):
    return next(t for t in core["wording"]["tests"]
                if t["comparison"] == comp and t["metric"] == metric and t["variant"] == variant)


def build_text(core, cfg):
    w = core["wording"]
    v = core["visibility"]
    fr, orr = fam(core, "Fellows"), fam(core, "Other")
    t_fel = test(core, "Fellows vs Other", "masc_per_1k", "raw")
    t_res = test(core, "Research-titled vs Other", "masc_per_1k", "raw")
    t_fel_f = test(core, "Fellows vs Other", "masc_per_1k", "sense_filtered")
    t_eng_f = test(core, "Engineering vs Other", "masc_per_1k", "sense_filtered")
    t_res_f = test(core, "Research-titled vs Other", "masc_per_1k", "sense_filtered")
    ff, of = fam(core, "Fellows", "f"), fam(core, "Other", "f")
    sa = w["sense_audit"]
    cc = w["convergent_check"]
    h1_raw_dir = "fewer" if t_fel["diff"] < 0 else "more"
    h1_supported_raw = t_fel["diff"] > 0 and t_fel["p_holm"] < 0.05
    women, men, unk = v["coded"]["women"], v["coded"]["men"], v["coded"]["unknown"]
    known = women + men
    wsk = v["women_share_known"]
    p_par = next(c for c in v["comparisons"] if c["vs"].startswith("parity"))["p"]
    p_fel = next(c for c in v["comparisons"] if c["vs"].startswith("Fellows"))["p"]
    lw = v["listings"]
    lwk = lw["women"] + lw["men"]
    mv = v["mentors_vs_credits"]
    gate = core["outcome_link"]
    n_cells = len(gate["cells"])
    both = sum(1 for c in gate["cells"] if c["male"] > 0 and c["female"] > 0)
    m1b = core["model1b"]

    findings = [
        (f"{'Contrary to' if not h1_supported_raw else 'Consistent with'} H1, Fellows postings used {h1_raw_dir} "
         f"masculine-coded words per 1,000 than Other postings on the raw lexicon ({f2(fr['masc_per_1k']['mean'])} vs. "
         f"{f2(orr['masc_per_1k']['mean'])}; difference {f2(t_fel['diff'])}, 95% CI {f2(t_fel['ci'][0])} to "
         f"{f2(t_fel['ci'][1])}; Holm-adjusted {pfmt(t_fel['p_holm'])}; Cliff's δ = {f2(t_fel['cliffs_delta'])}), and so "
         f"did research-titled postings ({f2(t_res['diff'])}, CI {f2(t_res['ci'][0])} to {f2(t_res['ci'][1])}; "
         f"Holm {pfmt(t_res['p_holm'])}) (RQ1)."),
        (f"The lexicon proved weakly valid in this technical text: only {pct(sa['overall_precision'])} of "
         f"{sa['sampled']} audited matches used a word in a trait sense (95% CI {pct(sa['overall_precision_ci'][0])}–"
         f"{pct(sa['overall_precision_ci'][1])}), {len(sa['dropped_stems'])} of {sa['stems_audited']} audited stems fell "
         f"below the 0.50 precision rule, and agreement with blind sentence ratings was κ = {f2(cc['kappa'])} "
         f"(95% CI {f2(cc['kappa_ci'][0])}–{f2(cc['kappa_ci'][1])}), below the pre-set 0.40 threshold (RQ2)."),
        (f"After the low-precision stems were removed, the direction reversed but the differences were under one word "
         f"per 1,000: Fellows {f2(ff['masc_per_1k']['mean'])} vs. Other {f2(of['masc_per_1k']['mean'])} "
         f"(difference {f2(t_fel_f['diff'])}, CI {f2(t_fel_f['ci'][0])} to {f2(t_fel_f['ci'][1])}; Holm "
         f"{pfmt(t_fel_f['p_holm'])}), research-titled {f2(t_res_f['diff'])} (CI {f2(t_res_f['ci'][0])} to "
         f"{f2(t_res_f['ci'][1])}; Holm {pfmt(t_res_f['p_holm'])}) and Engineering {f2(t_eng_f['diff'])} (CI "
         f"{f2(t_eng_f['ci'][0])} to {f2(t_eng_f['ci'][1])}; Holm {pfmt(t_eng_f['p_holm'])}); with {fr['n']} Fellows "
         f"postings and 3–4 audit labels per stem, this robustness check has low power and is not evidence either way "
         f"(RQ1)."),
        (f"Among the {v['named_people']} people named in Fellows postings, {known} had public self-identification: "
         f"{women} women and {men} men, a women's share of {pct(wsk['value'])} (Wilson 95% CI {pct(wsk['ci'][0])}–"
         f"{pct(wsk['ci'][1])}), below parity (exact binomial {pfmt(p_par)}) and below women's 36.4% share of known-sex "
         f"Fellows hires (Fisher's exact {pfmt(p_fel)}); because {unk} people ({pct(unk / v['named_people'])}) are "
         f"Unknown, the share of all named people could lie anywhere from {pct(wsk['bounds'][0])} to "
         f"{pct(wsk['bounds'][1])} (RQ1, RQ3)."),
        (f"Listed mentors were {mv['mentors']['women']} women, {mv['mentors']['men']} men and "
         f"{mv['mentors']['unknown']} Unknown, and past-project credits {mv['credits']['women']}, {mv['credits']['men']} "
         f"and {mv['credits']['unknown']}; counting every appearance across the {v['fellows_versions']} versions, women "
         f"were {pct(lw['women'] / lwk)} of known-gender listings ({lw['women']} of {lwk}; descriptive Wilson CI "
         f"{pct(v['listing_weighted_ci_descriptive'][0])}–{pct(v['listing_weighted_ci_descriptive'][1])}, listings "
         f"are not independent) (RQ3, RQ4)."),
        (f"The outcome link (H3) was not estimable: {n_cells} non-overlapping hire cells against "
         f"{cfg['outcome_link']['gate']['min_cells']} required, with both sexes in only {both}, so the \"Predictive ML "
         f"analysis\" layer stays \"Not estimable from public data\"; the applicant-level estimator built for internal "
         f"data (Model 1b) covered the known simulated effect in {pct(m1b['coverage_in_simulation'])} of "
         f"{m1b['simulations']} simulated data sets (95% CI {pct(m1b['coverage_ci'][0])}–{pct(m1b['coverage_ci'][1])}) "
         f"(RQ5)."),
    ]

    thesis = [
        {"question": "Primary", "question_text": THESIS["Primary"],
         "contribution": (f"Measured two recruiting-stage signals. Wording: no reliable masculine-coded excess in "
                          f"Fellows or research postings, and the lexicon is weakly valid here (κ = {f2(cc['kappa'])}). "
                          f"Visibility: of named people with public self-identification, {women} of {known} are women "
                          f"({pct(wsk['value'])})."),
         "status": "Partial"},
        {"question": "RQ1 Representation", "question_text": THESIS["RQ1 Representation"],
         "contribution": (f"H1 not supported (raw scores run opposite; filtered differences under 1 word per 1,000). "
                          f"H2: women are {pct(wsk['value'])} of named people with known self-identification, below "
                          f"parity and below Fellows hires, with Unknown bounds {pct(wsk['bounds'][0])}–"
                          f"{pct(wsk['bounds'][1])}. Explaining \"why\" needs applicant data."),
         "status": "Partial"},
        {"question": "RQ2 Algorithmic influence", "question_text": THESIS["RQ2 Algorithmic influence"],
         "contribution": (f"Measured the posting text any matching system would receive. The standard gendered-wording "
                          f"lexicon mostly matches technical terms in this text ({pct(sa['overall_precision'])} trait "
                          f"sense), so it is a weak instrument for what a system would 'see'. Whether any system uses the "
                          f"text is not observable."),
         "status": "Partial"},
        {"question": "RQ3 Human decision-making", "question_text": THESIS["RQ3 Human decision-making"],
         "contribution": (f"Observed the recruiting stage directly: Fellows postings are the only postings that name "
                          f"people, and among those with known self-identification {pct(men / known)} are men. The link "
                          f"to hires (H3) is not estimable from public data."),
         "status": "Partial"},
        {"question": "RQ4 Long-term AI risk", "question_text": THESIS["RQ4 Long-term AI risk"],
         "contribution": ("Tracked Fellows postings across versions: wording changed little between the April and "
                          "September versions, and women stayed a small share of named people in every version with "
                          "known codes. Feedback into AI systems is Model 2's question."),
         "status": "Partial"},
        {"question": "RQ5 Governance", "question_text": THESIS["RQ5 Governance"],
         "contribution": (f"Delivered a repeatable posting audit (wording with a sense audit, visibility with public "
                          f"self-identification) and the Model 1b estimator, validated at "
                          f"{pct(m1b['coverage_in_simulation'])} CI coverage, ready for internal applicant counts by "
                          f"posting."),
         "status": "Partial — method built; needs internal data"},
    ]

    layers = [
        {"layer": "Observed disparity", "conclusion": "Observable", "changed_by_model1": False},
        {"layer": "Posting signals (new)",
         "conclusion": (f"Observable: visibility measured (women {pct(wsk['value'])} of named people with known "
                        f"self-identification, {unk} Unknown); gendered wording measured but the lexicon is weakly "
                        f"valid in this text"),
         "changed_by_model1": True},
        {"layer": "Algorithmic causation", "conclusion": "Not established", "changed_by_model1": False},
        {"layer": "Predictive ML analysis", "conclusion": "Not estimable from public data", "changed_by_model1": False},
        {"layer": "Historical feedback loops", "conclusion": "Exploratory hypothesis", "changed_by_model1": False},
        {"layer": "Internal governance need", "conclusion": "Evidence supports further investigation",
         "changed_by_model1": False},
    ]

    exec_conc = (
        "The most consequential Model 1 finding is not that Anthropic's job postings use masculine-coded language: on "
        "a standard lexicon, Fellows and research postings show no reliable excess, and the lexicon itself proved "
        "weakly valid in technical text. It is that the only postings that show candidates who they would work "
        f"with, the Fellows postings, show mostly men: among named people with public self-identification, {women} of "
        f"{known} are women ({pct(wsk['value'])}), below parity and below women's share of Fellows hires, with {unk} "
        "people still Unknown. This measures what postings make visible, not whether visibility changed who applied "
        "or who was hired; that question needs applicant counts by posting, which the Model 1b estimator is ready to "
        "analyze."
    )

    limitations = [
        f"Lexicon validity in technical text: {pct(sa['overall_precision'])} of audited matches were trait sense and "
        f"κ = {f2(cc['kappa'])} against blind sentence ratings; terms like 'lead', 'analysis', 'support' and "
        "'responsibilities' dominate the raw scores.",
        "The gender-decoder word lists include additions to Gaucher et al. (2011); the original appendix was not "
        "obtained, so an original-stems-only score was not run.",
        f"Small Fellows n: {fr['n']} Fellows postings in the primary corpus (8 of 9 versions; the April 26 Economics "
        "capture was not provided as text).",
        "Role families are title-based; some titles land in a family they do not belong to by function (for example, "
        "'Communications Manager, Research' is research-titled and 'IT Support Engineer' is Engineering).",
        "Posting families are not hire families: hire groups come from People Data Labs titles and overlap.",
        f"Gender coding is limited to public self-identification: {unk} of {v['named_people']} people are Unknown, "
        "8 of the known codes rest on interview or podcast pages written by hosts, and two personal pages could not be "
        "opened in this session.",
        "Nothing here observes applicants; no statement about who applied or why is possible.",
        "The sense audit and convergent check were labeled by a single rater (a Claude subagent with a written "
        "rubric), so no inter-rater reliability is available; the stem-level precision rests on 3–4 labels per stem.",
        "542 of 1,246 historical records had no posting text; 1 record was excluded as under 150 words after "
        f"boilerplate removal, which removed {pct(core['corpus']['boilerplate_word_share_removed'])} of words.",
    ]

    return {
        "thesis_alignment": thesis,
        "research_layers": layers,
        "executive_conclusion_model1": exec_conc,
        "findings": findings,
        "limitations": limitations,
        "references": REFERENCES,
    }

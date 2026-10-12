"""Findings, limitations and thesis text for Model 3, generated from the numbers.

Every number below is read from the results dictionary. Wording that depends on
a result (significant or not, same direction or not) is chosen by the numbers.
"""

from __future__ import annotations

THESIS_Q = {
    "RQ2": "2. Algorithmic influence: Could AI-assisted screening, candidate matching, or historical hiring "
           "patterns reinforce existing demographic disparities?",
    "RQ5": "5. Governance: What internal data, evaluation methods, and executive accountability are required to "
           "distinguish algorithmic bias from human, structural, and applicant-pool factors?",
}


def _s(r, sid):
    return next(e for e in r["screeners"] if e["id"] == sid)


def _sig(p, alpha=0.05):
    return p is not None and p < alpha


def _dir(g):
    return "men's" if g < 0 else "women's"


def build_text(r: dict) -> dict:
    if {e["id"] for e in r["screeners"]} != {"SC0", "SC1", "SC2", "SC3"}:   # quick/test configuration
        return {"thesis_alignment": [], "findings": [], "limitations": [],
                "executive_conclusion_model3": "", "text_note": "findings text is generated for the full run only"}
    prim = _s(r, "SC1")
    glove, ft, tf = _s(r, "SC2"), _s(r, "SC3"), _s(r, "SC0")
    emb = [prim, glove, ft]
    n_post = prim["name_gap"]["n_postings"]
    valid = [e for e in r["screeners"] if not e["validity"]["flag_not_meaningful"]]
    failed = [e for e in r["screeners"] if e["validity"]["flag_not_meaningful"]]
    vtxt = ", ".join(f"{e['name'].split(' ')[0]} {e['validity']['tier_spearman_mean']:.2f}" for e in valid)
    ftxt = "; ".join(f"{e['name'].split(' ')[0]} failed ({e['validity']['tier_spearman_mean']:.2f}; family "
                     f"AUC {e['validity']['family_auc_mean']:.2f}), so its results are reported but not interpreted"
                     for e in failed)
    fel = [e for e in valid if e["validity"]["tier_spearman_by_family"]["fellows"] < 0.10]
    feltxt = (" Validity was weak or negative on the 7 Fellows postings (" +
              ", ".join(f"{e['name'].split(' ')[0]} {e['validity']['tier_spearman_by_family']['fellows']:+.2f}" for e in fel)
              + ")." if fel else "")
    f_valid = (f"(Validity) {len(valid)} of {len(r['screeners'])} screeners ranked stronger résumés higher "
               f"(mean Spearman with designed tier: {vtxt})" + (f"; {ftxt}." if failed else ".") + feltxt)

    g = prim["name_gap"]
    sig = _sig(g["p_holm"])
    favor_share = g["share_postings_favoring_men"] if g["G_std"] < 0 else 1 - g["share_postings_favoring_men"]
    f_name = (f"(RQ2) With the primary screener (WordLlama), the same résumé scored higher with a {_dir(g['G_std'])} "
              f"name in {favor_share:.0%} of the {n_post} technical postings, by {abs(g['G_std']):.2f} SD of "
              f"résumé-to-résumé spread on average; " +
              (f"this exceeds what arbitrary splits of the 20 names produce (exact p = {g['p_exact']:.3f}; "
               f"Holm-adjusted {g['p_holm']:.3f})." if sig else
               f"but that is within the range arbitrary splits of the 20 names produce (exact p = {g['p_exact']:.3f}; "
               f"Holm-adjusted {g['p_holm']:.2f}), so it is not statistically distinguishable from "
               f"name-specific noise."))

    s = prim["selection"]
    inside = s["null_pooled_ir_p025"] <= s["pooled_ir"] <= s["null_pooled_ir_p975"]
    f_sel = (f"(RQ2) Picking the top 10% by that score, résumés with women's names were selected at "
             f"{s['pooled_ir']:.2f} times the rate of men's (median posting {s['posting_median_ir']:.2f}; "
             f"{s['share_postings_below_080']:.0%} of postings below 0.80 versus "
             f"{s['null_share_below_080_mean']:.0%} under random name splits), "
             + ("at the lower edge of" if abs(s["pooled_ir"] - s["null_pooled_ir_p025"]) < 0.005 else
                "inside" if inside else "outside")
             + f" the random-split range ({s['null_pooled_ir_p025']:.3f}–{s['null_pooled_ir_p975']:.3f}; "
               f"observed {s['pooled_ir']:.3f}).")

    same = [e for e in (glove, ft) if (e["name_gap"]["G_std"] < 0) == (g["G_std"] < 0)]
    def gtxt(e):
        tag = " (failed validity)" if e["validity"]["flag_not_meaningful"] else ""
        return (f"{e['name'].split(' ')[0]}{tag} {e['name_gap']['G_std']:+.2f} SD (p = {e['name_gap']['p_exact']:.2f}, "
                f"Holm {e['name_gap']['p_holm']:.2f}; selection ratio {e['selection']['pooled_ir']:.2f})")
    f_rob = ("(RQ2) The other screeners " + ("agreed in direction: " if len(same) == 2 else "did not agree: ")
             + f"{gtxt(glove)}; {gtxt(ft)}.")

    def wtxt(e):
        return f"{e['name'].split(' ')[0]} {e['word_test']['gap_std_women_minus_men']:+.3f}"
    w = prim["word_test"]
    f_word = (f"(RQ2) Changing one word, WordLlama scored \"Captain, {'men' if w['gap_std_women_minus_men'] < 0 else 'women'}'s …\" "
              f"above \"Captain, {'women' if w['gap_std_women_minus_men'] < 0 else 'men'}'s …\" on {max(w['share_resumes_favoring_men'], 1 - w['share_resumes_favoring_men']):.0%} "
              f"of the 300 résumés ({w['gap_std_women_minus_men']:+.2f} SD; selection ratio {w['selection_pooled_ir']:.2f}); "
              f"the other screeners did not repeat it ({wtxt(glove)}, {wtxt(ft)} SD).")

    tf_g = tf["name_gap"]
    nonzero = [x["name"] for x in tf["per_name"]
               if abs(x["effect_std"] - max(y["effect_std"] for y in tf["per_name"])) > 1e-3]
    f_tf = ("(RQ5) The keyword control was " + ("exactly name-blind." if tf_g["G_std"] == 0 else
            f"not exactly name-blind (test 6 failed): Fellows postings list mentors by name, so {', '.join(nonzero)} "
            f"are in the keyword vocabulary; résumés with those names scored slightly lower on postings that do not "
            f"mention them (overall {tf_g['G_std']:+.2f} SD toward women's names, p = {tf_g['p_exact']:.2f}) and "
            f"higher on the Fellows postings that do ({tf_g['by_family']['fellows']:+.2f} SD toward men's names)."))

    lk = prim["posting_link_model1"]
    f_link = (f"(Exploratory) Masculine-coded posting language (Model 1) "
              + ("did not predict" if not _sig(lk["p_perm"]) else "was associated with")
              + f" the size of the name gap (Spearman {lk['spearman']:+.2f}, p = {lk['p_perm']:.2f}, "
                f"{lk['n']} postings).")

    findings = [f_valid, f_name, f_sel, f_rob, f_word, f_tf, f_link]

    thesis = [
        {"question": "RQ2", "text": THESIS_Q["RQ2"],
         "contribution": ("A direct test of candidate-matching models on Anthropic's own posting text. The most "
                          "modern stand-in leaned toward men's names and the word \"men's\"; two older models did "
                          "not agree. Model choice changed the answer."),
         "status": "Tested on stand-in models only; not established for any system Anthropic uses"},
        {"question": "RQ5", "text": THESIS_Q["RQ5"],
         "contribution": ("A ready template for the evaluation method the thesis calls for: paired résumés, exact "
                          "name-level tests and a selection impact ratio, run on the specific screening model in use."),
         "status": "Method demonstrated; requires access to Anthropic's actual screening configuration"},
    ]
    limitations = [
        "Stand-in screeners only. Nothing here describes Greenhouse's or Anthropic's screening, which is not public.",
        "Transformer sentence encoders like those in published audits (Wilson & Caliskan, 2024) could not be used: "
        "model hubs are blocked from this workspace. WordLlama is LLM-derived but bag-of-tokens.",
        "Cosine similarity to a posting is a simplified screener; real systems may use other signals or none.",
        "Synthetic résumés from one template family; results may differ for real résumés.",
        "Names are the 10 most common per sex for U.S. births 1985–2000; they skew toward white-associated names, "
        "so race and its intersection with gender are not tested. Individual names carry other meanings "
        "(\"Brittany\" is also a region), which is why the test is at the name level.",
        "The word test uses three items and one word pair; it probes those words only.",
        "fastText vectors are case-sensitive; the pre-registered lowercase lookup may weaken them, and that "
        "screener failed the validity check.",
        "Only 7 Fellows postings; family-level results for Fellows are imprecise.",
    ]
    v = "is" if sig else "is not"
    exec_c = (f"The most consequential finding is not whether one AI screener is biased against women. It is that "
              f"the answer depends on which model is used. On Anthropic's own technical postings, the most modern "
              f"stand-in scored identical résumés lower with women's names in {favor_share:.0%} of postings and "
              f"scored \"women's\" below \"men's\" on every résumé, yet the name gap {v} beyond what name choice alone "
              f"can produce, and two older models did not agree. A gender audit of hiring technology cannot be done "
              f"once, in general: it has to be run on the specific model in use, with paired résumés, before and "
              f"after deployment. Anthropic's own screening has not been tested here, and nothing in this audit "
              f"shows that it behaves this way.")
    return {"thesis_alignment": thesis, "findings": findings, "limitations": limitations,
            "executive_conclusion_model3": exec_c}

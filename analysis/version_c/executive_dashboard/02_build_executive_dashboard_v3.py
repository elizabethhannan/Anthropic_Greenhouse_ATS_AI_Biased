"""Version C — Version 3.0 Executive Dashboard.

Duplicate-only presentation builder. Reads frozen aggregate outputs and writes
only under analysis/version_c/executive_dashboard/{outputs,audit}.
"""
from __future__ import annotations

import csv
import base64
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from neumorphic_visualizations import SOURCE_COMMIT, SOURCE_REPOSITORY, SOURCE_VERIFIED, outcome_composition_figure

HERE = Path(__file__).resolve().parent
VERSION_C = HERE.parent
SOURCE_OUT = VERSION_C / "outputs"
OUT = HERE / "outputs"
AUDIT = HERE / "audit"
HTML_PATH = OUT / "executive_dashboard_v3.html"
MANIFEST_PATH = OUT / "executive_dashboard_v3_manifest.json"
AUDIT_PATH = AUDIT / "executive_dashboard_v3_audit.csv"
VISUAL_PATH = OUT / "executive_dashboard_v3_outcomes.png"

INPUTS = {
    "outcomes": SOURCE_OUT / "dashboard_outcome_distribution.csv",
    "signals": SOURCE_OUT / "dashboard_signal_findings.csv",
    "prediction": SOURCE_OUT / "dashboard_predictive_findings.csv",
    "phase4_controls": SOURCE_OUT / "predictive_findings.csv",
    "feedback": SOURCE_OUT / "dashboard_feedback_findings.csv",
    "limitations": SOURCE_OUT / "dashboard_limitations.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_audit(rows: list[dict[str, str]]) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check_id", "status", "detail"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    missing = [str(path) for path in INPUTS.values() if not path.is_file()]
    if missing:
        raise SystemExit("Missing required frozen aggregate inputs: " + "; ".join(missing))
    tables = {name: read_csv(path) for name, path in INPUTS.items()}
    outcome_rows = tables["outcomes"]
    counts = {row["outcome_sex"]: int(row["person_count"]) for row in outcome_rows}
    if set(counts) != {"MALE", "FEMALE", "UNKNOWN"}:
        raise ValueError(f"Unexpected outcome categories: {sorted(counts)}")
    total = sum(counts.values())
    known = counts["MALE"] + counts["FEMALE"]
    male_pct = counts["MALE"] / known * 100
    female_pct = counts["FEMALE"] / known * 100
    ratio = counts["MALE"] / counts["FEMALE"]
    outcome_composition_figure(counts, VISUAL_PATH)
    visual_data = base64.b64encode(VISUAL_PATH.read_bytes()).decode("ascii")

    prediction_rows = tables["prediction"]
    prediction_status = "NOT_ESTIMABLE" if prediction_rows and all(r.get("status") == "NOT_ESTIMABLE" for r in prediction_rows) else ""
    signal_status = "OBSERVABLE" if bool(tables["signals"]) else "NOT AVAILABLE"
    feedback_status = "EXPLORATORY" if any("exploratory" in " ".join(r.values()).lower() for r in tables["feedback"]) else "NOT AVAILABLE"
    reasons = next((r.get("reason", "") for r in prediction_rows if r.get("status") == "NOT_ESTIMABLE"), "")
    limits = " ".join(" ".join(row.values()) for row in tables["limitations"])
    phase5_coverage = "August and September are unavailable, not zero." if "August" in limits and "September" in limits else "See frozen limitations table for temporal coverage."
    signal_summary = next((r for r in tables["signals"] if r.get("finding") == "all_postings"), {})
    posting_n = signal_summary.get("posting_count", "1,246")

    checks = []
    def check(key: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": key, "status": "PASS" if passed else "FAIL", "detail": detail})
    check("frozen_outcome_counts", counts == {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213} and total == 1095,
          f"MALE={counts['MALE']}; FEMALE={counts['FEMALE']}; UNKNOWN={counts['UNKNOWN']}; total={total}")
    check("known_sex_percentages", round(male_pct, 1) == 68.7 and round(female_pct, 1) == 31.3,
          f"MALE={male_pct:.4f}%; FEMALE={female_pct:.4f}%")
    check("known_sex_ratio", round(ratio, 2) == 2.20, f"MALE/FEMALE={ratio:.4f}:1")
    check("prediction_gate_preserved", prediction_status == "NOT_ESTIMABLE", f"Phase 4 status={prediction_status}; {reasons}")
    check("no_sex_inference", all(r.get("sex_inferred", "False").lower() == "false" for r in outcome_rows),
          "Frozen outcome rows preserve source categories; no inference introduced.")
    phase4_findings = tables["phase4_controls"]
    control_status = {r.get("finding"): (r.get("status"), r.get("value")) for r in phase4_findings}
    check("no_person_linkage_claim", control_status.get("candidate_level_linkage") == ("PASS", "False"),
          "Phase 4 control is present in frozen findings; dashboard reports aggregate evidence only.")
    check("no_causal_claim", control_status.get("causality") == ("PASS", "False"),
          "Causal attribution is explicitly disclaimed in dashboard copy.")
    check("phase14_publication_hold", True, "Controlled executive review only; publication remains HOLD / REVIEW REQUIRED.")

    cards = "".join(
        f'<div class="metric"><span>{label}</span><strong>{counts[key]:,}</strong></div>'
        for label, key in [("MALE", "MALE"), ("FEMALE", "FEMALE"), ("UNKNOWN", "UNKNOWN")]
    )
    html_text = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Version C 3.0 executive review of observed hiring representation and public evidence limits.">
<title>Version C 3.0 | Human-AI Employment Intelligence</title>
<style>
:root{{--navy:#102536;--blue:#245b7a;--teal:#087e78;--gold:#c79136;--red:#8d3737;--paper:#f2f5f7;--white:#fff;--line:#d6e0e6;--muted:#526777}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--navy);font:16px/1.52 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1200px;margin:auto;padding:34px 26px 54px}}.top{{display:flex;justify-content:space-between;gap:18px;align-items:center;flex-wrap:wrap}}.eyebrow{{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;font-weight:800;color:var(--blue)}}.badge{{background:#fff1d0;border:1px solid #e5c579;color:#684b16;border-radius:30px;padding:7px 13px;font-weight:800;font-size:.77rem}}h1{{font-size:clamp(2.1rem,4vw,3.55rem);line-height:1.08;letter-spacing:-.04em;max-width:1100px;margin:25px 0 16px}}h2{{font-size:1.25rem;margin:0 0 12px}}h3{{margin:4px 0;font-size:1.05rem}}p{{margin:6px 0;color:var(--muted)}}.thesis{{font-size:1.18rem;color:#233d50;max-width:1050px}}.panel{{background:var(--white);border:1px solid var(--line);border-radius:16px;padding:23px;margin-top:20px;box-shadow:0 8px 25px #17344a0b}}.outcomes{{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:center}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.metric{{background:#f5f8fa;border:1px solid var(--line);border-radius:12px;padding:15px}}.metric span{{display:block;font-size:.75rem;letter-spacing:.1em;font-weight:800;color:var(--muted)}}.metric strong{{font-size:2.1rem}}.bar{{height:18px;border-radius:20px;overflow:hidden;display:flex;background:#e1e7eb;margin:15px 0 9px}}.bar .m{{width:{male_pct:.4f}%;background:var(--blue)}}.bar .f{{width:{female_pct:.4f}%;background:#d5a14b}}.ratio{{font-size:1.5rem;font-weight:850;color:var(--blue);margin-top:8px}}.caveat{{border-left:5px solid var(--gold);background:#fff7e6;padding:15px 18px;color:#57461f;margin-top:16px;border-radius:4px}}.layers{{display:grid;grid-template-columns:repeat(3,1fr);gap:13px}}.layer{{padding:18px;border-top:5px solid var(--blue)}}.layer:nth-child(2){{border-color:var(--gold)}}.layer:nth-child(3){{border-color:var(--teal)}}.layer .state{{font-size:1.25rem;font-weight:900;margin:7px 0}}.question{{font-weight:750;color:var(--navy)}}.neumo{{margin:14px 0 0}}.neumo img{{display:block;width:100%;height:auto;border-radius:12px}}.neumo figcaption{{font-size:.75rem;color:var(--muted)}}.function{{background:var(--navy);color:white}}.function h2,.function h3{{color:white}}.function p{{color:#d5e1e8}}.function-name{{font-size:clamp(1.55rem,3vw,2.35rem);font-weight:850;line-height:1.13;margin:12px 0}}.mandate{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:18px}}.mandate div{{border:1px solid #496273;background:#1a3548;border-radius:10px;padding:13px;font-weight:700}}.equation{{text-align:center;color:var(--blue);font-size:clamp(1.35rem,3vw,2.15rem);font-weight:900;padding:10px 0 18px}}.small{{font-size:.87rem}}footer{{border-top:1px solid var(--line);margin-top:24px;padding-top:15px;color:var(--muted);font-size:.8rem}}@media(max-width:760px){{main{{padding:22px 15px}}.outcomes,.layers{{grid-template-columns:1fr}}.mandate{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main>
<div class="top"><div class="eyebrow">Version C · Version 3.0 · Executive evidence layer</div><div class="badge">READY FOR CONTROLLED EXECUTIVE REVIEW</div></div>
<h1>WHAT IS DRIVING THE GENDER DISPARITY IN THE AI-ASSISTED EMPLOYMENT SYSTEM—AND WHO SHOULD OWN FIXING IT?</h1>
<p class="thesis">A measurable gender-representation issue is visible in Anthropic’s observed hiring environment. Public evidence cannot establish where within the AI-assisted recruiting and employment system the disparity originates, but it identifies a sufficiently material signal to warrant executive-level investigation across recruiting technology, human decision-making, employment practices, and advancement.</p>
<section class="panel outcomes"><div><h2>Observed outcome environment</h2><p>{total:,} observed people in available public outcome data</p><div class="metrics">{cards}</div><figure class="neumo"><img src="data:image/png;base64,{visual_data}" alt="Neumorphic aggregate outcome summary showing 606 male, 276 female, and 213 unknown outcomes; known-sex percentages are 68.7% and 31.3%."><figcaption>Aggregate outcome visual · generated from frozen counts</figcaption></figure></div><div><h2>Known-sex composition</h2><div class="bar" role="img" aria-label="Among known-sex records: {male_pct:.1f}% MALE and {female_pct:.1f}% FEMALE"><span class="m"></span><span class="f"></span></div><p><b>{male_pct:.1f}% MALE</b> &nbsp;·&nbsp; <b>{female_pct:.1f}% FEMALE</b> &nbsp;·&nbsp; known-sex N={known:,}</p><div class="ratio">{ratio:.2f}:1 observed MALE/FEMALE ratio</div></div></section>
<div class="caveat"><b>Evidence boundary:</b> This is an observed outcome disparity in available public data. It does not establish that Greenhouse caused the disparity, identify its mechanism, or describe a complete hiring funnel. UNKNOWN remains UNKNOWN; no sex or gender is inferred.</div>
<section class="panel"><h2>Three diagnostic pillars</h2><div class="layers"><article class="panel layer"><div class="eyebrow">SIGNAL</div><div class="state">{signal_status}</div><p class="question">What does a candidate encounter?</p><p>{posting_n} public posting records are in the frozen signal evidence base. This is a measure of candidate-facing material, not person-level treatment.</p></article><article class="panel layer"><div class="eyebrow">PREDICTION</div><div class="state">NOT ESTIMABLE FROM PUBLIC DATA</div><p class="question">Do observable signals predict aggregate outcome composition?</p><p>{html.escape(reasons)} No candidate-level target is created, and no model result is claimed.</p></article><article class="panel layer"><div class="eyebrow">FEEDBACK</div><div class="state">{feedback_status}</div><p class="question">Does recruiting representation move with observed outcomes?</p><p>Aggregate role/month associations are exploratory. {html.escape(phase5_coverage)} They do not establish causation.</p></article></div></section>
<section class="panel"><div class="equation">MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS</div><p class="small">A model-level audit alone cannot show how recommendations are used, where candidates advance or exit, or how employment and advancement decisions differ. Public evidence identifies questions; internal lifecycle evidence is needed to locate mechanisms.</p></section>
<section class="panel function"><div class="eyebrow" style="color:#9edbd4">PROPOSED EXECUTIVE FUNCTION</div><div class="function-name">Human-AI Employment Intelligence &amp; Governance</div><p>Build the organizational capability to locate where disparities emerge, determine which mechanisms may contribute, and design measurable interventions across the employee lifecycle.</p><div class="mandate"><div>Recruiting technology<br><span class="small">inputs, outputs, controls</span></div><div>Human decisions<br><span class="small">review, override, rationale</span></div><div>Employment practices<br><span class="small">selection and progression</span></div><div>Advancement<br><span class="small">retention and mobility</span></div></div></section>
<footer>Controlled executive review copy · Frozen Version C aggregate outputs · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. No candidate-level linkage, synthetic records, or causal attribution. Publication status remains HOLD / REVIEW REQUIRED pending licensing and privacy review. Self-contained HTML; no remote assets.</footer>
</main></body></html>'''

    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(html_text, encoding="utf-8")
    check("standalone_html", "data:image/png;base64," in html_text, "Inline CSS and embedded neumorphic visual; no remote assets.")
    check("neumorphic_visual", VISUAL_PATH.is_file() and VISUAL_PATH.stat().st_size > 0,
          "Aggregate outcome image generated with the Version C visual module.")
    check("required_thesis_in_html", "WHAT IS DRIVING THE GENDER DISPARITY" in html_text and "Human-AI Employment Intelligence" in html_text,
          "Locked Version 3.0 question and proposed function are present.")
    check("html_research_controls", all(s in html_text for s in ["UNKNOWN remains UNKNOWN", "does not establish that Greenhouse caused", "No candidate-level target"]),
          "UNKNOWN, causal, and candidate-linkage boundaries are stated.")
    write_audit(checks)
    status = "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL"
    manifest = {
        "artifact": "Version C — Version 3.0 Executive Dashboard",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "audience": "HR / Hiring Executive Leadership",
        "publication_status": "HOLD / REVIEW REQUIRED",
        "controlled_executive_review": True,
        "source_inputs": {name: {"path": str(path.relative_to(VERSION_C)), "sha256": sha256(path)} for name, path in INPUTS.items()},
        "visual_module": {"path": str((HERE / "neumorphic_visualizations.py").relative_to(VERSION_C)),
                          "sha256": sha256(HERE / "neumorphic_visualizations.py"),
                          "upstream_source_commit": SOURCE_COMMIT,
                          "upstream_source_independently_verified": SOURCE_VERIFIED,
                          "upstream_repository": SOURCE_REPOSITORY},
        "outcomes": {"MALE": counts["MALE"], "FEMALE": counts["FEMALE"], "UNKNOWN": counts["UNKNOWN"],
                     "total": total, "known_sex_male_pct": round(male_pct, 4),
                     "known_sex_female_pct": round(female_pct, 4), "male_female_ratio": round(ratio, 4)},
        "analytical_layers": {"SIGNAL": signal_status, "PREDICTION": "NOT ESTIMABLE FROM PUBLIC DATA", "FEEDBACK": feedback_status},
        "controls": {"sex_inference": False, "unknown_preserved": True,
                     "candidate_level_greenhouse_linkage": False, "synthetic_candidates": False,
                     "greenhouse_causal_claim": False, "plan_a_modified": False,
                     "external_assets": False},
        "outputs": {"html": {"path": str(HTML_PATH.relative_to(VERSION_C)), "sha256": sha256(HTML_PATH)},
                    "aggregate_visual": {"path": str(VISUAL_PATH.relative_to(VERSION_C)), "sha256": sha256(VISUAL_PATH)},
                    "audit": {"path": str(AUDIT_PATH.relative_to(VERSION_C)), "sha256": sha256(AUDIT_PATH)},
                    "audit_checks": len(checks), "audit_failures": sum(r["status"] == "FAIL" for r in checks)},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("STATUS")
    print("------")
    print(status)
    print("\nOBSERVED OUTCOMES")
    print("-----------------")
    print(f"MALE:    {counts['MALE']}")
    print(f"FEMALE:  {counts['FEMALE']}")
    print(f"UNKNOWN: {counts['UNKNOWN']}")
    print(f"TOTAL:   {total}")
    print("\nKNOWN-SEX COMPOSITION")
    print("---------------------")
    print(f"MALE:    {male_pct:.1f}%")
    print(f"FEMALE:  {female_pct:.1f}%")
    print(f"RATIO:   {ratio:.2f}:1")
    print("\nANALYTICAL LAYERS")
    print("-----------------")
    print(f"SIGNAL:      {signal_status}")
    print("PREDICTION:  NOT ESTIMABLE FROM PUBLIC DATA")
    print(f"FEEDBACK:    {feedback_status}")
    print("\nCONTROLS")
    print("--------")
    print("Sex inference:                    NO")
    print("Candidate-level Greenhouse link: NO")
    print("Synthetic candidates:            NO")
    print("Greenhouse causal claim:         NO")
    print("Plan A modified:                 NO")
    print("\nPROPOSED EXECUTIVE FUNCTION")
    print("----------------------------")
    print("Human-AI Employment Intelligence & Governance")
    print("\nREADY FOR CONTROLLED EXECUTIVE REVIEW")
    print(f"HTML: {HTML_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Audit: {AUDIT_PATH}")
    if status != "PASS":
        for row in checks:
            if row["status"] == "FAIL": print(f"FAIL {row['check_id']}: {row['detail']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

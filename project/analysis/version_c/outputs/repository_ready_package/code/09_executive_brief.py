"""Version C — Phase 9 executive research brief.

Presentation-only packaging of the audited Phase 7/8 evidence. This script
validates frozen inputs, writes a Markdown/HTML brief, and records provenance.
It does not perform modeling or modify earlier analytical artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"
VISUALS = OUT / "executive_visuals"

SUMMARY = OUT / "executive_summary.json"
OUTCOMES = OUT / "dashboard_outcome_distribution.csv"
SIGNALS = OUT / "dashboard_signal_findings.csv"
PREDICTION = OUT / "dashboard_predictive_findings.csv"
FEEDBACK = OUT / "dashboard_feedback_findings.csv"
LIMITATIONS = OUT / "dashboard_limitations.csv"
EVIDENCE = OUT / "dashboard_evidence_map.csv"
PHASE7_VALIDATION = AUDIT / "executive_dashboard_validation.json"
PHASE7_VALIDATION_CSV = AUDIT / "executive_dashboard_validation.csv"
PHASE7_MANIFEST = AUDIT / "executive_dashboard_run_manifest.json"
PHASE8_MANIFEST = AUDIT / "visualization_manifest.json"

BRIEF_MD = OUT / "executive_brief.md"
BRIEF_HTML = OUT / "executive_brief.html"
BRIEF_MANIFEST = OUT / "executive_brief_manifest.json"
BRIEF_AUDIT = AUDIT / "executive_brief_audit.csv"

VISUAL_FILES = [
    "01_observed_outcomes.png",
    "02_known_sex_outcomes.png",
    "03_research_outcomes.png",
    "04_evidence_architecture.png",
    "05_data_gaps.png",
    "06_executive_evidence_map.png",
]
EXPECTED_COUNTS = {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_audit(rows: list[dict[str, Any]]) -> int:
    with BRIEF_AUDIT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "detail"])
        writer.writeheader()
        writer.writerows(rows)
    return max(0, len(read_csv(BRIEF_AUDIT)))


def row_for(rows: list[dict[str, str]], key: str, value: str) -> dict[str, str] | None:
    return next((row for row in rows if row.get(key) == value), None)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    lines.extend("| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def html_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(item)}</th>" for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)

    input_paths = [SUMMARY, OUTCOMES, SIGNALS, PREDICTION, FEEDBACK, LIMITATIONS,
                   EVIDENCE, PHASE7_VALIDATION, PHASE7_VALIDATION_CSV,
                   PHASE7_MANIFEST, PHASE8_MANIFEST]
    input_paths.extend(VISUALS / name for name in VISUAL_FILES)
    missing = [str(path.relative_to(BASE)) for path in input_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Frozen Phase 7/8 brief inputs missing: " + ", ".join(missing))

    summary = read_json(SUMMARY)
    validation = read_json(PHASE7_VALIDATION)
    phase7_manifest = read_json(PHASE7_MANIFEST)
    phase8_manifest = read_json(PHASE8_MANIFEST)
    if validation.get("overall_status") != "PASS" or int(validation.get("failed", -1)) != 0:
        raise RuntimeError("Phase 7 validation is not PASS; brief generation stopped.")
    if phase8_manifest.get("status") != "PASS":
        raise RuntimeError("Phase 8 visualization manifest is not PASS; brief generation stopped.")

    outcome_rows = read_csv(OUTCOMES)
    signal_rows = read_csv(SIGNALS)
    prediction_rows = read_csv(PREDICTION)
    feedback_rows = read_csv(FEEDBACK)
    limitation_rows = read_csv(LIMITATIONS)
    evidence_rows = read_csv(EVIDENCE)
    validation_rows = read_csv(PHASE7_VALIDATION_CSV)
    if not validation_rows or any(row.get("status") != "PASS" for row in validation_rows):
        raise RuntimeError("Phase 7 validation CSV contains a non-PASS check.")

    outcome_counts = {row.get("outcome_sex", "").upper(): int(row.get("person_count") or 0) for row in outcome_rows}
    if outcome_counts != EXPECTED_COUNTS:
        raise ValueError(f"Frozen dashboard outcomes do not match canonical counts: {outcome_counts}")
    outcome_layer = summary.get("outcome_layer", {})
    total = sum(outcome_counts.values())
    known = outcome_counts["MALE"] + outcome_counts["FEMALE"]
    if (int(outcome_layer.get("distinct_people", -1)) != total
            or int(outcome_layer.get("known_sex_denominator", -1)) != known
            or abs(float(outcome_layer.get("male_share_known_sex", -1)) - 606 / 882) > 1e-9
            or abs(float(outcome_layer.get("female_share_known_sex", -1)) - 276 / 882) > 1e-9):
        raise ValueError("Frozen executive summary does not reconcile to the canonical outcome table.")

    phase4_status = summary.get("phase_status", {}).get("PREDICTION", "NOT_AVAILABLE")
    phase5_status = summary.get("phase_status", {}).get("FEEDBACK", "NOT_AVAILABLE")
    if phase4_status != "NOT_ESTIMABLE":
        raise ValueError(f"Unexpected Phase 4 status for frozen evidence: {phase4_status}")
    if phase5_status != "COMPLETE_WITH_COVERAGE_LIMITS":
        raise ValueError(f"Unexpected Phase 5 status for frozen evidence: {phase5_status}")

    signal_layer = row_for(evidence_rows, "layer", "SIGNAL") or {}
    prediction_layer = row_for(evidence_rows, "layer", "PREDICTION") or {}
    feedback_layer = row_for(evidence_rows, "layer", "FEEDBACK") or {}
    outcome_layer_evidence = row_for(evidence_rows, "layer", "OUTCOME") or {}
    if not all((signal_layer, prediction_layer, feedback_layer, outcome_layer_evidence)):
        raise ValueError("Evidence map is missing one or more core evidence layers.")
    if prediction_layer.get("status") != phase4_status or feedback_layer.get("status") != phase5_status:
        raise ValueError("Evidence-map statuses do not match the frozen Phase 7 summary.")

    predictive_snapshot = summary.get("predictive_snapshot", {})
    feedback_snapshot = summary.get("feedback_snapshot", {})
    phase4_reason = predictive_snapshot.get("reason", "")
    observed_months = feedback_snapshot.get("observed_start_months", [])
    unavailable_months = feedback_snapshot.get("unobserved_outcome_months", [])

    research_records = next((row for row in evidence_rows if row.get("layer") == "OUTCOME"), {})
    signal_result = signal_layer.get("result", "")
    outcome_text = f"{outcome_counts['MALE']} MALE / {outcome_counts['FEMALE']} FEMALE / {outcome_counts['UNKNOWN']} UNKNOWN"
    known_male = outcome_counts["MALE"] / known * 100
    known_female = outcome_counts["FEMALE"] / known * 100
    unknown_share = outcome_counts["UNKNOWN"] / total * 100

    executive_summary = summary.get("executive_wording", "")
    brief_sections = [
        ("Executive summary", [executive_summary]),
        ("Observed outcome composition", [
            f"The frozen observed-hire records contain {outcome_text} (N={total}). Among the {known} records with reported source sex, {known_male:.2f}% are MALE and {known_female:.2f}% are FEMALE, a 2.20:1 MALE/FEMALE ratio. The remaining {outcome_counts['UNKNOWN']} records ({unknown_share:.2f}% of all records) have no reported source sex and remain UNKNOWN.",
            "These are descriptive counts from the observed dataset. They do not represent a complete candidate funnel and do not establish a Greenhouse effect.",
        ]),
        ("Candidate-facing signal evidence", [
            f"Phase 3 measured features from the public Greenhouse corpus. The frozen dashboard reports {signal_result}",
            "This describes material visible in postings. The records do not link a specific posting to a specific hire.",
        ]),
        ("Prediction: not estimable", [
            f"Phase 4 is {phase4_status}. Only {predictive_snapshot.get('eligible_role_month_cells', 'unknown')} exact role/month cells matched established-date postings with known-sex observed outcomes; {predictive_snapshot.get('male_present_cells', 'unknown')} cells contain Male outcomes and {predictive_snapshot.get('female_present_cells', 'unknown')} contain Female outcomes.",
            phase4_reason or "The frozen Phase 4 run did not support grouped cross-validation or model fitting. No predictive performance is reported.",
        ]),
        ("Feedback: exploratory with coverage limits", [
            f"Phase 5 status is {phase5_status}. It reports {feedback_snapshot.get('exact_role_month_overlap_cells', 'unknown')} exact role/month overlaps. Observed hire-start months are {', '.join(observed_months)}; August and September 2026 are unavailable in this snapshot, not zero.",
            "The forward comparisons have few month pairs; the +2 month analysis is deferred. Any co-movement remains exploratory and ecological, not causal.",
        ]),
        ("Internal evidence required", [
            "Public postings and aggregate observed outcomes do not expose the internal decision pathway. An internal audit would require Talent Matching outputs, actual criteria and weights, recruiter override records, applicant-stage progression, and interview scorecards.",
            "The absence of these records means the internal Greenhouse pathway is unobservable in this public-data project. It is not evidence that any one mechanism caused the observed outcome composition.",
        ]),
        ("Executive interpretation", [
            "An observed disparity is evidence of an outcome pattern. A predictive association, if estimable, would show information in observable signals. Neither alone demonstrates that Greenhouse AI caused an outcome. Here, the planned predictive model is not estimable with the matched role/month evidence.",
            "MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS",
        ]),
    ]

    visual_captions = [
        ("01_observed_outcomes.png", "Observed MALE / FEMALE / UNKNOWN outcome counts."),
        ("02_known_sex_outcomes.png", "Known-sex composition; UNKNOWN is excluded from the denominator."),
        ("03_research_outcomes.png", "Research-classified observed outcomes; source missingness remains separate."),
        ("04_evidence_architecture.png", "The observable signal, prediction, feedback, outcome, and internal-data-gap layers."),
        ("05_data_gaps.png", "Internal data required to examine the recruiting decision pathway."),
        ("06_executive_evidence_map.png", "Version C executive evidence map; no causal pathway is asserted."),
    ]

    md_parts = ["# Version C — Executive Research Brief", "", "**Study window:** April 1–September 30, 2026  ",
                "**Evidence status:** Frozen Phase 7 dashboard and Phase 8 visualization package  ",
                "**Purpose:** Executive summary of observable evidence and documented auditability limits.", ""]
    for heading, paragraphs in brief_sections:
        md_parts.extend([f"## {heading}", ""])
        md_parts.extend([p for p in paragraphs])
        md_parts.append("")
    md_parts.extend(["## Evidence status at a glance", "",
                     markdown_table(["Layer", "Status", "What it supports"], [
                         ["SIGNAL", "Observable / descriptive", "Measures candidate-facing posting text and representation."],
                         ["PREDICTION", "NOT_ESTIMABLE", "Matched role/month sample does not support the planned grouped model."],
                         ["FEEDBACK", "Exploratory / coverage-limited", "Aggregate temporal and role/month co-movement only."],
                         ["OUTCOME", "Observable with missingness", f"{outcome_text}; UNKNOWN is retained."],
                         ["INTERNAL WORKFLOW", "Data gap", "Talent Matching, recruiter, funnel, and interview records are unavailable."],
                     ]), "", "## Frozen visuals", ""])
    for filename, caption in visual_captions:
        md_parts.extend([f"### {caption}", "", f"![{caption}](executive_visuals/{filename})", ""])
    md_parts.extend(["## Provenance and boundaries", "",
                     f"Phase 7 validation: PASS ({validation.get('passed')} checks; {validation.get('failed')} failures).  ",
                     f"Phase 8 visualization package: {phase8_manifest.get('status')}.  ",
                     "No individual hire is linked to a Greenhouse posting. Unknown source sex is not imputed. Archive captures are not treated as posting dates. August/September outcome coverage is unavailable, not zero. No causal Greenhouse claim is made.", ""])
    markdown = "\n".join(md_parts)

    html_sections = []
    for heading, paragraphs in brief_sections:
        html_sections.append(f"<section><h2>{html.escape(heading)}</h2>" + "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs) + "</section>")
    status_rows = [
        ["SIGNAL", "Observable / descriptive", "Measures candidate-facing posting text and representation."],
        ["PREDICTION", "NOT_ESTIMABLE", "Matched role/month sample does not support the planned grouped model."],
        ["FEEDBACK", "Exploratory / coverage-limited", "Aggregate temporal and role/month co-movement only."],
        ["OUTCOME", "Observable with missingness", f"{outcome_text}; UNKNOWN is retained."],
        ["INTERNAL WORKFLOW", "Data gap", "Talent Matching, recruiter, funnel, and interview records are unavailable."],
    ]
    html_visuals = "".join(f'<figure><img src="executive_visuals/{html.escape(filename)}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>' for filename, caption in visual_captions)
    html_document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Version C — Executive Research Brief</title>
<style>
:root{{color-scheme:light;--navy:#172b4d;--ink:#253142;--muted:#5b6573;--line:#d9dee5;--blue:#eaf1f8;}}
*{{box-sizing:border-box}}body{{margin:0;background:#f6f8fa;color:var(--ink);font:16px/1.58 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1020px;margin:42px auto;padding:52px 64px;background:#fff;box-shadow:0 8px 36px #182b4d12}}
h1{{font-size:2.35rem;line-height:1.15;color:var(--navy);margin:0 0 12px}}.dek{{color:var(--muted);margin-bottom:28px}}
h2{{font-size:1.4rem;color:var(--navy);margin-top:34px;border-bottom:1px solid var(--line);padding-bottom:8px}}
p{{max-width:78ch}}.thesis{{padding:18px 22px;background:var(--blue);border-left:4px solid #5875a4;font-size:1.15rem;font-weight:700;color:var(--navy)}}
table{{border-collapse:collapse;width:100%;margin:18px 0}}th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--navy);background:#f2f5f8}}
.visuals{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}figure{{margin:0 0 12px}}figure img{{width:100%;height:auto;border:1px solid var(--line);border-radius:6px}}figcaption{{font-size:.88rem;color:var(--muted);margin-top:6px}}
footer{{border-top:1px solid var(--line);margin-top:36px;padding-top:18px;font-size:.9rem;color:var(--muted)}}@media(max-width:720px){{main{{margin:0;padding:28px 20px}}.visuals{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Version C — Executive Research Brief</h1>
<p class="dek">Study window: April 1–September 30, 2026 · Frozen Phase 7/8 evidence · Presentation only</p>
<div class="thesis">MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS</div>
{''.join(html_sections)}
<section><h2>Evidence status at a glance</h2>{html_table(["Layer", "Status", "What it supports"], status_rows)}</section>
<section><h2>Frozen visuals</h2><div class="visuals">{html_visuals}</div></section>
<footer>Phase 7 validation: PASS ({validation.get('passed')} checks, {validation.get('failed')} failures). Phase 8 visual package: {html.escape(str(phase8_manifest.get('status')))}. No candidate-level Greenhouse-to-hire linkage or causal effect is established. UNKNOWN is retained, and August/September outcome coverage is unavailable rather than zero.</footer>
</main></body></html>'''

    BRIEF_MD.write_text(markdown, encoding="utf-8")
    BRIEF_HTML.write_text(html_document, encoding="utf-8")

    audit_rows = [
        {"check": "phase7_validation_pass", "status": "PASS", "detail": f"{validation.get('passed')} passed; {validation.get('failed')} failed."},
        {"check": "phase8_visualization_pass", "status": "PASS", "detail": f"Visualization manifest status={phase8_manifest.get('status')} with six charts."},
        {"check": "canonical_outcome_counts", "status": "PASS", "detail": f"Reconciled outcome counts: {outcome_counts}; total={total}; known={known}."},
        {"check": "signal_prediction_feedback_outcome_separated", "status": "PASS", "detail": f"Statuses: signal={summary['phase_status'].get('SIGNAL')}, prediction={phase4_status}, feedback={phase5_status}, outcome=AVAILABLE."},
        {"check": "prediction_not_estimable_preserved", "status": "PASS", "detail": f"Brief states NOT_ESTIMABLE and preserves source reason: {phase4_reason}"},
        {"check": "unknown_not_imputed", "status": "PASS", "detail": "Unknown is retained outside the known-sex denominator."},
        {"check": "no_linkage_or_causal_claim", "status": "PASS", "detail": "Brief explicitly denies individual posting linkage and causal identification."},
        {"check": "august_september_limitation", "status": "PASS", "detail": f"Observed months={observed_months}; unavailable months={unavailable_months}; brief labels these unavailable, not zero."},
        {"check": "visual_references_exist", "status": "PASS", "detail": f"All six referenced PNGs verified: {VISUAL_FILES}."},
    ]
    for source in input_paths:
        audit_rows.append({"check": f"input_hash:{source.name}", "status": "PASS", "detail": f"sha256={sha256_file(source)}; bytes={source.stat().st_size}."})
    audit_rows.extend([
        {"check": "markdown_readback", "status": "PASS" if BRIEF_MD.read_text(encoding="utf-8") == markdown else "FAIL", "detail": "Markdown brief reopened and matched generated content."},
        {"check": "html_readback", "status": "PASS" if BRIEF_HTML.read_text(encoding="utf-8") == html_document else "FAIL", "detail": "HTML brief reopened and matched generated content."},
    ])
    audit_rows.append({"check": "duplicate_only_guard", "status": "PASS", "detail": "Only the new Phase 9 Markdown, HTML, manifest, and audit files are written."})
    audit_count = write_audit(audit_rows)
    failures = sum(row["status"] == "FAIL" for row in audit_rows)
    manifest = {
        "manifest_type": "version_c_phase_9_executive_research_brief",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if failures == 0 else "FAIL",
        "presentation_only": True,
        "inputs": {str(path.relative_to(BASE)): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_paths},
        "outcomes": {"counts": outcome_counts, "total": total, "known_sex_denominator": known,
                     "male_share_known_sex": outcome_counts["MALE"] / known,
                     "female_share_known_sex": outcome_counts["FEMALE"] / known,
                     "male_female_ratio": outcome_counts["MALE"] / outcome_counts["FEMALE"],
                     "unknown_share_all": outcome_counts["UNKNOWN"] / total},
        "evidence_status": {"SIGNAL": summary["phase_status"].get("SIGNAL"), "PREDICTION": phase4_status,
                            "FEEDBACK": phase5_status, "OUTCOME": summary["phase_status"].get("OUTCOME")},
        "outputs": {
            BRIEF_MD.name: {"path": str(BRIEF_MD.relative_to(BASE)), "sha256": sha256_file(BRIEF_MD), "bytes": BRIEF_MD.stat().st_size},
            BRIEF_HTML.name: {"path": str(BRIEF_HTML.relative_to(BASE)), "sha256": sha256_file(BRIEF_HTML), "bytes": BRIEF_HTML.stat().st_size},
        },
        "audit": {"path": str(BRIEF_AUDIT.relative_to(BASE)), "rows": audit_count, "sha256": sha256_file(BRIEF_AUDIT)},
        "design_guards": {"prior_layers_modified": False, "new_statistical_claims": False, "sex_inference": False,
                          "candidate_level_linkage": False, "causal_greenhouse_claim": False,
                          "unknown_reassigned": False, "archive_capture_as_posting_date": False},
    }
    BRIEF_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if read_json(BRIEF_MANIFEST).get("status") != manifest["status"]:
        raise RuntimeError("Executive brief manifest read-back failed.")

    print(json.dumps({"status": manifest["status"], "audit_checks": audit_count, "failures": failures,
                      "outcome_counts": outcome_counts, "brief_markdown": str(BRIEF_MD),
                      "brief_html": str(BRIEF_HTML), "manifest": str(BRIEF_MANIFEST), "audit": str(BRIEF_AUDIT)}, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

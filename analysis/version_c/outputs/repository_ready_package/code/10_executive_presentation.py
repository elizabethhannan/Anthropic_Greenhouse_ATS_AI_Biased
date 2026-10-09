"""Version C — Phase 10 executive / ML scientist presentation package.

Presentation-only conversion of frozen Phase 7–9 evidence. The deck makes no
new statistical claims and does not alter any prior Version C artifact.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"
VISUALS = OUT / "executive_visuals"
DECK_PATH = OUT / "version_c_executive_deck.pptx"
OUTLINE_PATH = OUT / "version_c_executive_deck_outline.md"
MANIFEST_PATH = OUT / "presentation_manifest.json"
AUDIT_PATH = AUDIT / "presentation_audit.csv"

SUMMARY_PATH = OUT / "executive_summary.json"
BRIEF_PATH = OUT / "executive_brief.md"
BRIEF_HTML_PATH = OUT / "executive_brief.html"
BRIEF_MANIFEST_PATH = OUT / "executive_brief_manifest.json"
PHASE7_VALIDATION_PATH = AUDIT / "executive_dashboard_validation.json"
PHASE7_MANIFEST_PATH = AUDIT / "executive_dashboard_run_manifest.json"
PHASE8_MANIFEST_PATH = AUDIT / "visualization_manifest.json"
PHASE9_AUDIT_PATH = AUDIT / "executive_brief_audit.csv"
EVIDENCE_MAP_PATH = OUT / "dashboard_evidence_map.csv"

VISUALS_USED = {
    "outcomes": "01_observed_outcomes.png",
    "known_sex": "02_known_sex_outcomes.png",
    "research": "03_research_outcomes.png",
    "architecture": "04_evidence_architecture.png",
    "gaps": "05_data_gaps.png",
    "evidence_map": "06_executive_evidence_map.png",
}
EXPECTED_OUTCOMES = {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213}

# Visual system
NAVY = RGBColor(23, 43, 77)
INK = RGBColor(39, 50, 65)
MUTED = RGBColor(91, 101, 115)
LINE = RGBColor(220, 225, 231)
BG = RGBColor(248, 250, 252)
BLUE = RGBColor(234, 241, 248)
TEAL = RGBColor(220, 239, 234)
GOLD = RGBColor(247, 237, 208)
PINK = RGBColor(245, 228, 234)
WHITE = RGBColor(255, 255, 255)
MALE = RGBColor(88, 117, 164)
FEMALE = RGBColor(195, 109, 140)
UNKNOWN = RGBColor(154, 163, 174)

SLIDE_SPECS: list[dict[str, Any]] = [
    {"title": "The executive question", "purpose": "Frame what public evidence can and cannot tell us.", "evidence": ["outputs/executive_brief.md", "outputs/executive_summary.json"]},
    {"title": "Why model fairness is not enough", "purpose": "Separate model, workflow, and outcome fairness questions.", "evidence": ["outputs/dashboard_evidence_map.csv", "outputs/executive_brief.md"]},
    {"title": "Research architecture", "purpose": "Show the provenance-first evidence pipeline and separate outcome layer.", "evidence": ["outputs/executive_summary.json", "audit/executive_dashboard_validation.json"]},
    {"title": "Observed outcome environment", "purpose": "Present the source-sex outcome counts and missingness without imputing Unknown.", "evidence": ["outputs/dashboard_outcome_distribution.csv", "outputs/executive_summary.json", "outputs/executive_visuals/01_observed_outcomes.png"]},
    {"title": "SIGNAL — what candidates can see", "purpose": "Describe the public Greenhouse corpus and recovered descriptions.", "evidence": ["outputs/dashboard_evidence_map.csv", "outputs/dashboard_signal_findings.csv"]},
    {"title": "PREDICTION — not estimable", "purpose": "Report the role/month sample limitation without manufacturing model performance.", "evidence": ["outputs/dashboard_predictive_findings.csv", "outputs/executive_summary.json"]},
    {"title": "FEEDBACK — exploratory and coverage-limited", "purpose": "Keep ecological timing separate from causal or individual linkage.", "evidence": ["outputs/dashboard_evidence_map.csv", "outputs/dashboard_feedback_findings.csv", "outputs/executive_brief.md"]},
    {"title": "What public data cannot see", "purpose": "Identify the unavailable internal AI and recruiting workflow records.", "evidence": ["outputs/dashboard_limitations.csv", "outputs/executive_visuals/05_data_gaps.png"]},
    {"title": "Internal audit architecture", "purpose": "Specify the records required to evaluate deployed human-AI workflow treatment.", "evidence": ["outputs/dashboard_evidence_map.csv", "outputs/dashboard_limitations.csv"]},
    {"title": "Research conclusions", "purpose": "Summarize only the conclusions supported by the frozen evidence.", "evidence": ["outputs/executive_brief.md", "outputs/executive_summary.json"]},
    {"title": "Evidence that would close the gap", "purpose": "Translate governance questions into concrete data requirements.", "evidence": ["outputs/dashboard_limitations.csv", "outputs/executive_visuals/05_data_gaps.png"]},
    {"title": "ML / HXO research contribution", "purpose": "Position the contribution as a reproducible method and system-boundary analysis.", "evidence": ["outputs/executive_brief.md", "outputs/executive_brief_manifest.json", "audit/executive_dashboard_validation.json"]},
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def add_text(slide: Any, text: str, x: float, y: float, w: float, h: float,
             size: float = 18, color: RGBColor = INK, bold: bool = False,
             align: Any = PP_ALIGN.LEFT, font: str = "Aptos") -> Any:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(.03)
    tf.margin_right = Inches(.03)
    tf.margin_top = Inches(.02)
    tf.margin_bottom = Inches(.02)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_rich_lines(slide: Any, lines: list[str], x: float, y: float, w: float, h: float,
                   size: float = 16, color: RGBColor = INK, bullet: bool = False,
                   space_after: float = 10) -> Any:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(.06)
    tf.margin_right = Inches(.04)
    tf.margin_top = Inches(.03)
    tf.margin_bottom = Inches(.03)
    for idx, line in enumerate(lines):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = ("•  " if bullet else "") + line
        p.font.name = "Aptos"
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(space_after)
        p.level = 0
    return box


def add_box(slide: Any, x: float, y: float, w: float, h: float, title: str,
            detail: str = "", fill: RGBColor = BLUE, title_size: int = 15,
            detail_size: int = 10, align: Any = PP_ALIGN.CENTER) -> Any:
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = LINE
    shape.line.width = Pt(1)
    tf = shape.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    tf.margin_left = Inches(.12)
    tf.margin_right = Inches(.12)
    tf.margin_top = Inches(.06)
    tf.margin_bottom = Inches(.06)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = title
    run.font.name = "Aptos Display"
    run.font.size = Pt(title_size)
    run.font.bold = True
    run.font.color.rgb = NAVY
    if detail:
        p2 = tf.add_paragraph()
        p2.alignment = align
        p2.space_before = Pt(4)
        r2 = p2.add_run()
        r2.text = detail
        r2.font.name = "Aptos"
        r2.font.size = Pt(detail_size)
        r2.font.color.rgb = MUTED
    return shape


def add_arrow(slide: Any, x1: float, y1: float, x2: float, y2: float, color: RGBColor = MUTED) -> None:
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    line.line.color.rgb = color
    line.line.width = Pt(1.6)
    line.line.end_arrowhead = True


def new_slide(prs: Presentation, number: int, section: str, title: str, source: str) -> Any:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(.14)).fill.solid()
    slide.shapes[-1].fill.fore_color.rgb = NAVY
    add_text(slide, section.upper(), .62, .34, 4.2, .25, 9, MUTED, True)
    add_text(slide, title, .62, .73, 12.0, .58, 27, NAVY, True)
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(.62), Inches(1.43), Inches(.78), Inches(.055)).fill.solid()
    slide.shapes[-1].fill.fore_color.rgb = MALE
    # Footer source note plus slide number.
    footer = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(.62), Inches(7.08), Inches(12.05), Inches(.012))
    footer.fill.solid(); footer.fill.fore_color.rgb = LINE; footer.line.fill.background()
    add_text(slide, f"EVIDENCE  {source}", .64, 7.13, 11.35, .20, 8, MUTED)
    add_text(slide, f"{number:02d} / 12", 11.95, 7.12, .7, .22, 8, MUTED, align=PP_ALIGN.RIGHT)
    return slide


def add_image(slide: Any, path: Path, x: float, y: float, w: float, h: float) -> None:
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))


def make_presentation(summary: dict[str, Any], evidence_rows: list[dict[str, str]],
                      prediction_rows: list[dict[str, str]], feedback_rows: list[dict[str, str]],
                      phase7_validation: dict[str, Any]) -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = "Version C — Executive / ML Scientist Research Presentation"
    prs.core_properties.subject = "Public evidence, observed outcomes, and human-AI recruiting auditability boundaries"
    prs.core_properties.author = "Version C research project"
    prs.core_properties.keywords = "ML, HXO, governance, hiring, auditability"

    outcome = summary["outcome_layer"]
    phase_status = summary["phase_status"]
    signal_map = next((r for r in evidence_rows if r.get("layer") == "SIGNAL"), {})
    feedback_map = next((r for r in evidence_rows if r.get("layer") == "FEEDBACK"), {})
    limits = read_csv(OUT / "dashboard_limitations.csv")
    prediction_reason = next((r.get("reason", "") for r in prediction_rows if r.get("reason")), "")
    estimated_feedback = sum(r.get("evidence_strength") == "LOW_EXPLORATORY" for r in feedback_rows)
    visual = {key: VISUALS / filename for key, filename in VISUALS_USED.items()}

    # 1 — Executive question
    s = new_slide(prs, 1, "Version C · Research question", "Can public recruiting signals be connected to observed hiring outcomes?", "Phase 7 executive summary · Phase 9 brief")
    add_text(s, "A public-data study of candidate-facing recruiting signals, observed workforce composition, and the limits of auditing an internal AI-mediated workflow.", .8, 1.78, 11.7, .78, 20, INK)
    add_box(s, .85, 3.05, 5.55, 1.18, "WHAT IS OBSERVABLE?", "Public job postings and aggregate observed outcomes", BLUE, 17, 12)
    add_box(s, 6.9, 3.05, 5.55, 1.18, "WHAT REMAINS HIDDEN?", "Candidate-level decisions, recommendations, overrides, and funnel stages", GOLD, 17, 12)
    add_text(s, "The study tests the evidence boundary; it does not attribute the outcome pattern to Greenhouse.", 1.2, 5.1, 10.9, .55, 17, NAVY, True, PP_ALIGN.CENTER)

    # 2 — Fairness distinction
    s = new_slide(prs, 2, "Governance frame", "Why model fairness is not enough", "Phase 7/9 evidence map")
    add_box(s, .72, 2.15, 3.55, 1.05, "MODEL FAIRNESS", "Does the model behave fairly?", BLUE, 15, 11)
    add_text(s, "≠", 4.38, 2.39, .55, .45, 25, MUTED, True, PP_ALIGN.CENTER)
    add_box(s, 4.95, 2.15, 3.45, 1.05, "WORKFLOW FAIRNESS", "How do people and tools act together?", TEAL, 14, 10)
    add_text(s, "≠", 8.48, 2.39, .55, .45, 25, MUTED, True, PP_ALIGN.CENTER)
    add_box(s, 9.05, 2.15, 3.55, 1.05, "OUTCOME FAIRNESS", "What composition is observed?", PINK, 15, 11)
    add_rich_lines(s, ["A model-level evaluation cannot reveal how recommendations are used in a recruiting workflow.",
                       "Observed outcome composition alone cannot identify which stage produced it.",
                       "Version C measures what public data show and names the internal records needed to audit the pathway."],
                   1.0, 4.1, 11.3, 1.6, 17, INK, bullet=True, space_after=12)

    # 3 — Research architecture
    s = new_slide(prs, 3, "Evidence design", "Research architecture: preserve provenance and keep layers separate", "Phase 7/8 manifests · frozen Phase 7 summary")
    add_box(s, .65, 2.02, 2.55, 1.0, "PUBLIC JOB POSTINGS", "Greenhouse snapshot + historical corpus", BLUE, 13, 9)
    add_box(s, 3.72, 2.02, 2.55, 1.0, "SIGNAL MEASUREMENT", "Posting text + representation features", TEAL, 13, 9)
    add_box(s, 7.08, 2.02, 2.55, 1.0, "AGGREGATE BRIDGE", "Role × month only; no person linkage", GOLD, 13, 9)
    add_box(s, 10.14, 2.02, 2.55, 1.0, "OBSERVED OUTCOMES", "MALE / FEMALE / UNKNOWN", PINK, 13, 9)
    add_arrow(s, 3.21, 2.52, 3.66, 2.52); add_arrow(s, 6.28, 2.52, 7.02, 2.52); add_arrow(s, 9.64, 2.52, 10.08, 2.52)
    add_box(s, 2.05, 4.32, 3.9, .95, "DATE EVIDENCE", "Posting date ≠ archive capture date", BG, 14, 11)
    add_box(s, 7.4, 4.32, 3.9, .95, "SOURCE SEX", "Unknown retained; never inferred", BG, 14, 11)
    add_text(s, "Each output has a source, status, and explicit claim boundary.", 1.4, 5.9, 10.5, .4, 17, NAVY, True, PP_ALIGN.CENTER)

    # 4 — Outcome environment
    s = new_slide(prs, 4, "Observed outcome", "What the frozen observed-hire data show", "Phase 7 dashboard · Phase 8 outcome chart")
    add_image(s, visual["outcomes"], .95, 1.68, 7.7, 4.85)
    add_box(s, 9.0, 2.0, 3.25, .88, "1,095", "distinct observed people", BLUE, 21, 12)
    add_box(s, 9.0, 3.18, 3.25, .88, "882", "known-sex denominator", TEAL, 21, 12)
    add_box(s, 9.0, 4.36, 3.25, .88, "213 UNKNOWN", "19.45% of all records", GOLD, 17, 11)
    add_text(s, "Descriptive outcome pattern; not a complete hiring-funnel record.", 8.95, 5.65, 3.4, .6, 12, MUTED, False, PP_ALIGN.CENTER)

    # 5 — Signal
    s = new_slide(prs, 5, "SIGNAL · candidate-facing environment", "What a candidate can see", "Phase 7 dashboard signal findings · executive evidence map")
    add_box(s, .8, 2.0, 3.35, 1.25, "1,246", "posting records in analytical master", BLUE, 21, 12)
    add_box(s, 4.98, 2.0, 3.35, 1.25, "704", "descriptions recovered", TEAL, 21, 12)
    add_box(s, 9.15, 2.0, 3.35, 1.25, "13", "postings with named-person references", GOLD, 21, 11)
    add_rich_lines(s, ["Signal features describe candidate-facing text and representation.",
                       "They do not establish intent, preference, discrimination, or individual exposure.",
                       "Historical date evidence remains distinct from archive capture timing."],
                   1.0, 4.0, 11.1, 1.5, 17, INK, bullet=True, space_after=12)
    add_text(s, "SIGNAL = observable recruiting environment", 1.2, 6.2, 10.9, .35, 15, NAVY, True, PP_ALIGN.CENTER)

    # 6 — Prediction
    s = new_slide(prs, 6, "PREDICTION · ecological diagnostic", "The planned predictive model is not estimable", "Phase 4 metrics and run manifest, carried through Phase 7")
    add_box(s, .9, 2.0, 2.75, 1.18, "3", "matched exact role/month cells", GOLD, 18, 12)
    add_box(s, 4.0, 2.0, 2.75, 1.18, "3", "cells with Male outcomes", BLUE, 18, 12)
    add_box(s, 7.1, 2.0, 2.75, 1.18, "0", "cells with Female outcomes", PINK, 18, 12)
    add_box(s, 10.2, 2.0, 2.25, 1.18, "NO AUC", "no model fit", BG, 17, 11)
    add_text(s, "Why stop?", .95, 3.85, 1.6, .36, 17, NAVY, True)
    add_text(s, prediction_reason, .95, 4.32, 11.3, 1.15, 15, INK)
    add_text(s, "This is a sample-support limitation—not evidence for or against discrimination.", .95, 5.85, 11.3, .44, 14, MUTED, True)

    # 7 — Feedback
    s = new_slide(prs, 7, "FEEDBACK · temporal/ecological", "Feedback is exploratory and coverage-limited", "Phase 7 feedback findings · frozen executive brief")
    add_box(s, .9, 2.0, 3.3, 1.12, "5", "exact role/month overlaps", TEAL, 19, 12)
    add_box(s, 5.0, 2.0, 3.3, 1.12, "APR–JUL", "observed start-month coverage", BLUE, 16, 12)
    add_box(s, 9.1, 2.0, 3.3, 1.12, "AUG–SEP", "unavailable, not zero", GOLD, 16, 12)
    add_rich_lines(s, ["Forward comparisons have very few month pairs; the +2 month analysis is deferred.",
                       "The unit is an aggregate role/month cell, not an applicant or hire linked to a posting.",
                       "Co-movement does not establish a posting-to-hire pathway or causal effect."],
                   1.0, 3.85, 11.2, 1.65, 17, INK, bullet=True, space_after=12)
    add_text(s, "Association is not causation—and this association is exploratory.", .95, 6.0, 11.3, .4, 15, NAVY, True, PP_ALIGN.CENTER)

    # 8 — Public-data boundary
    s = new_slide(prs, 8, "Observability boundary", "What public data cannot see", "Phase 8 data-gap visual · Phase 7 limitations")
    add_image(s, visual["gaps"], 1.1, 1.65, 10.9, 4.95)

    # 9 — Internal audit architecture
    s = new_slide(prs, 9, "Internal audit architecture", "What an internal workflow audit would need", "Phase 7 evidence map · limitations")
    add_box(s, .55, 2.1, 2.2, 1.15, "MODEL INPUTS", "criteria · weights · thresholds", BLUE, 13, 9)
    add_box(s, 3.2, 2.1, 2.2, 1.15, "AI OUTPUTS", "rank · recommendation · match score", GOLD, 12, 9)
    add_box(s, 5.85, 2.1, 2.2, 1.15, "HUMAN ACTIONS", "accept · override · rationale", TEAL, 12, 9)
    add_box(s, 8.5, 2.1, 2.0, 1.15, "FUNNEL", "stage · transition · disposition", PINK, 12, 9)
    add_box(s, 10.95, 2.1, 1.85, 1.15, "INTERVIEW", "scorecards · evaluators", BG, 12, 9)
    add_arrow(s, 2.8, 2.66, 3.12, 2.66); add_arrow(s, 5.45, 2.66, 5.77, 2.66); add_arrow(s, 8.1, 2.66, 8.42, 2.66); add_arrow(s, 10.55, 2.66, 10.87, 2.66)
    add_box(s, 2.15, 4.35, 8.95, 1.0, "AUDITABLE, PRIVACY-GOVERNED DATASET", "stable pseudonymous IDs · timestamps · versioned definitions · access controls", BLUE, 15, 11)
    add_arrow(s, 6.63, 3.34, 6.63, 4.27)
    add_text(s, "These records are requirements for a future audit; their absence does not establish a particular mechanism or result.", 1.0, 5.9, 11.3, .52, 14, MUTED, False, PP_ALIGN.CENTER)

    # 10 — Research conclusions
    s = new_slide(prs, 10, "Supported conclusions", "What Version C can responsibly conclude", "Phase 7–9 frozen executive outputs")
    add_rich_lines(s, ["The observed outcome composition is measurable: 606 MALE, 276 FEMALE, 213 UNKNOWN.",
                       "Candidate-facing public recruiting signals can be measured and traced to postings.",
                       "The planned role/month predictive model is not estimable with the current matched sample.",
                       "Temporal comparisons are exploratory and limited by sparse overlap and missing Aug/Sep starts.",
                       "The internal AI-mediated decision pathway cannot be audited from the public data used here."],
                   .95, 1.85, 11.4, 3.9, 18, INK, bullet=True, space_after=15)
    add_text(s, "No causal claim about Greenhouse is supported by this evidence package.", 1.0, 6.15, 11.2, .38, 15, NAVY, True, PP_ALIGN.CENTER)

    # 11 — Evidence to close the gap
    s = new_slide(prs, 11, "Next evidence", "What evidence would close the auditability gap?", "Phase 7 data-gap table · Phase 8 data-gap visual")
    gap_items = [
        ("01", "Talent Matching outputs", "Recommendations, rank, score, and model/version metadata"),
        ("02", "Criteria and weights", "Configured features, thresholds, and change history"),
        ("03", "Recruiter overrides", "Actions, timestamps, and documented rationale"),
        ("04", "Candidate funnel", "Applications, stage transitions, and dispositions"),
        ("05", "Interview scorecards", "Structured evaluations and evaluator records"),
    ]
    for i, (number, title, detail) in enumerate(gap_items):
        y = 1.82 + i * .88
        add_box(s, .9, y, .72, .62, number, fill=NAVY, title_size=15, detail_size=10)
        add_box(s, 1.85, y, 3.1, .62, title, fill=BLUE, title_size=13, detail_size=10, align=PP_ALIGN.LEFT)
        add_text(s, detail, 5.15, y + .12, 7.1, .38, 13, INK)
    add_text(s, "A future internal study would also need governance-approved linkage, privacy controls, and versioned definitions.", .95, 6.4, 11.4, .32, 11, MUTED, False, PP_ALIGN.CENTER)

    # 12 — ML/HXO contribution
    s = new_slide(prs, 12, "Portfolio contribution", "A reproducible ML / HXO research method", "Phase 9 brief · Phase 7 validation · Phase 8 visualization manifest")
    add_text(s, "Designed and implemented a provenance-first method for separating model-level questions, human-AI workflow questions, and observed outcome evidence.", .95, 1.82, 11.35, .85, 20, NAVY, True)
    add_box(s, .85, 3.15, 3.55, 1.18, "ML RIGOR", "grouped ecological unit · leakage boundaries · stop rule for insufficient support", BLUE, 15, 10)
    add_box(s, 4.9, 3.15, 3.55, 1.18, "HXO / UX", "candidate-facing signals · human actions · workflow observability", TEAL, 15, 10)
    add_box(s, 8.95, 3.15, 3.55, 1.18, "GOVERNANCE", "provenance · unknown retention · explicit internal-data requirements", GOLD, 15, 10)
    add_text(s, "The model was not estimable on the available role/month evidence; methodological discipline includes reporting that boundary.", 1.0, 5.0, 11.2, .62, 15, INK, False, PP_ALIGN.CENTER)
    add_text(s, "Outcome pattern observed. Candidate-facing signals measured. Internal pathway still unobservable.", 1.0, 6.1, 11.2, .4, 14, NAVY, True, PP_ALIGN.CENTER)

    return prs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    required = [SUMMARY_PATH, BRIEF_PATH, BRIEF_HTML_PATH, BRIEF_MANIFEST_PATH,
                PHASE7_VALIDATION_PATH, PHASE7_MANIFEST_PATH, PHASE8_MANIFEST_PATH,
                PHASE9_AUDIT_PATH, EVIDENCE_MAP_PATH, OUT / "dashboard_predictive_findings.csv",
                OUT / "dashboard_feedback_findings.csv", OUT / "dashboard_limitations.csv"]
    required.extend(VISUALS / name for name in VISUALS_USED.values())
    missing = [str(path.relative_to(BASE)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Frozen Phase 7–9 inputs missing: " + ", ".join(missing))

    summary = read_json(SUMMARY_PATH)
    validation = read_json(PHASE7_VALIDATION_PATH)
    phase7_manifest = read_json(PHASE7_MANIFEST_PATH)
    phase8_manifest = read_json(PHASE8_MANIFEST_PATH)
    phase9_manifest = read_json(BRIEF_MANIFEST_PATH)
    phase9_audit_rows = read_csv(PHASE9_AUDIT_PATH)
    if validation.get("overall_status") != "PASS" or validation.get("failed") != 0:
        raise RuntimeError("Phase 7 validation is not PASS; presentation build stopped.")
    if phase8_manifest.get("status") != "PASS" or phase9_manifest.get("status") != "PASS":
        raise RuntimeError("Phase 8 visualization or Phase 9 brief is not PASS; presentation build stopped.")
    if not phase9_audit_rows or any(row.get("status") != "PASS" for row in phase9_audit_rows):
        raise RuntimeError("Phase 9 audit contains a non-PASS check; presentation build stopped.")
    for path in (BRIEF_PATH, BRIEF_HTML_PATH):
        expected_hash = phase9_manifest.get("outputs", {}).get(path.name, {}).get("sha256")
        if not expected_hash or sha256_file(path) != expected_hash:
            raise ValueError(f"Phase 9 brief hash does not match its manifest: {path.name}")
    for filename in VISUALS_USED.values():
        relative = str((VISUALS / filename).relative_to(BASE))
        expected_hash = phase8_manifest.get("outputs", {}).get(relative, {}).get("sha256")
        if not expected_hash or sha256_file(VISUALS / filename) != expected_hash:
            raise ValueError(f"Phase 8 visual hash does not match its manifest: {filename}")

    outcomes = read_csv(OUT / "dashboard_outcome_distribution.csv")
    outcome_counts = {row.get("outcome_sex", "").upper(): int(row.get("person_count") or 0) for row in outcomes}
    if outcome_counts != EXPECTED_OUTCOMES:
        raise ValueError(f"Frozen outcome counts mismatch: {outcome_counts}")
    if phase7_manifest.get("outcome_counts", {}) != {**EXPECTED_OUTCOMES, "known_sex": 882}:
        raise ValueError("Phase 7 manifest outcome counts are not canonical.")
    if phase9_manifest.get("outcomes", {}).get("counts") != EXPECTED_OUTCOMES:
        raise ValueError("Phase 9 brief manifest outcome counts do not reconcile.")

    evidence_rows = read_csv(EVIDENCE_MAP_PATH)
    prediction_rows = read_csv(OUT / "dashboard_predictive_findings.csv")
    feedback_rows = read_csv(OUT / "dashboard_feedback_findings.csv")
    if summary.get("phase_status", {}).get("PREDICTION") != "NOT_ESTIMABLE":
        raise ValueError("Unexpected frozen prediction status; do not draft deck from unsupported status.")
    if summary.get("phase_status", {}).get("FEEDBACK") != "COMPLETE_WITH_COVERAGE_LIMITS":
        raise ValueError("Unexpected frozen feedback status.")

    prs = make_presentation(summary, evidence_rows, prediction_rows, feedback_rows, validation)
    prs.save(DECK_PATH)
    outline = ["# Version C — Executive / ML Scientist Presentation Outline", "",
               "**Evidence boundary:** Frozen Phase 7–9 outputs only; no new statistical analysis.",
               "**Core thesis:** MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS.",
               "**Outcome counts:** 606 MALE / 276 FEMALE / 213 UNKNOWN (N=1,095; known-sex N=882).", ""]
    for idx, spec in enumerate(SLIDE_SPECS, start=1):
        outline.extend([f"## Slide {idx}: {spec['title']}", "", spec["purpose"], "",
                        "Evidence: " + "; ".join(spec["evidence"]), ""])
    outline.extend(["## Interpretation boundary", "",
                    "The deck reports an observed outcome pattern, public candidate-facing signals, a predictive analysis that is NOT_ESTIMABLE with the current matched cells, exploratory feedback with temporal coverage limits, and internal data gaps. It does not claim that Greenhouse caused an outcome or assign an individual hire to a posting.", ""])
    outline_text = "\n".join(outline)
    OUTLINE_PATH.write_text(outline_text, encoding="utf-8")

    # Reopen the PPTX to verify packaging and the required slide count.
    reopened = Presentation(str(DECK_PATH))
    if len(reopened.slides) != 12:
        raise RuntimeError(f"Expected 12 slides, found {len(reopened.slides)}")
    if OUTLINE_PATH.read_text(encoding="utf-8") != outline_text:
        raise RuntimeError("Presentation outline read-back did not match.")

    input_paths = [SUMMARY_PATH, BRIEF_PATH, BRIEF_HTML_PATH, BRIEF_MANIFEST_PATH,
                   PHASE7_VALIDATION_PATH, PHASE7_MANIFEST_PATH, PHASE8_MANIFEST_PATH,
                   PHASE9_AUDIT_PATH, EVIDENCE_MAP_PATH, OUT / "dashboard_outcome_distribution.csv",
                   OUT / "dashboard_predictive_findings.csv", OUT / "dashboard_feedback_findings.csv",
                   OUT / "dashboard_limitations.csv", *(VISUALS / name for name in VISUALS_USED.values())]
    audit_rows: list[dict[str, Any]] = []
    for path in input_paths:
        audit_rows.append({"check": f"input:{path.name}", "status": "PASS", "detail": f"Read-only frozen input; sha256={sha256_file(path)}"})
    audit_rows.extend([
        {"check": "phase7_validation_pass", "status": "PASS", "detail": f"{validation.get('passed')} passed; 0 failed."},
        {"check": "phase8_visual_package_pass", "status": "PASS", "detail": "All six frozen visuals are available; Phase 8 manifest is PASS."},
        {"check": "phase9_brief_pass", "status": "PASS", "detail": "Phase 9 brief manifest is PASS."},
        {"check": "frozen_phase8_phase9_hashes", "status": "PASS", "detail": "Phase 9 brief files and all six Phase 8 charts match their recorded manifest hashes."},
        {"check": "phase9_audit_pass", "status": "PASS", "detail": f"All {len(phase9_audit_rows)} Phase 9 audit rows are PASS."},
        {"check": "canonical_outcomes", "status": "PASS", "detail": f"Canonical counts reconciled: {outcome_counts}; Unknown remains separate."},
        {"check": "prediction_not_estimable_preserved", "status": "PASS", "detail": "PREDICTION remains NOT_ESTIMABLE; no model metrics are invented."},
        {"check": "feedback_limits_preserved", "status": "PASS", "detail": "FEEDBACK remains exploratory/coverage-limited; Aug/Sep are unavailable, not zero."},
        {"check": "no_causal_or_person_linkage_claim", "status": "PASS", "detail": "No individual hire/posting linkage or Greenhouse causal claim is made."},
        {"check": "slide_count", "status": "PASS", "detail": f"Reopened presentation contains {len(reopened.slides)} slides."},
        {"check": "outline_readback", "status": "PASS", "detail": "Markdown outline reopened and matched generated content."},
    ])

    with AUDIT_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "detail"])
        writer.writeheader()
        writer.writerows(audit_rows)
    audit_readback = read_csv(AUDIT_PATH)
    failures = sum(row["status"] == "FAIL" for row in audit_readback)
    if len(audit_readback) != len(audit_rows):
        raise RuntimeError("Presentation audit CSV read-back row count mismatch.")

    manifest = {
        "manifest_type": "version_c_phase_10_executive_presentation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if failures == 0 else "FAIL",
        "slide_count": len(reopened.slides),
        "presentation_only": True,
        "source_validation": {"path": str(PHASE7_VALIDATION_PATH.relative_to(BASE)), "status": validation.get("overall_status"), "checks": validation.get("checks"), "sha256": sha256_file(PHASE7_VALIDATION_PATH)},
        "evidence_status": summary.get("phase_status", {}),
        "outcomes": {"counts": outcome_counts, "total": sum(outcome_counts.values()), "known_sex_denominator": 882},
        "inputs": {str(path.relative_to(BASE)): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_paths},
        "outputs": {
            DECK_PATH.name: {"path": str(DECK_PATH.relative_to(BASE)), "sha256": sha256_file(DECK_PATH), "bytes": DECK_PATH.stat().st_size},
            OUTLINE_PATH.name: {"path": str(OUTLINE_PATH.relative_to(BASE)), "sha256": sha256_file(OUTLINE_PATH), "bytes": OUTLINE_PATH.stat().st_size},
        },
        "audit": {"path": str(AUDIT_PATH.relative_to(BASE)), "rows": len(audit_readback), "sha256": sha256_file(AUDIT_PATH)},
        "design_guards": {"prior_phases_modified": False, "new_statistical_analysis": False, "sex_inference": False,
                          "unknown_reassigned": False, "candidate_level_linkage": False, "causal_greenhouse_claim": False,
                          "archive_capture_as_posting_date": False, "august_september_as_zero_hiring": False},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if read_json(MANIFEST_PATH).get("status") != manifest["status"]:
        raise RuntimeError("Presentation manifest read-back failed.")

    print(json.dumps({"status": manifest["status"], "slides": len(reopened.slides), "audit_checks": len(audit_readback), "audit_failures": failures,
                      "deck": str(DECK_PATH), "outline": str(OUTLINE_PATH), "manifest": str(MANIFEST_PATH), "audit": str(AUDIT_PATH)}, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

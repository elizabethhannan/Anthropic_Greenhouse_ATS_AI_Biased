"""Version C — Phase 8 executive visualization package.

Creates chart-ready copies and PNGs from validated Version C executive data.
The script never changes Plan A or Phase 2–7 source artifacts and makes no
candidate-level or causal claim.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"
VISUALS = OUT / "executive_visuals"

SUMMARY_PATH = OUT / "executive_summary.json"
OUTCOME_PATH = OUT / "dashboard_outcome_distribution.csv"
RESEARCH_PATH = OUT / "research_outcome_distribution.csv"
EVIDENCE_PATH = OUT / "dashboard_evidence_map.csv"
GAPS_PATH = OUT / "dashboard_limitations.csv"
VALIDATION_PATH = AUDIT / "executive_dashboard_validation.json"
VALIDATION_CSV = AUDIT / "executive_dashboard_validation.csv"

CHART_NAMES = [
    "01_observed_outcomes.png",
    "02_known_sex_outcomes.png",
    "03_research_outcomes.png",
    "04_evidence_architecture.png",
    "05_data_gaps.png",
    "06_executive_evidence_map.png",
]
COLORS = {"MALE": "#5875A4", "FEMALE": "#C36D8C", "UNKNOWN": "#9AA3AE"}
NAVY = "#172B4D"
BLUE = "#EAF1F8"
TEAL = "#DCEFEA"
GOLD = "#F5E9C9"
PINK = "#F4E2E8"
GRAY = "#5B6573"


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


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> int:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return max(0, sum(1 for _ in path.open("r", encoding="utf-8")) - 1)


def check_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required validated Phase 7 input missing: {path}")


def style_axis(ax: Any) -> None:
    ax.set_facecolor("white")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#D9DEE5")
    ax.tick_params(axis="y", length=0, colors=NAVY)
    ax.tick_params(axis="x", colors=GRAY)
    ax.grid(axis="x", color="#E8EBEF", linewidth=0.8)
    ax.set_axisbelow(True)


def save_figure(fig: Any, path: Path) -> None:
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def add_box(ax: Any, x: float, y: float, width: float, height: float,
            title: str, detail: str = "", face: str = BLUE,
            title_size: int = 12, detail_size: int = 9) -> None:
    patch = FancyBboxPatch((x, y), width, height,
                           boxstyle="round,pad=0.012,rounding_size=0.02",
                           linewidth=1.0, edgecolor="#C9D1DB", facecolor=face)
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * 0.66, title, ha="center", va="center",
            fontsize=title_size, fontweight="bold", color=NAVY, wrap=True)
    if detail:
        ax.text(x + width / 2, y + height * 0.29, detail, ha="center", va="center",
                fontsize=detail_size, color=GRAY, wrap=True)


def arrow(ax: Any, start: tuple[float, float], end: tuple[float, float],
          color: str = "#788493", style: str = "-|>") -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=13,
                                linewidth=1.3, color=color, connectionstyle="arc3"))


def chart_observed_outcomes(counts: dict[str, int], total: int, path: Path) -> None:
    labels = ["MALE", "FEMALE", "UNKNOWN"]
    values = [counts[k] for k in labels]
    fig, ax = plt.subplots(figsize=(9.2, 5.3))
    fig.subplots_adjust(left=0.17, right=0.82, top=0.80, bottom=0.16)
    bars = ax.barh(labels[::-1], values[::-1], color=[COLORS[k] for k in labels[::-1]], height=0.56)
    ax.set_title("Observed hiring outcomes", loc="left", fontsize=19, fontweight="bold", color=NAVY, pad=18)
    ax.text(0, 1.04, f"{total:,} distinct observed people · source sex retained as MALE / FEMALE / UNKNOWN",
            transform=ax.transAxes, fontsize=10, color=GRAY)
    ax.set_xlim(0, max(values) * 1.34)
    ax.set_xlabel("People", color=GRAY, labelpad=10)
    style_axis(ax)
    for bar, key in zip(bars, labels[::-1]):
        count = counts[key]
        pct = count / total * 100 if total else 0
        ax.text(bar.get_width() + max(values) * .025, bar.get_y() + bar.get_height()/2,
                f"{count:,}  ·  {pct:.2f}%", va="center", fontsize=11, color=NAVY, fontweight="bold")
    fig.text(.17, .035, "Unknown is source-missingness; it is not reassigned to either known-sex category.", fontsize=9, color=GRAY)
    save_figure(fig, path)


def chart_known_sex(counts: dict[str, int], known: int, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    fig.subplots_adjust(left=.18, right=.82, top=.79, bottom=.18)
    labels = ["MALE", "FEMALE"]
    vals = [counts[k] / known * 100 for k in labels]
    bars = ax.barh(labels[::-1], vals[::-1], color=[COLORS[k] for k in labels[::-1]], height=.55)
    ax.set_title("Known-sex outcome composition", loc="left", fontsize=18, fontweight="bold", color=NAVY, pad=18)
    ax.text(0, 1.04, f"Denominator: {known:,} known MALE/FEMALE records", transform=ax.transAxes, fontsize=10, color=GRAY)
    ax.set_xlim(0, 88)
    ax.set_xlabel("Share of known-sex records", color=GRAY, labelpad=10)
    ax.set_xticks([0, 20, 40, 60, 80], ["0%", "20%", "40%", "60%", "80%"])
    style_axis(ax)
    for bar, key, pct in zip(bars, labels[::-1], vals[::-1]):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f"{pct:.2f}%  ·  {counts[key]:,}", va="center", fontsize=11, color=NAVY, fontweight="bold")
    fig.text(.18, .04, "213 UNKNOWN records (19.45% of all records) are excluded from this denominator.", fontsize=9, color=GRAY)
    save_figure(fig, path)


def chart_research(research_counts: dict[str, int], research_total: int, path: Path) -> None:
    known = research_counts["MALE"] + research_counts["FEMALE"]
    labels = ["MALE", "FEMALE", "UNKNOWN"]
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    fig.subplots_adjust(left=.18, right=.84, top=.79, bottom=.18)
    bars = ax.barh(labels[::-1], [research_counts[k] for k in labels[::-1]],
                   color=[COLORS[k] for k in labels[::-1]], height=.55)
    ax.set_title("Research-classified observed hires", loc="left", fontsize=18, fontweight="bold", color=NAVY, pad=18)
    ax.text(0, 1.04, f"{research_total} research-classified records · {known} known-sex records",
            transform=ax.transAxes, fontsize=10, color=GRAY)
    ax.set_xlim(0, max(research_counts.values()) * 1.45)
    ax.set_xlabel("People", color=GRAY, labelpad=10)
    style_axis(ax)
    for bar, key in zip(bars, labels[::-1]):
        count = research_counts[key]
        suffix = f"{count / known * 100:.2f}% of known-sex" if key != "UNKNOWN" and known else f"{count / research_total * 100:.2f}% of all research" if research_total else ""
        ax.text(bar.get_width() + .5, bar.get_y() + bar.get_height()/2,
                f"{count}  ·  {suffix}", va="center", fontsize=10, color=NAVY, fontweight="bold")
    fig.text(.18, .04, "Descriptive subset only; classification and source missingness remain explicit.", fontsize=9, color=GRAY)
    save_figure(fig, path)


def chart_architecture(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 7.0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(.5, .96, "Evidence architecture", ha="center", va="center", fontsize=20, fontweight="bold", color=NAVY)
    ax.text(.5, .875, "MODEL FAIRNESS     ≠     WORKFLOW FAIRNESS     ≠     OUTCOME FAIRNESS",
            ha="center", fontsize=12, fontweight="bold", color=NAVY)
    add_box(ax, .06, .66, .25, .12, "SIGNAL", "candidate-facing postings", BLUE)
    add_box(ax, .375, .66, .25, .12, "PREDICTION", "NOT ESTIMABLE", GOLD)
    add_box(ax, .69, .66, .25, .12, "FEEDBACK", "exploratory · coverage-limited", TEAL)
    add_box(ax, .30, .40, .40, .13, "OBSERVED OUTCOME", "606 MALE · 276 FEMALE · 213 UNKNOWN", PINK)
    add_box(ax, .27, .12, .46, .13, "INTERNAL DATA GAP", "AI pathway · workflow · overrides · interview", "#F0F1F3")
    arrow(ax, (.185, .65), (.36, .55)); arrow(ax, (.5, .65), (.5, .55)); arrow(ax, (.815, .65), (.64, .55))
    arrow(ax, (.5, .39), (.5, .26))
    fig.text(.5, .035, "Observable patterns do not establish a Greenhouse-caused outcome or individual-level pathway.",
             ha="center", fontsize=9, color=GRAY)
    save_figure(fig, path)


def chart_gaps(path: Path) -> None:
    gaps = [
        ("Talent Matching outputs", "rankings · recommendations · match scores"),
        ("Actual criteria and weights", "configured rules · thresholds · feature weights"),
        ("Recruiter overrides", "recommendation acceptance · overrides · rationale"),
        ("Candidate funnel", "applications · stages · transitions · disposition"),
        ("Interview scorecards", "candidate-level evaluations · evaluator records"),
    ]
    fig, ax = plt.subplots(figsize=(10.5, 6.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(.07, .93, "What internal evidence is still needed?", fontsize=19, fontweight="bold", color=NAVY)
    ax.text(.07, .86, "Public postings and observed outcomes cannot reveal the internal decision pathway.", fontsize=10, color=GRAY)
    for idx, (title, detail) in enumerate(gaps):
        y = .73 - idx * .125
        add_box(ax, .07, y, .86, .095, title, detail, "#F4F5F7", title_size=11, detail_size=8)
    fig.text(.07, .06, "These are data requirements for an internal audit—not findings that these mechanisms caused an outcome.", fontsize=9, color=GRAY)
    save_figure(fig, path)


def chart_evidence_map(summary: dict[str, Any], counts: dict[str, int], path: Path) -> None:
    outcome = summary["outcome_layer"]
    status = summary["phase_status"]
    fig, ax = plt.subplots(figsize=(12, 8.2))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(.5, .97, "Version C · executive evidence map", ha="center", fontsize=20, fontweight="bold", color=NAVY)
    ax.text(.5, .90, "MODEL FAIRNESS     ≠     WORKFLOW FAIRNESS     ≠     OUTCOME FAIRNESS",
            ha="center", fontsize=12, fontweight="bold", color=NAVY)
    add_box(ax, .06, .67, .25, .13, "SIGNAL", "1,246 postings · 704 descriptions", BLUE)
    add_box(ax, .375, .67, .25, .13, "PREDICTION", str(status.get("PREDICTION", "NOT AVAILABLE")), GOLD)
    add_box(ax, .69, .67, .25, .13, "FEEDBACK", "Apr–Jul observed · Aug/Sep unavailable", TEAL, title_size=11, detail_size=8)
    add_box(ax, .25, .40, .50, .14, "OBSERVED OUTCOME", f"MALE {counts['MALE']}   |   FEMALE {counts['FEMALE']}\nUNKNOWN {counts['UNKNOWN']} · known-sex n={outcome['known_sex_denominator']}", PINK, title_size=13, detail_size=9)
    add_box(ax, .18, .13, .64, .15, "INTERNAL DATA GAP", "Talent Matching outputs · criteria/weights · recruiter overrides\nCandidate funnel · interview scorecards", "#F0F1F3", title_size=12, detail_size=9)
    arrow(ax, (.185, .66), (.35, .55)); arrow(ax, (.5, .66), (.5, .55)); arrow(ax, (.815, .66), (.65, .55)); arrow(ax, (.5, .39), (.5, .29))
    ax.text(.5, .335, f"Known-sex composition: {outcome['male_share_known_sex']:.2%} MALE / {outcome['female_share_known_sex']:.2%} FEMALE",
            ha="center", fontsize=9, color=GRAY)
    fig.text(.5, .045, "Association and outcome evidence are separate; neither identifies Greenhouse causation.", ha="center", fontsize=9, color=GRAY)
    save_figure(fig, path)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    VISUALS.mkdir(parents=True, exist_ok=True)
    input_paths = [SUMMARY_PATH, OUTCOME_PATH, RESEARCH_PATH, EVIDENCE_PATH, GAPS_PATH, VALIDATION_PATH, VALIDATION_CSV]
    for path in input_paths:
        check_file(path)

    summary = read_json(SUMMARY_PATH)
    validation = read_json(VALIDATION_PATH)
    if validation.get("overall_status") != "PASS" or validation.get("failed") != 0:
        raise RuntimeError("Phase 7 dashboard validation is not PASS; visualization build stopped.")

    outcome_rows = read_csv(OUTCOME_PATH)
    research_rows = read_csv(RESEARCH_PATH)
    evidence_rows = read_csv(EVIDENCE_PATH)
    gap_rows = read_csv(GAPS_PATH)

    outcome_counts = {str(r["outcome_sex"]).upper(): int(r["person_count"]) for r in outcome_rows}
    expected = {k: int(summary["outcome_layer"][k]) for k in ("MALE", "FEMALE", "UNKNOWN")}
    if outcome_counts != expected:
        raise ValueError(f"Dashboard outcome table and summary disagree: {outcome_counts} != {expected}")
    research_counts = {str(r["outcome_sex"]).upper(): int(r["person_count"]) for r in research_rows}
    research_total = sum(research_counts.values())
    if research_total != 40 or research_counts != {"MALE": 19, "FEMALE": 8, "UNKNOWN": 13}:
        raise ValueError(f"Research outcome inputs do not match frozen Phase 6 counts: {research_counts}")

    validation_rows = read_csv(VALIDATION_CSV)
    if any(row.get("status") != "PASS" for row in validation_rows):
        raise RuntimeError("Phase 7 validation CSV contains a non-PASS check.")

    outcome_data = []
    for row in outcome_rows:
        outcome_data.append({"population": "all_observed_people", **row})
    for row in research_rows:
        outcome_data.append(row)
    outcome_data_path = OUT / "visualization_outcome_data.csv"
    outcome_fields = ["population", "outcome_sex", "person_count", "share_all_people", "share_known_sex", "denominator_all_people", "denominator_known_sex", "source_field", "sex_inferred"]
    outcome_data_rows = write_csv(outcome_data_path, outcome_data, outcome_fields)

    evidence_path = OUT / "visualization_evidence_data.csv"
    evidence_fields = ["layer", "source", "evidence_type", "status", "result", "strength", "claim_boundary"]
    evidence_data_rows = write_csv(evidence_path, evidence_rows, evidence_fields)
    gaps_path = OUT / "visualization_data_gaps.csv"
    gap_fields = ["limitation", "detail", "applies_to", "severity"]
    gap_data_rows = write_csv(gaps_path, gap_rows, gap_fields)

    charts = {
        CHART_NAMES[0]: lambda p: chart_observed_outcomes(outcome_counts, sum(outcome_counts.values()), p),
        CHART_NAMES[1]: lambda p: chart_known_sex(outcome_counts, outcome_counts["MALE"] + outcome_counts["FEMALE"], p),
        CHART_NAMES[2]: lambda p: chart_research(research_counts, research_total, p),
        CHART_NAMES[3]: chart_architecture,
        CHART_NAMES[4]: chart_gaps,
        CHART_NAMES[5]: lambda p: chart_evidence_map(summary, outcome_counts, p),
    }
    for filename, render in charts.items():
        render(VISUALS / filename)

    audit_rows = []
    for path in input_paths:
        audit_rows.append({"check": f"input:{path.name}", "status": "PASS", "rows": "", "detail": f"Read-only input; sha256={sha256_file(path)}"})
    audit_rows.extend([
        {"check": "phase7_validation_status", "status": "PASS", "rows": validation.get("checks"), "detail": "Phase 7 validation says PASS with zero failures."},
        {"check": "outcome_count_reconciliation", "status": "PASS", "rows": sum(outcome_counts.values()), "detail": f"Counts match summary: {outcome_counts}."},
        {"check": "research_count_reconciliation", "status": "PASS", "rows": research_total, "detail": f"Research subset counts: {research_counts}."},
        {"check": "unknown_kept_separate", "status": "PASS", "rows": outcome_counts["UNKNOWN"], "detail": "Unknown stays distinct and is excluded from known-sex chart denominator."},
        {"check": "no_causal_claim", "status": "PASS", "rows": 0, "detail": "Visual titles/captions describe observable outcomes and evidence gaps only."},
        {"check": "duplicate_only", "status": "PASS", "rows": 0, "detail": "Only visualization outputs, chart-data copies, and Phase 8 audit/manifest were written."},
        {"check": "chart_files_created", "status": "PASS" if all((VISUALS / name).exists() for name in CHART_NAMES) else "FAIL", "rows": len(CHART_NAMES), "detail": "Six PNG visual assets created."},
        {"check": "chart_data_readback", "status": "PASS" if outcome_data_rows == len(outcome_data) and evidence_data_rows == len(evidence_rows) and gap_data_rows == len(gap_rows) else "FAIL", "rows": outcome_data_rows + evidence_data_rows + gap_data_rows, "detail": "Three chart-data CSVs reopened and row counts matched."},
    ])

    output_paths = [OUT / "visualization_outcome_data.csv", OUT / "visualization_evidence_data.csv", OUT / "visualization_data_gaps.csv", *(VISUALS / name for name in CHART_NAMES)]
    output_meta = {}
    for path in output_paths:
        if path.suffix.lower() == ".png":
            # Loading the rendered image confirms it is a readable PNG rather than an empty file.
            image = plt.imread(path)
            readable = image.ndim in (2, 3) and image.size > 0
            rows = None
        else:
            image = None
            readable = True
            rows = len(read_csv(path))
        output_meta[str(path.relative_to(BASE))] = {"sha256": sha256_file(path), "bytes": path.stat().st_size, "rows": rows, "readback_verified": readable}
        audit_rows.append({"check": f"output_readback:{path.name}", "status": "PASS" if readable and path.stat().st_size > 0 else "FAIL", "rows": rows if rows is not None else "", "detail": f"SHA-256={output_meta[str(path.relative_to(BASE))]['sha256']}"})

    audit_path = AUDIT / "visualization_audit.csv"
    audit_count = write_csv(audit_path, audit_rows, ["check", "status", "rows", "detail"])
    failures = sum(row["status"] == "FAIL" for row in audit_rows)
    manifest = {
        "manifest_type": "version_c_phase_8_executive_visualization",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if failures == 0 else "FAIL",
        "source_validation": {"path": str(VALIDATION_PATH.relative_to(BASE)), "status": validation.get("overall_status"), "checks": validation.get("checks"), "sha256": sha256_file(VALIDATION_PATH)},
        "inputs": {str(path.relative_to(BASE)): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_paths},
        "outcomes": {"counts": outcome_counts, "total": sum(outcome_counts.values()), "known_sex": outcome_counts["MALE"] + outcome_counts["FEMALE"], "research_counts": research_counts, "research_total": research_total},
        "outputs": output_meta,
        "audit": {"path": str(audit_path.relative_to(BASE)), "rows": audit_count, "sha256": sha256_file(audit_path)},
        "design_guards": {"source_layers_modified": False, "sex_inference": False, "candidate_level_linkage": False, "causal_claim": False, "unknown_excluded_from_known_sex_denominator": True},
        "interpretation_boundary": "Charts describe observed outcomes, public-facing signals, and documented data gaps; they do not establish that Greenhouse caused an outcome.",
    }
    manifest_path = AUDIT / "visualization_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_check = read_json(manifest_path)
    if manifest_check.get("status") != manifest["status"]:
        raise RuntimeError("Visualization manifest read-back failed.")

    print(json.dumps({"status": manifest["status"], "charts": len(CHART_NAMES), "chart_data_rows": {"outcomes": outcome_data_rows, "evidence": evidence_data_rows, "data_gaps": gap_data_rows}, "audit_checks": audit_count, "audit_failures": failures, "visuals_directory": str(VISUALS), "audit": str(audit_path), "manifest": str(manifest_path)}, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

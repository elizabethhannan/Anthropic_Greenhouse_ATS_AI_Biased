"""Version C — Phase 12 external research release candidate builder.

Builds a conservative, allowlist-only candidate. This does not grant or certify
publication rights. The gate remains HOLD until licensing/privacy review.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
AUDIT = BASE / "audit"
DEST = OUT / "external_release_candidate"

CODE = [
    "01_prepare_version_c.py", "02_signal_diagnostic.py", "03_predictive_models.py",
    "04_feedback_diagnostic.py", "05_male_female_unknown_outcomes.py",
    "06_executive_dashboard_data.py", "07_validate_executive_dashboard.py",
    "07_version_c_final_audit.py", "08_executive_visualization_data.py",
    "09_executive_brief.py", "10_executive_presentation.py",
    "11_reproducibility_package_audit.py", "12_build_external_release_candidate.py",
]
RESULTS = [
    "dashboard_outcome_distribution.csv", "research_outcome_distribution.csv",
    "dashboard_signal_findings.csv", "dashboard_predictive_findings.csv",
    "dashboard_feedback_findings.csv", "dashboard_limitations.csv",
    "dashboard_evidence_map.csv", "signal_summary.csv", "predictive_findings.csv",
    "feedback_summary.csv", "outcome_distribution.csv", "fellowship_outcome_distribution.csv",
]
VISUALS = [f"{i:02d}_{n}.png" for i, n in enumerate([
    "observed_outcomes", "known_sex_outcomes", "research_outcomes",
    "evidence_architecture", "data_gaps", "executive_evidence_map"], 1)]
DOCS = ["executive_brief.md", "version_c_executive_deck_outline.md"]
AUDITS = ["phase11_reproducibility_checks.csv", "phase11_claim_audit.csv",
          "phase11_schema_audit.csv", "phase11_provenance_manifest.json"]

PII_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "credential_assignment": re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_files(paths: list[tuple[Path, Path]], missing: list[str]) -> list[dict]:
    inventory = []
    for source, relative in paths:
        if not source.is_file():
            missing.append(str(source.relative_to(BASE)))
            continue
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        inventory.append({"path": relative.as_posix(), "bytes": target.stat().st_size,
                          "sha256": sha256(target)})
    return inventory


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["check_id", "status", "detail"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    missing: list[str] = []
    sources: list[tuple[Path, Path]] = []
    sources += [(BASE / name, Path("code") / name) for name in CODE]
    sources += [(OUT / name, Path("results") / name) for name in RESULTS]
    sources += [(OUT / "executive_visuals" / name, Path("visuals") / name) for name in VISUALS]
    sources += [(OUT / name, Path("docs") / name) for name in DOCS]
    sources += [(AUDIT / name, Path("audit") / name) for name in AUDITS]
    sources.append((OUT / "version_c_reproducibility_report.md", Path("audit") / "version_c_reproducibility_report.md"))
    inventory = copy_files(sources, missing)

    readme = """# Version C — External Research Release Candidate\n\nSTATUS: RELEASE CANDIDATE — NOT APPROVED FOR PUBLICATION.\n\nThis conservative package contains analysis code, aggregate research outputs, selected visuals, documentation, and Phase 11 audit records. It excludes raw/row-level Dewey data, person-level records, person identifiers, candidate-level linkage, resumes, recruiter records, interview scorecards, internal Greenhouse/Anthropic data, and credentials.\n\nAll source licensing, privacy, and redistribution questions remain open. Do not publish or redistribute until the licensing/privacy gate is cleared by the responsible human reviewers. The Phase 12 scan is a screening aid, not legal clearance or a guarantee that all sensitive content has been found.\n\nSee `RELEASE_STATUS.md` and `docs/data_license_and_publication_boundary.md` for the review boundary.\n"""
    (DEST / "README.md").write_text(readme, encoding="utf-8")
    (DEST / "RELEASE_STATUS.md").write_text("""# Release status\n\n**Gate: HOLD — REVIEW REQUIRED**\n\nThis is a release candidate only. External publication is blocked pending documented licensing and privacy review, including source terms and personal-information/context review. Phase 11 reported `PASS_WITH_WARNINGS`; reproducibility does not establish redistribution permission.\n\nRequired before the gate can change: review applicable Greenhouse, Internet Archive, Dewey/PDL, and third-party source terms; review named-person references and privacy/context; confirm redistribution rights for job-description text and visuals; approve intended audience and limitations language.\n""", encoding="utf-8")
    (DEST / "docs" / "data_license_and_publication_boundary.md").write_text("""# Data license and publication boundary\n\nNo license or permission evidence in the Phase 11 package certifies redistribution. Human review must establish whether Greenhouse, Internet Archive, Dewey/PDL, and other source terms permit the proposed use. Review personal names, biographies, contextual privacy, job-description text, screenshots, and visual assets. Prefer source links or minimal excerpts where terms require it. This candidate does not provide legal clearance.\n\n## Preserved research limitations\n\n- Phase 4 prediction is **NOT_ESTIMABLE**: only 3 exact role/month cells matched dated postings and known-sex observed hires, below the prespecified cell and class thresholds; grouped cross-validation was not estimable.\n- Phase 5 is exploratory and coverage-limited: observed start months are April–July 2026; August and September are unavailable, not zero. Forward comparisons have few month pairs and the +2 month comparison is deferred. Aggregate co-movement is not causal or person-level evidence.\n- Observed outcome counts (606 MALE, 276 FEMALE, 213 UNKNOWN) describe the observed dataset, not a complete hiring funnel. No individual posting-to-hire linkage is claimed.\n""", encoding="utf-8")
    for src in [BASE / "outputs" / "executive_brief.md"]:
        if src.is_file():
            shutil.copy2(src, DEST / "docs" / "methodology.md")
    (DEST / "docs" / "data_dictionary.md").write_text("""# Data dictionary\n\nThe `results/` directory contains aggregate tables only. Outcome counts and shares retain the `UNKNOWN` source-sex category; known-sex shares use only the 882 records with reported source sex. Signal, predictive, and feedback tables summarize study-level findings. The unit for feedback comparisons is role/month, not a person or candidate. Consult each CSV header and the methodology for field-level definitions.\n""", encoding="utf-8")

    scans = []
    scan_hits = []
    for path in sorted(DEST.rglob("*")):
        if not path.is_file() or path.name == "release_candidate_manifest.json":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            scans.append({"path": str(path.relative_to(DEST)), "status": "SKIPPED_BINARY", "findings": ""})
            continue
        findings = []
        for label, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(content):
                findings.append(label)
                scan_hits.append({"path": str(path.relative_to(DEST)), "finding": label,
                                  "line": content.count("\n", 0, match.start()) + 1})
        scans.append({"path": str(path.relative_to(DEST)), "status": "FINDING" if findings else "CLEAR",
                      "findings": ";".join(sorted(set(findings)))})
    write_csv(DEST / "audit" / "phase12_sensitive_content_scan.csv", scans)

    generated = [p for p in DEST.rglob("*") if p.is_file() and p.name != "release_candidate_manifest.json"]
    manifest = {
        "phase": 12, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "HOLD_REVIEW_REQUIRED", "phase11_status": "PASS_WITH_WARNINGS",
        "publication_certified": False,
        "exclusions": ["raw/row-level Dewey data", "person-level data and person IDs",
                       "candidate-level linkage", "resumes", "recruiter records", "interview scorecards",
                       "internal Greenhouse/Anthropic data", "credentials/secrets"],
        "missing_allowlisted_inputs": missing,
        "sensitive_scan_findings": scan_hits,
        "artifact_inventory": [{"path": str(p.relative_to(DEST)), "bytes": p.stat().st_size,
                                "sha256": sha256(p)} for p in sorted(generated)],
        "gate_reason": "Licensing/privacy review is incomplete; Phase 11 warnings remain open.",
    }
    (DEST / "release_candidate_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("PHASE 12 — EXTERNAL RESEARCH RELEASE CANDIDATE")
    print(f"Candidate: {DEST}")
    print(f"Allowlisted inputs missing: {len(missing)}")
    if missing:
        for name in missing:
            print(f"  MISSING: {name}")
    print(f"Sensitive-content scan: {len(scans)} files scanned; {len(scan_hits)} findings")
    for hit in scan_hits:
        print(f"  FINDING: {hit['path']}:{hit['line']} {hit['finding']}")
    print("Release gate: HOLD / REVIEW REQUIRED")
    print("Reason: licensing/privacy review and redistribution permissions are not certified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

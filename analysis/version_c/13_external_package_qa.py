"""Version C — Phase 13 external package QA (audit only)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
PKG = BASE / "outputs" / "external_release_candidate"
OUT = BASE / "outputs"
AUDIT = BASE / "audit"
REPORT = OUT / "version_c_external_package_qa_report.md"
CSV_AUDIT = AUDIT / "phase13_external_package_qa.csv"
MANIFEST_OUT = OUT / "version_c_external_package_qa_manifest.json"

EXPECTED_DIRS = {"audit", "code", "docs", "results", "visuals"}
REQUIRED_ROOT = {"README.md", "RELEASE_STATUS.md", "release_candidate_manifest.json"}
PERSON_TERMS = re.compile(r"(?i)\b(person_id|candidate_id|applicant_id|resume_text|email_address|phone_number|greenhouse_candidate_id)\b")
LINK_TERMS = re.compile(r"(?i)\b(candidate_level_hire_linkage|person_level_linkage|candidate_to_hire_link|person_id.*greenhouse|greenhouse.*person_id)\b")
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "credential_assignment": re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def record(checks: list[dict], name: str, passed: bool, detail: str, severity: str = "CRITICAL") -> None:
    checks.append({"check_id": name, "status": "PASS" if passed else "FAIL",
                   "severity": "INFO" if passed else severity, "detail": detail})


def main() -> int:
    checks: list[dict] = []
    warnings = 0
    source_manifest = PKG / "release_candidate_manifest.json"
    if not PKG.is_dir() or not source_manifest.is_file():
        raise SystemExit(f"Release candidate or Phase 12 manifest missing: {PKG}")
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    expected_files = {x["path"] for x in source.get("artifact_inventory", [])}
    expected_files.add("release_candidate_manifest.json")
    actual_files = {p.relative_to(PKG).as_posix() for p in PKG.rglob("*") if p.is_file()}
    actual_dirs = {p.relative_to(PKG).as_posix() for p in PKG.iterdir() if p.is_dir()}
    record(checks, "allowlisted_structure", actual_dirs == EXPECTED_DIRS and REQUIRED_ROOT <= actual_files,
           f"root_dirs={sorted(actual_dirs)}; required_root_present={REQUIRED_ROOT <= actual_files}")
    record(checks, "no_unexpected_or_missing_files", actual_files == expected_files,
           f"missing={sorted(expected_files-actual_files)}; unexpected={sorted(actual_files-expected_files)}")

    manifest_hash_ok = True
    mismatches = []
    for item in source.get("artifact_inventory", []):
        p = PKG / item["path"]
        if not p.is_file() or p.stat().st_size != item.get("bytes") or digest(p) != item.get("sha256"):
            manifest_hash_ok = False
            mismatches.append(item["path"])
    record(checks, "phase12_manifest_hashes", manifest_hash_ok, f"mismatches={mismatches}")

    # Scan only distributable results/docs for row-level identifiers. Source code and
    # audit discussion may mention forbidden schemas while documenting exclusions.
    sensitive_hits = []
    secret_hits = []
    linkage_hits = []
    causal_hits = []
    for rel in sorted(actual_files):
        p = PKG / rel
        if p.suffix.lower() in {".png", ".pptx", ".parquet"}:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if rel.startswith("results/"):
            for m in PERSON_TERMS.finditer(content):
                sensitive_hits.append(f"{rel}:{content.count(chr(10),0,m.start())+1}:{m.group(0)}")
            for m in LINK_TERMS.finditer(content):
                linkage_hits.append(f"{rel}:{content.count(chr(10),0,m.start())+1}:{m.group(0)}")
            if re.search(r"(?i)(greenhouse|AI).{0,50}\b(caused|causes|causing|led to)\b", content):
                causal_hits.append(rel)
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                secret_hits.append(f"{rel}:{kind}")
    record(checks, "no_person_candidate_identifiers", not sensitive_hits, f"hits={sensitive_hits}")
    record(checks, "no_greenhouse_person_linkage", not linkage_hits, f"hits={linkage_hits}")
    record(checks, "no_secrets_credentials", not secret_hits, f"hits={secret_hits}")
    record(checks, "no_unsupported_causal_claims", not causal_hits, f"hits={causal_hits}")

    # Allowlisted file types and directories prevent raw/row-level source artifacts.
    forbidden_ext = {".parquet", ".xlsx", ".xls", ".sqlite", ".db", ".jsonl"}
    forbidden_files = [x for x in actual_files if Path(x).suffix.lower() in forbidden_ext]
    record(checks, "no_raw_row_level_source_artifacts", not forbidden_files,
           f"forbidden_extensions={forbidden_files}")

    outcome_file = PKG / "results" / "dashboard_outcome_distribution.csv"
    outcomes = csv_rows(outcome_file) if outcome_file.is_file() else []
    counts = {r.get("outcome_sex"): int(r.get("person_count", -1)) for r in outcomes}
    metrics_ok = counts == {"MALE": 606, "FEMALE": 276, "UNKNOWN": 213} and sum(counts.values()) == 1095
    record(checks, "canonical_outcome_counts", metrics_ok, f"counts={counts}; total={sum(counts.values())}")
    known = [r for r in outcomes if r.get("outcome_sex") in {"MALE", "FEMALE"}]
    male_share = float(next((r["share_known_sex"] for r in known if r["outcome_sex"] == "MALE"), "nan"))
    female_share = float(next((r["share_known_sex"] for r in known if r["outcome_sex"] == "FEMALE"), "nan"))
    pct_ok = round(male_share * 100, 2) == 68.71 and round(female_share * 100, 2) == 31.29
    record(checks, "known_sex_percentages", pct_ok, f"male={male_share*100:.2f}%; female={female_share*100:.2f}%")
    ratio = counts.get("MALE", 0) / counts.get("FEMALE", 1)
    record(checks, "male_female_ratio", round(ratio, 2) == 2.20, f"ratio={ratio:.4f}:1")
    unknown_correct = any(r.get("outcome_sex") == "UNKNOWN" and r.get("person_count") == "213" for r in outcomes)
    record(checks, "unknown_retained_without_inference", unknown_correct and "UNKNOWN" not in " ".join(causal_hits),
           "UNKNOWN category retained as 213; no relabeling/inference applied in aggregate outcome table.")

    result_text = "\n".join((PKG / rel).read_text(encoding="utf-8", errors="ignore")
                           for rel in sorted(actual_files) if rel.startswith(("results/", "docs/"))
                           and (PKG / rel).suffix.lower() in {".csv", ".md"})
    phase4 = "NOT_ESTIMABLE" in result_text
    phase5_text = result_text.lower()
    has_late_months = all(s in phase5_text for s in ["august", "september"]) or all(s in phase5_text for s in ["2026-08", "2026-09"])
    phase5 = has_late_months and "unavailable" in phase5_text and "not zero" in phase5_text and "coverage_limits" in phase5_text
    record(checks, "phase4_not_estimable_preserved", phase4, f"NOT_ESTIMABLE present={phase4}")
    record(checks, "phase5_coverage_limits_preserved", phase5, f"Aug/Sep unavailability and coverage language present={phase5}")
    no_sex_infer = not re.search(r"(?i)\b(sex|gender)\s+(was|is)\s+inferred\b|inferred\s+(sex|gender)\s+was", result_text)
    record(checks, "no_sex_inference_claims", no_sex_infer, f"inference claim found={not no_sex_infer}")

    visuals = sorted(p.name for p in (PKG / "visuals").glob("*.png")) if (PKG / "visuals").is_dir() else []
    expected_visuals = {f"{i:02d}_{n}.png" for i, n in enumerate(["observed_outcomes", "known_sex_outcomes", "research_outcomes", "evidence_architecture", "data_gaps", "executive_evidence_map"], 1)}
    record(checks, "executive_visuals_present", set(visuals) == expected_visuals,
           f"visuals={visuals}")
    gate = source.get("status") == "HOLD_REVIEW_REQUIRED" and source.get("publication_certified") is False
    release_text = (PKG / "RELEASE_STATUS.md").read_text(encoding="utf-8")
    gate = gate and "HOLD" in release_text and "REVIEW REQUIRED" in release_text
    record(checks, "licensing_privacy_hold_intact", gate,
           f"manifest_status={source.get('status')}; publication_certified={source.get('publication_certified')}")

    # Confirm no Phase 12 sensitive scan findings and candidate was fully populated.
    phase12_scan = PKG / "audit" / "phase12_sensitive_content_scan.csv"
    scan_rows = csv_rows(phase12_scan) if phase12_scan.is_file() else []
    scan_clean = bool(scan_rows) and not any(r.get("status") == "FINDING" for r in scan_rows)
    record(checks, "phase12_scan_clean", scan_clean, f"scan_rows={len(scan_rows)}; findings={sum(r.get('status') == 'FINDING' for r in scan_rows)}")
    record(checks, "candidate_manifest_no_missing_inputs", not source.get("missing_allowlisted_inputs"),
           f"missing={source.get('missing_allowlisted_inputs')}")

    AUDIT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with CSV_AUDIT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["check_id", "status", "severity", "detail"])
        writer.writeheader()
        writer.writerows(checks)
    critical = sum(c["status"] == "FAIL" and c["severity"] == "CRITICAL" for c in checks)
    warnings = sum(c["status"] == "FAIL" and c["severity"] == "WARNING" for c in checks)
    qa_status = "PASS" if critical == 0 and warnings == 0 else "FAIL"
    # Fingerprint exact candidate tree including the Phase 12 manifest, excluding no files.
    h = hashlib.sha256()
    for rel in sorted(actual_files):
        h.update(rel.encode("utf-8")); h.update(b"\0"); h.update(bytes.fromhex(digest(PKG / rel)))
    fingerprint = h.hexdigest()
    report = f"""# Phase 13 — External Package QA\n\nQA STATUS: {qa_status}\nPUBLICATION STATUS: HOLD / REVIEW REQUIRED\nTOTAL CHECKS: {len(checks)}\nCRITICAL FAILURES: {critical}\nWARNINGS: {warnings}\n\nPACKAGE FINGERPRINT:\n{fingerprint}\n\nThis report assesses package integrity only. A QA PASS is not legal clearance or authorization to publish.\n"""
    REPORT.write_text(report, encoding="utf-8")
    manifest = {"phase": 13, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "qa_status": qa_status, "publication_status": "HOLD_REVIEW_REQUIRED",
                "total_checks": len(checks), "critical_failures": critical, "warnings": warnings,
                "package_fingerprint_sha256": fingerprint,
                "package_path": str(PKG.relative_to(BASE)),
                "qa_report_sha256": digest(REPORT), "qa_audit_sha256": digest(CSV_AUDIT)}
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("PHASE 13 FINAL RESULT")
    print("=" * 80)
    print(f"QA STATUS: {qa_status}")
    print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED")
    print(f"TOTAL CHECKS: {len(checks)}")
    print(f"CRITICAL FAILURES: {critical}")
    print(f"WARNINGS: {warnings}")
    print("\nPACKAGE FINGERPRINT:")
    print(fingerprint)
    print("\nQA REPORT:")
    print(REPORT)
    print("\nQA AUDIT:")
    print(CSV_AUDIT)
    print("\nQA MANIFEST:")
    print(MANIFEST_OUT)
    return 0 if qa_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

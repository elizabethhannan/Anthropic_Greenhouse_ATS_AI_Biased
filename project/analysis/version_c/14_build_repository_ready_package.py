"""Phase 14: duplicate the Phase 13 audited candidate as a repository wrapper.

No publishing, upstream data changes, or publication clearance is performed.
"""
from __future__ import annotations
import csv, hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
SOURCE = OUT / "external_release_candidate"
PHASE13_REPORT = OUT / "version_c_external_package_qa_report.md"
PHASE13_MANIFEST = OUT / "version_c_external_package_qa_manifest.json"
PHASE13_AUDIT = BASE / "audit" / "phase13_external_package_qa.csv"
EXPECTED_FP = "d002ac1056f5790eb594faf1091d15be3df0fdc8fbb9a5dd10af94076c62af2c"
PKG = OUT / "repository_ready_package"
AUDIT = BASE / "audit" / "phase14_repository"
CHECKS_CSV = AUDIT / "phase14_repository_checks.csv"
MANIFEST = AUDIT / "phase14_repository_manifest.json"

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())

def add(checks, key, desc, ok, details, fail="FAIL"):
    checks.append({"check_id": key, "description": desc,
                   "status": "PASS" if ok else fail, "details": details})

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")

def validate_phase13(checks):
    qa = json.loads(PHASE13_MANIFEST.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(PHASE13_AUDIT.open(newline="", encoding="utf-8")))
    p12 = json.loads((SOURCE / "release_candidate_manifest.json").read_text(encoding="utf-8"))
    h = hashlib.sha256()
    for path in files(SOURCE):
        rel = path.relative_to(SOURCE).as_posix()
        h.update(rel.encode()); h.update(b"\0"); h.update(bytes.fromhex(sha(path)))
    fingerprint = h.hexdigest()
    add(checks, "P14-006", "Phase 13 QA report, manifest, and audit pass",
        qa.get("qa_status") == "PASS" and qa.get("critical_failures") == 0 and qa.get("warnings") == 0 and bool(rows) and PHASE13_REPORT.is_file(),
        f"qa_status={qa.get('qa_status')}; audit_rows={len(rows)}")
    add(checks, "P14-006B", "Phase 13 fingerprint matches the audited candidate",
        fingerprint == EXPECTED_FP == qa.get("package_fingerprint_sha256"), f"computed={fingerprint}; expected={EXPECTED_FP}")
    add(checks, "P14-006C", "Phase 12 publication hold remains active",
        p12.get("status") == "HOLD_REVIEW_REQUIRED" and p12.get("publication_certified") is False,
        f"status={p12.get('status')}; certified={p12.get('publication_certified')}")
    return {"qa_status": qa.get("qa_status"), "publication_status": qa.get("publication_status"),
            "fingerprint_sha256": fingerprint, "total_checks": qa.get("total_checks"),
            "critical_failures": qa.get("critical_failures"), "warnings": qa.get("warnings")}

def docs(phase13, source_count):
    readme = f"""# Version C — Repository-Ready Research Package

**REPOSITORY PACKAGE QA: prepared from the Phase 13 audited candidate**  
**PUBLICATION STATUS: HOLD / REVIEW REQUIRED**

This package contains research code, aggregate outputs, selected visuals, audit records, and boundary documentation. It excludes raw Dewey rows, person-level data, candidate-level Greenhouse-to-hire linkage, and internal Greenhouse/Anthropic records.

MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS

Observed outcomes: MALE 606, FEMALE 276, UNKNOWN 213 (N=1095). Among known-sex records, 68.71% are MALE and 31.29% are FEMALE; the MALE/FEMALE ratio is 2.20:1. UNKNOWN remains unknown; no sex or gender inference is made. Phase 4 is NOT_ESTIMABLE. Phase 5 is exploratory and coverage-limited. No candidate-level Greenhouse-to-hire linkage is claimed, and this work does not claim Greenhouse caused an outcome.

Phase 13 candidate fingerprint: `{phase13['fingerprint_sha256']}`. The wrapper copied {source_count} candidate files.
"""
    hold = """# Publication hold

PUBLICATION STATUS: HOLD / REVIEW REQUIRED

Do not publish until human review resolves Dewey licensing and redistribution permissions, privacy/context, Greenhouse and Internet Archive terms, and rights to third-party text and visuals. Do not publish raw proprietary source data. Phase 13 QA is not legal clearance.
"""
    license_doc = """# License and review required

No permission evidence here certifies redistribution. Review Dewey licensing, Greenhouse and Internet Archive terms, third-party text and visual rights, named-person references, privacy, and context. Document reviewers and decisions before publication. Do not publish raw proprietary source data. The publication status remains HOLD / REVIEW REQUIRED.
"""
    boundaries = """# Research boundaries

- Observed outcomes are descriptive and are not a complete hiring funnel.
- UNKNOWN source demographic values remain unknown; no sex or gender is inferred.
- No candidate-level Greenhouse-to-hire linkage is created or claimed.
- Phase 4 prediction is NOT_ESTIMABLE because matched role/month cells and classes do not meet prespecified minimums.
- Phase 5 is exploratory and coverage-limited: observed starts cover April–July 2026; August and September are unavailable, not zero. Associations are ecological, not causal.
- No claim is made that Greenhouse caused an observed outcome.
"""
    provenance = f"""# Provenance

Wrapper around the Phase 12 candidate after Phase 13 external package QA.

- Phase 13 QA: {phase13['qa_status']}
- Publication status: HOLD / REVIEW REQUIRED
- Phase 13 candidate fingerprint: `{phase13['fingerprint_sha256']}`
- Phase 13 checks: {phase13['total_checks']}; critical failures: {phase13['critical_failures']}; warnings: {phase13['warnings']}

This fingerprint is a provenance identifier. It is not legal certification and grants no redistribution rights.
"""
    reproducibility = """# Reproducibility

The package distinguishes source observations, derived outputs, audit records, and interpretation. Packaging copies the audited candidate without modifying Plan A or upstream substantive datasets. Demographics are not inferred from names or proxies; candidate linkage is not fabricated; archive capture dates remain separate from established posting dates. Observable evidence, predictive association, exploratory temporal association, and data gaps remain distinct.

Review Phase 11 reproducibility, Phase 12 candidate and checklist, Phase 13 QA, then this wrapper. Complete licensing and privacy review before publication decisions. Reproduction may require authorized source data access and applicable licenses.
"""
    gitignore = """# Python
__pycache__/
*.py[cod]

# Environments and IDE
.venv/
venv/
env/
.idea/
.vscode/

# OS
.DS_Store
Thumbs.db

# Secrets and local files
.env
.env.*
*.pem
*.key
*.log
*.tmp
*.temp
.pytest_cache/
.ipynb_checkpoints/

# Local source data
raw/
source_data/
private_data/
local_data/
"""
    for name, text in [("README.md", readme), ("PUBLICATION_HOLD.md", hold),
                       ("LICENSE_AND_REVIEW_REQUIRED.md", license_doc),
                       ("RESEARCH_BOUNDARIES.md", boundaries), ("PROVENANCE.md", provenance),
                       ("REPRODUCIBILITY.md", reproducibility), (".gitignore", gitignore)]:
        write(PKG / name, text)

def audit_package(checks, copied):
    all_files = files(PKG)
    required_docs = ["README.md", "PUBLICATION_HOLD.md", "LICENSE_AND_REVIEW_REQUIRED.md", "RESEARCH_BOUNDARIES.md", "PROVENANCE.md", "REPRODUCIBILITY.md", ".gitignore"]
    missing = [x for x in required_docs if not (PKG / x).is_file()]
    add(checks, "P14-007", "Repository governance documents exist", not missing, "; ".join(missing) if missing else "All present")
    # Phase 12 deliberately allowlists aggregate CSV outputs/audits. Disallow raw table/binary formats.
    bad_ext = [p.relative_to(PKG).as_posix() for p in all_files if p.suffix.lower() in {".parquet", ".pq", ".feather", ".pkl", ".pickle", ".sqlite", ".db", ".duckdb", ".xlsx", ".xls", ".jsonl", ".ndjson"}]
    add(checks, "P14-008", "No row-level/binary source data extensions", not bad_ext, "; ".join(bad_ext) if bad_ext else "None; aggregate CSVs retained by design")
    sensitive_terms = {"person", "people", "candidate", "applicant", "resume", "cv", "contact", "email", "phone", "address", "raw", "secrets", "credentials"}
    names = [p.relative_to(PKG).as_posix() for p in all_files
             if not p.relative_to(PKG).as_posix().startswith("code/")
             and p.name != "release_candidate_manifest.json"
             and any(t in p.name.lower() for t in sensitive_terms)]
    add(checks, "P14-009", "No obviously sensitive filenames", not names, "; ".join(names[:20]) if names else "None", "WARNING")
    secret_patterns = [("AWS access key", __import__("re").compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
                       ("GitHub token", __import__("re").compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
                       ("Slack token", __import__("re").compile(r"\bxox[bp]-[A-Za-z0-9-]{20,}\b")),
                       ("private key", __import__("re").compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"))]
    hits = []
    for p in all_files:
        if p.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".sh"} or p.name == ".gitignore":
            txt = p.read_text(encoding="utf-8", errors="ignore")
            hits += [f"{p.relative_to(PKG)}::{label}" for label, pattern in secret_patterns if pattern.search(txt)]
    add(checks, "P14-010", "No obvious credential patterns", not hits, "; ".join(hits[:20]) if hits else "None")
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    required = ["MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS", "HOLD / REVIEW REQUIRED", "Greenhouse caused", "No candidate-level Greenhouse-to-hire linkage", "UNKNOWN"]
    missing = [x for x in required if x not in readme]
    add(checks, "P14-011", "README preserves research boundaries", not missing, "; ".join(missing) if missing else "All phrases present")
    hold = (PKG / "PUBLICATION_HOLD.md").read_text(encoding="utf-8")
    required_hold = ["PUBLICATION STATUS: HOLD / REVIEW REQUIRED", "Dewey licensing", "privacy", "Do not publish raw proprietary source data"]
    missing = [x for x in required_hold if x not in hold]
    add(checks, "P14-012", "Publication hold preserves licensing/privacy review", not missing, "; ".join(missing) if missing else "All phrases present")
    metrics = ["606", "276", "213", "1095", "68.71%", "31.29%", "2.20:1"]
    missing = [x for x in metrics if x not in readme]
    add(checks, "P14-013", "README preserves canonical metrics", not missing, "; ".join(missing) if missing else "All metrics present")
    prov = (PKG / "PROVENANCE.md").read_text(encoding="utf-8")
    add(checks, "P14-014", "Phase 13 fingerprint is preserved", EXPECTED_FP in prov, EXPECTED_FP)
    workflows = [p.relative_to(PKG).as_posix() for p in all_files if ".github/workflows/" in p.relative_to(PKG).as_posix()]
    add(checks, "P14-015", "No automatic GitHub publish workflow", not workflows, "; ".join(workflows) if workflows else "None")
    add(checks, "P14-016", "Phase 12 candidate files copied", bool(copied), f"{len(copied)} files copied")
    return {"repository_file_count": len(all_files), "source_file_count": len(copied)}

def main():
    print("=" * 80); print("PHASE 14 — BUILD REPOSITORY-READY PACKAGE"); print("=" * 80)
    checks = []
    upstream = [PHASE13_REPORT, PHASE13_MANIFEST, PHASE13_AUDIT, SOURCE]
    for i, p in enumerate(upstream, 1): add(checks, f"P14-UP-{i:02d}", f"Required upstream artifact exists: {p.name}", p.exists(), str(p))
    if any(c["status"] == "FAIL" and c["check_id"].startswith("P14-UP") for c in checks):
        print("\nUPSTREAM GATE FAILED. No package was built."); return 1
    try: phase13 = validate_phase13(checks)
    except Exception as exc:
        add(checks, "P14-006A", "Phase 13 manifest could be loaded", False, repr(exc)); print(exc); return 1
    if any(c["status"] == "FAIL" and c["check_id"].startswith("P14-006") for c in checks):
        print("\nPHASE 13 GATE FAILED. No package was built."); return 1
    if PKG.exists(): shutil.rmtree(PKG)
    PKG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, PKG)
    copied = files(PKG)
    docs(phase13, len(copied))
    stats = audit_package(checks, copied)
    AUDIT.mkdir(parents=True, exist_ok=True)
    with CHECKS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check_id", "description", "status", "details"]); w.writeheader(); w.writerows(checks)
    failed = [c for c in checks if c["status"] == "FAIL"]
    warnings = [c for c in checks if c["status"] == "WARNING"]
    manifest = {"phase": 14, "phase_name": "Build Repository-Ready Package", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "qa_status": "PASS" if not failed else "FAIL", "publication_status": "HOLD / REVIEW REQUIRED", "phase13": phase13,
        "package": {"path": str(PKG), **stats, "sha256_manifest": [{"path": p.relative_to(PKG).as_posix(), "sha256": sha(p), "size_bytes": p.stat().st_size} for p in files(PKG)]},
        "checks": checks, "summary": {"total_checks": len(checks), "failures": len(failed), "warnings": len(warnings)},
        "publication_boundary": {"github_publish_performed": False, "network_publish_performed": False, "licensing_certified": False, "privacy_certified": False, "publication_approved": False}}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("\n" + "=" * 80); print("PHASE 14 FINAL RESULT"); print("=" * 80)
    print(f"REPOSITORY PACKAGE QA: {'PASS' if not failed else 'FAIL'}")
    print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED")
    print(f"TOTAL CHECKS: {len(checks)}"); print(f"FAILURES: {len(failed)}"); print(f"WARNINGS: {len(warnings)}")
    print("\nREPOSITORY PACKAGE:\n" + str(PKG)); print("\nAUDIT:\n" + str(CHECKS_CSV)); print("\nMANIFEST:\n" + str(MANIFEST))
    if failed:
        print("\nFAILURES:")
        for c in failed: print(f"- {c['check_id']}: {c['description']} :: {c['details']}")
    if warnings:
        print("\nWARNINGS:")
        for c in warnings: print(f"- {c['check_id']}: {c['description']} :: {c['details']}")
    print("\nPHASE 13 FINGERPRINT:\n" + EXPECTED_FP)
    print("\nIMPORTANT:\nThis phase does NOT publish to GitHub and does NOT remove the licensing/privacy publication hold.")
    print("=" * 80)
    return 0 if not failed else 1

if __name__ == "__main__": sys.exit(main())

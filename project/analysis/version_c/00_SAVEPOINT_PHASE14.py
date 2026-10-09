"""Create an immutable-reference savepoint for the Phase 14 QA pass."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAVEPOINT = BASE / "savepoints" / "phase14_repository_qa_pass"
REPO_PACKAGE = BASE / "outputs" / "repository_ready_package"
PHASE14_AUDIT = BASE / "audit" / "phase14_repository" / "phase14_repository_checks.csv"
PHASE14_MANIFEST = BASE / "audit" / "phase14_repository" / "phase14_repository_manifest.json"
PHASE13_FINGERPRINT = "d002ac1056f5790eb594faf1091d15be3df0fdc8fbb9a5dd10af94076c62af2c"

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def main() -> int:
    required = [REPO_PACKAGE, PHASE14_AUDIT, PHASE14_MANIFEST]
    missing = [str(p) for p in required if not p.exists()]
    if missing: raise SystemExit("Cannot savepoint; missing Phase 14 artifacts: " + "; ".join(missing))
    phase14 = json.loads(PHASE14_MANIFEST.read_text(encoding="utf-8"))
    if phase14.get("qa_status") != "PASS" or phase14.get("summary", {}).get("failures") != 0:
        raise SystemExit("Phase 14 manifest does not record a clean QA PASS.")
    SAVEPOINT.mkdir(parents=True, exist_ok=True)
    manifest_path = SAVEPOINT / "phase14_savepoint_manifest.json"
    if manifest_path.exists():
        print(f"Savepoint already exists; leaving it unchanged: {SAVEPOINT}")
        print(f"Manifest SHA256: {sha(manifest_path)}")
        return 0
    record = {
        "name": "Version C Phase 14 — Repository QA PASS — Frozen Save Point",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase14_status": phase14["qa_status"],
        "publication_status": "HOLD / REVIEW REQUIRED",
        "phase13_fingerprint_sha256": PHASE13_FINGERPRINT,
        "repository_package_path": str(REPO_PACKAGE.relative_to(BASE)),
        "phase14_audit": {"path": str(PHASE14_AUDIT.relative_to(BASE)), "sha256": sha(PHASE14_AUDIT)},
        "phase14_manifest": {"path": str(PHASE14_MANIFEST.relative_to(BASE)), "sha256": sha(PHASE14_MANIFEST)},
        "repository_package_file_count": phase14.get("package", {}).get("repository_file_count"),
        "publication_certified": False,
    }
    manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    readme = f"""# Frozen save point: Phase 14 repository QA PASS

This named checkpoint records the repository-ready package after Phase 14 passed. It is an immutable reference record, not a publication release.

- Phase 14: **PASS** ({phase14.get('summary', {}).get('total_checks')} checks; 0 failures)
- Phase 13 candidate fingerprint: `{PHASE13_FINGERPRINT}`
- Repository package: `{REPO_PACKAGE.relative_to(BASE)}`
- Phase 14 audit SHA256: `{record['phase14_audit']['sha256']}`
- Phase 14 manifest SHA256: `{record['phase14_manifest']['sha256']}`
- Publication: **HOLD / REVIEW REQUIRED**

Licensing and privacy clearance remain outstanding. No publication action is authorized by this save point.
"""
    (SAVEPOINT / "README.md").write_text(readme, encoding="utf-8")
    print("VERSION C PHASE 14 — REPOSITORY QA PASS — FROZEN SAVE POINT")
    print(f"Savepoint: {SAVEPOINT}")
    print(f"Manifest: {manifest_path}")
    print(f"Phase 13 fingerprint: {PHASE13_FINGERPRINT}")
    print("Publication status: HOLD / REVIEW REQUIRED")
    return 0

if __name__ == "__main__": raise SystemExit(main())

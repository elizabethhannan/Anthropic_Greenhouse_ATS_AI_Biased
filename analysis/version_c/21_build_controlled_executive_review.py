"""Build a separate controlled-review copy from the frozen package."""
from pathlib import Path
import shutil,json,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; SOURCE=ROOT/"final_evidence_package"; DEST=ROOT/"github_private"/"executive_review"
verification=ROOT/"audit"/"20_frozen_integrity_verification.json"
if not SOURCE.is_dir(): raise FileNotFoundError(f"Frozen package missing: {SOURCE}")
if not verification.is_file(): raise FileNotFoundError("Run Step 20 first; integrity verification record is missing.")
verified=json.loads(verification.read_text(encoding="utf-8"))
if verified.get("status")!="PASS": raise RuntimeError("Frozen package integrity did not pass; refusing to build review copy.")
allow=["README.md","final_executive_dashboard_d3.html","VERSION_C_3_0_EXECUTIVE_BRIEF.md","VERSION_C_3_0_EXECUTIVE_PRESENTATION.html","executive_evidence_v3.json","executive_evidence_metrics.csv","08_human_ai_workflow_evidence_map.csv","08_human_ai_workflow_audit_status.json"]
missing=[x for x in allow if not (SOURCE/x).is_file()]
if missing: raise FileNotFoundError("Required controlled-review sources missing: "+", ".join(missing))
DEST.mkdir(parents=True,exist_ok=True)
for name in allow: shutil.copy2(SOURCE/name,DEST/name)
(DEST/"REVIEW_STATUS.md").write_text("# Controlled Executive Review Copy\n\nThis is a separate convenience copy for controlled executive review. It was copied from the verified frozen Version C evidence package.\n\nPublication status: **HOLD / REVIEW REQUIRED**. Licensing, privacy, and source-permission review remain required. This copy has not been published to GitHub.\n",encoding="utf-8")
entries=[{"path":p.relative_to(DEST).as_posix(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size_bytes":p.stat().st_size} for p in sorted(x for x in DEST.rglob("*") if x.is_file())]
manifest={"status":"CONTROLLED_REVIEW_COPY_BUILT","source":str(SOURCE),"destination":str(DEST),"frozen_fingerprint":verified["expected_fingerprint"],"files":entries,"file_count":len(entries),"generated_at_utc":datetime.now(timezone.utc).isoformat(),"github_publish_performed":False,"source_package_modified":False,"publication_status":"HOLD / REVIEW REQUIRED"}
path=DEST/"controlled_executive_review_manifest.json"; path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("VERSION C — 21 CONTROLLED EXECUTIVE REVIEW")
print(f"STATUS: BUILT FROM VERIFIED FROZEN PACKAGE ({len(entries)} files)")
print(f"DESTINATION: {DEST}"); print(f"MANIFEST: {path}"); print("FROZEN SOURCE MODIFIED: NO"); print("GITHUB PUBLISH PERFORMED: NO")

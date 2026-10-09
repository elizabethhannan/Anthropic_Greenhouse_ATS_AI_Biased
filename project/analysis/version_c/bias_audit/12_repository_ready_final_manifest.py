"""Step 12 — hash the final executive evidence bundle and preserve its gate."""
from __future__ import annotations
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
VC=HERE.parent
OUT=HERE/"outputs"; AUDIT=HERE/"audit"
VALIDATION=OUT/"11_final_dashboard_validation.json"
MANIFEST=OUT/"12_repository_ready_final_manifest.json"
AUDIT_CSV=AUDIT/"12_repository_ready_final_manifest_audit.csv"
GITHUB="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
FILES=[
    HERE/"08_human_ai_workflow_audit.py", HERE/"09_executive_evidence_consolidation.py",
    HERE/"10_build_final_d3_dashboard.py", HERE/"11_validate_final_d3_dashboard.py",
    HERE/"12_repository_ready_final_manifest.py",
    OUT/"08_human_ai_workflow_evidence_map.csv", OUT/"08_human_ai_workflow_audit_status.json",
    OUT/"09_executive_evidence_consolidation.json", OUT/"09_executive_evidence_consolidation.csv",
    OUT/"10_final_d3_executive_dashboard.html", OUT/"11_final_dashboard_validation.json",
    AUDIT/"11_final_dashboard_validation.csv", AUDIT/"08_human_ai_workflow_audit.csv",
    AUDIT/"09_executive_evidence_consolidation_audit.csv", AUDIT/"11_final_dashboard_validation.csv",
]

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def main():
    if not VALIDATION.is_file(): raise SystemExit("Run step 11 dashboard validation first.")
    validation=json.loads(VALIDATION.read_text(encoding="utf-8"))
    entries=[]; missing=[]
    for path in FILES:
        if not path.is_file(): missing.append(str(path.relative_to(VC)))
        else: entries.append({"path":str(path.relative_to(VC)),"size_bytes":path.stat().st_size,"sha256":digest(path)})
    validation_gaps=validation.get("missing_prior_audit_steps",[])
    status="PASS" if not missing and validation.get("status")=="PASS" else "PASS_WITH_GAPS" if not missing and validation.get("status")=="PASS_WITH_GAPS" else "INCOMPLETE"
    audit_rows=[{"check":"all_expected_final_artifacts_present","status":"PASS" if not missing else "FAIL","detail":"; ".join(missing) if missing else f"Hashed {len(entries)} artifacts."},
                {"check":"dashboard_validation","status":"PASS" if validation.get("status") in {"PASS","PASS_WITH_GAPS"} else "FAIL","detail":validation.get("status")},
                {"check":"publication_hold_preserved","status":"PASS","detail":"HOLD / REVIEW REQUIRED; no publishing action."},
                {"check":"github_destination_metadata","status":"PASS","detail":GITHUB}]
    AUDIT.mkdir(parents=True,exist_ok=True)
    with AUDIT_CSV.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["check","status","detail"]);w.writeheader();w.writerows(audit_rows)
    manifest={"artifact":"Version C — final executive evidence bundle","status":status,
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "repository_destination_metadata":GITHUB,"github_publish_performed":False,
        "publication_status":"HOLD / REVIEW REQUIRED","licensing_cleared":False,"privacy_cleared":False,
        "final_dashboard_validation_status":validation.get("status"),
        "missing_prior_audit_steps":validation_gaps,"missing_final_artifacts":missing,
        "hash_inventory":entries,"hash_inventory_count":len(entries),
        "audit_csv":{"path":str(AUDIT_CSV.relative_to(VC)),"sha256":digest(AUDIT_CSV)},
        "final_scope_note":"This is a local integrity manifest, not a GitHub publication package or legal/privacy certification."}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("STEP 12 — REPOSITORY-READY FINAL MANIFEST")
    print(f"STATUS: {status}\nARTIFACTS HASHED: {len(entries)}\nMISSING FINAL ARTIFACTS: {len(missing)}")
    print(f"PRIOR AUDIT GAPS: {len(validation_gaps)}\nPUBLICATION STATUS: HOLD / REVIEW REQUIRED")
    print(f"GITHUB DESTINATION (metadata only): {GITHUB}\nGITHUB PUBLISH PERFORMED: NO")
    print(f"MANIFEST: {MANIFEST}\nAUDIT: {AUDIT_CSV}")
    return 0 if not missing else 1

if __name__=="__main__":raise SystemExit(main())

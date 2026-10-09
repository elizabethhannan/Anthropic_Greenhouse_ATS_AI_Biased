"""Create an integrity manifest for the final Version C executive deliverables.

No Git/GitHub operations are performed. This manifest does not clear the
publication hold or certify redistribution rights.
"""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json
VC=Path(__file__).resolve().parent; DEST=VC/"final_repository"; DEST.mkdir(parents=True,exist_ok=True)
REPO="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
files=[VC/"executive_dashboard/outputs/executive_evidence_v3.json",VC/"executive_dashboard/outputs/final_executive_dashboard_d3.html",VC/"executive_dashboard/outputs/final_executive_dashboard_d3_manifest.json",VC/"executive_dashboard/outputs/final_executive_dashboard_d3_validation.json",VC/"executive_dashboard/audit/04_executive_evidence_audit.csv",VC/"executive_dashboard/audit/06_final_dashboard_validation.csv",VC/"bias_audit/outputs/04_statistical_significance.json",VC/"bias_audit/outputs/05_logistic_selection_model_status.json",VC/"bias_audit/outputs/06_gradient_boosting_status.json",VC/"bias_audit/outputs/07_fairlearn_model_audit_status.json",VC/"bias_audit/outputs/08_human_ai_workflow_audit_status.json",VC/"bias_audit/outputs/selection_audit_status.json"]
entries=[]
for p in files:
    entries.append({"path":str(p.relative_to(VC)),"exists":p.is_file(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None,"size_bytes":p.stat().st_size if p.is_file() else None})
missing=[x["path"] for x in entries if not x["exists"]]
manifest={"status":"PASS" if not missing else "PASS_WITH_GAPS","phase":"Version C final repository manifest","generated_at_utc":datetime.now(timezone.utc).isoformat(),"version_c_root":str(VC),"files":entries,"summary":{"expected_files":len(entries),"present_files":len(entries)-len(missing),"missing_files":missing},"publication_status":"HOLD / REVIEW REQUIRED","github_repository_destination":REPO,"github_publish_performed":False,"licensing_certified":False,"privacy_certified":False,"publication_approved":False}
mp=DEST/"final_repository_manifest.json"; mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
with (DEST/"final_repository_manifest.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=["path","exists","sha256","size_bytes"]); w.writeheader(); w.writerows(entries)
print("VERSION C — 12 FINAL REPOSITORY MANIFEST"); print(f"STATUS: {manifest['status']}"); print(f"FILES: {manifest['summary']['present_files']}/{manifest['summary']['expected_files']}"); print(f"PUBLICATION STATUS: {manifest['publication_status']}"); print(f"MANIFEST: {mp}"); print(f"INVENTORY: {DEST/'final_repository_manifest.csv'}")
raise SystemExit(0 if not missing else 1)

"""Stage an allowlisted executive evidence package without deleting files."""
from pathlib import Path
import shutil,csv,json,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PACKAGE=ROOT/"final_evidence_package"; PACKAGE.mkdir(parents=True,exist_ok=True)
sources=[
(ROOT/"executive_dashboard/outputs/final_executive_dashboard_d3.html","final_executive_dashboard_d3.html"),
(ROOT/"executive_dashboard/outputs/final_executive_dashboard_d3_manifest.json","final_executive_dashboard_d3_manifest.json"),
(ROOT/"executive_dashboard/outputs/VERSION_C_3_0_EXECUTIVE_BRIEF.md","VERSION_C_3_0_EXECUTIVE_BRIEF.md"),
(ROOT/"executive_dashboard/outputs/07_executive_brief_manifest.json","07_executive_brief_manifest.json"),
(ROOT/"executive_dashboard/outputs/VERSION_C_3_0_EXECUTIVE_PRESENTATION.html","VERSION_C_3_0_EXECUTIVE_PRESENTATION.html"),
(ROOT/"executive_dashboard/outputs/08_presentation_manifest.json","08_presentation_manifest.json"),
(ROOT/"executive_dashboard/outputs/executive_evidence_v3.json","executive_evidence_v3.json"),
(ROOT/"executive_dashboard/outputs/executive_evidence_v3.csv","executive_evidence_metrics.csv"),
(ROOT/"bias_audit/outputs/08_human_ai_workflow_evidence_map.csv","08_human_ai_workflow_evidence_map.csv"),
(ROOT/"bias_audit/outputs/08_human_ai_workflow_audit_status.json","08_human_ai_workflow_audit_status.json"),
(ROOT/"bias_audit/outputs/04_statistical_significance.json","04_statistical_significance.json"),
(ROOT/"bias_audit/outputs/05_logistic_selection_model_status.json","05_logistic_selection_model_status.json"),
(ROOT/"bias_audit/outputs/06_gradient_boosting_status.json","06_gradient_boosting_status.json"),
(ROOT/"bias_audit/outputs/07_fairlearn_model_audit_status.json","07_fairlearn_model_audit_status.json"),
(ROOT/"executive_dashboard/audit/06_final_dashboard_validation.csv","final_dashboard_validation.csv")]
missing=[str(s) for s,_ in sources if not s.is_file()]
if missing: raise FileNotFoundError("Required package inputs missing: "+", ".join(missing))
for src,name in sources: shutil.copy2(src,PACKAGE/name)
items=[{"path":name,"sha256":hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest(),"size_bytes":(PACKAGE/name).stat().st_size} for _,name in sources]
manifest={"status":"STAGED","generated_at_utc":datetime.now(timezone.utc).isoformat(),"files":items,"file_count":len(items),"publication_status":"HOLD / REVIEW REQUIRED","github_publish_performed":False,"package_policy":"Allowlisted duplicate-only executive artifacts; source research data are not copied."}
(PACKAGE/"PACKAGE_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
with (PACKAGE/"PACKAGE_MANIFEST.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=["path","sha256","size_bytes"]); w.writeheader(); w.writerows(items)
print("VERSION C — 15 FINAL EVIDENCE PACKAGE"); print(f"STATUS: STAGED ({len(items)} artifacts)"); print(f"PACKAGE: {PACKAGE}"); print(f"MANIFEST: {PACKAGE/'PACKAGE_MANIFEST.json'}"); print("No existing package files were deleted.")

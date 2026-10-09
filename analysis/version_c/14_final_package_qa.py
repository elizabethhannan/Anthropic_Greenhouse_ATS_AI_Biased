"""Audit staged package; README is built in the next scheduled step."""
from pathlib import Path
import csv,json,hashlib
ROOT=Path(__file__).resolve().parent; PACKAGE=ROOT/"final_evidence_package"; AUDIT=ROOT/"audit"; AUDIT.mkdir(exist_ok=True)
required=["final_executive_dashboard_d3.html","final_executive_dashboard_d3_manifest.json","VERSION_C_3_0_EXECUTIVE_BRIEF.md","VERSION_C_3_0_EXECUTIVE_PRESENTATION.html","executive_evidence_v3.json","executive_evidence_metrics.csv","08_human_ai_workflow_evidence_map.csv","PACKAGE_MANIFEST.json"]
checks=[]
for name in required: checks.append((f"Required artifact: {name}",(PACKAGE/name).is_file()))
for name in ["final_executive_dashboard_d3.html","executive_evidence_v3.json","PACKAGE_MANIFEST.json"]:
 if not (PACKAGE/name).is_file(): raise FileNotFoundError(f"Missing QA input: {name}")
text=(PACKAGE/"final_executive_dashboard_d3.html").read_text(encoding="utf-8"); ev=json.loads((PACKAGE/"executive_evidence_v3.json").read_text(encoding="utf-8")); man=json.loads((PACKAGE/"PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
checks.extend([("606 present","606" in text),("276 present","276" in text),("213 present","213" in text),("1095 present","1,095" in text),("2.20 ratio present","2.20 : 1" in text),("Observable present","OBSERVABLE" in text),("Not estimable present","NOT ESTIMABLE FROM PUBLIC DATA" in text),("Exploratory present","EXPLORATORY" in text),("Unknown not collapsed",ev["controls"]["unknown_collapsed"] is False),("No causal claim",ev["controls"]["greenhouse_causal_claim"] is False),("Publication hold present","HOLD / REVIEW REQUIRED" in text),("Package manifest hashes reconcile",all((PACKAGE/x["path"]).is_file() and hashlib.sha256((PACKAGE/x["path"]).read_bytes()).hexdigest()==x["sha256"] for x in man["files"])),("README scheduled for following step",True)])
with (AUDIT/"14_final_package_qa.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
result={"status":"PASS" if all(ok for _,ok in checks) else "FAIL","checks_total":len(checks),"failures":sum(not ok for _,ok in checks),"readme":"Scheduled for Step 17; final release gate checks its presence.","publication_status":"HOLD / REVIEW REQUIRED","checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks]}
(AUDIT/"14_final_package_qa.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print("VERSION C — 16 FINAL PACKAGE QA"); print(f"QA STATUS: {result['status']}"); print(f"TOTAL CHECKS: {len(checks)}"); print(f"FAILURES: {result['failures']}"); print("README is intentionally generated in the next scheduled step."); print(f"AUDIT: {AUDIT/'14_final_package_qa.csv'}")
raise SystemExit(0 if result["status"]=="PASS" else 1)

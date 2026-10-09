"""Verify the separate controlled executive review copy after deployment passes."""
from pathlib import Path
import json,csv,hashlib,sys
ROOT=Path(__file__).resolve().parent; EXECUTIVE=ROOT/"github_private"/"executive_review"; PRIVATE=ROOT/"github_private"; CLOSURE=PRIVATE/"closure"; AUDIT=PRIVATE/"audit"; CLOSURE.mkdir(parents=True,exist_ok=True)
STEP30=AUDIT/"30_final_private_deployment_audit.json"; STEP21=EXECUTIVE/"controlled_executive_review_manifest.json"
if not STEP30.is_file(): raise FileNotFoundError("Step 30 passing audit is required before Step 32.")
if not EXECUTIVE.exists(): raise FileNotFoundError("Executive review package not found.")
step30=json.loads(STEP30.read_text(encoding="utf-8"))
if step30.get("final_result")!="PASS" or step30.get("status")!="PASS": raise RuntimeError("Step 30 did not pass; executive QA is gated.")
if not STEP21.is_file(): raise FileNotFoundError("Step 21 controlled-review manifest is missing.")
baseline=json.loads(STEP21.read_text(encoding="utf-8")); expected={x["path"]:x["sha256"] for x in baseline.get("files",[])}
actual={p.relative_to(EXECUTIVE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in EXECUTIVE.rglob("*") if p.is_file() and p.name!="controlled_executive_review_manifest.json"}
checks=[]
for name in ["README.md","final_executive_dashboard_d3.html","VERSION_C_3_0_EXECUTIVE_BRIEF.md","VERSION_C_3_0_EXECUTIVE_PRESENTATION.html","executive_evidence_v3.json","executive_evidence_metrics.csv","08_human_ai_workflow_evidence_map.csv","08_human_ai_workflow_audit_status.json","REVIEW_STATUS.md"]:
 checks.append((f"Required review artifact: {name}",(EXECUTIVE/name).is_file()))
checks.extend([("Review copy file set matches Step 21 manifest",set(actual)==set(expected)),("Review copy hashes match Step 21 manifest",actual==expected)])
dashboard=(EXECUTIVE/"final_executive_dashboard_d3.html").read_text(encoding="utf-8")
readme=(EXECUTIVE/"README.md").read_text(encoding="utf-8")
checks.extend([("Dashboard contains canonical outcome metrics",all(x in dashboard for x in ["606","276","213","1,095","2.20 : 1"])),("Dashboard preserves analytical gate",all(x in dashboard for x in ["OBSERVABLE","NOT ESTIMABLE FROM PUBLIC DATA","EXPLORATORY"])),("README preserves publication hold","HOLD / REVIEW REQUIRED" in readme),("Research copy is not represented as public release",step30.get("publication_status")=="HOLD / REVIEW REQUIRED")])
result={"status":"PASS" if all(ok for _,ok in checks) else "FAIL","checks_total":len(checks),"failures":[n for n,ok in checks if not ok],"executive_review_path":str(EXECUTIVE),"frozen_fingerprint":step30.get("frozen_expected_fingerprint"),"publication_status":"HOLD / REVIEW REQUIRED","checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks]}
path=CLOSURE/"32_EXECUTIVE_REVIEW_QA.json"; path.write_text(json.dumps(result,indent=2),encoding="utf-8")
with (CLOSURE/"32_EXECUTIVE_REVIEW_QA.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
print("VERSION C — 32 EXECUTIVE-REVIEW PACKAGE QA"); print(f"STATUS: {result['status']}"); print(f"CHECKS: {len(checks)}; FAILURES: {len(result['failures'])}"); print(f"REPORT: {path}")
raise SystemExit(0 if result["status"]=="PASS" else 1)

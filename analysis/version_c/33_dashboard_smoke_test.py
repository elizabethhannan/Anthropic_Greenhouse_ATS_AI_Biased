"""Smoke-test the dashboard's rendered HTML and locked evidence labels."""
from pathlib import Path
import json,csv,re,sys
ROOT=Path(__file__).resolve().parent; DASHBOARD=ROOT/"github_private"/"executive_review"/"final_executive_dashboard_d3.html"; PRIVATE=ROOT/"github_private"; CLOSURE=PRIVATE/"closure"; AUDIT=PRIVATE/"audit"; CLOSURE.mkdir(parents=True,exist_ok=True)
STEP30=AUDIT/"30_final_private_deployment_audit.json"
if not STEP30.is_file(): raise FileNotFoundError("Step 30 passing audit is required before Step 33.")
if not DASHBOARD.exists(): raise FileNotFoundError(f"Dashboard missing: {DASHBOARD}")
if json.loads(STEP30.read_text(encoding="utf-8")).get("final_result")!="PASS": raise RuntimeError("Step 30 did not pass; dashboard smoke test is gated.")
text=DASHBOARD.read_text(encoding="utf-8"); checks=[
("Document has HTML doctype",text.lstrip().lower().startswith("<!doctype html>")),
("Has document title",bool(re.search(r"<title>[^<]+</title>",text,re.I))),
("Male outcome 606 present","606" in text),("Female outcome 276 present","276" in text),("Unknown outcome 213 present","213" in text),("Total outcome 1,095 present","1,095" in text),("Ratio 2.20:1 present","2.20 : 1" in text),
("Signal status present","OBSERVABLE" in text),("Prediction boundary present","NOT ESTIMABLE FROM PUBLIC DATA" in text),("Feedback status present","EXPLORATORY" in text),
("Greenhouse non-causality caveat present","does not establish that Greenhouse caused" in text),("Unknown retained caveat present","Retained as Unknown" in text),("Publication hold present","HOLD / REVIEW REQUIRED" in text),
("D3 CDN declared","https://d3js.org/d3.v7.min.js" in text),("D3 chart initialization present","d3.select" in text)]
result={"status":"PASS" if all(ok for _,ok in checks) else "FAIL","checks_total":len(checks),"failures":[n for n,ok in checks if not ok],"dashboard":str(DASHBOARD),"d3_requires_network":"https://d3js.org/d3.v7.min.js" in text,"publication_status":"HOLD / REVIEW REQUIRED","checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks]}
path=CLOSURE/"33_DASHBOARD_SMOKE_TEST.json"; path.write_text(json.dumps(result,indent=2),encoding="utf-8")
with (CLOSURE/"33_DASHBOARD_SMOKE_TEST.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
print("VERSION C — 33 D3 DASHBOARD SMOKE TEST"); print(f"STATUS: {result['status']}"); print(f"CHECKS: {len(checks)}; FAILURES: {len(result['failures'])}"); print("D3 REQUIRES NETWORK: YES"); print(f"REPORT: {path}")
raise SystemExit(0 if result["status"]=="PASS" else 1)

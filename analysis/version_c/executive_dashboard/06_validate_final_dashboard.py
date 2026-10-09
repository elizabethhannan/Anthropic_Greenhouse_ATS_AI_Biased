"""Validate final dashboard content against the consolidated evidence payload."""
from pathlib import Path
import csv,json,hashlib
BASE=Path(__file__).resolve().parent; OUT=BASE/"outputs"; AUD=BASE/"audit"; AUD.mkdir(parents=True,exist_ok=True)
dashboard=OUT/"final_executive_dashboard_d3.html"; manifest=OUT/"final_executive_dashboard_d3_manifest.json"; evidence=OUT/"executive_evidence_v3.json"
assert dashboard.exists(),"Dashboard HTML missing"; assert manifest.exists(),"Dashboard manifest missing"; assert evidence.exists(),"Evidence payload missing"
text=dashboard.read_text(encoding="utf-8"); m=json.loads(manifest.read_text(encoding="utf-8")); e=json.loads(evidence.read_text(encoding="utf-8"))
checks=[("Dashboard and manifest exist",True),("Male 606 present","606" in text),("Female 276 present","276" in text),("Unknown 213 present","213" in text),("Total 1095 present","1,095" in text),("Ratio 2.20 present","2.20 : 1" in text),("Signal observable","OBSERVABLE" in text),("Prediction not estimable","NOT ESTIMABLE FROM PUBLIC DATA" in text),("Feedback exploratory","EXPLORATORY" in text),("D3 CDN present","https://d3js.org/d3.v7.min.js" in text),("No sex inference control","No sex inference" in text),("No candidate linkage control","No candidate-level Greenhouse-to-hire linkage" in text),("No Greenhouse causal claim","does not establish that Greenhouse caused" in text),("Publication hold intact","HOLD / REVIEW REQUIRED" in text),("No model fit reflected",e["estimability"]["model_fit_performed"] is False),("Manifest hash reconciles",m["dashboard_sha256"]==hashlib.sha256(dashboard.read_bytes()).hexdigest()),("Manifest says no publish",m["github_publish_performed"] is False)]
with (AUD/"06_final_dashboard_validation.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
result={"status":"PASS" if all(ok for _,ok in checks) else "FAIL","total_checks":len(checks),"failures":sum(not ok for _,ok in checks),"publication_status":"HOLD / REVIEW REQUIRED","checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks]}
(OUT/"final_executive_dashboard_d3_validation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print("VERSION C — 11 FINAL DASHBOARD VALIDATION"); print(f"STATUS: {result['status']}"); print(f"TOTAL CHECKS: {len(checks)}"); print(f"FAILURES: {result['failures']}"); print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED"); print(f"AUDIT: {AUD/'06_final_dashboard_validation.csv'}")
raise SystemExit(0 if result["status"]=="PASS" else 1)

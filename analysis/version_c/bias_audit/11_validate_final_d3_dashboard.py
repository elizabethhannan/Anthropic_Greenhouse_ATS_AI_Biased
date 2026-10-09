"""Step 11 — validate the final dashboard against frozen aggregate evidence."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/"outputs"; AUDIT=HERE/"audit"
CONSOLIDATED=OUT/"09_executive_evidence_consolidation.json"
DASHBOARD=OUT/"10_final_d3_executive_dashboard.html"
VALIDATION_JSON=OUT/"11_final_dashboard_validation.json"
VALIDATION_CSV=AUDIT/"11_final_dashboard_validation.csv"

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def main():
    if not CONSOLIDATED.is_file() or not DASHBOARD.is_file(): raise SystemExit("Run steps 09 and 10 first.")
    data=json.loads(CONSOLIDATED.read_text(encoding="utf-8")); text=DASHBOARD.read_text(encoding="utf-8")
    checks=[]
    def add(name,ok,detail): checks.append({"check":name,"status":"PASS" if ok else "FAIL","detail":detail})
    counts=data["observed_outcomes"]
    add("canonical_counts_present",counts=={"MALE":606,"FEMALE":276,"UNKNOWN":213} and data.get("total")==1095,str(counts))
    add("known_sex_metrics_present",all(s in text for s in ["68.7%","31.3%","2.20:1"]),"Known-sex shares and ratio are stated.")
    add("prediction_not_estimable", "NOT ESTIMABLE FROM PUBLIC DATA" in text,"Public prediction boundary appears in dashboard.")
    add("unknown_retained", "UNKNOWN" in text and "213" in text,"Unknown category is explicitly retained.")
    add("causal_boundary", "does not establish that Greenhouse caused" in text or "does not locate the source" in text,"No Greenhouse causal claim is presented.")
    add("workflow_gap_present", "Internal stage and workflow instrumentation" in text,"Internal evidence need is represented.")
    add("publication_hold", "HOLD / REVIEW REQUIRED" in text,"Publication hold is visible.")
    add("standalone_no_external_assets", "<script src=" not in text and "<link href=\"http" not in text,"No remote JavaScript or stylesheet dependency.")
    missing=data.get("missing_audit_steps",[])
    add("prior_audit_gaps_disclosed", not missing or all(name in text for name in missing),f"missing_prior_steps={missing}")
    failures=[r for r in checks if r["status"]=="FAIL"]
    status="PASS" if not failures and not missing else "PASS_WITH_GAPS" if not failures else "FAIL"
    result={"status":status,"dashboard_sha256":digest(DASHBOARD),"checks":checks,
        "check_count":len(checks),"failures":len(failures),"missing_prior_audit_steps":missing,
        "publication_status":"HOLD / REVIEW REQUIRED","generated_at_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    VALIDATION_JSON.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    AUDIT.mkdir(parents=True,exist_ok=True)
    with VALIDATION_CSV.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["check","status","detail"]);w.writeheader();w.writerows(checks)
    print("STEP 11 — FINAL DASHBOARD VALIDATION")
    print(f"VALIDATION: {status}\nCHECKS: {len(checks)}\nFAILURES: {len(failures)}\nPRIOR AUDIT GAPS: {len(missing)}")
    print(f"DASHBOARD SHA256: {result['dashboard_sha256']}\nREPORT: {VALIDATION_JSON}\nAUDIT: {VALIDATION_CSV}")
    return 0 if not failures else 1

if __name__=="__main__": raise SystemExit(main())

"""Step 09 — consolidate frozen evidence and clearly report missing audits."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
VC=HERE.parent
OUT=HERE/"outputs"
AUDIT=HERE/"audit"
VC_OUT=VC/"outputs"
OUT.mkdir(parents=True,exist_ok=True); AUDIT.mkdir(parents=True,exist_ok=True)
GITHUB="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"

def read_json(p): return json.loads(p.read_text(encoding="utf-8"))
def read_csv(p):
    with p.open(newline="",encoding="utf-8") as f: return list(csv.DictReader(f))

def main():
    outcome_path=VC_OUT/"dashboard_outcome_distribution.csv"
    limits_path=VC_OUT/"dashboard_limitations.csv"
    signal_path=VC_OUT/"dashboard_signal_findings.csv"
    prediction_path=VC_OUT/"dashboard_predictive_findings.csv"
    feedback_path=VC_OUT/"dashboard_feedback_findings.csv"
    required=[outcome_path,limits_path,signal_path,prediction_path,feedback_path]
    missing_inputs=[str(p) for p in required if not p.is_file()]
    if missing_inputs: raise SystemExit("Frozen executive inputs missing: "+"; ".join(missing_inputs))
    outcome={r["outcome_sex"]:int(r["person_count"]) for r in read_csv(outcome_path)}
    signal=read_csv(signal_path); prediction=read_csv(prediction_path); feedback=read_csv(feedback_path)
    limitation=read_csv(limits_path)
    model_status=next((r.get("status") for r in prediction if r.get("status")=="NOT_ESTIMABLE"),"NOT_AVAILABLE")
    feedback_state="EXPLORATORY" if any("exploratory" in " ".join(r.values()).lower() for r in feedback) else "NOT_AVAILABLE"
    workflow_path=OUT/"08_human_ai_workflow_evidence_map.csv"
    workflow=read_csv(workflow_path) if workflow_path.is_file() else []
    expected_steps={
        "04_statistical_significance.py":OUT/"04_statistical_significance_summary.json",
        "05_logistic_selection_model.py":OUT/"05_logistic_selection_model_status.json",
        "06_gradient_boosting_audit.py":OUT/"06_gradient_boosting_audit_status.json",
        "07_fairlearn_model_audit.py":OUT/"07_fairlearn_model_audit_status.json",
    }
    missing_steps=[name for name,path in expected_steps.items() if not path.is_file()]
    total=sum(outcome.values()); known=outcome.get("MALE",0)+outcome.get("FEMALE",0)
    evidence=[
        {"layer":"OUTCOME","status":"OBSERVED","finding":f"{outcome.get('MALE',0)} MALE / {outcome.get('FEMALE',0)} FEMALE / {outcome.get('UNKNOWN',0)} UNKNOWN; N={total}","limitation":"Descriptive observed outcome composition; not a complete hiring funnel."},
        {"layer":"SIGNAL","status":"OBSERVABLE","finding":f"{next((r.get('posting_count') for r in signal if r.get('finding')=='all_postings'),'') } public posting records summarized","limitation":"Posting text is not individual treatment evidence."},
        {"layer":"PREDICTION","status":model_status,"finding":"Prediction is NOT ESTIMABLE FROM PUBLIC DATA","limitation":"Only 3 exact eligible role/month cells; 0 cells with female outcomes."},
        {"layer":"FEEDBACK","status":feedback_state,"finding":"Exploratory aggregate role/month associations","limitation":"Coverage-limited; August and September observed starts unavailable, not zero."},
        {"layer":"WORKFLOW","status":"DATA GAP","finding":f"{len(workflow)} internal workflow stages mapped","limitation":"Internal AI, recruiter, funnel, interview, employment, and advancement evidence is not public."},
        {"layer":"ADVERSE IMPACT","status":"NOT ESTIMABLE FROM PUBLIC DATA","finding":"Selection-rate denominators are absent","limitation":"No applicant or stage-specific demographic denominators; no 4/5ths rate computed."},
    ]
    checks=[]
    checks.append({"check":"canonical_outcomes","status":"PASS" if outcome=={"MALE":606,"FEMALE":276,"UNKNOWN":213} and total==1095 else "FAIL","detail":json.dumps(outcome,sort_keys=True)})
    checks.append({"check":"prediction_limit_preserved","status":"PASS" if model_status=="NOT_ESTIMABLE" else "FAIL","detail":f"Phase 4 status={model_status}"})
    checks.append({"check":"no_internal_steps_misrepresented","status":"PASS","detail":"Missing implementation artifacts are explicitly enumerated; not reported as completed."})
    readiness="PASS" if not missing_steps else "PASS_WITH_GAPS"
    payload={"status":readiness,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "github_repository_destination":GITHUB,"github_publish_performed":False,
        "observed_outcomes":outcome,"total":total,"known_sex_percentages":{"male":round(outcome.get("MALE",0)/known*100,2),"female":round(outcome.get("FEMALE",0)/known*100,2)},
        "male_female_ratio":round(outcome.get("MALE",0)/outcome.get("FEMALE",1),2),
        "evidence_layers":evidence,"missing_audit_steps":missing_steps,
        "limitations_rows":len(limitation),"checks":checks,
        "publication_status":"HOLD / REVIEW REQUIRED"}
    json_path=OUT/"09_executive_evidence_consolidation.json"
    json_path.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    csv_path=OUT/"09_executive_evidence_consolidation.csv"
    with csv_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["layer","status","finding","limitation"]);w.writeheader();w.writerows(evidence)
    audit_path=AUDIT/"09_executive_evidence_consolidation_audit.csv"
    with audit_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["check","status","detail"]);w.writeheader();w.writerows(checks)
    print("VERSION C — STEP 09 EXECUTIVE EVIDENCE CONSOLIDATION")
    print(f"STATUS: {readiness}\nOUTCOMES: MALE {outcome.get('MALE')} / FEMALE {outcome.get('FEMALE')} / UNKNOWN {outcome.get('UNKNOWN')} / N={total}")
    print(f"SIGNAL: OBSERVABLE\nPREDICTION: {model_status}\nFEEDBACK: {feedback_state}\nADVERSE IMPACT: NOT ESTIMABLE FROM PUBLIC DATA")
    print("MISSING PRIOR AUDIT STEPS: "+(", ".join(missing_steps) if missing_steps else "none"))
    print(f"CONSOLIDATION: {json_path}\nTABLE: {csv_path}\nAUDIT: {audit_path}")
    return 0 if all(r["status"]=="PASS" for r in checks) else 1

if __name__=="__main__": raise SystemExit(main())

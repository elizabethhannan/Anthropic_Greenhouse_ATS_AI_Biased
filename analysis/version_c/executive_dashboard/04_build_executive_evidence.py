"""Consolidate frozen Version C evidence for the final executive dashboard.

Reads existing artifacts and copies their reported values into a presentation
payload. This step does not recalculate analytical results.
"""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent; VC=HERE.parent; ROOT=VC.parent.parent
OUT=HERE/"outputs"; AUD=HERE/"audit"; OUT.mkdir(parents=True,exist_ok=True); AUD.mkdir(parents=True,exist_ok=True)
REPO="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"

def rows(path):
    with path.open(newline="",encoding="utf-8-sig") as f: return list(csv.DictReader(f))
def pick(source, key, value):
    return next((r for r in source if r.get(key)==value),None)
def load_json(path): return json.loads(path.read_text(encoding="utf-8"))

outcomes=rows(VC/"outputs/outcome_distribution.csv")
def count(label):
    r=pick(outcomes,"outcome_sex",label)
    if not r: raise ValueError(f"Missing frozen outcome {label}")
    return int(r["person_count"])
male,female,unknown=count("MALE"),count("FEMALE"),count("UNKNOWN")
total=sum((male,female,unknown)); known=male+female
signals=rows(VC/"outputs/dashboard_signal_findings.csv")
def signal_count(finding):
    r=pick(signals,"finding",finding)
    if not r: raise ValueError(f"Missing signal finding {finding}")
    return int(r["posting_count"])
research=rows(VC/"outputs/research_outcome_distribution.csv")
research_rows={r["outcome_sex"].upper():int(r["person_count"]) for r in research if r.get("population")=="observed_research_hires"}
feedback_rows=rows(VC/"outputs/feedback_summary.csv")
feedback={r["item"]:r["value"] for r in feedback_rows}
gate=load_json(VC/"ml_models/outputs/02_employment_selection_ml_gate.json")
selection=load_json(VC/"bias_audit/outputs/selection_audit_status.json")
evidence={
 "version":"Version C — Version 3.0", "study_window":"2026-04-01 through 2026-09-30",
 "executive_question":"WHAT IS DRIVING THE GENDER DISPARITY IN THE AI-ASSISTED EMPLOYMENT SYSTEM — AND WHO SHOULD OWN FIXING IT?",
 "observed_outcomes":{"male":male,"female":female,"unknown":unknown,"total":total,"known_sex_n":known,"male_share_known":male/known,"female_share_known":female/known,"male_female_ratio":male/female},
 "greenhouse_postings":{"all_postings":signal_count("all_postings"),"established_dates_in_window":signal_count("date_evidence:GREENHOUSE_POSTING_DATE"),"archive_capture_only":signal_count("date_evidence:ARCHIVE_CAPTURE_ONLY"),"outside_window":signal_count("date_evidence:POSTING_DATE_OUTSIDE_WINDOW")},
 "research_classified_outcomes":{"male":research_rows.get("MALE",0),"female":research_rows.get("FEMALE",0),"unknown":research_rows.get("UNKNOWN",0),"total":sum(research_rows.values()),"population":"Observed research-hire subset; distinct subset, not additive to overall observed outcomes."},
 "diagnostics":{"signal":"OBSERVABLE","prediction":"NOT ESTIMABLE FROM PUBLIC DATA","feedback":"EXPLORATORY"},
 "estimability":{"eligible_matched_role_month_cells":gate["estimability"]["eligible_dated_posting_and_known_sex_cells"],"male_outcome_cells":gate["estimability"]["male_outcome_cells"],"female_outcome_cells":gate["estimability"]["female_outcome_cells"],"model_fit_performed":False,"selection_rates":"NOT ESTIMABLE FROM PUBLIC DATA","adverse_impact":"NOT ESTIMABLE FROM PUBLIC DATA"},
 "feedback_coverage":{"status":feedback.get("status"),"hiring_observed_coverage":feedback.get("hiring_observed_coverage"),"note":feedback.get("question_A_forward_1_sample_months")},
 "executive_proposition":"Human-AI Employment Intelligence & Governance",
 "interpretation_boundary":"Observed representation disparity in available public data; does not establish that Greenhouse caused the disparity or locate its origin within the employment system.",
 "controls":{"sex_inference":False,"unknown_collapsed":False,"candidate_level_greenhouse_linkage":False,"synthetic_candidates":False,"greenhouse_causal_claim":False,"plan_a_modified":False},
 "publication_status":"HOLD / REVIEW REQUIRED","github_repository_destination":REPO,"github_publish_performed":False,"source_artifacts_read_only":True,"generated_at_utc":datetime.now(timezone.utc).isoformat()
}
path=OUT/"executive_evidence_v3.json"; path.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
flat=[]
def flatten(prefix,obj):
    if isinstance(obj,dict):
        for k,v in obj.items(): flatten(f"{prefix}.{k}" if prefix else k,v)
    else: flat.append((prefix,obj))
flatten("",evidence)
with (OUT/"executive_evidence_v3.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["evidence_key","value"]); w.writerows(flat)
checks=[("Frozen overall outcome counts reconcile",total==1095 and (male,female,unknown)==(606,276,213)),("Frozen Greenhouse posting categories reconcile",evidence["greenhouse_postings"]["established_dates_in_window"]+evidence["greenhouse_postings"]["archive_capture_only"]+evidence["greenhouse_postings"]["outside_window"]==evidence["greenhouse_postings"]["all_postings"]==1246),("Prediction gate preserved",evidence["diagnostics"]["prediction"]=="NOT ESTIMABLE FROM PUBLIC DATA"),("No model fit claimed",evidence["estimability"]["model_fit_performed"] is False),("Publication hold preserved",evidence["publication_status"]=="HOLD / REVIEW REQUIRED"),("Unknown retained",evidence["controls"]["unknown_collapsed"] is False)]
with (AUD/"04_executive_evidence_audit.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["check","status","detail"]); w.writerows((n,"PASS" if ok else "FAIL","" if ok else "Reconcile frozen input artifacts") for n,ok in checks)
print("VERSION C — 09 EXECUTIVE EVIDENCE CONSOLIDATION")
print(f"OUTCOMES: {male} Male / {female} Female / {unknown} Unknown / {total} total")
print(f"GREENHOUSE POSTINGS: {evidence['greenhouse_postings']}")
print("SIGNAL: OBSERVABLE | PREDICTION: NOT ESTIMABLE FROM PUBLIC DATA | FEEDBACK: EXPLORATORY")
print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED")
print(f"EVIDENCE: {path}"); print(f"AUDIT: {AUD/'04_executive_evidence_audit.csv'}")
raise SystemExit(0 if all(c[1] for c in checks) else 1)

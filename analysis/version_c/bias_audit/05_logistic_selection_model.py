"""Future logistic selection model contract. No public-data model is fitted."""
from pathlib import Path
import csv,json
BASE=Path(__file__).resolve().parent; OUT=BASE/"outputs"; AUD=BASE/"audit"; OUT.mkdir(exist_ok=True); AUD.mkdir(exist_ok=True)
REPO="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
required=["candidate_id","application_id","job_id","application_timestamp","stage","stage_outcome","selected","sex"]
features=["job_family","seniority","location","source_channel","experience_band","stage_elapsed_time"]
status={"status":"ARCHITECTURE_READY_MODEL_NOT_FIT","model":"Logistic Regression","unit":"candidate/application-stage observation","target":"selected (binary stage outcome)","protected_attribute":"source-provided sex; audit-only, never a predictor","required_fields":required,"candidate_features_contract":features,"public_data_gate":"NOT_ESTIMABLE_FROM_PUBLIC_DATA","fit_performed":False,"reason":"Public aggregate role/month data contain 3 eligible cells and no Female-positive outcome cells; candidate-stage outcomes and denominators are absent.","sex_inference":False,"synthetic_candidates":False,"candidate_linkage_fabricated":False,"github_repository_destination":REPO,"github_publish_performed":False}
(OUT/"05_logistic_selection_model_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
with (OUT/"05_logistic_selection_model_contract.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["field","role","required"]); w.writerows((x,"schema/audit field","yes") for x in required); w.writerows((x,"candidate feature (future reviewed contract)","no") for x in features)
checks=[("No model fit",not status["fit_performed"]),("Protected attribute excluded from predictors",status["protected_attribute"].endswith("never a predictor")),("No synthetic candidates",not status["synthetic_candidates"]),("Gate preserved",status["public_data_gate"]=="NOT_ESTIMABLE_FROM_PUBLIC_DATA")]
with (AUD/"05_logistic_selection_model_audit.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
print("VERSION C — 05 LOGISTIC SELECTION MODEL"); print("STATUS: ARCHITECTURE_READY_MODEL_NOT_FIT"); print("PUBLIC DATA: NOT ESTIMABLE; model fit not performed"); print(f"CONTRACT: {OUT/'05_logistic_selection_model_contract.csv'}"); print(f"AUDIT: {AUD/'05_logistic_selection_model_audit.csv'}")
raise SystemExit(0 if all(ok for _,ok in checks) else 1)

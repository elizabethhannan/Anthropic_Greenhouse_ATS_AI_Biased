"""Version C — Step 08 Human-AI workflow audit evidence map.

Defines internal instrumentation needed to locate where disparities may
emerge. It does not claim that any proposed mechanism exists.
"""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
AUDIT_DIR = BASE_DIR / "audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
GITHUB_REPO = "https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"

workflow = [
    {"stage":"AI_RECRUITING","question":"What AI-generated or algorithmic signals enter recruiting?","required_evidence":"Talent Matching outputs; ranking; recommendations; scores","current_public_status":"DATA GAP"},
    {"stage":"CANDIDATE_EXPERIENCE","question":"What candidate-facing language or recommendations are presented?","required_evidence":"Candidate-facing prompts; generated text; recommendations","current_public_status":"DATA GAP"},
    {"stage":"SCREENING","question":"Which candidates progress through screening?","required_evidence":"Applicant denominator; screening outcomes; timestamps","current_public_status":"DATA GAP"},
    {"stage":"HUMAN_RECRUITING","question":"Where do recruiters override or modify AI recommendations?","required_evidence":"Recruiter criteria; overrides; decision logs","current_public_status":"DATA GAP"},
    {"stage":"INTERVIEW","question":"Do evaluation outcomes differ by demographic group?","required_evidence":"Interview scorecards; interviewer identity; stage outcomes","current_public_status":"DATA GAP"},
    {"stage":"HIRING","question":"What demographic selection-rate differences occur?","required_evidence":"Candidate-stage denominators and hiring outcomes","current_public_status":"DATA GAP"},
    {"stage":"EMPLOYMENT","question":"Do opportunity, assignment, recognition, or evaluation differ?","required_evidence":"Assignments; performance; compensation; opportunity data","current_public_status":"DATA GAP"},
    {"stage":"ADVANCEMENT","question":"Do promotion and advancement pathways differ?","required_evidence":"Promotion; sponsorship; succession; advancement data","current_public_status":"DATA GAP"},
]

def main() -> int:
    csv_path = OUTPUT_DIR / "08_human_ai_workflow_evidence_map.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(workflow[0]))
        writer.writeheader(); writer.writerows(workflow)
    status = {"status":"WORKFLOW_AUDIT_ARCHITECTURE_READY","stages":len(workflow),
        "all_current_public_status":"DATA GAP",
        "interpretation":"Public data do not expose the internal workflow evidence needed to locate the origin of observed disparities.",
        "causal_claim":False,"greenhouse_causal_claim":False,"sex_inference":False,
        "candidate_level_linkage":False,"synthetic_candidates":False,
        "github_destination":GITHUB_REPO,"github_publish_performed":False,
        "generated_at_utc":datetime.now(timezone.utc).isoformat()}
    json_path = OUTPUT_DIR / "08_human_ai_workflow_audit_status.json"
    json_path.write_text(json.dumps(status, indent=2)+"\n", encoding="utf-8")
    checks = [("Workflow stages defined",len(workflow)==8),("Public data treated as data-limited",all(r["current_public_status"]=="DATA GAP" for r in workflow)),("No candidate linkage",not status["candidate_level_linkage"]),("No sex inference",not status["sex_inference"]),("No synthetic candidates",not status["synthetic_candidates"]),("No Greenhouse causal claim",not status["greenhouse_causal_claim"])]
    audit_path = AUDIT_DIR / "08_human_ai_workflow_audit.csv"
    with audit_path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f); writer.writerow(["check","status"])
        writer.writerows((name,"PASS" if ok else "FAIL") for name,ok in checks)
    print("="*68); print("VERSION C — 08 HUMAN-AI WORKFLOW AUDIT"); print("="*68)
    print("WORKFLOW STAGES:",len(workflow)); print("CURRENT INTERNAL EVIDENCE: NOT PROVIDED")
    print("PUBLIC CAUSAL ATTRIBUTION: NO\nCANDIDATE LINKAGE:          NO\nSEX INFERENCE:              NO")
    print("\nSTATUS: WORKFLOW_AUDIT_ARCHITECTURE_READY")
    print(f"EVIDENCE MAP: {csv_path}\nSTATUS:       {json_path}\nAUDIT:        {audit_path}")
    print("="*68)
    return 0 if all(ok for _,ok in checks) else 1

if __name__ == "__main__": raise SystemExit(main())

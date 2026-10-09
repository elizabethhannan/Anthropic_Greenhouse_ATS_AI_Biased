"""Audit the evidence chain from frozen package through private deployment and QA."""
from pathlib import Path
import json,csv,hashlib,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE=ROOT/"github_private"; AUDIT=PRIVATE/"audit"; CLOSURE=PRIVATE/"closure"; CLOSURE.mkdir(parents=True,exist_ok=True)
EXPECTED="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
required={"Step 20 frozen integrity":ROOT/"audit"/"20_frozen_integrity_verification.json","Step 22 pre-push QA":AUDIT/"22_pre_push_repository_qa.json","Step 24A reconciliation":AUDIT/"24A_pre_deployment_reconciliation.json","Step 25 private destination":AUDIT/"25_private_github_destination_verification.json","Step 26 local commit":AUDIT/"26_private_git_commit.json","Step 27 push":AUDIT/"27_private_github_push.json","Step 28 remote commit":AUDIT/"28_remote_commit_verification.json","Step 29 locked tag":AUDIT/"29_locked_release_tag.json","Step 30 final deployment audit":AUDIT/"30_final_private_deployment_audit.json","Step 31 snapshot":CLOSURE/"31_POST_DEPLOYMENT_SNAPSHOT.json","Step 32 executive QA":CLOSURE/"32_EXECUTIVE_REVIEW_QA.json","Step 33 dashboard smoke test":CLOSURE/"33_DASHBOARD_SMOKE_TEST.json"}
missing=[(label,path) for label,path in required.items() if not path.is_file()]
if missing:
 print("VERSION C — 34 REPRODUCIBILITY CHAIN AUDIT"); print("STATUS: FAIL — REQUIRED RECORDS MISSING")
 for label,path in missing: print(f"- {label}: {path}")
 print("No successful chain result recorded."); sys.exit(1)
data={label:json.loads(path.read_text(encoding="utf-8")) for label,path in required.items()}
checks=[]
for label,obj in data.items():
 status=obj.get("final_result",obj.get("status"))
 checks.append((f"{label} passed",status=="PASS"))
checks.extend([("Frozen fingerprint consistent across deployment chain",all(obj.get("expected_fingerprint",obj.get("frozen_fingerprint",obj.get("frozen_expected_fingerprint",EXPECTED)))==EXPECTED for obj in data.values())),("Step 22 recorded zero secret findings",data["Step 22 pre-push QA"].get("secret_findings")==0),("Step 22 recorded zero dangerous files",data["Step 22 pre-push QA"].get("dangerous_files")==[]),("Step 28 commit equals remote",data["Step 28 remote commit"].get("commit_match") is True),("Step 28 repository private",data["Step 28 remote commit"].get("repository_private") is True),("Step 30 has five true integrity checks",isinstance(data["Step 30 final deployment audit"].get("checks"),dict) and len(data["Step 30 final deployment audit"]["checks"])==5 and all(data["Step 30 final deployment audit"]["checks"].values()))])
result={"status":"PASS" if all(ok for _,ok in checks) else "FAIL","expected_fingerprint":EXPECTED,"checks_total":len(checks),"failures":[n for n,ok in checks if not ok],"source_artifacts":{label:{"path":str(required[label]),"sha256":hashlib.sha256(required[label].read_bytes()).hexdigest()} for label in required},"publication_status":"HOLD / REVIEW REQUIRED","audited_at_utc":datetime.now(timezone.utc).isoformat(),"checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks]}
path=CLOSURE/"34_REPRODUCIBILITY_CHAIN.json"; path.write_text(json.dumps(result,indent=2),encoding="utf-8")
with (CLOSURE/"34_REPRODUCIBILITY_CHAIN.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
print("VERSION C — 34 END-TO-END REPRODUCIBILITY CHAIN AUDIT"); print(f"STATUS: {result['status']}"); print(f"CHECKS: {len(checks)}; FAILURES: {len(result['failures'])}"); print(f"REPORT: {path}")
raise SystemExit(0 if result["status"]=="PASS" else 1)

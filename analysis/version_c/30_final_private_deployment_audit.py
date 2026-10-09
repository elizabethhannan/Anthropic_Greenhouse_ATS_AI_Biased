"""Verify final private deployment against frozen package, Git, tag, privacy, and results."""
from pathlib import Path
import subprocess,hashlib,json,sys,shutil
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; FROZEN_PACKAGE=ROOT/"final_evidence_package"; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"; AUDIT.mkdir(parents=True,exist_ok=True)
EXPECTED_FINGERPRINT="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"; TAG="version-c-v3.0-locked"; SLUG="elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
def run(args,cwd=None): return subprocess.run(args,cwd=cwd,capture_output=True,text=True)
def load(path):
 if not path.is_file(): raise FileNotFoundError(f"Required audit record missing: {path}")
 return json.loads(path.read_text(encoding="utf-8"))
baseline=load(ROOT/"audit"/"17_final_integrity_manifest.json")
step20=load(ROOT/"audit"/"20_frozen_integrity_verification.json")
step26=load(AUDIT/"26_private_git_commit.json"); step27=load(AUDIT/"27_private_github_push.json"); step28=load(AUDIT/"28_remote_commit_verification.json"); step29=load(AUDIT/"29_locked_release_tag.json")
expected={x["path"]:x["sha256"] for x in baseline["files"]}; actual={p.relative_to(FROZEN_PACKAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN_PACKAGE.rglob("*") if p.is_file()}
base_payload={k:v for k,v in baseline.items() if k!="package_fingerprint_sha256"}
computed_fingerprint=hashlib.sha256(json.dumps(base_payload,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
frozen_ok=(set(actual)==set(expected) and actual==expected and computed_fingerprint==EXPECTED_FINGERPRINT==baseline.get("package_fingerprint_sha256") and step20.get("status")=="PASS")
if not shutil.which("gh"): raise RuntimeError("GitHub CLI required for final remote privacy verification.")
privacy_run=run(["gh","repo","view",SLUG,"--json","nameWithOwner,visibility,isPrivate"])
if privacy_run.returncode: raise RuntimeError("Could not query GitHub privacy for final audit.")
remote_info=json.loads(privacy_run.stdout); private=(remote_info.get("nameWithOwner","").lower()==SLUG.lower() and remote_info.get("visibility")=="PRIVATE" and remote_info.get("isPrivate") is True)
fetch=run(["git","fetch","origin","main"],cwd=REPOSITORY)
if fetch.returncode: raise RuntimeError("Remote main fetch failed during final audit.")
local=run(["git","rev-parse","HEAD"],cwd=REPOSITORY).stdout.strip(); remote=run(["git","rev-parse","refs/remotes/origin/main"],cwd=REPOSITORY).stdout.strip()
commit_match=(local==remote==step26.get("commit") and step27.get("status")=="PASS" and step28.get("status")=="PASS")
local_tag=run(["git","rev-parse","refs/tags/"+TAG],cwd=REPOSITORY)
tag_commit=run(["git","rev-list","-n","1",TAG],cwd=REPOSITORY)
remote_tag=run(["git","ls-remote","origin",f"refs/tags/{TAG}",f"refs/tags/{TAG}^{{}}"],cwd=REPOSITORY)
remote_tag_map={line.split()[1]:line.split()[0] for line in remote_tag.stdout.splitlines() if len(line.split())==2} if remote_tag.returncode==0 else {}
tag_ok=(local_tag.returncode==0 and tag_commit.returncode==0 and tag_commit.stdout.strip()==local and remote_tag.returncode==0 and f"refs/tags/{TAG}^{{}}" in remote_tag_map and remote_tag_map[f"refs/tags/{TAG}^{{}}"]==local and step29.get("status")=="PASS")
payload_path=REPOSITORY/"executive_evidence_v3.json"; readme_path=REPOSITORY/"README.md"
evidence=json.loads(payload_path.read_text(encoding="utf-8")) if payload_path.is_file() else {}
o=evidence.get("observed_outcomes",{})
canonical_ok=(o.get("male")==606 and o.get("female")==276 and o.get("unknown")==213 and o.get("total")==1095 and abs(o.get("male_female_ratio",0)-2.2)<0.01 and evidence.get("diagnostics",{}).get("signal")=="OBSERVABLE" and evidence.get("diagnostics",{}).get("prediction")=="NOT ESTIMABLE FROM PUBLIC DATA" and evidence.get("diagnostics",{}).get("feedback")=="EXPLORATORY" and readme_path.is_file() and "HOLD / REVIEW REQUIRED" in readme_path.read_text(encoding="utf-8"))
checks={"frozen_analytical_package_fingerprint":frozen_ok,"local_commit_equals_remote_commit":commit_match,"locked_tag_exists_locally_and_remotely_at_verified_commit":tag_ok,"github_repository_is_private":private,"canonical_results_and_publication_hold":canonical_ok}
status="PASS" if all(checks.values()) else "FAIL"
record={"status":status,"final_result":status,"checks":checks,"local_commit":local,"remote_commit":remote,"tag":TAG,"tag_commit":tag_commit.stdout.strip() if tag_commit.returncode==0 else None,"remote_visibility":remote_info.get("visibility"),"private":private,"frozen_expected_fingerprint":EXPECTED_FINGERPRINT,"frozen_recomputed_fingerprint":computed_fingerprint,"publication_status":"HOLD / REVIEW REQUIRED","github_push_performed":True,"audited_at_utc":datetime.now(timezone.utc).isoformat()}
path=AUDIT/"30_final_private_deployment_audit.json"; path.write_text(json.dumps(record,indent=2),encoding="utf-8")
print("VERSION C — 30 FINAL PRIVATE-DEPLOYMENT AUDIT")
for name,ok in checks.items(): print(f"{name}: {ok}")
print(f"FINAL RESULT: {status}"); print("PUBLIC RELEASE: HOLD / REVIEW REQUIRED"); print(f"AUDIT: {path}")
raise SystemExit(0 if status=="PASS" else 1)

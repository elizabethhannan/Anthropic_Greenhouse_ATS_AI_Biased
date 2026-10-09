"""Push the approved local commit only after rechecking GitHub privacy."""
from pathlib import Path
import subprocess,json,sys,shutil,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"; AUDIT.mkdir(parents=True,exist_ok=True)
STEP26=AUDIT/"26_private_git_commit.json"; STEP22=AUDIT/"22_pre_push_repository_qa.json"; STEP19=AUDIT/"19_private_repository_security_manifest.json"
SLUG="elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"; REMOTE="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased.git"
def run(args,cwd=None): return subprocess.run(args,cwd=cwd,capture_output=True,text=True)
for p in (STEP26,STEP22,STEP19):
    if not p.is_file(): raise FileNotFoundError(f"Required pre-push record missing: {p}")
commit=json.loads(STEP26.read_text(encoding="utf-8")); qa=json.loads(STEP22.read_text(encoding="utf-8")); security=json.loads(STEP19.read_text(encoding="utf-8"))
if commit.get("status")!="PASS" or qa.get("status")!="PASS" or security.get("status")!="PASS": raise RuntimeError("A required local QA gate did not pass; push refused.")
if not REPOSITORY.is_dir(): raise FileNotFoundError(f"Repository missing: {REPOSITORY}")
if not shutil.which("gh"): raise RuntimeError("GitHub CLI is required; push refused.")
auth=run(["gh","auth","status"])
if auth.returncode: raise RuntimeError("GitHub CLI authentication is unavailable; push refused.")
view=run(["gh","repo","view",SLUG,"--json","nameWithOwner,visibility,isPrivate"])
if view.returncode: raise RuntimeError("Could not reverify GitHub destination; push refused.")
remote_info=json.loads(view.stdout)
if remote_info.get("nameWithOwner","").lower()!=SLUG.lower() or remote_info.get("visibility")!="PRIVATE" or remote_info.get("isPrivate") is not True: raise RuntimeError("Destination is not verified PRIVATE; push refused.")
url=run(["git","remote","get-url","origin"],cwd=REPOSITORY)
if url.returncode or url.stdout.strip()!=REMOTE: raise RuntimeError("Git origin does not exactly match approved destination.")
head=run(["git","rev-parse","HEAD"],cwd=REPOSITORY)
if head.returncode or head.stdout.strip()!=commit.get("commit"): raise RuntimeError("Local HEAD differs from Step 26 commit; push refused.")
dirty=run(["git","status","--porcelain"],cwd=REPOSITORY)
if dirty.returncode or dirty.stdout.strip(): raise RuntimeError("Worktree is not clean; push refused.")
push=run(["git","push","-u","origin","main"],cwd=REPOSITORY)
record={"status":"PASS" if push.returncode==0 else "FAIL","repository":SLUG,"visibility":"PRIVATE","private":True,"local_commit":head.stdout.strip(),"push_return_code":push.returncode,"github_push_performed":push.returncode==0,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
path=AUDIT/"27_private_github_push.json"; path.write_text(json.dumps(record,indent=2),encoding="utf-8")
print("VERSION C — 27 CONTROLLED PRIVATE GITHUB PUSH"); print(f"VISIBILITY RECHECK: {remote_info.get('visibility')}"); print(f"LOCAL COMMIT: {record['local_commit']}"); print(f"PUSH STATUS: {record['status']}"); print(f"PUSH PERFORMED: {record['github_push_performed']}"); print(f"AUDIT: {path}")
if push.returncode:
    # Do not emit potentially sensitive remote diagnostics into the audit; stdout/stderr are summarized.
    print("Git push failed. Remote output is not reproduced here; inspect the local command result securely.")
    sys.exit(1)

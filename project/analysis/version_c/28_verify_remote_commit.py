"""Fetch and verify that GitHub's main commit equals the approved local commit."""
from pathlib import Path
import subprocess,json,sys,shutil
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"
STEP26=AUDIT/"26_private_git_commit.json"; STEP27=AUDIT/"27_private_github_push.json"; SLUG="elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
def run(args,cwd=None): return subprocess.run(args,cwd=cwd,capture_output=True,text=True)
for p in (STEP26,STEP27):
 if not p.is_file(): raise FileNotFoundError(f"Required deployment record missing: {p}")
commit=json.loads(STEP26.read_text(encoding="utf-8")); pushed=json.loads(STEP27.read_text(encoding="utf-8"))
if pushed.get("status")!="PASS" or not pushed.get("github_push_performed"): raise RuntimeError("Step 27 did not record a successful push.")
if not shutil.which("gh"): raise RuntimeError("GitHub CLI unavailable; remote verification cannot proceed.")
q=run(["gh","repo","view",SLUG,"--json","nameWithOwner,visibility,isPrivate"])
if q.returncode: raise RuntimeError("Unable to verify remote repository privacy.")
info=json.loads(q.stdout); private=info.get("nameWithOwner","").lower()==SLUG.lower() and info.get("visibility")=="PRIVATE" and info.get("isPrivate") is True
if not private: raise RuntimeError("Remote repository is not confirmed PRIVATE.")
fetch=run(["git","fetch","origin","main"],cwd=REPOSITORY)
if fetch.returncode: raise RuntimeError("Git fetch failed; remote commit could not be verified.")
local=run(["git","rev-parse","HEAD"],cwd=REPOSITORY).stdout.strip(); remote=run(["git","rev-parse","refs/remotes/origin/main"],cwd=REPOSITORY).stdout.strip()
match=local==remote==commit.get("commit")
record={"status":"PASS" if match and private else "FAIL","repository":SLUG,"local_commit":local,"remote_commit":remote,"commit_match":match,"repository_private":private,"visibility":info.get("visibility"),"verified_at_utc":datetime.now(timezone.utc).isoformat()}
path=AUDIT/"28_remote_commit_verification.json"; path.write_text(json.dumps(record,indent=2),encoding="utf-8")
print("VERSION C — 28 VERIFY REMOTE COMMIT"); print(f"LOCAL COMMIT: {local}"); print(f"REMOTE COMMIT: {remote}"); print(f"COMMIT MATCH: {match}"); print(f"REPOSITORY PRIVATE: {private}"); print(f"STATUS: {record['status']}"); print(f"AUDIT: {path}")
if record["status"]!="PASS": sys.exit(1)

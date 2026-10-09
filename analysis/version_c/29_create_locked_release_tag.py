"""Create and push an annotated locked tag after commit/privacy verification."""
from pathlib import Path
import subprocess,json,sys,shutil
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"
STEP28=AUDIT/"28_remote_commit_verification.json"; STEP20=ROOT/"audit"/"20_frozen_integrity_verification.json"
TAG="version-c-v3.0-locked"; EXPECTED_FINGERPRINT="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"; SLUG="elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
def run(args): return subprocess.run(args,cwd=REPOSITORY,capture_output=True,text=True)
for p in (STEP28,STEP20):
 if not p.is_file(): raise FileNotFoundError(f"Required verified gate missing: {p}")
v28=json.loads(STEP28.read_text(encoding="utf-8")); v20=json.loads(STEP20.read_text(encoding="utf-8"))
if v28.get("status")!="PASS" or not v28.get("commit_match") or v28.get("repository_private") is not True: raise RuntimeError("Step 28 commit/privacy verification failed; tag creation stopped.")
if v20.get("status")!="PASS" or v20.get("expected_fingerprint")!=EXPECTED_FINGERPRINT: raise RuntimeError("Frozen integrity gate failed; tag creation stopped.")
if not shutil.which("gh"): raise RuntimeError("GitHub CLI unavailable; cannot recheck destination.")
q=subprocess.run(["gh","repo","view",SLUG,"--json","nameWithOwner,visibility,isPrivate"],capture_output=True,text=True)
if q.returncode: raise RuntimeError("Unable to recheck destination privacy; tag push stopped.")
info=json.loads(q.stdout)
if info.get("nameWithOwner","").lower()!=SLUG.lower() or info.get("visibility")!="PRIVATE" or info.get("isPrivate") is not True: raise RuntimeError("Destination is not confirmed PRIVATE; tag push stopped.")
head=run(["git","rev-parse","HEAD"]).stdout.strip()
if head!=v28.get("local_commit"): raise RuntimeError("HEAD changed after remote commit verification.")
existing=run(["git","rev-parse","--verify",f"refs/tags/{TAG}"])
if existing.returncode==0:
    tag_commit=run(["git","rev-list","-n","1",TAG]).stdout.strip()
    if tag_commit!=head: raise RuntimeError("Locked tag already exists at a different commit; refusing to move it.")
    created=False
else:
    r=run(["git","tag","-a",TAG,"-m",f"Version C v3.0 locked package; frozen fingerprint {EXPECTED_FINGERPRINT}"])
    if r.returncode: raise RuntimeError("Could not create locked tag.")
    created=True
push=run(["git","push","origin",f"refs/tags/{TAG}"])
if push.returncode: raise RuntimeError("Tag push failed; see local Git output securely.")
tag_commit=run(["git","rev-list","-n","1",TAG]).stdout.strip()
record={"status":"PASS" if tag_commit==head else "FAIL","tag":TAG,"tag_commit":tag_commit,"head_commit":head,"tag_created_in_this_run":created,"tag_pushed":push.returncode==0,"repository_private":True,"frozen_fingerprint":EXPECTED_FINGERPRINT,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
path=AUDIT/"29_locked_release_tag.json"; path.write_text(json.dumps(record,indent=2),encoding="utf-8")
print("VERSION C — 29 CREATE LOCKED VERSION TAG"); print(f"TAG: {TAG}"); print(f"TAG COMMIT: {tag_commit}"); print(f"TAG PUSHED: {record['tag_pushed']}"); print(f"STATUS: {record['status']}"); print(f"AUDIT: {path}")
if record["status"]!="PASS": sys.exit(1)

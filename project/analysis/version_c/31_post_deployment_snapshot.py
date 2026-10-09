"""Capture verified deployment metadata after Step 30 passes."""
from pathlib import Path
import subprocess,json,hashlib,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE=ROOT/"github_private"; REPOSITORY=PRIVATE/"repository"; AUDIT=PRIVATE/"audit"; CLOSURE=PRIVATE/"closure"; CLOSURE.mkdir(parents=True,exist_ok=True)
STEP30=AUDIT/"30_final_private_deployment_audit.json"; EXPECTED="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
if not STEP30.is_file(): raise FileNotFoundError(f"Step 30 audit is required before snapshot: {STEP30}")
a=json.loads(STEP30.read_text(encoding="utf-8"))
if a.get("final_result")!="PASS" or a.get("status")!="PASS" or not isinstance(a.get("checks"),dict) or len(a["checks"])!=5 or not all(a["checks"].values()):
 print("STEP 31 STOPPED: Step 30 did not pass all five checks."); sys.exit(1)
if a.get("frozen_expected_fingerprint")!=EXPECTED: raise RuntimeError("Step 30 fingerprint differs from the frozen expected value.")
def git(*args):
 r=subprocess.run(["git",*args],cwd=REPOSITORY,capture_output=True,text=True)
 if r.returncode: raise RuntimeError("Git metadata could not be read after Step 30 PASS.")
 return r.stdout.strip()
snapshot={"status":"PASS","captured_at_utc":datetime.now(timezone.utc).isoformat(),"frozen_fingerprint":EXPECTED,"local_commit":git("rev-parse","HEAD"),"remote_tracking_commit":git("rev-parse","refs/remotes/origin/main"),"locked_tag":"version-c-v3.0-locked","locked_tag_commit":git("rev-list","-n","1","version-c-v3.0-locked"),"repository_private":a["checks"].get("github_repository_is_private") is True,"public_release":False,"publication_status":"HOLD / REVIEW REQUIRED","step30_audit_sha256":hashlib.sha256(STEP30.read_bytes()).hexdigest()}
path=CLOSURE/"31_POST_DEPLOYMENT_SNAPSHOT.json"; path.write_text(json.dumps(snapshot,indent=2),encoding="utf-8")
print("VERSION C — 31 POST-DEPLOYMENT SNAPSHOT"); print("STATUS: PASS"); print(f"COMMIT: {snapshot['local_commit']}"); print(f"FROZEN FINGERPRINT: {EXPECTED}"); print(f"SNAPSHOT: {path}")

"""Verify the GitHub destination is actually private. This script never pushes."""
from pathlib import Path
import subprocess,json,shutil,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; AUDIT=PRIVATE_ROOT/"audit"; AUDIT.mkdir(parents=True,exist_ok=True)
SLUG="elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
gh=shutil.which("gh"); result_data={"status":"FAIL","repository":SLUG,"visibility":"UNKNOWN","private":False,"push_performed":False,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
if not gh:
    result_data["reason"]="GitHub CLI (gh) is not installed or not on PATH."
else:
    auth=subprocess.run([gh,"auth","status"],capture_output=True,text=True)
    if auth.returncode!=0:
        result_data["reason"]="GitHub CLI is not authenticated. Output omitted to avoid exposing account/session details."
    else:
        q=subprocess.run([gh,"repo","view",SLUG,"--json","nameWithOwner,visibility,isPrivate,url"],capture_output=True,text=True)
        if q.returncode!=0:
            result_data["reason"]="GitHub repository could not be queried. Details are omitted from the audit."
        else:
            try:
                remote=json.loads(q.stdout); is_private=remote.get("isPrivate") is True and remote.get("visibility")=="PRIVATE" and remote.get("nameWithOwner"," ").lower()==SLUG.lower()
                result_data.update({"status":"PASS" if is_private else "FAIL","name_with_owner":remote.get("nameWithOwner"),"visibility":remote.get("visibility"),"private":remote.get("isPrivate") is True,"url":remote.get("url"),"reason":"Destination visibility verified." if is_private else "Destination is not PRIVATE or repository identity did not match."})
            except (ValueError,TypeError): result_data["reason"]="GitHub CLI returned an unreadable repository response."
path=AUDIT/"25_private_github_destination_verification.json"; path.write_text(json.dumps(result_data,indent=2),encoding="utf-8")
print("VERSION C — 25 VERIFY PRIVATE GITHUB DESTINATION")
print(f"STATUS: {result_data['status']}"); print(f"VISIBILITY: {result_data['visibility']}"); print(f"PRIVATE: {result_data['private']}"); print("PUSH PERFORMED: NO"); print(f"AUDIT: {path}")
if result_data["status"]!="PASS":
    print(f"REASON: {result_data.get('reason')}"); sys.exit(1)

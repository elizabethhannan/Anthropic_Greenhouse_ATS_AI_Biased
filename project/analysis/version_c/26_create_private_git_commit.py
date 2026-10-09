"""Initialize and commit the verified private staging repository locally; no push."""
from pathlib import Path
import subprocess,json,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"; AUDIT.mkdir(parents=True,exist_ok=True)
STEP25=AUDIT/"25_private_github_destination_verification.json"; STEP22=AUDIT/"22_pre_push_repository_qa.json"; STEP20=ROOT/"audit"/"20_frozen_integrity_verification.json"
REMOTE_URL="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased.git"; EXPECTED_FINGERPRINT="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
def run(args,check=True):
    r=subprocess.run(args,cwd=REPOSITORY,capture_output=True,text=True)
    if check and r.returncode: raise RuntimeError(f"Command failed ({r.returncode}): {' '.join(args)}\n{r.stderr.strip()}")
    return r
for p in (STEP25,STEP22,STEP20):
    if not p.is_file(): raise FileNotFoundError(f"Required prior gate missing: {p}")
v25=json.loads(STEP25.read_text(encoding="utf-8")); v22=json.loads(STEP22.read_text(encoding="utf-8")); v20=json.loads(STEP20.read_text(encoding="utf-8"))
if v25.get("status")!="PASS" or v25.get("private") is not True or v25.get("visibility")!="PRIVATE": raise RuntimeError("Step 25 did not verify PRIVATE destination; no local repository created.")
if v22.get("status")!="PASS" or v20.get("status")!="PASS" or v20.get("expected_fingerprint")!=EXPECTED_FINGERPRINT: raise RuntimeError("Pre-commit QA or frozen integrity gate failed.")
if not REPOSITORY.is_dir(): raise FileNotFoundError(f"Staging repository missing: {REPOSITORY}")
git="git"
if not (REPOSITORY/".git").exists():
    run([git,"init","-b","main"])
else:
    branch=run([git,"branch","--show-current"]).stdout.strip()
    if branch!="main": raise RuntimeError(f"Existing repository branch is {branch!r}, expected 'main'.")
remote=run([git,"remote","get-url","origin"],check=False)
if remote.returncode==0 and remote.stdout.strip()!=REMOTE_URL: raise RuntimeError("Existing origin URL differs from the verified destination.")
if remote.returncode!=0: run([git,"remote","add","origin",REMOTE_URL])
fetch=run([git,"fetch","origin","main"],check=False)
if fetch.returncode==0:
    connected=run([git,"merge-base","HEAD","origin/main"],check=False)
    if connected.returncode==1:
        # The GitHub repository has a pre-existing root commit. Preserve it by
        # merging unrelated histories; if its only conflict is the one-line
        # placeholder README, retain our fuller controlled-review README.
        merge=run([git,"merge","--allow-unrelated-histories","--no-commit","origin/main"],check=False)
        if merge.returncode:
            conflicts=run([git,"diff","--name-only","--diff-filter=U"],check=False).stdout.splitlines()
            if conflicts==["README.md"]:
                run([git,"checkout","--ours","--","README.md"])
                run([git,"add","--","README.md"])
            else:
                run([git,"merge","--abort"],check=False)
                raise RuntimeError(f"Remote history merge has unexpected conflicts: {conflicts}")
        run([git,"-c","user.name=Version C Release Automation","-c","user.email=version-c-release@users.noreply.github.com","commit","--no-edit","-m","Merge existing private repository history"])
    elif connected.returncode!=0:
        raise RuntimeError("Could not determine whether the remote history is related.")
    else:
        ancestor=run([git,"merge-base","--is-ancestor","origin/main","HEAD"],check=False)
        if ancestor.returncode!=0:
            # Do not silently discard a remote commit when branches diverged.
            raise RuntimeError("Local and remote histories diverged; manual merge review is required.")
run([git,"add","--all"])
# CSV artifacts use valid CRLF record endings. Tell Git to treat CR before LF
# as part of the line ending so whitespace QA does not flag each CSV row.
staged=run([git,"-c","core.whitespace=cr-at-eol","diff","--cached","--check"])
changed=run([git,"diff","--cached","--quiet"],check=False)
if changed.returncode==1:
    run([git,"-c","user.name=Version C Release Automation","-c","user.email=version-c-release@users.noreply.github.com","commit","-m","Version C v3.0 controlled private package"])
elif changed.returncode!=0: raise RuntimeError("Unable to determine staged diff state.")
head=run([git,"rev-parse","HEAD"]).stdout.strip(); tree=run([git,"rev-parse","HEAD^{tree}"]).stdout.strip()
status=run([git,"status","--porcelain"]).stdout
if status.strip(): raise RuntimeError("Worktree is not clean after local commit; refusing to report success.")
record={"status":"PASS","repository_path":str(REPOSITORY),"branch":"main","commit":head,"tree":tree,"remote_url":REMOTE_URL,"frozen_fingerprint":EXPECTED_FINGERPRINT,"worktree_clean":True,"git_push_performed":False,"github_push_performed":False,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
path=AUDIT/"26_private_git_commit.json"; path.write_text(json.dumps(record,indent=2),encoding="utf-8")
print("VERSION C — 26 CREATE PRIVATE GIT COMMIT"); print("STATUS: PASS"); print(f"BRANCH: main"); print(f"LOCAL COMMIT: {head}"); print("PUSH PERFORMED: NO"); print(f"AUDIT: {path}")

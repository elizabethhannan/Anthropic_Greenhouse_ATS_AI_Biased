"""Read-only reconciliation of QA assertions, index placement, staged files, and frozen fingerprint."""
from pathlib import Path
import hashlib,json,csv,subprocess
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent; PRIVATE=ROOT/"github_private"; REPO=PRIVATE/"repository"; AUDIT=PRIVATE/"audit"
EXPECTED_FP="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
step22_csv=AUDIT/"22_pre_push_repository_qa.csv"; step22_json=AUDIT/"22_pre_push_repository_qa.json"
step19=AUDIT/"19_private_repository_security_manifest.json"; frozen_manifest=ROOT/"audit"/"17_final_integrity_manifest.json"
for p in (step22_csv,step22_json,step19,frozen_manifest):
    if not p.is_file(): raise FileNotFoundError(f"Required reconciliation input missing: {p}")

# Read exact Step 22 assertion rows, separating the visibility note from scored checks.
with step22_csv.open(newline="",encoding="utf-8") as f: qa_rows=list(csv.DictReader(f))
scored=[r for r in qa_rows if r.get("check")!="GitHub visibility independently verified"]
visibility_rows=[r for r in qa_rows if r.get("check")=="GitHub visibility independently verified"]

# Report exact Step 23 index destinations and confirm they are outside the staged repository.
index_paths=[PRIVATE/"REPOSITORY_INDEX.md",PRIVATE/"REPOSITORY_INDEX.json",PRIVATE/"REPOSITORY_INDEX.csv"]
indexes=[{"path":str(p),"exists":p.is_file(),"inside_staged_repository":p.is_relative_to(REPO)} for p in index_paths]

# Reconcile actual staged files with Step 19's SHA-256 inventory, the post-security baseline.
security=json.loads(step19.read_text(encoding="utf-8")); expected_files={x["path"]:x["sha256"] for x in security.get("files",[])}
actual_paths=sorted(p for p in REPO.rglob("*") if p.is_file())
actual_files={p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in actual_paths}
unexpected=sorted(set(actual_files)-set(expected_files)); missing=sorted(set(expected_files)-set(actual_files))
changed=sorted(k for k in set(actual_files)&set(expected_files) if actual_files[k]!=expected_files[k])
git_probe=subprocess.run(["git","-C",str(REPO),"rev-parse","--show-toplevel"],capture_output=True,text=True)
git_top=Path(git_probe.stdout.strip()).resolve() if git_probe.returncode==0 else None
git_initialized_here=(REPO/".git").exists() or git_top==REPO.resolve()

# Recompute exact frozen baseline digest and rehash every original package file.
baseline=json.loads(frozen_manifest.read_text(encoding="utf-8")); package=ROOT/"final_evidence_package"
baseline_files={x["path"]:x["sha256"] for x in baseline.get("files",[])}
current_files={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob("*") if p.is_file()}
payload={k:v for k,v in baseline.items() if k!="package_fingerprint_sha256"}
recomputed=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
frozen_ok=(set(baseline_files)==set(current_files) and baseline_files==current_files and recomputed==EXPECTED_FP==baseline.get("package_fingerprint_sha256"))

checks={
 "step22_scored_assertion_count_is_13":len(scored)==13,
 "step22_assertions_all_pass":all(r.get("status")=="PASS" for r in scored),
 "step23_index_files_exist_outside_staged_repository":all(x["exists"] and not x["inside_staged_repository"] for x in indexes),
 "staged_repository_has_19_files":len(actual_files)==19,
 "no_unexpected_or_missing_staged_files":not unexpected and not missing,
 "staged_hashes_match_step19_security_manifest":not changed,
 "frozen_package_matches_expected_fingerprint":frozen_ok,
}
result={
 "status":"PASS" if all(checks.values()) else "FAIL",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "step22_scored_assertion_count":len(scored),
 "step22_assertions":[{"check":r.get("check"),"status":r.get("status")} for r in scored],
 "step22_visibility_note":visibility_rows,
 "step23_index_files":indexes,
 "staged_repository":{"path":str(REPO),"file_count":len(actual_files),"git_repository_initialized_here":git_initialized_here,"git_metadata_path":str(REPO/".git") if (REPO/".git").exists() else None,"ancestor_git_root_detected":str(git_top) if git_top and git_top!=REPO.resolve() else None,"expected_file_count_from_step19":len(expected_files),"unexpected_files":unexpected,"missing_files":missing,"hash_mismatches":changed,"file_paths":sorted(actual_files)},
 "frozen_package":{"expected_fingerprint":EXPECTED_FP,"recomputed_fingerprint":recomputed,"file_set_matches_baseline":set(baseline_files)==set(current_files),"file_hashes_match_baseline":baseline_files==current_files},
 "checks":checks,
 "frozen_package_modified":False,
 "staged_repository_modified":False,
 "github_push_performed":False,
}
out=AUDIT/"24A_pre_deployment_reconciliation.json"; out.write_text(json.dumps(result,indent=2),encoding="utf-8")
with (AUDIT/"24A_pre_deployment_reconciliation.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["check","status","detail"])
    for name,ok in checks.items(): w.writerow([name,"PASS" if ok else "FAIL",""])
    for row in scored: w.writerow(["Step 22: "+str(row.get("check")),row.get("status"),"Recorded assertion"])
    w.writerow(["Step 22: GitHub visibility independently verified","NOT VERIFIED","Separate external gate; Step 25 must query GitHub."])
print("VERSION C — 24A PRE-DEPLOYMENT RECONCILIATION")
print("STEP 22 ASSERTIONS:")
for row in scored: print(f"- {row.get('status')}: {row.get('check')}")
print(f"STEP 22 ASSERTION COUNT: {len(scored)}")
print("STEP 23 INDEX FILES:")
for item in indexes: print(f"- {item['path']} | exists={item['exists']} | inside repository={item['inside_staged_repository']}")
print(f"STAGED REPOSITORY FILE COUNT: {len(actual_files)}")
print(f"GIT REPOSITORY INITIALIZED AT STAGING ROOT: {git_initialized_here}")
if git_top and git_top!=REPO.resolve(): print(f"ANCESTOR GIT ROOT (NOT THE STAGING REPOSITORY): {git_top}")
print(f"UNEXPECTED FILES: {len(unexpected)}; MISSING BASELINE FILES: {len(missing)}; HASH MISMATCHES: {len(changed)}")
print(f"FROZEN FINGERPRINT: {recomputed}")
print(f"FROZEN PACKAGE MATCH: {frozen_ok}")
print(f"RECONCILIATION STATUS: {result['status']}")
print(f"REPORT: {out}")
raise SystemExit(0 if result["status"]=="PASS" else 1)

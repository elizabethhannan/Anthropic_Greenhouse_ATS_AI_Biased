"""Final local QA of the private GitHub staging repository; never pushes."""
from pathlib import Path
import hashlib,json,csv,re
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"; AUDIT.mkdir(parents=True,exist_ok=True)
FINGERPRINT="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
SECURITY= AUDIT/"19_private_repository_security_manifest.json"
FROZEN=ROOT/"audit"/"20_frozen_integrity_verification.json"
SECURITY_POLICY=REPOSITORY/"SECURITY.md"
if not REPOSITORY.is_dir(): raise FileNotFoundError(f"Private repository staging area missing: {REPOSITORY}")
if not SECURITY.is_file() or not FROZEN.is_file(): raise FileNotFoundError("Steps 19 and 20 must pass before Step 22.")
security=json.loads(SECURITY.read_text(encoding="utf-8")); frozen=json.loads(FROZEN.read_text(encoding="utf-8"))
files=sorted(p for p in REPOSITORY.rglob("*") if p.is_file()); actual={p.relative_to(REPOSITORY).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
expected={x["path"]:x["sha256"] for x in security.get("files",[])}
secret_patterns=[re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b"),re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
secret_hits=[]
for p in files:
    if p.suffix.lower() not in {".md",".txt",".json",".csv",".html",".css",".js",".yml",".yaml",".toml",".py",".sh"} and p.name!=".gitignore": continue
    text=p.read_text(encoding="utf-8",errors="ignore")
    for pat in secret_patterns:
        for m in pat.finditer(text): secret_hits.append({"path":p.relative_to(REPOSITORY).as_posix(),"line":text.count("\n",0,m.start())+1})
dangerous_ext={".parquet",".pq",".feather",".pkl",".pickle",".sqlite",".db",".duckdb",".xls",".xlsx",".pem",".key",".p12",".pfx"}
dangerous=[p.relative_to(REPOSITORY).as_posix() for p in files if p.suffix.lower() in dangerous_ext]
def contains(filename,phrase):
 p=REPOSITORY/filename
 return p.is_file() and phrase in p.read_text(encoding="utf-8",errors="ignore")
checks=[
 ("Step 19 security scan passed",security.get("status")=="PASS"),
 ("Step 20 frozen integrity passed",frozen.get("status")=="PASS" and frozen.get("expected_fingerprint")==FINGERPRINT),
 ("Staged file set matches Step 19 hash baseline",set(actual)==set(expected)),
 ("Staged content hashes match Step 19 baseline",not [x for x in actual if x in expected and actual[x]!=expected[x]]),
 ("No secret patterns detected",not secret_hits),
 ("No dangerous file extensions",not dangerous),
 ("Canonical Male/Female/Unknown/total present",all(contains("README.md",x) for x in ["606","276","213","1,095"])),
 ("Known-sex ratio preserved",contains("README.md","2.20:1")),
 ("Signal status preserved",contains("README.md","OBSERVABLE")),
 ("Prediction gate preserved",contains("README.md","NOT ESTIMABLE FROM PUBLIC DATA")),
 ("Feedback status preserved",contains("README.md","EXPLORATORY")),
 ("Publication hold preserved",contains("README.md","HOLD / REVIEW REQUIRED")),
 ("Security policy included",SECURITY_POLICY.is_file()),
]
failures=[n for n,ok in checks if not ok]
# Local files can verify intended visibility only; GitHub repository visibility is remote state.
qa={"status":"PASS" if not failures else "FAIL","checks_total":len(checks),"failures":failures,"checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks],"secret_findings":len(secret_hits),"dangerous_files":dangerous,"staged_file_count":len(files),"repository_visibility":"NOT_VERIFIED_EXTERNALLY","deployment_gate":"HOLD_UNTIL_PRIVATE_VISIBILITY_INDEPENDENTLY_CONFIRMED" if not failures else "BLOCKED_BY_QA_FAILURE","frozen_fingerprint":FINGERPRINT,"publication_status":"HOLD / REVIEW REQUIRED","github_publish_performed":False,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
(AUDIT/"22_pre_push_repository_qa.json").write_text(json.dumps(qa,indent=2),encoding="utf-8")
with (AUDIT/"22_pre_push_repository_qa.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks); w.writerow(["GitHub visibility independently verified","NOT VERIFIED"])
print("VERSION C — 22 PRE-PUSH PRIVATE REPOSITORY QA"); print(f"QA STATUS: {qa['status']}"); print(f"CHECKS: {len(checks)} | FAILURES: {len(failures)}"); print(f"SECRET FINDINGS: {len(secret_hits)} | DANGEROUS FILES: {len(dangerous)}"); print("GITHUB VISIBILITY: NOT VERIFIED EXTERNALLY"); print(f"DEPLOYMENT GATE: {qa['deployment_gate']}"); print(f"AUDIT: {AUDIT/'22_pre_push_repository_qa.csv'}")
raise SystemExit(0 if not failures else 1)

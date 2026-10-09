"""Screen staged private repository for secrets/dangerous files and hash it."""
from pathlib import Path
import hashlib,json,re,csv
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; REPO=ROOT/"github_private"/"repository"; AUD=ROOT/"github_private"/"audit"; AUD.mkdir(parents=True,exist_ok=True)
if not REPO.is_dir(): raise FileNotFoundError(f"Private staging repository missing: {REPO}")
SECRET_PATTERNS={
 "AWS access key":re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
 "GitHub token":re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
 "Slack token":re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b"),
 "Private key header":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
 "Generic credential assignment":re.compile(r"(?i)\b(api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"]?(?!YOUR_|REPLACE_|EXAMPLE)[A-Za-z0-9_./+\-=]{20,}"),
}
DANGEROUS={".parquet",".pq",".feather",".pkl",".pickle",".sqlite",".db",".duckdb",".xls",".xlsx",".zip",".pem",".key",".p12",".pfx"}
ALLOW={".md",".txt",".json",".csv",".html",".css",".js",".yml",".yaml",".toml",".py",".sh",".gitignore"}
files=sorted(p for p in REPO.rglob("*") if p.is_file())
hits=[]; dangerous=[]
for p in files:
    rel=p.relative_to(REPO).as_posix()
    if p.suffix.lower() in DANGEROUS: dangerous.append(rel)
    if p.suffix.lower() not in ALLOW and p.name not in {".gitignore"}: continue
    text=p.read_text(encoding="utf-8",errors="ignore")
    for label,pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            # Record location and rule only; never print or store matched secret text.
            hits.append({"path":rel,"rule":label,"line":text.count("\n",0,match.start())+1})
checks=[("Repository staging directory exists",True),("No credential patterns detected",not hits),("No dangerous file extensions",not dangerous),("Private mode policy documented",True),("Hash inventory covers all staged files",True)]
with (REPO/"SECURITY.md").open("w",encoding="utf-8") as f:
    f.write("# Private repository security policy\n\nThis repository is intended for private, controlled review. Keep repository visibility private until licensing, privacy, and source-permission reviews are complete.\n\n- Require multifactor authentication for maintainers.\n- Use least-privilege access and review membership periodically.\n- Protect the default branch and require reviewed changes.\n- Never commit credentials, raw/person-level data, or local source datasets.\n- Treat detected credentials as compromised: revoke and replace them; do not preserve values in audit output.\n- Verify the SHA-256 manifest before accepting package changes.\n- Security controls support detection and risk reduction; they do not guarantee immunity from compromise.\n")
files=sorted(p for p in REPO.rglob("*") if p.is_file())
inventory=[{"path":p.relative_to(REPO).as_posix(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size_bytes":p.stat().st_size} for p in files]
policy={"status":"PASS" if all(ok for _,ok in checks) else "FAIL","scope":"Secret-pattern and dangerous-extension screening of staged repository text/files; this is not a guarantee against compromise.","secret_hits":hits,"dangerous_files":dangerous,"checks":[{"check":n,"status":"PASS" if ok else "FAIL"} for n,ok in checks],"repository_security_controls":{"private_visibility_required":True,"multifactor_authentication_required":True,"least_privilege_access":True,"protected_branch_recommended":True,"github_publish_performed":False},"files":inventory,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
manifest_path=AUD/"19_private_repository_security_manifest.json"; manifest_path.write_text(json.dumps(policy,indent=2),encoding="utf-8")
with (AUD/"19_private_repository_security.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["check","status","details"])
    w.writerows((n,"PASS" if ok else "FAIL","" if ok else "See security manifest") for n,ok in checks)
print("VERSION C — 19 PRIVATE REPOSITORY SECURITY")
print(f"STATUS: {policy['status']}"); print(f"FILES SCANNED/HASHED: {len(files)}"); print(f"SECRET FINDINGS: {len(hits)}"); print(f"DANGEROUS FILES: {len(dangerous)}")
print(f"SECURITY AUDIT: {AUD/'19_private_repository_security.csv'}"); print(f"HASH MANIFEST: {manifest_path}")
raise SystemExit(0 if policy["status"]=="PASS" else 1)

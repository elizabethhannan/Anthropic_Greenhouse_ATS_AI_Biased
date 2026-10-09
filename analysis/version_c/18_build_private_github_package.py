"""Stage a private GitHub repository copy from the frozen evidence package.

This is local-only. It does not modify the source package or publish remotely.
"""
from pathlib import Path
import shutil,json,hashlib
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/"final_evidence_package"
DEST=ROOT/"github_private"/"repository"
BASELINE=ROOT/"audit"/"17_final_integrity_manifest.json"
if not SOURCE.is_dir(): raise FileNotFoundError(f"Frozen package missing: {SOURCE}")
if not BASELINE.is_file(): raise FileNotFoundError(f"Integrity baseline missing: {BASELINE}")
baseline=json.loads(BASELINE.read_text(encoding="utf-8"))
expected={item["path"]:item["sha256"] for item in baseline["files"]}
source_files={p.relative_to(SOURCE).as_posix():p for p in SOURCE.rglob("*") if p.is_file()}
if set(source_files)!=set(expected):
    raise RuntimeError("Frozen package file set differs from its integrity baseline; refusing to stage.")
for rel,path in source_files.items():
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected[rel]:
        raise RuntimeError(f"Frozen package hash mismatch; refusing to stage: {rel}")
DEST.mkdir(parents=True,exist_ok=True)
for rel,path in source_files.items():
    target=DEST/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,target)
copied={p.relative_to(DEST).as_posix() for p in DEST.rglob("*") if p.is_file()}
if copied!=set(expected): raise RuntimeError("Staged repository contains an unexpected or missing file.")
stage_manifest={"status":"STAGED_PRIVATE_REPOSITORY_COPY","source":str(SOURCE),"destination":str(DEST),"frozen_fingerprint":baseline["package_fingerprint_sha256"],"files":[{"path":rel,"sha256":hashlib.sha256((DEST/rel).read_bytes()).hexdigest(),"size_bytes":(DEST/rel).stat().st_size} for rel in sorted(copied)],"generated_at_utc":datetime.now(timezone.utc).isoformat(),"github_publish_performed":False,"source_package_modified":False}
manifest_path=DEST.parent/"18_private_package_manifest.json"
manifest_path.write_text(json.dumps(stage_manifest,indent=2),encoding="utf-8")
print("VERSION C — 18 BUILD PRIVATE GITHUB PACKAGE")
print("STATUS: STAGED; SOURCE FINGERPRINT VERIFIED")
print(f"FILES COPIED: {len(copied)}")
print(f"DESTINATION: {DEST}")
print(f"MANIFEST: {manifest_path}")
print("GITHUB PUBLISH PERFORMED: NO")

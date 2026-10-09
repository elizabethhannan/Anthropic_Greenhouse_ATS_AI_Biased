"""Verify original frozen package files against Phase 19 baseline fingerprint."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parent; PACKAGE=ROOT/"final_evidence_package"
BASELINE=ROOT/"audit"/"17_final_integrity_manifest.json"
EXPECTED_FINGERPRINT="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
if not PACKAGE.exists(): raise FileNotFoundError(f"Frozen package missing: {PACKAGE}")
if not BASELINE.is_file(): raise FileNotFoundError(f"Integrity baseline missing: {BASELINE}")
saved=json.loads(BASELINE.read_text(encoding="utf-8")); saved_fp=saved.get("package_fingerprint_sha256")
actual_files=sorted(p for p in PACKAGE.rglob("*") if p.is_file())
actual={p.relative_to(PACKAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in actual_files}
expected={item["path"]:item["sha256"] for item in saved.get("files",[])}
set_match=set(actual)==set(expected); hash_mismatches=sorted(k for k in set(actual)&set(expected) if actual[k]!=expected[k])
baseline_payload={k:v for k,v in saved.items() if k!="package_fingerprint_sha256"}
computed_fp=hashlib.sha256(json.dumps(baseline_payload,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
fingerprint_match=(saved_fp==EXPECTED_FINGERPRINT==computed_fp)
ok=set_match and not hash_mismatches and fingerprint_match
audit_dir=ROOT/"audit"; audit_dir.mkdir(exist_ok=True)
record={"status":"PASS" if ok else "FAIL","expected_fingerprint":EXPECTED_FINGERPRINT,"saved_baseline_fingerprint":saved_fp,"recomputed_baseline_fingerprint":computed_fp,"file_set_match":set_match,"expected_file_count":len(expected),"actual_file_count":len(actual),"hash_mismatches":hash_mismatches,"baseline_path":str(BASELINE),"package_path":str(PACKAGE)}
(audit_dir/"20_frozen_integrity_verification.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
print("VERSION C — 20 VERIFY FROZEN INTEGRITY")
print(f"EXPECTED FINGERPRINT: {EXPECTED_FINGERPRINT}")
print(f"SAVED BASELINE FINGERPRINT: {saved_fp}")
print(f"BASELINE FINGERPRINT RECOMPUTES: {computed_fp}")
print(f"FILE SET MATCH: {set_match}"); print(f"CONTENT HASH MISMATCHES: {len(hash_mismatches)}")
print(f"FROZEN PACKAGE INTEGRITY: {'PASS' if ok else 'FAIL'}")
print(f"VERIFICATION RECORD: {audit_dir/'20_frozen_integrity_verification.json'}")
if hash_mismatches: print("MISMATCHED PATHS:"); [print(f"- {p}") for p in hash_mismatches]
if not set_match: print("Package paths differ from the saved baseline. Expected/actual:",len(expected),len(actual))
raise SystemExit(0 if ok else 1)

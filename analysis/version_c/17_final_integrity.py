"""Fingerprint the final local package; no publication action is performed."""
from pathlib import Path
import hashlib,json,csv
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PACKAGE=ROOT/"final_evidence_package"; AUD=ROOT/"audit"
def sha256(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
 return h.hexdigest()
files=sorted(p for p in PACKAGE.rglob("*") if p.is_file())
inventory=[{"path":p.relative_to(PACKAGE).as_posix(),"sha256":sha256(p),"size_bytes":p.stat().st_size} for p in files]
payload={"status":"FINGERPRINTED","generated_at_utc":datetime.now(timezone.utc).isoformat(),"package_path":str(PACKAGE),"file_count":len(inventory),"files":inventory,"publication_status":"HOLD / REVIEW REQUIRED","github_publish_performed":False,"licensing_certified":False,"privacy_certified":False,"source_permission_certified":False,"scope":"SHA-256 inventory of final package files. Fingerprint is an integrity identifier, not legal clearance."}
canonical=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("utf-8"); payload["package_fingerprint_sha256"]=hashlib.sha256(canonical).hexdigest()
AUD.mkdir(exist_ok=True); path=AUD/"17_final_integrity_manifest.json"; path.write_text(json.dumps(payload,indent=2),encoding="utf-8")
with (AUD/"17_final_integrity_inventory.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=["path","sha256","size_bytes"]); w.writeheader(); w.writerows(inventory)
print("VERSION C — 19 FINAL INTEGRITY FINGERPRINT"); print(f"PACKAGE FILES: {len(inventory)}"); print(f"PACKAGE FINGERPRINT SHA256: {payload['package_fingerprint_sha256']}"); print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED"); print(f"MANIFEST: {path}")

"""Publication gate: package completeness only; human reviews remain required."""
from pathlib import Path
import json,csv,hashlib
ROOT=Path(__file__).resolve().parent; PACKAGE=ROOT/"final_evidence_package"; AUD=ROOT/"audit"; AUD.mkdir(exist_ok=True)
required=["README.md","final_executive_dashboard_d3.html","VERSION_C_3_0_EXECUTIVE_BRIEF.md","VERSION_C_3_0_EXECUTIVE_PRESENTATION.html","executive_evidence_v3.json","PACKAGE_MANIFEST.json"]
missing=[name for name in required if not (PACKAGE/name).is_file()]
readme=(PACKAGE/"README.md").read_text(encoding="utf-8") if not missing else ""
required_readme=["606","276","213","1,095","NOT ESTIMABLE FROM PUBLIC DATA","HOLD / REVIEW REQUIRED","Unknown records remain Unknown","No candidate-level Greenhouse-to-hire linkage"]
readme_missing=[phrase for phrase in required_readme if phrase not in readme]
manifest_data=json.loads((PACKAGE/"PACKAGE_MANIFEST.json").read_text(encoding="utf-8")) if not missing else {"files":[]}
hash_failures=[item["path"] for item in manifest_data["files"] if not (PACKAGE/item["path"]).is_file() or hashlib.sha256((PACKAGE/item["path"]).read_bytes()).hexdigest()!=item["sha256"]]
gate={"package_complete":not missing,"readme_content_valid":not readme_missing,"package_manifest_reconciles":not hash_failures,"publication_status":"HOLD / REVIEW REQUIRED","github_publish_performed":False,"licensing_review":"REQUIRED","privacy_review":"REQUIRED","source_permission_review":"REQUIRED","missing_files":missing,"readme_missing_phrases":readme_missing,"manifest_hash_failures":hash_failures,"results_locked":True,"github_repository":"https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased","publication_approved":False,"reason":"This script cannot grant legal, privacy, or source redistribution clearance."}
path=AUD/"16_release_gate.json"; path.write_text(json.dumps(gate,indent=2),encoding="utf-8")
with (AUD/"16_release_gate_checks.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f); w.writerow(["check","status"])
 w.writerows((f"required:{name}","PASS" if name not in missing else "FAIL") for name in required)
 w.writerow(["README required content present","PASS" if not readme_missing else "FAIL"])
 w.writerow(["package manifest hashes reconcile","PASS" if not hash_failures else "FAIL"])
 w.writerow(["publication hold preserved","PASS"]); w.writerow(["no publish performed","PASS"])
print("VERSION C — 18 PUBLICATION / RELEASE GATE"); print(f"PACKAGE COMPLETE: {gate['package_complete']}"); print(f"README CONTENT: {gate['readme_content_valid']}"); print(f"PACKAGE HASHES RECONCILE: {gate['package_manifest_reconciles']}"); print(f"PUBLICATION STATUS: {gate['publication_status']}"); print(f"MISSING FILES: {len(missing)}"); print("LICENSING / PRIVACY / SOURCE PERMISSION: REVIEW REQUIRED"); print(f"GATE: {path}")
raise SystemExit(0 if not missing and not readme_missing and not hash_failures else 1)

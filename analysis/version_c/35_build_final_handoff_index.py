"""Build a C-suite handoff index after all deployment and QA gates pass."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE=ROOT/"github_private"; EXECUTIVE=PRIVATE/"executive_review"; CLOSURE=PRIVATE/"closure"; CLOSURE.mkdir(parents=True,exist_ok=True)
EXPECTED="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"
chain_path=CLOSURE/"34_REPRODUCIBILITY_CHAIN.json"
if not chain_path.is_file(): raise FileNotFoundError("Step 34 passing chain audit is required before Step 35.")
chain=json.loads(chain_path.read_text(encoding="utf-8"))
if chain.get("status")!="PASS" or chain.get("expected_fingerprint")!=EXPECTED: raise RuntimeError("Step 34 chain audit did not pass; handoff index stopped.")
required=[EXECUTIVE/"README.md",EXECUTIVE/"final_executive_dashboard_d3.html",EXECUTIVE/"VERSION_C_3_0_EXECUTIVE_BRIEF.md",EXECUTIVE/"VERSION_C_3_0_EXECUTIVE_PRESENTATION.html",EXECUTIVE/"executive_evidence_v3.json",EXECUTIVE/"REVIEW_STATUS.md",PRIVATE/"PRIVATE_GITHUB_DEPLOYMENT_PLAN.md",PRIVATE/"REPOSITORY_INDEX.md",CLOSURE/"31_POST_DEPLOYMENT_SNAPSHOT.json",CLOSURE/"32_EXECUTIVE_REVIEW_QA.json",CLOSURE/"33_DASHBOARD_SMOKE_TEST.json",chain_path,PRIVATE/"audit"/"30_final_private_deployment_audit.json"]
missing=[str(p) for p in required if not p.is_file()]
if missing: raise FileNotFoundError("Handoff sources missing: "+", ".join(missing))
manifest_data={"status":"PASS","frozen_fingerprint":EXPECTED,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"artifacts":[{"path":str(p.relative_to(ROOT)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in required],"publication_status":"HOLD / REVIEW REQUIRED","public_release":False,"github_push_performed":True,"private_repository":"https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased","tag":"version-c-v3.0-locked"}
lines=["# VERSION C — VERSION 3.0 C-SUITE HANDOFF","","**Controlled private review copy. Public release remains HOLD / REVIEW REQUIRED.**","",f"Frozen analytical fingerprint: `{EXPECTED}`","", "## Executive artifacts", "", "| Artifact | Location | SHA-256 |", "|---|---|---|"]
for item in manifest_data["artifacts"]: lines.append(f"| {Path(item['path']).name} | `{item['path']}` | `{item['sha256']}` |")
lines += ["", "## Locked evidence", "", "- Observed outcomes: 606 Male / 276 Female / 213 Unknown / 1,095 total.", "- Known-sex Male/Female ratio: 2.20:1.", "- Signal: OBSERVABLE.", "- Prediction: NOT ESTIMABLE FROM PUBLIC DATA.", "- Feedback: EXPLORATORY.", "- No Greenhouse causal claim; no sex inference; no candidate-level posting-to-hire linkage.", "", "The private repository and tag identify the controlled review artifacts. Licensing, privacy, and source-permission review remain required before any public release."]
doc=CLOSURE/"35_FINAL_CSUITE_HANDOFF.md"; doc.write_text("\n".join(lines)+"\n",encoding="utf-8")
manifest_data["handoff_document_sha256"]=hashlib.sha256(doc.read_bytes()).hexdigest()
manifest=CLOSURE/"35_FINAL_CSUITE_HANDOFF_MANIFEST.json"; manifest.write_text(json.dumps(manifest_data,indent=2),encoding="utf-8")
print("VERSION C — 35 FINAL C-SUITE HANDOFF INDEX"); print("STATUS: PASS"); print(f"FROZEN FINGERPRINT: {EXPECTED}"); print(f"HANDOFF: {doc}"); print(f"MANIFEST: {manifest}")

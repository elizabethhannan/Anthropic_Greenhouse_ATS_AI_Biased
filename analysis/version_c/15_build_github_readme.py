"""Create local repository README; this script does not publish it."""
from pathlib import Path
import json,csv,hashlib
ROOT=Path(__file__).resolve().parent; PACKAGE=ROOT/"final_evidence_package"
E=json.loads((PACKAGE/"executive_evidence_v3.json").read_text(encoding="utf-8")); o=E["observed_outcomes"]
readme=f'''# Anthropic Greenhouse ATS AI Bias — Version C

## Version 3.0: Human-AI Employment Intelligence & Governance

This repository contains a controlled research and evidence architecture examining gender representation in an observed Anthropic hiring environment and measurement gaps across an AI-assisted employment system.

## Canonical observed outcome

| Category | Count |
|---|---:|
| Male | {o['male']:,} |
| Female | {o['female']:,} |
| Unknown | {o['unknown']:,} |
| Total | {o['total']:,} |

Known-sex composition is {o['male_share_known']:.1%} Male and {o['female_share_known']:.1%} Female; the observed Male/Female ratio is {o['male_female_ratio']:.2f}:1. Unknown records remain Unknown.

## Analytical status

| Layer | Status |
|---|---|
| Signal | OBSERVABLE |
| Prediction | NOT ESTIMABLE FROM PUBLIC DATA |
| Feedback | EXPLORATORY |

No candidate-level model was fit. The public evidence does not contain sufficient independent matched outcome cells or candidate-stage outcomes. No applicant denominators were manufactured.

## Methodological controls

- No sex inference; Unknown remains Unknown.
- No candidate-level Greenhouse-to-hire linkage.
- No synthetic candidates.
- No claim that Greenhouse caused the observed disparity.
- The research-classified subset is not added to the overall outcomes.

The observed outcome disparity does not establish adverse impact or its cause. The package identifies evidence gaps and a proposed Human-AI Employment Intelligence & Governance function.

## Publication status

**HOLD / REVIEW REQUIRED.** Licensing, privacy, and source-permission reviews are required before public release. The local package has not been published.

Repository destination metadata: {E['github_repository_destination']}
'''
(PACKAGE/"README.md").write_text(readme,encoding="utf-8")
entries=[]
for p in sorted(x for x in PACKAGE.rglob("*") if x.is_file() and x.name not in {"PACKAGE_MANIFEST.json","PACKAGE_MANIFEST.csv"}):
 entries.append({"path":p.relative_to(PACKAGE).as_posix(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size_bytes":p.stat().st_size})
manifest={"status":"STAGED","files":entries,"file_count":len(entries),"publication_status":"HOLD / REVIEW REQUIRED","github_publish_performed":False,"manifest_hash_scope":"All package files except the manifest files themselves."}
(PACKAGE/"PACKAGE_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
with (PACKAGE/"PACKAGE_MANIFEST.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=["path","sha256","size_bytes"]); w.writeheader(); w.writerows(entries)
print("VERSION C — 17 GITHUB README"); print("STATUS: CREATED LOCALLY; NOT PUBLISHED"); print(f"README: {PACKAGE/'README.md'}"); print(f"PACKAGE FILES HASHED: {len(entries)}"); print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED")

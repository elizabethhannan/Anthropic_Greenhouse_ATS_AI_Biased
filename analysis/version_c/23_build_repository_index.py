"""Create a local human/machine index of staged private repository files."""
from pathlib import Path
import hashlib,json,csv
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; PRIVATE_ROOT=ROOT/"github_private"; REPOSITORY=PRIVATE_ROOT/"repository"; AUDIT=PRIVATE_ROOT/"audit"
if not REPOSITORY.is_dir(): raise FileNotFoundError(f"Staged repository missing: {REPOSITORY}")
files=sorted(p for p in REPOSITORY.rglob("*") if p.is_file())
descriptions={"README.md":"Repository overview, observed outcome, evidence status, and publication boundary.","final_executive_dashboard_d3.html":"Executive dashboard presentation layer.","VERSION_C_3_0_EXECUTIVE_BRIEF.md":"Controlled-review executive brief.","VERSION_C_3_0_EXECUTIVE_PRESENTATION.html":"Self-contained executive presentation.","executive_evidence_v3.json":"Consolidated aggregate evidence payload.","executive_evidence_metrics.csv":"Flattened aggregate evidence metrics.","08_human_ai_workflow_evidence_map.csv":"Future internal evidence requirements by workflow stage.","SECURITY.md":"Private repository handling and security policy."}
entries=[{"path":p.relative_to(REPOSITORY).as_posix(),"description":descriptions.get(p.name,"Supporting audit, manifest, or aggregate executive artifact."),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size_bytes":p.stat().st_size} for p in files]
index={"status":"INDEXED","repository_path":str(REPOSITORY),"file_count":len(entries),"files":entries,"canonical_outcomes":{"male":606,"female":276,"unknown":213,"total":1095,"male_female_ratio":"2.20:1"},"analytical_status":{"signal":"OBSERVABLE","prediction":"NOT ESTIMABLE FROM PUBLIC DATA","feedback":"EXPLORATORY"},"publication_status":"HOLD / REVIEW REQUIRED","github_publish_performed":False,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
AUDIT.mkdir(parents=True,exist_ok=True)
(PRIVATE_ROOT/"REPOSITORY_INDEX.json").write_text(json.dumps(index,indent=2),encoding="utf-8")
with (PRIVATE_ROOT/"REPOSITORY_INDEX.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=["path","description","sha256","size_bytes"]); w.writeheader(); w.writerows(entries)
lines=["# Private repository index","",f"Staged repository: `{REPOSITORY}`","",f"Files: {len(entries)}","","| Path | Description | SHA-256 |","|---|---|---|"]
lines += [f"| `{x['path']}` | {x['description']} | `{x['sha256']}` |" for x in entries]
lines += ["","**Publication status: HOLD / REVIEW REQUIRED.** No GitHub push has been performed."]
(PRIVATE_ROOT/"REPOSITORY_INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print("VERSION C — 23 BUILD PRIVATE REPOSITORY INDEX"); print(f"FILES INDEXED: {len(entries)}"); print(f"INDEX: {PRIVATE_ROOT/'REPOSITORY_INDEX.md'}"); print(f"JSON: {PRIVATE_ROOT/'REPOSITORY_INDEX.json'}"); print(f"CSV: {PRIVATE_ROOT/'REPOSITORY_INDEX.csv'}"); print("STAGED REPOSITORY MODIFIED: NO")

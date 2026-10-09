"""Close Version C v3.0 only after all deployment and closure gates pass.

This script never changes the frozen analytical package or the locked Git
repository. It writes closure documents only after validating every required
prior artifact and the frozen package's exact saved fingerprint.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys

ROOT=Path(__file__).resolve().parent
PRIVATE=ROOT/"github_private"
CLOSURE=PRIVATE/"closure"
AUDIT=PRIVATE/"audit"
EXPECTED_FROZEN_FINGERPRINT="6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0"

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def load_json(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def frozen_package_check():
    package=ROOT/"final_evidence_package"
    baseline_path=ROOT/"audit"/"17_final_integrity_manifest.json"
    if not package.is_dir() or not baseline_path.is_file():
        return False,"Frozen package or saved integrity baseline is missing.",None
    baseline=load_json(baseline_path)
    expected={x["path"]:x["sha256"] for x in baseline.get("files",[])}
    actual={p.relative_to(package).as_posix():sha256_file(p) for p in package.rglob("*") if p.is_file()}
    payload={k:v for k,v in baseline.items() if k!="package_fingerprint_sha256"}
    computed=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    ok=(expected==actual and computed==EXPECTED_FROZEN_FINGERPRINT==baseline.get("package_fingerprint_sha256"))
    return ok,"Frozen package hashes and fingerprint reconcile." if ok else "Frozen package differs from the saved fingerprint.",computed

def main()->int:
    required={
        "Step 30 final deployment audit":AUDIT/"30_final_private_deployment_audit.json",
        "Step 31 post-deployment snapshot":CLOSURE/"31_POST_DEPLOYMENT_SNAPSHOT.json",
        "Step 32 executive-review QA":CLOSURE/"32_EXECUTIVE_REVIEW_QA.json",
        "Step 33 dashboard smoke test":CLOSURE/"33_DASHBOARD_SMOKE_TEST.json",
        "Step 34 reproducibility-chain audit":CLOSURE/"34_REPRODUCIBILITY_CHAIN.json",
        "Step 35 handoff document":CLOSURE/"35_FINAL_CSUITE_HANDOFF.md",
        "Step 35 handoff manifest":CLOSURE/"35_FINAL_CSUITE_HANDOFF_MANIFEST.json",
    }
    print("VERSION C — STEP 36 FINAL PROJECT CLOSURE")
    checks=[]; missing=[]; loaded={}
    for label,path in required.items():
        exists=path.is_file(); checks.append((label,exists))
        if not exists: missing.append((label,path))
        elif path.suffix.lower()==".json":
            try: loaded[label]=load_json(path)
            except Exception as exc: checks.append((f"{label} is valid JSON",False)); print(f"INVALID JSON: {path} :: {exc}")
    if missing:
        print("STATUS: NOT CLOSED — PREREQUISITES MISSING")
        print("MISSING REQUIRED ARTIFACTS:")
        for label,path in missing: print(f"- {label}: {path}")
        print("No closure artifacts were written.")
        return 1

    step30=loaded.get("Step 30 final deployment audit",{})
    checks.append(("Step 30 final deployment audit passed",step30.get("final_result")=="PASS" and step30.get("status")=="PASS"))
    checks.append(("Step 30 all five integrity checks passed",isinstance(step30.get("checks"),dict) and len(step30["checks"])==5 and all(step30["checks"].values())))
    checks.append(("Step 30 frozen fingerprint matches",step30.get("frozen_expected_fingerprint")==EXPECTED_FROZEN_FINGERPRINT))
    checks.append(("Step 30 publication hold preserved",step30.get("publication_status")=="HOLD / REVIEW REQUIRED"))

    snapshot=loaded.get("Step 31 post-deployment snapshot",{})
    qa32=loaded.get("Step 32 executive-review QA",{})
    smoke33=loaded.get("Step 33 dashboard smoke test",{})
    chain34=loaded.get("Step 34 reproducibility-chain audit",{})
    handoff35=loaded.get("Step 35 handoff manifest",{})
    for label,obj in [("Step 31 snapshot passed",snapshot),("Step 32 executive-review QA passed",qa32),("Step 33 dashboard smoke test passed",smoke33),("Step 34 reproducibility chain passed",chain34)]:
        checks.append((label,obj.get("status")=="PASS"))
    checks.append(("Step 35 handoff manifest passed",handoff35.get("status")=="PASS"))
    checks.append(("Step 35 frozen fingerprint matches",handoff35.get("frozen_fingerprint")==EXPECTED_FROZEN_FINGERPRINT))

    frozen_ok,frozen_detail,actual_fp=frozen_package_check()
    checks.append(("Frozen analytical package fingerprint unchanged",frozen_ok))
    # Confirm canonical values from the frozen staged executive evidence.
    evidence_path=ROOT/"final_evidence_package"/"executive_evidence_v3.json"
    evidence=load_json(evidence_path) if evidence_path.is_file() else {}
    outcomes=evidence.get("observed_outcomes",{})
    canonical=(outcomes.get("male")==606 and outcomes.get("female")==276 and outcomes.get("unknown")==213 and outcomes.get("total")==1095 and abs(outcomes.get("male_female_ratio",0)-2.20)<0.01)
    checks.append(("Canonical observed outcomes reconcile",canonical))
    checks.append(("Analytical statuses and public hold preserved",evidence.get("diagnostics")=={"signal":"OBSERVABLE","prediction":"NOT ESTIMABLE FROM PUBLIC DATA","feedback":"EXPLORATORY"} and evidence.get("publication_status")=="HOLD / REVIEW REQUIRED"))

    failures=[label for label,ok in checks if not ok]
    print("CLOSURE CHECKS:")
    for label,ok in checks: print(f"{'PASS' if ok else 'FAIL'} — {label}")
    print(f"{len(failures)} FAIL")
    if failures:
        print("STATUS: NOT CLOSED — GATE FAILURE")
        print(f"FROZEN CHECK: {frozen_detail}; fingerprint={actual_fp}")
        print("No closure artifacts were written.")
        return 1

    CLOSURE.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    closure_md=f'''# VERSION C — VERSION 3.0 FINAL CLOSURE

**Status: CLOSED**  
**Closed at (UTC):** {now}

## Frozen analytical fingerprint

`{EXPECTED_FROZEN_FINGERPRINT}`

## Observed outcome

- Male: 606
- Female: 276
- Unknown: 213
- Total: 1,095
- Known-sex composition: 68.7% Male / 31.3% Female
- Male/Female ratio: 2.20:1

## Analytical status

- Signal: OBSERVABLE
- Prediction: NOT ESTIMABLE FROM PUBLIC DATA
- Feedback: EXPLORATORY

No sex inference, synthetic candidates, applicant-denominator fabrication, or candidate-level Greenhouse-to-hire linkage was used. The observed disparity does not establish Greenhouse causality.

## Publication boundary

Public release: **NO**  
Publication status: **HOLD / REVIEW REQUIRED**

The private deployment and integrity checks do not certify licensing, privacy, or redistribution permission.

## Closure checks

All {len(checks)} closure checks passed. Version C v3.0 is closed. Future analytical work must proceed in a new version/workstream; do not modify the frozen Version C package.
'''
    doc_path=CLOSURE/"36_VERSION_C_FINAL_CLOSURE.md"; doc_path.write_text(closure_md,encoding="utf-8")
    manifest={"status":"CLOSED","version":"Version C — Version 3.0","closed_at_utc":now,"frozen_analytical_fingerprint":EXPECTED_FROZEN_FINGERPRINT,"frozen_package_recomputed_fingerprint":actual_fp,"closure_document":doc_path.name,"closure_document_sha256":sha256_file(doc_path),"prerequisite_artifacts":{label:{"path":str(path),"sha256":sha256_file(path)} for label,path in required.items()},"canonical_outcomes":{"male":606,"female":276,"unknown":213,"total":1095,"known_sex_male_share":606/882,"known_sex_female_share":276/882,"male_female_ratio":606/276},"analytical_status":{"signal":"OBSERVABLE","prediction":"NOT ESTIMABLE FROM PUBLIC DATA","feedback":"EXPLORATORY"},"public_release":False,"publication_status":"HOLD / REVIEW REQUIRED","checks":[{"check":label,"status":"PASS"} for label,_ in checks],"future_work_boundary":"Any additional research must use a new version/workstream and must not mutate the frozen Version C package."}
    manifest_path=CLOSURE/"36_VERSION_C_FINAL_CLOSURE_MANIFEST.json"
    canonical=json.dumps(manifest,sort_keys=True,separators=(",",":")).encode("utf-8"); manifest["closure_manifest_sha256"]=hashlib.sha256(canonical).hexdigest()
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("STATUS: CLOSED")
    print("OBSERVED OUTCOME"); print("MALE:       606"); print("FEMALE:     276"); print("UNKNOWN:    213"); print("TOTAL:      1095")
    print("KNOWN-SEX COMPOSITION:"); print("MALE:       68.7%"); print("FEMALE:     31.3%"); print("RATIO:      2.20:1")
    print("ANALYTICAL STATUS"); print("SIGNAL:      OBSERVABLE"); print("PREDICTION:  NOT ESTIMABLE FROM PUBLIC DATA"); print("FEEDBACK:    EXPLORATORY")
    print("PUBLIC RELEASE: NO"); print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED")
    print("VERSION C — VERSION 3.0 IS NOW CLOSED.")
    print("DO NOT MODIFY THE FROZEN VERSION.")
    print(f"CLOSURE DOCUMENT: {doc_path}"); print(f"CLOSURE MANIFEST: {manifest_path}")
    return 0

if __name__=="__main__": raise SystemExit(main())

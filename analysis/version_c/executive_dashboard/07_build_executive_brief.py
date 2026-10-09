"""Build a controlled-review executive brief from frozen evidence."""
from pathlib import Path
import json, hashlib
from datetime import datetime, timezone

BASE=Path(__file__).resolve().parent; OUT=BASE/"outputs"; OUT.mkdir(parents=True,exist_ok=True)
E=json.loads((OUT/"executive_evidence_v3.json").read_text(encoding="utf-8")); o=E["observed_outcomes"]; g=E["greenhouse_postings"]; r=E["research_classified_outcomes"]
repo=E["github_repository_destination"]
brief=f'''# VERSION C — VERSION 3.0

## Human-AI Employment Intelligence & Governance

**Controlled Executive Review**

### Executive Question

> {E["executive_question"]}

## Executive Finding

A measurable gender-representation signal is visible in the observed hiring environment. Public evidence does not establish where within the AI-assisted employment system that disparity originates.

| Outcome | Count |
|---|---:|
| Male | {o['male']:,} |
| Female | {o['female']:,} |
| Unknown | {o['unknown']:,} |
| **Total** | **{o['total']:,}** |

Among records with known Male/Female values, the observed composition is **{o['male_share_known']:.1%} Male** and **{o['female_share_known']:.1%} Female**, a **{o['male_female_ratio']:.2f}:1** ratio. Unknown remains Unknown.

This is an observed outcome disparity in the available public data. It does not establish that Greenhouse caused the disparity.

## Evidence layers

| Layer | Current evidence | Interpretation |
|---|---|---|
| SIGNAL | OBSERVABLE | Public recruiting signals can be measured descriptively. |
| PREDICTION | NOT ESTIMABLE FROM PUBLIC DATA | 3 eligible matched role/month cells; no Female outcome cells; no model was fit. |
| FEEDBACK | EXPLORATORY | Temporal coverage and sample size are limited. |

There are {g['all_postings']:,} postings: {g['established_dates_in_window']:,} with established dates in the study window, {g['archive_capture_only']:,} archive-capture-only records, and {g['outside_window']:,} outside-window records. Archive capture dates are not treated as posting dates.

The research-classified subset contains {r['total']} records ({r['male']} Male, {r['female']} Female, {r['unknown']} Unknown). It is a subset and is not added to the overall observed outcomes.

## What the evidence cannot establish

- Applicant or candidate-stage selection rates and adverse impact are not estimable from public data because demographic stage denominators are unavailable.
- The public data do not link Greenhouse postings to individual hires.
- The evidence does not identify a causal mechanism or establish that a particular system caused the disparity.
- No sex inference or synthetic candidate records were used.

## Executive proposition

Version C proposes a **Human-AI Employment Intelligence & Governance** function to instrument recruiting, human decision-making, employment opportunity, and advancement so that the origin of disparities can be investigated and interventions measured.

**MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS**

## Release status

**PUBLICATION STATUS: HOLD / REVIEW REQUIRED.** Human licensing, privacy, and source-permission review is required before public release.

Repository destination metadata: {repo}

Generated {datetime.now(timezone.utc).isoformat()}.
'''
path=OUT/"VERSION_C_3_0_EXECUTIVE_BRIEF.md"; path.write_text(brief,encoding="utf-8")
manifest={"status":"BUILT_FROM_FROZEN_EVIDENCE","brief":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"evidence_source":str(OUT/"executive_evidence_v3.json"),"publication_status":"HOLD / REVIEW REQUIRED","github_repository_destination":repo,"github_publish_performed":False}
(OUT/"07_executive_brief_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("VERSION C — 13 EXECUTIVE BRIEF"); print("STATUS: BUILT"); print(f"BRIEF: {path}"); print(f"MANIFEST: {OUT/'07_executive_brief_manifest.json'}"); print("PUBLICATION STATUS: HOLD / REVIEW REQUIRED")

# Version C build sequence

## Phase 0 — Freeze the evidence base

Completed in this folder. The manifest records the current source versions, R2 locations, extraction times, source coverage, classification artifacts, and code hashes available locally. The headline audit uses distinct people and maps only the original `SEX` source field to `MALE`, `FEMALE`, or `UNKNOWN`. It does not change Plan A files or infer sex.

## Phase 1 — Build the analysis-ready signal table

Create new Version C code and outputs in this folder. Join the frozen posting-level language metrics and hiring outcomes only at a prespecified aggregate level. Keep these units distinct:

- Hiring outcome: distinct observed person.
- Job posting: a Greenhouse posting, retaining current/historical status and date-evidence class.
- Posting-language signal: measured description feature with source text/context and a manual-review flag.

Do not treat 1,246 posting records as 1,246 in-window postings. Keep the 514 Greenhouse-dated records, 617 archive-capture-only candidates, and other date classes separate. Do not use post-period or undated archive material as dated exposure without an explicit sensitivity analysis.

## Phase 2 — RQ1 descriptive signal report

Describe role mix, research/fellowship representation, description availability, named-person candidates, explicit text references, and posting-date evidence. Treat automated person/name and text matches as review candidates, not verified identity or intent. Report missingness and date-class denominators alongside every percentage.

## Phase 3 — RQ2 predictive association

After Phase 1 features and denominators are reviewed, compare prespecified Logistic Regression and Gradient Boosting models against a simple baseline. Use observed Male/Female source values as the binary target; retain Unknown in the audit and report its share, but do not silently impute or infer a binary outcome. Define the prediction unit, time alignment, train/test separation, feature cutoff, missing-data handling, calibration, and uncertainty before model fitting. Report predictive association only, not causation or internal workflow fairness.

## Phase 4 — RQ3 exploratory temporal association

Use only explicitly time-supported candidate-facing signals and observed start composition. Preserve the current Dewey coverage gap: August/September have no observed starts in this snapshot, which does not mean no hiring occurred. Describe timing and coverage before any lagged comparison; use exploratory language and no causal claim.

## Phase 5 — Executive report and governance boundary

State that observed outcome composition and public candidate-facing signals are measurable while internal matching configuration, candidate-level funnel stages, recommendations, and recruiter overrides are not present. Do not claim Greenhouse is biased or that public signals caused observed outcomes.

## Paused questions

- RQ4 internal AI decision path: requires internal candidate-level Greenhouse/Talent Matching data.
- RQ5 funnel attrition: requires candidate-level stage history.
- RQ6 human/AI override: requires recommendations and recruiter override logs.

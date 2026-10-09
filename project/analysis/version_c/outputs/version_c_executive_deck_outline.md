# Version C — Executive / ML Scientist Presentation Outline

**Evidence boundary:** Frozen Phase 7–9 outputs only; no new statistical analysis.
**Core thesis:** MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS.
**Outcome counts:** 606 MALE / 276 FEMALE / 213 UNKNOWN (N=1,095; known-sex N=882).

## Slide 1: The executive question

Frame what public evidence can and cannot tell us.

Evidence: outputs/executive_brief.md; outputs/executive_summary.json

## Slide 2: Why model fairness is not enough

Separate model, workflow, and outcome fairness questions.

Evidence: outputs/dashboard_evidence_map.csv; outputs/executive_brief.md

## Slide 3: Research architecture

Show the provenance-first evidence pipeline and separate outcome layer.

Evidence: outputs/executive_summary.json; audit/executive_dashboard_validation.json

## Slide 4: Observed outcome environment

Present the source-sex outcome counts and missingness without imputing Unknown.

Evidence: outputs/dashboard_outcome_distribution.csv; outputs/executive_summary.json; outputs/executive_visuals/01_observed_outcomes.png

## Slide 5: SIGNAL — what candidates can see

Describe the public Greenhouse corpus and recovered descriptions.

Evidence: outputs/dashboard_evidence_map.csv; outputs/dashboard_signal_findings.csv

## Slide 6: PREDICTION — not estimable

Report the role/month sample limitation without manufacturing model performance.

Evidence: outputs/dashboard_predictive_findings.csv; outputs/executive_summary.json

## Slide 7: FEEDBACK — exploratory and coverage-limited

Keep ecological timing separate from causal or individual linkage.

Evidence: outputs/dashboard_evidence_map.csv; outputs/dashboard_feedback_findings.csv; outputs/executive_brief.md

## Slide 8: What public data cannot see

Identify the unavailable internal AI and recruiting workflow records.

Evidence: outputs/dashboard_limitations.csv; outputs/executive_visuals/05_data_gaps.png

## Slide 9: Internal audit architecture

Specify the records required to evaluate deployed human-AI workflow treatment.

Evidence: outputs/dashboard_evidence_map.csv; outputs/dashboard_limitations.csv

## Slide 10: Research conclusions

Summarize only the conclusions supported by the frozen evidence.

Evidence: outputs/executive_brief.md; outputs/executive_summary.json

## Slide 11: Evidence that would close the gap

Translate governance questions into concrete data requirements.

Evidence: outputs/dashboard_limitations.csv; outputs/executive_visuals/05_data_gaps.png

## Slide 12: ML / HXO research contribution

Position the contribution as a reproducible method and system-boundary analysis.

Evidence: outputs/executive_brief.md; outputs/executive_brief_manifest.json; audit/executive_dashboard_validation.json

## Interpretation boundary

The deck reports an observed outcome pattern, public candidate-facing signals, a predictive analysis that is NOT_ESTIMABLE with the current matched cells, exploratory feedback with temporal coverage limits, and internal data gaps. It does not claim that Greenhouse caused an outcome or assign an individual hire to a posting.

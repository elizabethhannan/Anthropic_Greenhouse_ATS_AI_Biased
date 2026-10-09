# Saved analysis handoff — paused

The user requested a pause after completion, then requested that everything be
saved. No further ingestion, classification changes, or analysis is authorized
by this save request. Resume only on a new user instruction.

## Completed work

- Experience: 80 batches; 1,097 employment rows, 1,095 distinct people.
- Person: streamed 388 of 389 compressed CSV files; all 1,095 target IDs found;
  stopped early as requested. No full source files stored locally. No duplicate
  matches in scanned files; the unscanned file was not checked for duplicates.
- Joined Person source SEX and other selected fields to the existing roles.
- Added uncertainty reason/evidence/display columns without overwriting source
  values or changing classifications.
- Published seven final cross-tabs, each in CSV and Parquet, and read all 14
  outputs back for verification.

## Canonical R2 objects

Bucket: anthropic-bias-data

- filtered/analysis/anthropic_role_dimensions_2026-04-01_to_2026-09-30.parquet
- filtered/person/anthropic_person_profiles_current_snapshot.parquet
- filtered/analysis/anthropic_hires_enriched_current_snapshot.parquet

Final files under outputs/ (both .csv and .parquet):

- anthropic_all_hires_demographics_current_snapshot
- anthropic_research_status_demographics_current_snapshot
- anthropic_research_category_demographics_current_snapshot
- anthropic_engineering_demographics_current_snapshot
- anthropic_leadership_demographics_current_snapshot
- anthropic_uncertainty_reason_demographics_current_snapshot
- anthropic_gender_summary_current_snapshot

Audits:

- audit/person-enrichment/full-person-scan/checkpoint.json
- audit/person-enrichment/full-person-scan/report.json
- audit/person-enrichment/final-sex-role-crosstabs.json
- audit/reason-codes/methodology.json
- audit/reason-codes/reason_counts.parquet
- audit/reason-codes/enriched_before_reason_codes.parquet
- audit/data-freshness/

## Headline results: distinct people

| Population | Female | Male | Source Blank | Total | Female % all | Female % known |
|---|---:|---:|---:|---:|---:|---:|
| All observed hires | 276 | 606 | 213 | 1,095 | 25.21 | 31.29 |
| Existing Research classification | 8 | 19 | 13 | 40 | 20.00 | 29.63 |
| Research + Probable Research | 8 | 19 | 13 | 40 | 20.00 | 29.63 |
| Engineering - General / Unspecified | 51 | 235 | 72 | 358 | 14.25 | 17.83 |

No Probable Research records exist. All eight female research-classified people
are Fellows Researcher. Another 511 people have unresolved research status.
Research is an existing title-based classification, not independent verification.
People may belong to multiple role groups through different employment records;
group totals and monthly distinct-person counts are not necessarily additive.

## Source limitations and preservation rules

Use: "Within the current Dewey / People Data Labs snapshot of observed Anthropic
starts..." Observed starts: April 342, May 339, June 318, July 98, August 0,
September 0. This is not complete April–September 2026 hiring. Zero observations
do not establish zero hiring.

Do not infer SEX from names or any other fields. All 213 unknown values are
Source Blank. No disability field exists in the inspected Person schema.
Do not alter role classifications or reason codes without new authorization.
Existing raw fields remain unchanged. Reason columns are in the enriched table:
sex_reason_code, sex_reason_evidence, sex_display_label, research_reason_code,
research_reason_evidence, research_display_label.
The actual research category source column is ROLE_CATEGORY.

## Local saved work

- final_sex_role_crosstabs.py and final_sex_role_crosstabs_report.json
- finalize_hire_demographics.py and final_demographics_report.json
- add_analysis_reason_codes.py and analysis_reason_codes_report.json
- scan_person_checkpointed.py, person_scan_checkpoint.json, person_scan_progress.log
- test_person_stream.py and person_one_file_test_report.json
- ANALYSIS_INSTRUCTIONS.md and upstream ingestion/classification scripts

Credentials remain in r2.env, which is excluded by .gitignore. No credentials
are copied into this handoff. Analysis datasets remain in R2; do not download
them permanently onto the Mac just to resume work.

Do not rerun finalize_hire_demographics.py casually: it predates the reason-code
columns and would replace the enriched table without those additions. The final
cross-tab script only reads the enriched table and writes summaries.

User preference: provide a completion notification for future large tasks.

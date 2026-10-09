# Version D candidate source SEX matching

Scope: 143 additional provider IDs absent from Version C. The two overlapping Version C IDs are excluded.

Person catalog version 1.2; source version timestamp September 21, 2026; refresh September 28, 2026. All 384 compressed CSV files streamed; only matching rows retained. No full Person dataset saved locally.

| Start month | Male | Female | Source blank / Unknown | Unmatched | Conflicting | Unrecognized |
|---|---:|---:|---:|---:|---:|---:|
| 2026-08 | 81 | 37 | 21 | 0 | 0 | 0 |
| 2026-09 | 2 | 0 | 2 | 0 | 0 | 0 |

Totals: {"MALE": 83, "FEMALE": 37, "UNKNOWN_SOURCE_BLANK": 23, "UNMATCHED": 0, "CONFLICTING_SOURCE_VALUES": 0, "UNRECOGNIZED_SOURCE_VALUE": 0}. Male minus Female: 46. Matched IDs: 143/143. Duplicate extra matching rows: 0.

Raw SEX values preserved; only recognized male/female source values mapped to counts. Missing, unmatched, conflicting and unrecognized values remain separate. No sex inferred from names, titles or other proxies.

Provider-reported SEX is not independently verified. All dates have month precision; source lag and September coverage limitations remain. Version C is unchanged and integrity PASS; fingerprint `6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0`.

Public release: HOLD / REVIEW REQUIRED.

Record-level DATASET_VERSION values: ["35.2"]; frozen Version C values: ["35.1"]. These are distinct from Dewey catalog/DOI version numbers.

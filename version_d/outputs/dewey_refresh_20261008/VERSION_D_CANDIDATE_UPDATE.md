# Version D candidate source update

Checked: 2026-10-09T06:52:23.702928+00:00. Authenticated Dewey project 34978.

Refreshed Experience contains 145 August/September Anthropic employment rows, 145 distinct provider person IDs, and 143 IDs absent from the frozen Version C roster. 2 IDs overlap Version C. These are candidate records, not a revised hiring census.

| Start month | Rows | Distinct IDs | Absent from Version C | Already in Version C |
|---|---:|---:|---:|---:|
| 2026-08 | 141 | 141 | 139 | 2 |
| 2026-09 | 4 | 4 | 4 | 0 |

Exact duplicate rows: 0. Extra rows beyond distinct IDs: 0. IDs with multiple rows: 0.

All 774 refreshed Experience files queried remotely with company/month filters; only matching records retained. No Person bulk payload downloaded.

## Dataset snapshots

- person: frozen metadata {"doiVersionString": "1.1", "doi": "10.82551/wzkb-ts67", "versionTimestamp": "2026-08-20T16:27:42.145000+00:00", "lastRefreshAt": "2026-08-28T07:57:35.419230Z", "rowsCount": 814867031, "sizeBytes": 92923583333}; current metadata {"doiVersionString": "1.2", "doi": "10.82551/wzkb-ts67", "versionTimestamp": "2026-09-21T19:44:59.910000+00:00", "lastRefreshAt": "2026-09-28T07:55:12.239582Z", "rowsCount": 815476877, "sizeBytes": 92733163831}.
- experience: frozen metadata {"doiVersionString": "", "doi": "", "versionTimestamp": "2026-08-20T16:57:50.707000+00:00", "lastRefreshAt": "2026-08-28T08:00:33.136202Z", "rowsCount": 1654638456, "sizeBytes": 195957558296}; current metadata {"doiVersionString": "", "doi": "", "versionTimestamp": "2026-09-21T20:04:29.821000+00:00", "lastRefreshAt": "2026-09-28T08:01:01.665564Z", "rowsCount": 1664446321, "sizeBytes": 191714141596}.

## Coverage limitations

- Observed employment-start records are not a census of hires; profile collection and update lag remain unknown.
- September 21 source version and September 28 export do not establish complete coverage through September 30.
- Company filter is exact Anthropic after lowercase and trim; aliases and subsidiaries may be missed.
- Month and day precision are retained; day precision is not assumed for month-only dates.
- Identity is based on provider PERSON_ID. Changed or duplicate provider IDs can overcount people; no name-based identity inference was performed.
- People already in Version C with a later recorded start are reported separately, not automatically added to frozen totals.
- Monthly distinct counts can overlap and are not additive.
- No Person payload was downloaded. Person current-job records and employment histories were not joined; no SEX field was fetched, inferred, or analyzed.
- Existing project Experience folder remains on the August snapshot; refreshed dataset-level path was queried instead.
- Version D candidate only; no causal, applicant-denominator, demographic, or finalized analytical claims.

The two overlapping person IDs both had April 2026 starts in Version C and now have August 2026 starts in the refreshed source. They are source-date revisions to existing IDs, not newly counted people. Details: `overlap_with_version_c.json`.

The source Experience manifest was reread after the scan and all 774 file names, sizes, modification times and partitions matched the initial manifest.

Export metadata: {"person": {"file_count": 384, "earliest_modified_at": "2026-09-28T07:49:31.493000+00:00", "latest_modified_at": "2026-09-28T07:54:40.981000+00:00", "size_bytes": 92733163831}, "experience": {"file_count": 774, "earliest_modified_at": "2026-09-28T07:51:00.282000+00:00", "latest_modified_at": "2026-09-28T07:58:16.712000+00:00", "size_bytes": 191714141596}}


Frozen Version C integrity: PASS. File set match: True. Content hash mismatches: 0. Fingerprint: `6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0`. Version C unchanged.

Public release: HOLD / REVIEW REQUIRED.

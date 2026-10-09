"""Count distinct candidate IDs using raw source SEX; preserve frozen Version C."""
from pathlib import Path
from collections import Counter
import json, csv, hashlib
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'version_d/outputs/dewey_refresh_20261008'
state=json.loads((OUT/'person_sex_match_checkpoint.json').read_text())
assert len(state['completed'])==len(state['source_manifest'])==384 and not state['errors']
assert json.loads((OUT/'person_manifest_after_sex_scan.json').read_text())==state['source_manifest'], 'Person snapshot changed during scan'
roster=[r for r in csv.DictReader((OUT/'anthropic_aug_sep_candidate_records.csv').open()) if r['already_in_version_c']=='False']
assert len(roster)==143 and {r['PERSON_ID'] for r in roster}==set(state['target_ids'])
source_rows=[r for f in state['completed'].values() for r in f['matches']]
catalog=json.loads((OUT/'person_details.json').read_text())['dataset']
assert sum(f['rows_parsed'] for f in state['completed'].values())==catalog['rowsCount'], 'Parsed row count must reconcile with source metadata'
grouped={pid:[] for pid in state['target_ids']}
for row in source_rows:grouped[row['PERSON_ID']].append(row)
enriched=[]
for person in roster:
    matches=grouped[person['PERSON_ID']]
    raw=sorted({r['SEX'] for r in matches})
    normalized={v.strip().lower() for v in raw if v.strip()}
    if not matches:status='UNMATCHED'
    elif not normalized:status='UNKNOWN_SOURCE_BLANK'
    elif normalized=={'male'}:status='MALE'
    elif normalized=={'female'}:status='FEMALE'
    elif len(normalized)>1:status='CONFLICTING_SOURCE_VALUES'
    else:status='UNRECOGNIZED_SOURCE_VALUE'
    enriched.append({'PERSON_ID':person['PERSON_ID'],'START_DATE':person['START_DATE'],'source_sex_status':status,'raw_sex_values_json':json.dumps(raw),'matching_person_rows':len(matches),'source_files_json':json.dumps(sorted({r['source_file'] for r in matches})),'source_dataset_versions_json':json.dumps(sorted({r['DATASET_VERSION'] for r in matches}))})
categories=['MALE','FEMALE','UNKNOWN_SOURCE_BLANK','UNMATCHED','CONFLICTING_SOURCE_VALUES','UNRECOGNIZED_SOURCE_VALUE']
counts={key:sum(r['source_sex_status']==key for r in enriched) for key in categories}
monthly={m:{key:sum(r['source_sex_status']==key and r['START_DATE']==m for r in enriched) for key in categories} for m in ['2026-08','2026-09']}
baseline=json.loads((ROOT/'analysis/version_c/audit/17_final_integrity_manifest.json').read_text())
package=ROOT/'analysis/version_c/final_evidence_package'
expected={r['path']:r['sha256'] for r in baseline['files']}
actual={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file()}
fp=hashlib.sha256(json.dumps({k:v for k,v in baseline.items() if k!='package_fingerprint_sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert actual==expected and fp==baseline['package_fingerprint_sha256']=='6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0'
summary={'status':'VERSION_D_CANDIDATE_SOURCE_SEX_UPDATE','completed_at_utc':datetime.now(timezone.utc).isoformat(),'target_ids':143,'excluded_version_c_overlaps':2,'person_catalog_version':'1.2','person_version_timestamp':'2026-09-21T19:44:59.910000+00:00','person_refresh_at':'2026-09-28T07:55:12.239582Z','files_scanned':384,'compressed_bytes_streamed':sum(f['compressed_bytes_read'] for f in state['completed'].values()),'source_rows_parsed':sum(f['rows_parsed'] for f in state['completed'].values()),'matched_ids':sum(bool(v) for v in grouped.values()),'matching_person_rows':len(source_rows),'extra_matching_rows_over_matched_ids':sum(max(0,len(v)-1) for v in grouped.values()),'raw_sex_counts_by_row':dict(Counter(r['SEX'] for r in source_rows)),'source_dataset_version_values':sorted({r['DATASET_VERSION'] for r in source_rows}),'counts_by_distinct_person_id':counts,'monthly_counts_by_distinct_person_id':monthly,'male_minus_female':counts['MALE']-counts['FEMALE'],'male_female_ratio':counts['MALE']/counts['FEMALE'] if counts['FEMALE'] else None,'frozen_integrity':'PASS','frozen_fingerprint':fp,'inference_performed':False,'limitations':['SEX is a provider source field; no independently verified sex or documented field-method confidence is established.','Provider ID changes can affect distinct-person comparisons.','Missing source SEX is separate from unmatched IDs and conflicts.','Date precision is month-only; September coverage is incomplete.','All counts refer only to the 143 additional candidate IDs and do not change frozen Version C.'],'public_release':'HOLD / REVIEW REQUIRED'}
summary['source_compressed_bytes_scanned_nominal']=summary.pop('compressed_bytes_streamed')
summary['transfer_measurement_note']='Nominal completed source-file bytes, not total physical network transfer; parser sampling, retries and interrupted attempts may add transfer.'
summary['version_c_record_dataset_version_values']=json.loads((OUT/'version_c_baseline_record_versions.json').read_text())
(OUT/'version_d_candidate_source_sex_summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'candidate_person_source_sex_raw_matches.json').write_text(json.dumps(source_rows,indent=2))
with (OUT/'candidate_records_with_source_sex.csv').open('w',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=list(enriched[0]));writer.writeheader();writer.writerows(enriched)
table='\n'.join('| '+m+' | '+' | '.join(str(c[key]) for key in categories)+' |' for m,c in monthly.items())
report=f'''# Version D candidate source SEX matching

Scope: 143 additional provider IDs absent from Version C. The two overlapping Version C IDs are excluded.

Person catalog version 1.2; source version timestamp September 21, 2026; refresh September 28, 2026. All 384 compressed CSV files streamed; only matching rows retained. No full Person dataset saved locally.

| Start month | Male | Female | Source blank / Unknown | Unmatched | Conflicting | Unrecognized |
|---|---:|---:|---:|---:|---:|---:|
{table}

Totals: {json.dumps(counts)}. Male minus Female: {summary['male_minus_female']}. Matched IDs: {summary['matched_ids']}/143. Duplicate extra matching rows: {summary['extra_matching_rows_over_matched_ids']}.

Raw SEX values preserved; only recognized male/female source values mapped to counts. Missing, unmatched, conflicting and unrecognized values remain separate. No sex inferred from names, titles or other proxies.

Provider-reported SEX is not independently verified. All dates have month precision; source lag and September coverage limitations remain. Version C is unchanged and integrity PASS; fingerprint `{fp}`.

Public release: HOLD / REVIEW REQUIRED.
'''
report+='\nRecord-level DATASET_VERSION values: '+json.dumps(summary['source_dataset_version_values'])+'; frozen Version C values: '+json.dumps(summary['version_c_record_dataset_version_values'])+'. These are distinct from Dewey catalog/DOI version numbers.\n'
(OUT/'VERSION_D_SOURCE_SEX_REPORT.md').write_text(report)
print(json.dumps(summary,indent=2))

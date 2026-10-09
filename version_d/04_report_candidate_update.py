"""Report refreshed start records separately; do not inspect or infer sex."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv, json, hashlib, re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'version_d/outputs/dewey_refresh_20261008'
EXPECTED = '6a3ebd7f014fc75394570aa9c397e3a4cc3ca9be0ce6ac12e8dd1f22b0b618a0'
def load(name): return json.loads((OUT/name).read_text())
state = load('experience_candidate_checkpoint.json')
manifest = load('experience_dataset_path_check.json')['files']
assert len(state['completed']) == len(manifest) and not state['errors'], 'Full scan required'
assert set(state['completed']) == {f['file_name'] for f in manifest}
assert sorted(manifest,key=lambda x:x['file_name']) == sorted(load('experience_manifest_after_scan.json'),key=lambda x:x['file_name'])
for f in manifest:
    assert state['completed'][f['file_name']]['source_modified_at'] == f['modified_at']
baseline_ids = set(load('version_c_baseline_person_ids.json'))
rows=[]
for name, value in state['completed'].items():
    for row in value['rows']:
        row=dict(row,source_file=name,source_modified_at=value['source_modified_at'])
        row['already_in_version_c']=str(row['PERSON_ID']) in baseline_ids
        rows.append(row)
fields=['PERSON_ID','COMPANY_NAME','COMPANY_ID','TITLE_NAME','START_DATE','END_DATE','IS_PRIMARY']
keys=[json.dumps({k:r[k] for k in fields},sort_keys=True,default=str) for r in rows]
ids={str(r['PERSON_ID']) for r in rows if r['PERSON_ID'] is not None and str(r['PERSON_ID']).strip()}
old_ids=ids & baseline_ids
month_stats={}
for month in ['2026-08','2026-09']:
    selected=[r for r in rows if str(r['START_DATE']).startswith(month)]
    people={str(r['PERSON_ID']) for r in selected if r['PERSON_ID'] is not None and str(r['PERSON_ID']).strip()}
    month_stats[month]={'employment_rows':len(selected),'distinct_people':len(people),'not_in_version_c':len(people-baseline_ids),'already_in_version_c':len(people & baseline_ids)}
baseline_path=ROOT/'analysis/version_c/audit/17_final_integrity_manifest.json'
saved=json.loads(baseline_path.read_text())
package=ROOT/'analysis/version_c/final_evidence_package'
expected_hashes={r['path']:r['sha256'] for r in saved['files']}
actual_hashes={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file()}
fingerprint=hashlib.sha256(json.dumps({k:v for k,v in saved.items() if k!='package_fingerprint_sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
integrity={'file_set_match':set(expected_hashes)==set(actual_hashes),'content_hash_mismatches':sum(actual_hashes[k]!=expected_hashes[k] for k in actual_hashes.keys() & expected_hashes.keys()),'fingerprint':fingerprint}
assert actual_hashes==expected_hashes and fingerprint==EXPECTED==saved['package_fingerprint_sha256']
integrity['status']='PASS'
previous=json.loads((ROOT/'dewey_person_catalog_metadata.json').read_text())
versions={}
for slug in ['person','experience']:
    current=load(slug+'_details.json')['dataset']
    prior=previous['get_dataset_details_'+slug]['dataset']
    names=['doiVersionString','doi','versionTimestamp','lastRefreshAt','rowsCount','sizeBytes']
    versions[slug]={'frozen':{k:prior.get(k) for k in names},'current':{k:current.get(k) for k in names}}
limitations=[
 'Observed employment-start records are not a census of hires; profile collection and update lag remain unknown.',
 'September 21 source version and September 28 export do not establish complete coverage through September 30.',
 'Company filter is exact Anthropic after lowercase and trim; aliases and subsidiaries may be missed.',
 'Month and day precision are retained; day precision is not assumed for month-only dates.',
 'Identity is based on provider PERSON_ID. Changed or duplicate provider IDs can overcount people; no name-based identity inference was performed.',
 'People already in Version C with a later recorded start are reported separately, not automatically added to frozen totals.',
 'Monthly distinct counts can overlap and are not additive.',
 'No Person payload was downloaded. Person current-job records and employment histories were not joined; no SEX field was fetched, inferred, or analyzed.',
 'Existing project Experience folder remains on the August snapshot; refreshed dataset-level path was queried instead.',
 'Version D candidate only; no causal, applicant-denominator, demographic, or finalized analytical claims.',
]
summary={'status':'VERSION_D_CANDIDATE_UPDATE','checked_at_utc':datetime.now(timezone.utc).isoformat(),'project_id':34978,'project_external_id':'prj_37ga6vtz','versions':versions,'experience_files_queried':len(manifest),'employment_rows':len(rows),'distinct_people':len(ids),'new_distinct_ids_vs_version_c':len(ids-baseline_ids),'already_in_version_c':len(old_ids),'exact_duplicate_rows':len(keys)-len(set(keys)),'extra_rows_over_distinct_people':len(rows)-len(ids),'people_with_multiple_rows':sum(n>1 for n in Counter(str(r['PERSON_ID']) for r in rows).values()),'missing_person_id_rows':sum(r['PERSON_ID'] is None or not str(r['PERSON_ID']).strip() for r in rows),'monthly':month_stats,'date_precision':dict(Counter('day' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(r['START_DATE'])) else 'month' if re.fullmatch(r'\d{4}-\d{2}',str(r['START_DATE'])) else 'other' for r in rows)),'frozen_integrity':integrity,'limitations':limitations,'repository_visibility':'PRIVATE'}
summary['source_manifest_unchanged_after_scan'] = True
summary['version_c_overlap_start_date_changes'] = load('overlap_with_version_c.json')
summary['frozen_source_counts'] = {'employment_rows':1097,'distinct_people':1095,'extra_rows_over_distinct_people':2,'august_september_starts':0}
summary['source_exports'] = {}
for slug,files in [('person',load('person_bulk_files.json')),('experience',manifest)]:
    mods=[f['modified_at'] for f in files]
    summary['source_exports'][slug]={'file_count':len(files),'earliest_modified_at':min(mods),'latest_modified_at':max(mods),'size_bytes':sum(f['file_size_bytes'] for f in files)}
(OUT/'version_d_candidate_update.json').write_text(json.dumps(summary,indent=2))
with (OUT/'anthropic_aug_sep_candidate_records.csv').open('w',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=fields+['source_file','source_modified_at','already_in_version_c']);writer.writeheader();writer.writerows(rows)
table='\n'.join(f"| {m} | {s['employment_rows']} | {s['distinct_people']} | {s['not_in_version_c']} | {s['already_in_version_c']} |" for m,s in month_stats.items())
report=f'''# Version D candidate source update

Checked: {summary['checked_at_utc']}. Authenticated Dewey project 34978.

Refreshed Experience contains {len(rows)} August/September Anthropic employment rows, {len(ids)} distinct provider person IDs, and {len(ids-baseline_ids)} IDs absent from the frozen Version C roster. {len(old_ids)} IDs overlap Version C. These are candidate records, not a revised hiring census.

| Start month | Rows | Distinct IDs | Absent from Version C | Already in Version C |
|---|---:|---:|---:|---:|
{table}

Exact duplicate rows: {summary['exact_duplicate_rows']}. Extra rows beyond distinct IDs: {summary['extra_rows_over_distinct_people']}. IDs with multiple rows: {summary['people_with_multiple_rows']}.

All {len(manifest)} refreshed Experience files queried remotely with company/month filters; only matching records retained. No Person bulk payload downloaded.

## Dataset snapshots

'''
for slug,v in versions.items():
    report+=f"- {slug}: frozen metadata {json.dumps(v['frozen'])}; current metadata {json.dumps(v['current'])}.\n"
report+='\n## Coverage limitations\n\n'+'\n'.join('- '+x for x in limitations)
report+='\n\nThe two overlapping person IDs both had April 2026 starts in Version C and now have August 2026 starts in the refreshed source. They are source-date revisions to existing IDs, not newly counted people. Details: `overlap_with_version_c.json`.\n'
report+='\nThe source Experience manifest was reread after the scan and all 774 file names, sizes, modification times and partitions matched the initial manifest.\n'
report+='\nExport metadata: '+json.dumps(summary['source_exports'])+'\n'
report+=f'\n\nFrozen Version C integrity: PASS. File set match: True. Content hash mismatches: 0. Fingerprint: `{EXPECTED}`. Version C unchanged.\n\nRepository visibility: PRIVATE.\n'
(OUT/'VERSION_D_CANDIDATE_UPDATE.md').write_text(report)
print(json.dumps(summary,indent=2))

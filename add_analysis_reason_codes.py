"""Add auditable uncertainty reasons without changing source values or role decisions."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import boto3
import duckdb

from finalize_hire_demographics import ENRICHED, PERSON, LABEL
from test_person_stream import ROSTER

SEX_CODES = ['Source Blank', 'Source Conflicting', 'Source Unavailable', 'Explicit Public Self-ID', 'Unresolved']
ROLE_CODES = ['Engineering - Generic MTS', 'Engineering - Manager MTS', 'Applied AI - Ambiguous', 'Technical - Research Adjacent', 'Technical - Infrastructure', 'Technical - Product/Applied', 'Nontechnical - Ambiguous', 'Insufficient Title Detail', 'Conflicting Evidence', 'Research Evidence Missing']


def role_reason(row):
    if row['research_status'] != 'Insufficient Evidence':
        return None, None
    title = (row.get('TITLE_NAME') or '').strip().lower()
    role = (row.get('TITLE_ROLE') or '').strip().lower()
    sub = (row.get('TITLE_SUB_ROLE') or '').strip().lower()
    combined = ' | '.join((title, role, sub))
    mts = bool(re.search(r'\bmember of (?:the )?technical staff\b|\bmts\b', title))
    if mts and re.search(r'\bmanager\b', title):
        code = 'Engineering - Manager MTS'
    elif re.search(r'\bapplied ai\b', title):
        code = 'Applied AI - Ambiguous'
    elif re.search(r'\bresearch\w*\b|\bscientific\b|\bphysics\b|\bsafeguards\b|\bhuman data\b', combined):
        code = 'Technical - Research Adjacent'
    elif re.search(r'\binfrastructure\b|\bplatform\b|\bbackend\b|\bcorporate systems\b|\bnixos\b|\bdata engineer\w*\b|\bdata_engineering\b', combined) or title in ('compute', 'inference and performance'):
        code = 'Technical - Infrastructure'
    elif re.search(r'\bsolutions?\b|\bdesign engineer\b|\btechnical staff, design\b|\bdeployments\b|\benterprise clients\b', title) and (role == 'engineering' or 'technical' in title or 'engineer' in title):
        code = 'Technical - Product/Applied'
    elif mts:
        code = 'Engineering - Generic MTS'
    elif role in ('engineering','research') or row.get('functional_category') in ('Security','Data / Analytics','Engineering - General / Unspecified'):
        code = 'Research Evidence Missing'
    elif re.search(r'\b(?:business|community|education|events|social|creative|affairs|public sector|insurance|order management|compensation|rewards|pricing|reporting|intellectual property|workforce|media|deal ops|occupancy|transactions|risk management|strategic pursuits)\b', title):
        code = 'Nontechnical - Ambiguous'
    else:
        code = 'Insufficient Title Detail'
    evidence = json.dumps({k:row.get(k) for k in ('TITLE_NAME','TITLE_ROLE','TITLE_SUB_ROLE')}, ensure_ascii=False)
    return code, evidence + '; title-based reason for unresolved research responsibility; not a new role classification.'


def main():
    s3 = boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'], region_name='auto', aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
    bucket = os.environ['R2_BUCKET']
    con = duckdb.connect()
    con.execute("SET temp_directory=''")
    for name,key in [('original',ENRICHED),('profiles',PERSON),('roles',ROSTER)]:
        url = s3.generate_presigned_url('get_object',Params={'Bucket':bucket,'Key':key})
        con.execute('CREATE TABLE '+name+' AS SELECT * FROM read_parquet(?)',[url])
    columns = [r[0] for r in con.execute('DESCRIBE original').fetchall()]
    additions = ['sex_reason_code','sex_reason_evidence','sex_display_label','research_reason_code','research_reason_evidence','research_display_label']
    assert not set(additions) & set(columns), 'Already annotated; review before rerunning'
    rows = [dict(zip(columns,r)) for r in con.execute('SELECT * FROM original').fetchall()]
    profiles = {}
    for person, sex in con.execute('SELECT PERSON_ID,SEX FROM profiles').fetchall():
        profiles.setdefault(person,set()).add(sex)
    reasons = []
    for row in rows:
        values = profiles.get(row['PERSON_ID'])
        nonblank = {v for v in (values or set()) if v is not None and v.strip()}
        if values is None:
            sex_code, sex_evidence = 'Source Unavailable', 'No matching Person source record.'
        elif len(nonblank)>1:
            sex_code, sex_evidence = 'Source Conflicting', 'Multiple distinct nonblank source SEX values; no canonical value inferred.'
        elif not nonblank:
            sex_code, sex_evidence = 'Source Blank', 'Matched Person record has null or blank SEX.'
        elif nonblank <= {'female','male'}:
            sex_code, sex_evidence = None, 'Explicit raw source SEX value; no inference.'
        else:
            sex_code, sex_evidence = 'Unresolved', 'Source value has no approved analysis mapping.'
        code, evidence = role_reason(row)
        reasons.append([sex_code,sex_evidence,sex_code or row['sex_analysis'],code,evidence,code or row['research_status']])
    con.execute('CREATE TABLE enriched AS SELECT *, '+','.join('CAST(NULL AS VARCHAR) AS '+n for n in additions)+' FROM original WHERE false')
    con.executemany('INSERT INTO enriched VALUES ('+','.join('?' for _ in columns+additions)+')',[[row[c] for c in columns]+reason for row,reason in zip(rows,reasons)])
    original_cols = ','.join('"'+c+'"' for c in columns)
    assert con.execute('SELECT count(*) FROM ((SELECT * FROM original EXCEPT ALL SELECT '+original_cols+' FROM enriched) UNION ALL (SELECT '+original_cols+' FROM enriched EXCEPT ALL SELECT * FROM original))').fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM enriched WHERE research_status='Insufficient Evidence' AND research_reason_code IS NOT NULL").fetchone()[0] == 511
    assert con.execute("SELECT count(DISTINCT PERSON_ID) FROM enriched WHERE sex_reason_code='Source Blank'").fetchone()[0] == 213
    q = lambda v: "'"+v.replace("'","''")+"'"
    con.execute('CREATE SECRET reasons_r2 (TYPE S3, KEY_ID '+q(os.environ['R2_ACCESS_KEY_ID'])+', SECRET '+q(os.environ['R2_SECRET_ACCESS_KEY'])+", REGION 'auto', ENDPOINT "+q(urlparse(os.environ['R2_ENDPOINT']).netloc)+", URL_STYLE 'path', USE_SSL true)")
    def save(table,key,fmt='parquet'):
        url='s3://'+bucket+'/'+key
        con.execute('COPY '+table+' TO '+q(url)+(' (FORMAT PARQUET, COMPRESSION ZSTD)' if fmt=='parquet' else ' (FORMAT CSV, HEADER true)'))
        assert s3.head_object(Bucket=bucket,Key=key)['ContentLength']>0
        if fmt=='parquet':
            assert con.execute('SELECT count(*) FROM ((SELECT * FROM '+table+' EXCEPT ALL SELECT * FROM read_parquet(?)) UNION ALL (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM '+table+'))',[url,url]).fetchone()[0]==0
    # Retain a recoverable pre-annotation snapshot before replacing the canonical enriched table.
    save('original','audit/reason-codes/enriched_before_reason_codes.parquet')
    save('enriched',ENRICHED)
    con.execute('CREATE TABLE reason_counts (dimension VARCHAR, reason_code VARCHAR, employment_rows BIGINT, distinct_people BIGINT)')
    for dimension,column,codes in [('SEX','sex_reason_code',SEX_CODES),('Research uncertainty','research_reason_code',ROLE_CODES)]:
        for code in codes:
            counts=con.execute('SELECT count(*),count(DISTINCT PERSON_ID) FROM enriched WHERE '+column+'=?',[code]).fetchone()
            con.execute('INSERT INTO reason_counts VALUES (?,?,?,?)',[dimension,code,*counts])
    save('reason_counts','outputs/anthropic_uncertainty_reason_counts_current_snapshot.csv','csv')
    save('reason_counts','audit/reason-codes/reason_counts.parquet')
    report={'snapshot_scope':LABEL,'new_columns':additions,'counts':con.execute('SELECT * FROM reason_counts').fetchall(),
            'rules':['All original columns and values preserved and verified with multiset comparison.',
                     'Use sex_display_label and research_display_label instead of generic labels in detailed analysis.',
                     'Known source female/male have null sex_reason_code; this is not missing evidence.',
                     'Explicit Public Self-ID is reserved for documented self-identification. No such evidence supplied or collected; no assignments made.',
                     'Conflicting Evidence requires documented contradictory role evidence; none established here. Current Person job titles are not assumed to describe historical hires.',
                     'Reason codes explain title uncertainty and do not establish research/non-research status. Original classifications and prior demographic totals unchanged.']}
    body=json.dumps(report,indent=2).encode()
    s3.put_object(Bucket=bucket,Key='audit/reason-codes/methodology.json',Body=body,ContentType='application/json')
    assert s3.get_object(Bucket=bucket,Key='audit/reason-codes/methodology.json')['Body'].read()==body
    Path('analysis_reason_codes_report.json').write_bytes(body)
    print(body.decode())


if __name__=='__main__':
    main()

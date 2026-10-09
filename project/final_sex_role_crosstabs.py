"""Read-only analysis of canonical roles/reasons; publish verified cross-tabs."""
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import duckdb

from add_analysis_reason_codes import ROLE_CODES
from finalize_hire_demographics import CATEGORIES, ENRICHED, LABEL


def main():
    s3 = boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT'],region_name='auto',aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
    bucket = os.environ['R2_BUCKET']
    before = s3.head_object(Bucket=bucket,Key=ENRICHED)['ETag']
    con = duckdb.connect()
    con.execute("SET temp_directory=''")
    url=s3.generate_presigned_url('get_object',Params={'Bucket':bucket,'Key':ENRICHED})
    con.execute('CREATE TABLE hires AS SELECT * FROM read_parquet(?)',[url])
    columns={r[0] for r in con.execute('DESCRIBE hires').fetchall()}
    category='research_category' if 'research_category' in columns else 'ROLE_CATEGORY'
    reason='research_reason_code'
    assert con.execute('SELECT count(*),count(DISTINCT PERSON_ID) FROM hires').fetchone()==(1097,1095)
    assert con.execute('SELECT count(*) FROM (SELECT PERSON_ID FROM hires GROUP BY 1 HAVING count(DISTINCT sex_analysis)>1)').fetchone()[0]==0
    assert dict(con.execute('SELECT sex_analysis,count(DISTINCT PERSON_ID) FROM hires GROUP BY 1').fetchall())=={'Female':276,'Male':606,'Unknown':213}
    assert con.execute("SELECT count(*) FROM hires WHERE sex_analysis='Unknown' AND sex_reason_code IS DISTINCT FROM 'Source Blank'").fetchone()[0]==0
    all_rows=[]
    def counts(dimension,label,condition='true',params=()):
        f,m,u,n=con.execute("SELECT count(DISTINCT PERSON_ID) FILTER(WHERE sex_analysis='Female'),count(DISTINCT PERSON_ID) FILTER(WHERE sex_analysis='Male'),count(DISTINCT PERSON_ID) FILTER(WHERE sex_analysis='Unknown'),count(DISTINCT PERSON_ID) FROM hires WHERE "+condition,params).fetchone()
        assert f+m+u==n
        row=(dimension,label,f,m,u,n,100*f/n if n else None,100*f/(f+m) if f+m else None,LABEL)
        all_rows.append(row)
        return row
    counts('all_hires','All observed Anthropic hires')
    statuses=['Research','Probable Research','Insufficient Evidence','Probable Non-Research','Non-Research']
    actual={r[0] for r in con.execute('SELECT DISTINCT research_status FROM hires').fetchall()}
    assert actual<=set(statuses)
    for status in statuses: counts('research_status',status,'research_status=?',[status])
    headlines=[counts('headline','Confirmed Research',"research_status='Research'"),counts('headline','Confirmed + Probable Research',"research_status IN ('Research','Probable Research')")]
    for label in CATEGORIES: counts('research_category',label,category+'=?',[label])
    engineering='Engineering - General / Unspecified'
    counts('engineering',engineering,'functional_category=?',[engineering])
    engineering_reasons=['Engineering - Generic MTS','Engineering - Manager MTS','Technical - Infrastructure','Technical - Product/Applied','Applied AI - Ambiguous','Technical - Research Adjacent']
    for label in engineering_reasons:
        counts('engineering_reason_within_function',label,'functional_category=? AND '+reason+'=?',[engineering,label])
    for label in ['Individual Contributor','Lead','Manager','Senior Manager','Director','Senior Director','Head','VP / SVP / EVP','C-Suite / Executive','Founder / Co-founder','Unclear Leadership Level']:
        counts('leadership',label,'leadership_level=?',[label])
    for label in ROLE_CODES: counts('uncertainty_reason',label,reason+'=?',[label])
    con.execute('CREATE TABLE summary (dimension VARCHAR, group_name VARCHAR, female BIGINT, male BIGINT, unknown BIGINT, total BIGINT, female_pct_all DOUBLE, female_pct_known DOUBLE, snapshot_scope VARCHAR)')
    con.executemany('INSERT INTO summary VALUES (?,?,?,?,?,?,?,?,?)',all_rows)
    con.execute('CREATE TABLE all_hires (sex_category VARCHAR, distinct_people BIGINT, pct_all_hires DOUBLE, pct_known_sex_hires DOUBLE, snapshot_scope VARCHAR)')
    con.executemany('INSERT INTO all_hires VALUES (?,?,?,?,?)',[(label,n,100*n/1095,known,LABEL) for label,n,known in [('Female',276,100*276/882),('Male',606,100*606/882),('Unknown / Source Blank',213,None),('Total',1095,100.0)]])
    q=lambda v:"'"+v.replace("'","''")+"'"
    con.execute('CREATE SECRET crosstab_r2 (TYPE S3, KEY_ID '+q(os.environ['R2_ACCESS_KEY_ID'])+', SECRET '+q(os.environ['R2_SECRET_ACCESS_KEY'])+", REGION 'auto', ENDPOINT "+q(urlparse(os.environ['R2_ENDPOINT']).netloc)+", URL_STYLE 'path', USE_SSL true)")
    artifacts=[]
    def save(table,stem):
        for ext in ('csv','parquet'):
            key='outputs/'+stem+'_current_snapshot.'+ext
            target='s3://'+bucket+'/'+key
            con.execute('COPY '+table+' TO '+q(target)+(' (FORMAT CSV, HEADER true)' if ext=='csv' else ' (FORMAT PARQUET, COMPRESSION ZSTD)'))
            size=s3.head_object(Bucket=bucket,Key=key)['ContentLength'];assert size>0
            if ext=='parquet':
                assert con.execute('SELECT count(*) FROM ((SELECT * FROM '+table+' EXCEPT ALL SELECT * FROM read_parquet(?)) UNION ALL (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM '+table+'))',[target,target]).fetchone()[0]==0
            else:
                actual=list(csv.reader(io.StringIO(s3.get_object(Bucket=bucket,Key=key)['Body'].read().decode())))
                description=con.execute('SELECT * FROM '+table).description
                assert actual[0]==[c[0] for c in description]
                expected=con.execute('SELECT * FROM '+table).fetchall()
                assert len(actual)-1==len(expected)
                for source,loaded in zip(expected,actual[1:]):
                    for a,b in zip(source,loaded):
                        assert (b=='' if a is None else float(b)==a if isinstance(a,(int,float)) else b==a)
            artifacts.append({'key':key,'bytes':size})
    save('all_hires','anthropic_all_hires_demographics')
    for stem,condition in [('research_status',"dimension='research_status'"),('research_category',"dimension='research_category'"),('engineering',"dimension IN ('engineering','engineering_reason_within_function')"),('leadership',"dimension='leadership'"),('uncertainty_reason',"dimension='uncertainty_reason'")]:
        con.execute('CREATE OR REPLACE TABLE export AS SELECT * FROM summary WHERE '+condition)
        save('export','anthropic_'+stem+'_demographics')
    save('summary','anthropic_gender_summary')
    monthly=con.execute('SELECT substr(START_DATE,1,7),count(*),count(DISTINCT PERSON_ID) FROM hires GROUP BY 1 ORDER BY 1').fetchall()
    assert s3.head_object(Bucket=bucket,Key=ENRICHED)['ETag']==before
    report={'scope':LABEL,'headlines':headlines,'source_columns':{'research_category':category,'research_uncertainty_reason':reason},'monthly_observed_starts':monthly,'artifacts':artifacts,
            'methodology':['All counts are distinct people within each group; groups can overlap across employment records.',
                           'Research means the existing Research classification, not independent verification. No probable classifications currently exist.',
                           'Unknown is Source Blank throughout this snapshot. Raw SEX and reasons are unchanged.',
                           'Engineering reason breakdown intersects each reason with the engineering function; the full uncertainty table includes those reasons across all functions.',
                           'Zero-person groups retained; undefined percentages are null. Known-sex denominator is Female + Male.',
                           'August and September have zero observed starts; this does not establish zero hiring.',
                           'Enriched source ETag unchanged; every output was read back and verified.']}
    body=json.dumps(report,indent=2).encode()
    key='audit/person-enrichment/final-sex-role-crosstabs.json'
    s3.put_object(Bucket=bucket,Key=key,Body=body,ContentType='application/json')
    assert s3.get_object(Bucket=bucket,Key=key)['Body'].read()==body
    Path('final_sex_role_crosstabs_report.json').write_bytes(body)
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()

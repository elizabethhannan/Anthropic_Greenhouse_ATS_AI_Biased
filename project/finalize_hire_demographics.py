"""Join existing classifications to source SEX; count people without reclassification."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import duckdb

from test_person_stream import ROSTER
from role_dimensions import LEADERSHIP_LEVELS

PERSON = 'filtered/person/anthropic_person_profiles_current_snapshot.parquet'
ENRICHED = 'filtered/analysis/anthropic_hires_enriched_current_snapshot.parquet'
LABEL = 'Within the current Dewey/People Data Labs snapshot of observed Anthropic starts (April–July 2026); not complete April–September hiring.'
CATEGORIES = ['Research Scientist', 'Research Engineer', 'Research-oriented MTS', 'Fellows Researcher', 'Alignment / AI Safety', 'Interpretability', 'Pre-training', 'Post-training', 'Reinforcement Learning', 'Evaluations', 'Model Behavior', 'AI/ML Research - Other']


def main():
    bucket = os.environ['R2_BUCKET']
    s3 = boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'], region_name='auto', aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
    con = duckdb.connect()
    con.execute("SET temp_directory=''")
    con.execute("SET memory_limit='256MB'")
    for table, key in [('roles', ROSTER), ('person', PERSON)]:
        url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key})
        con.execute('CREATE TABLE '+table+' AS SELECT * FROM read_parquet(?)', [url])
    assert con.execute('SELECT count(*),count(DISTINCT PERSON_ID) FROM roles').fetchone() == (1097, 1095)
    assert con.execute('SELECT count(*),count(DISTINCT PERSON_ID) FROM person').fetchone() == (1095, 1095)
    assert con.execute('SELECT count(*) FROM roles r ANTI JOIN person p USING(PERSON_ID)').fetchone()[0] == 0
    raw = con.execute('SELECT SEX,count(*) FROM person GROUP BY SEX ORDER BY SEX').fetchall()
    assert all(value in ('female','male',None) or not value.strip() for value, _ in raw), 'Unexpected SEX value needs explicit review'
    statuses = dict(con.execute('SELECT research_status,count(DISTINCT PERSON_ID) FROM roles GROUP BY 1').fetchall())
    assert set(statuses) <= {'Research','Confirmed Research','Probable Research','Insufficient Evidence','Non-Research','Probable Non-Research'}
    con.execute("""CREATE TABLE enriched AS SELECT r.*, p.* EXCLUDE(PERSON_ID),
        CASE WHEN p.SEX='female' THEN 'Female' WHEN p.SEX='male' THEN 'Male'
        WHEN p.SEX IS NULL OR trim(p.SEX)='' THEN 'Unknown' END AS sex_analysis
        FROM roles r LEFT JOIN person p USING(PERSON_ID)""")
    assert con.execute('SELECT count(*),count(DISTINCT PERSON_ID) FROM enriched').fetchone() == (1097,1095)
    role_columns = ','.join('"'+r[0]+'"' for r in con.execute('DESCRIBE roles').fetchall())
    assert con.execute('SELECT count(*) FROM ((SELECT * FROM roles EXCEPT ALL SELECT '+role_columns+' FROM enriched) UNION ALL (SELECT '+role_columns+' FROM enriched EXCEPT ALL SELECT * FROM roles))').fetchone()[0] == 0
    quote = lambda value: "'"+value.replace("'", "''")+"'"
    con.execute('CREATE SECRET demographic_r2 (TYPE S3, KEY_ID '+quote(os.environ['R2_ACCESS_KEY_ID'])+', SECRET '+quote(os.environ['R2_SECRET_ACCESS_KEY'])+", REGION 'auto', ENDPOINT "+quote(urlparse(os.environ['R2_ENDPOINT']).netloc)+", URL_STYLE 'path', USE_SSL true)")
    artifacts = []
    def save(table, key, fmt):
        url = 's3://'+bucket+'/'+key
        options = 'FORMAT PARQUET, COMPRESSION ZSTD' if fmt == 'parquet' else 'FORMAT CSV, HEADER true'
        con.execute('COPY '+table+' TO '+quote(url)+' ('+options+')')
        size = s3.head_object(Bucket=bucket,Key=key)['ContentLength']
        assert size > 0
        if fmt == 'parquet':
            assert con.execute('SELECT count(*) FROM ((SELECT * FROM '+table+' EXCEPT ALL SELECT * FROM read_parquet(?)) UNION ALL (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM '+table+'))',[url,url]).fetchone()[0] == 0
        else:
            assert con.execute('SELECT count(*) FROM read_csv(?, header=true)',[url]).fetchone()[0] == con.execute('SELECT count(*) FROM '+table).fetchone()[0]
        artifacts.append({'key':key,'bytes':size})
    save('enriched', ENRICHED, 'parquet')

    summaries = []
    def count(dimension, group, condition, params=()):
        female,male,unknown,total = con.execute("""SELECT
            count(DISTINCT PERSON_ID) FILTER(WHERE sex_analysis='Female'),
            count(DISTINCT PERSON_ID) FILTER(WHERE sex_analysis='Male'),
            count(DISTINCT PERSON_ID) FILTER(WHERE sex_analysis='Unknown'),
            count(DISTINCT PERSON_ID) FROM enriched WHERE """+condition, params).fetchone()
        assert female+male+unknown == total
        result = dict(dimension=dimension,group_name=group,female=female,male=male,unknown=unknown,total=total,
                      female_pct_all=100*female/total if total else None,
                      female_pct_known=100*female/(female+male) if female+male else None,
                      snapshot_scope=LABEL)
        summaries.append(result)
        return result
    count('all_hires','All Anthropic hires','true')
    for group, condition in [
        ('Confirmed Research',"research_status IN ('Research','Confirmed Research')"),
        ('Confirmed + Probable Research',"research_status IN ('Research','Confirmed Research','Probable Research')"),
        ('Insufficient Evidence',"research_status='Insufficient Evidence'"),
        ('Non-Research',"research_status='Non-Research'"),
        ('Probable Non-Research',"research_status='Probable Non-Research'")]:
        count('research_status',group,condition)
    for category in CATEGORIES:
        count('research_category',category,'ROLE_CATEGORY=?',[category])
    count('functional_category','Engineering - General / Unspecified','functional_category=?',['Engineering - General / Unspecified'])
    for level in LEADERSHIP_LEVELS:
        count('leadership_level',level,'leadership_level=?',[level])
    con.execute('CREATE TABLE summary (dimension VARCHAR, group_name VARCHAR, female BIGINT, male BIGINT, unknown BIGINT, total BIGINT, female_pct_all DOUBLE, female_pct_known DOUBLE, snapshot_scope VARCHAR)')
    con.executemany('INSERT INTO summary VALUES (?,?,?,?,?,?,?,?,?)',[list(row.values()) for row in summaries])
    for stem, dimension in [('all_hires','all_hires'),('research','research_status'),('research_category','research_category'),('engineering','functional_category'),('leadership','leadership_level')]:
        con.execute('CREATE OR REPLACE TABLE export AS SELECT * FROM summary WHERE dimension=?',[dimension])
        save('export','outputs/anthropic_'+stem+'_demographics_current_snapshot.csv','csv')
    save('summary','outputs/anthropic_gender_summary_current_snapshot.csv','csv')
    report = {'snapshot_scope':LABEL,'employment_rows':1097,'distinct_people':1095,'unmatched_people':0,
              'raw_sex_counts':[{'value':v,'people':n} for v,n in raw],'source_research_status_counts':statuses,
              'methodology':['Research is the existing title-based classification, reported as Confirmed Research without upgrading its evidence.',
                             'No probable classifications exist in this source; unresolved roles remain Insufficient Evidence.',
                             'Distinct people counted within each group. Multiple employment records can put a person in multiple groups; totals across groups are not additive.',
                             'Raw SEX preserved. Unknown values were not inferred. Percentages for empty groups are null.',
                             'Person extract has unique IDs; duplicate search covered 388 of 389 source files before all targets were found.'],
              'summaries':summaries,'verified_artifacts':artifacts}
    body = json.dumps(report,indent=2).encode()
    key = 'audit/person-enrichment/final-demographics-report.json'
    s3.put_object(Bucket=bucket,Key=key,Body=body,ContentType='application/json')
    assert s3.get_object(Bucket=bucket,Key=key)['Body'].read() == body
    Path('final_demographics_report.json').write_bytes(body)
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

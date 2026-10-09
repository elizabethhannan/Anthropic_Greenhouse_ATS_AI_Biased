"""Filter refreshed remote Parquet; checkpoint only Anthropic Aug/Sep rows."""
from pathlib import Path
import json, hashlib, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'version_d/outputs/dewey_refresh_20261008'
FILES = json.loads(Path('/private/tmp/version_d_current_experience_links.json').read_text())
CHECKPOINT = OUT / 'experience_candidate_checkpoint.json'
state = json.loads(CHECKPOINT.read_text()) if CHECKPOINT.exists() else {'completed': {}, 'errors': {}}
fields = ['PERSON_ID','COMPANY_NAME','COMPANY_ID','TITLE_NAME','START_DATE','END_DATE','IS_PRIMARY']
def scan(file):
    con = duckdb.connect()
    try:
        con.execute("SET threads=1")
        con.execute("SET memory_limit='96MB'")
        con.execute("SET temp_directory=''")
        query = '''SELECT PERSON_ID,COMPANY_NAME,COMPANY_ID,TITLE_NAME,START_DATE,END_DATE,IS_PRIMARY
          FROM read_parquet(?) WHERE lower(trim(COMPANY_NAME))='anthropic'
          AND substr(CAST(START_DATE AS VARCHAR),1,7) IN ('2026-08','2026-09')'''
        rows = con.execute(query, [file['link']]).fetchall()
        return [dict(zip(fields, row)) for row in rows]
    finally:
        con.close()

pending = [f for f in FILES if f['file_name'] not in state['completed']]
print('FILES TOTAL:',len(FILES),'PENDING:',len(pending),flush=True)
with ThreadPoolExecutor(max_workers=64) as pool:
    futures = {pool.submit(scan, f): f for f in pending}
    for future in as_completed(futures):
        file = futures[future]; name = file['file_name']
        try:
            rows = future.result()
            state['completed'][name] = {'source_modified_at':file['modified_at'],'rows':rows}
            state['errors'].pop(name,None)
        except Exception as exc:
            state['errors'][name] = type(exc).__name__
        CHECKPOINT.write_text(json.dumps(state,indent=2,default=str))
        done=len(state['completed'])
        if done%10==0 or state['errors']:
            count=sum(len(v['rows']) for v in state['completed'].values())
            print('COMPLETED:',done,'/',len(FILES),'MATCHING ROWS:',count,'ERRORS:',len(state['errors']),flush=True)
        if state['errors']:
            for task in futures: task.cancel()
            break
print('SCAN FINISHED:',len(state['completed']),'ERRORS:',len(state['errors']),flush=True)
raise SystemExit(0 if len(state['completed'])==len(FILES) and not state['errors'] else 1)

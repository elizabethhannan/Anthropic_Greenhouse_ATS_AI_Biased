"""Stream refreshed Person CSV, retaining only candidate-ID matches and raw SEX."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import json, os, sys, csv, gzip, io, time
import httpx
import duckdb

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'version_d/outputs/dewey_refresh_20261008'
CHECKPOINT=OUT/'person_sex_match_checkpoint.json'
sys.path.insert(0,str(ROOT))
class StreamReader(io.RawIOBase):
    def __init__(self,response):
        self.chunks=response.iter_raw(chunk_size=65536)
        self.pending=b''
        self.bytes_read=0
    def readable(self):return True
    def readinto(self,buffer):
        if not self.pending:
            self.pending=next(self.chunks,b'');self.bytes_read+=len(self.pending)
        size=min(len(buffer),len(self.pending))
        buffer[:size]=self.pending[:size];self.pending=self.pending[size:]
        return size

def scan_file(file, targets):
    started=time.monotonic()
    con=duckdb.connect()
    try:
        con.execute("SET threads=1")
        con.execute("SET memory_limit='192MB'")
        con.execute("SET enable_progress_bar=false")
        con.execute("SET temp_directory=''")
        result=con.execute('''SELECT count(*),
          list(struct_pack(PERSON_ID := PERSON_ID, SEX := SEX, DATASET_VERSION := DATASET_VERSION))
          FILTER (WHERE PERSON_ID IN (SELECT unnest(?)))
          FROM read_csv(?, header=true, all_varchar=true, compression='gzip',
            nullstr='__NOT_A_SOURCE_NULL_VALUE__', force_not_null=['PERSON_ID','SEX','DATASET_VERSION'])''',
          [sorted(targets),file['link']]).fetchone()
        matches=[dict(row,source_file=file['file_name'],source_modified_at=file['modified_at']) for row in (result[1] or [])]
        return {'rows_parsed':result[0],'compressed_bytes_read':file['file_size_bytes'],'byte_count_basis':'source manifest full-file size; remote CSV scanned completely','elapsed_seconds':round(time.monotonic()-started,2),'matches':matches}
    finally:con.close()

def main():
    targets={r['PERSON_ID'] for r in csv.DictReader((OUT/'anthropic_aug_sep_candidate_records.csv').open()) if r['already_in_version_c']=='False'}
    assert len(targets)==143
    for line in (ROOT/'r2.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1);os.environ.setdefault(key.strip(),value.strip().strip('\"').strip("'"))
    files=[]
    with httpx.Client(headers={'X-API-KEY':os.environ['DEWEY_API_KEY']},timeout=60) as api:
        page=1
        while True:
            response=api.get('https://api.deweydata.io/api/v1/external/data/prj_37ga6vtz__dst_m4nxsxh8aggbim3d/files',params={'page':page});response.raise_for_status()
            data=response.json();files.extend(data['download_links'])
            if page>=data['total_pages']:break
            page+=1
    stable=lambda f:{k:f.get(k) for k in ['file_name','file_size_bytes','modified_at','partition_key']}
    manifest=sorted([stable(f) for f in files],key=lambda f:f['file_name'])
    expected=sorted(json.loads((OUT/'person_bulk_files.json').read_text()),key=lambda f:f['file_name'])
    assert manifest==expected and len(files)==384,'Person snapshot changed; do not mix versions'
    state=json.loads(CHECKPOINT.read_text()) if CHECKPOINT.exists() else {'target_ids':sorted(targets),'source_manifest':manifest,'completed':{},'errors':{}}
    assert state['target_ids']==sorted(targets) and state['source_manifest']==manifest
    pending=[f for f in files if f['file_name'] not in state['completed']]
    print('PERSON SOURCE FILES:',len(files),'PENDING:',len(pending),'TARGET IDS:',len(targets),flush=True)
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=32) as pool:
        tasks={pool.submit(scan_file,file,targets):file for file in pending}
        for task in as_completed(tasks):
            file=tasks[task]; name=file['file_name']
            try:
                state['completed'][name]=task.result();state['errors'].pop(name,None)
            except Exception as exc:
                state['errors'][name]=type(exc).__name__
            CHECKPOINT.write_text(json.dumps(state,indent=2))
            matched={r['PERSON_ID'] for f in state['completed'].values() for r in f['matches']}
            processed=sum(f['compressed_bytes_read'] for f in state['completed'].values())
            print('FILES:',len(state['completed']),'/',len(files),'MATCHED IDS:',len(matched),'/',len(targets),'PROCESSED GiB:',round(processed/2**30,2),'ELAPSED:',round(time.monotonic()-start),'ERRORS:',len(state['errors']),flush=True)
    complete=len(state['completed'])==len(files) and not state['errors']
    print('PERSON MATCH SCAN COMPLETE:',complete,flush=True)
    return 0 if complete else 1

if __name__=='__main__':raise SystemExit(main())

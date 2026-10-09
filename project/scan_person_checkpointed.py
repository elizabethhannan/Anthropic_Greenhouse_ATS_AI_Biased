"""Resume a streaming Person scan; retain only roster matches in R2."""
import collections
import csv
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
import duckdb
import httpx

from test_person_stream import FIELDS, ROSTER, StreamReader

PREFIX = 'audit/person-enrichment/full-person-scan/'
CHECKPOINT = Path('person_scan_checkpoint.json')
OUTPUT = 'filtered/person/anthropic_person_profiles_current_snapshot.parquet'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode()


def stable(file):
    return {key: file[key] for key in ('file_name', 'file_size_bytes', 'modified_at')}


def main():
    lock = open('person_scan.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    bucket = os.environ['R2_BUCKET']
    s3 = boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'], region_name='auto',
                      aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
                      aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])

    def get(key):
        return json.loads(s3.get_object(Bucket=bucket, Key=key)['Body'].read())

    def put(key, value):
        body = encoded(value)
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType='application/json')
        # Verify payload, not just successful request status.
        assert s3.get_object(Bucket=bucket, Key=key)['Body'].read() == body

    con = duckdb.connect()
    con.execute("SET temp_directory=''")
    con.execute("SET memory_limit='256MB'")
    url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': ROSTER})
    targets = {str(row[0]) for row in con.execute('SELECT DISTINCT PERSON_ID FROM read_parquet(?)', [url]).fetchall()}
    assert len(targets) == 1095 and 'None' not in targets
    target_hash = hashlib.sha256(encoded(sorted(targets))).hexdigest()
    base = os.environ['PERSON_BULK_API_URL'].rstrip('/')
    api = httpx.Client(headers={'X-API-KEY': os.environ['DEWEY_API_KEY']}, timeout=60)

    def listing():
        response = api.get(base + '/files', params={'page': 1}); response.raise_for_status()
        data = response.json()
        files = data['download_links']
        for page in range(2, data['total_pages'] + 1):
            response = api.get(base + '/files', params={'page': page}); response.raise_for_status()
            files.extend(response.json()['download_links'])
        assert len(files) == 389 and len({f['file_name'] for f in files}) == 389
        assert all(f['file_name'].startswith('person_') and f['file_name'].endswith('.csv.gz') for f in files)
        return files

    files = listing()
    manifest = [stable(f) for f in files]
    fingerprint = {'target_hash': target_hash, 'source_api': base, 'manifest': sorted(manifest, key=lambda f: f['file_name']), 'fields': FIELDS}
    try:
        state = get(PREFIX + 'checkpoint.json')
        assert state['fingerprint'] == fingerprint, 'Source snapshot or target roster changed'
    except ClientError as exc:
        if exc.response['Error']['Code'] not in ('NoSuchKey', '404'):
            raise
        if CHECKPOINT.exists():
            state = json.loads(CHECKPOINT.read_text())
            assert state['fingerprint'] == fingerprint
        else:
            test = get('audit/person-enrichment/one-file-stream-test/report.json')
            first = next(f for f in files if f['file_name'] == test['source_file'])
            original = json.loads(Path('dewey_person_verified_resource.json').read_text())
            old_first = next(f for f in original['files'] if f['file_name'] == first['file_name'])
            assert stable(first) == stable(old_first)
            matches = get(test['matches_key'])
            assert test['target_ids'] == len(targets) and test['compressed_bytes_read'] == first['file_size_bytes']
            assert len(matches) == test['matching_rows'] and {r['PERSON_ID'] for r in matches} <= targets
            state = {'fingerprint': fingerprint, 'completed': [dict(stable(first), rows_parsed=test['rows_parsed'], elapsed_seconds=test['elapsed_seconds'])],
                     'matches': matches, 'elapsed_seconds': test['elapsed_seconds'], 'errors_retries': [], 'status': 'running'}
    start = time.monotonic()
    prior_elapsed = state['elapsed_seconds']

    def checkpoint():
        found = {row['PERSON_ID'] for row in state['matches']}
        state.update(files_completed=len(state['completed']), compressed_bytes_processed=sum(f['file_size_bytes'] for f in state['completed']),
                     target_ids_found=sorted(found), target_ids_remaining=sorted(targets-found), match_count=len(state['matches']),
                     elapsed_seconds=prior_elapsed + time.monotonic()-start)
        put(PREFIX + 'checkpoint.json', state)
        temporary = CHECKPOINT.with_suffix('.tmp')
        temporary.write_bytes(encoded(state)); temporary.replace(CHECKPOINT)

    def progress(event):
        processed = state['compressed_bytes_processed']
        remaining = sum(f['file_size_bytes'] for f in files) - processed
        print(json.dumps({'event': event, 'files_completed': state['files_completed'], 'files_total': len(files),
                          'matched_ids': len(state['target_ids_found']), 'remaining_ids': len(state['target_ids_remaining']),
                          'compressed_gib': round(processed / 2**30, 3), 'elapsed_seconds': round(state['elapsed_seconds'], 1),
                          'estimated_remaining_seconds': round(state['elapsed_seconds'] * remaining / processed, 1),
                          'errors_retries': len(state['errors_retries'])}), flush=True)

    checkpoint()
    progress('resumed')
    completed = {f['file_name'] for f in state['completed']}
    csv.field_size_limit(16 * 1024 * 1024)
    for initial_source in files:
        if not state['target_ids_remaining']:
            break
        if initial_source['file_name'] in completed:
            continue
        source = initial_source
        for attempt in range(1, 5):
            file_start = time.monotonic()
            matches, rows = [], 0
            try:
                with httpx.Client(timeout=httpx.Timeout(60, read=120), follow_redirects=True) as client:
                    with client.stream('GET', source['link'], headers={'Accept-Encoding': 'identity'}) as response:
                        response.raise_for_status()
                        raw = StreamReader(response)
                        with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BufferedReader(raw)), encoding='utf-8-sig', newline='') as text:
                            reader = csv.reader(text)
                            header = next(reader)
                            assert len(header) == 57 and {'PERSON_ID', 'SEX', 'JOB_TITLE', 'JOB_COMPANY_NAME'}.issubset(header)
                            selected = [(field, header.index(field)) for field in FIELDS if field in header]
                            index = header.index('PERSON_ID')
                            for row in reader:
                                if len(row) != len(header):
                                    raise ValueError('CSV width mismatch')
                                rows += 1
                                if row[index] in targets:
                                    matches.append({field: row[i] for field, i in selected})
                assert raw.bytes_read == source['file_size_bytes']
                break
            except (httpx.HTTPError, OSError, EOFError) as exc:
                state['errors_retries'].append({'file': source['file_name'], 'attempt': attempt, 'error_type': type(exc).__name__})
                checkpoint()
                progress('retry')
                if attempt == 4:
                    raise
                time.sleep(attempt * 2)
                fresh = listing()
                assert sorted([stable(f) for f in fresh], key=lambda f: f['file_name']) == fingerprint['manifest']
                source = next(f for f in fresh if f['file_name'] == initial_source['file_name'])
        # Commit only fully validated files; partial attempts never add matches.
        state['matches'].extend(matches)
        state['completed'].append(dict(stable(source), rows_parsed=rows, elapsed_seconds=time.monotonic()-file_start))
        checkpoint()
        progress('milestone' if state['files_completed'] % 25 == 0 else 'file_completed')

    # Raw strings (including empty SEX) are preserved, and duplicate rows retained.
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    con.execute('CREATE TABLE person (' + ','.join('"'+f+'" VARCHAR' for f in FIELDS) + ')')
    if state['matches']:
        con.executemany('INSERT INTO person VALUES (' + ','.join('?' for _ in FIELDS) + ')',
                        [[row.get(f) for f in FIELDS] for row in state['matches']])
    con.execute('CREATE SECRET person_r2 (TYPE S3, KEY_ID '+quote(os.environ['R2_ACCESS_KEY_ID'])+', SECRET '+quote(os.environ['R2_SECRET_ACCESS_KEY'])+", REGION 'auto', ENDPOINT "+quote(urlparse(os.environ['R2_ENDPOINT']).netloc)+", URL_STYLE 'path', USE_SSL true)")
    output_url = f's3://{bucket}/{OUTPUT}'
    con.execute('COPY person TO '+quote(output_url)+' (FORMAT PARQUET, COMPRESSION ZSTD)')
    assert s3.head_object(Bucket=bucket, Key=OUTPUT)['ContentLength'] > 0
    assert con.execute('SELECT count(*) FROM ((SELECT * FROM person EXCEPT ALL SELECT * FROM read_parquet(?)) UNION ALL (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM person))', [output_url, output_url]).fetchone()[0] == 0
    sex_ids = collections.defaultdict(set)
    ids = collections.Counter()
    for row in state['matches']:
        sex_ids[row.get('SEX')].add(row['PERSON_ID'])
        ids[row['PERSON_ID']] += 1
    duplicates = [row for row in state['matches'] if ids[row['PERSON_ID']] > 1]
    put(PREFIX+'duplicate_person_rows.json', duplicates)
    state['status'] = 'complete'
    checkpoint()
    report = {k:state[k] for k in ('files_completed','compressed_bytes_processed','elapsed_seconds','match_count','errors_retries')}
    report.update(matched_person_ids=len(ids), unmatched_person_ids=len(targets-set(ids)), duplicate_person_rows=sum(n-1 for n in ids.values()),
                  ids_with_duplicates=sum(n>1 for n in ids.values()), raw_sex_counts=[{'raw_value': sex, 'distinct_people':len(people)} for sex,people in sex_ids.items()],
                  raw_sex_count_note='Distinct people per raw value; conflicting values can overlap.',
                  early_stop=len(state['completed'])<len(files), source_files_stored_locally=False,
                  duplicate_audit_scope='Scanned files only; early stop cannot establish absence of duplicates in unscanned files.', output_key=OUTPUT)
    put(PREFIX+'report.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Scan stopped safely: '+type(exc).__name__+'; resume using checkpoint.', file=sys.stderr, flush=True)
        sys.exit(1)

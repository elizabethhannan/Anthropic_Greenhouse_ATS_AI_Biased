"""Bounded one-file Person streaming validation. Never starts a second file."""
import csv
import gzip
import io
import json
import os
import resource
import sys
import time
from pathlib import Path

import boto3
import duckdb
import httpx

FIELDS = 'PERSON_ID SEX JOB_TITLE JOB_TITLE_ROLE JOB_TITLE_SUB_ROLE JOB_TITLE_CLASS JOB_COMPANY_NAME JOB_COMPANY_ID JOB_START_DATE JOB_LAST_CHANGED JOB_LAST_VERIFIED LOCATION_NAME LOCATION_LOCALITY LOCATION_REGION LOCATION_COUNTRY DATASET_VERSION'.split()
ROSTER = 'filtered/analysis/anthropic_role_dimensions_2026-04-01_to_2026-09-30.parquet'


class StreamReader(io.RawIOBase):
    def __init__(self, response):
        self.chunks = response.iter_raw(chunk_size=65536)
        self.pending = b''
        self.bytes_read = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        if not self.pending:
            self.pending = next(self.chunks, b'')
            self.bytes_read += len(self.pending)
        n = min(len(buffer), len(self.pending))
        buffer[:n] = self.pending[:n]
        self.pending = self.pending[n:]
        return n


def main():
    s3 = boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'], region_name='auto',
                      aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
                      aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
    bucket = os.environ['R2_BUCKET']
    con = duckdb.connect()
    con.execute("SET temp_directory=''")
    con.execute("SET memory_limit='256MB'")
    url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': ROSTER})
    targets = {str(r[0]) for r in con.execute('SELECT DISTINCT PERSON_ID FROM read_parquet(?)', [url]).fetchall()}
    assert len(targets) == 1095 and 'None' not in targets
    con.close()
    base = os.environ['PERSON_BULK_API_URL'].rstrip('/')
    with httpx.Client(headers={'X-API-KEY': os.environ['DEWEY_API_KEY']}, timeout=60) as client:
        r = client.get(base + '/metadata'); r.raise_for_status(); meta = r.json()
        r = client.get(base + '/files', params={'page': 1}); r.raise_for_status()
        source = r.json()['download_links'][0]
    assert source['file_name'].startswith('person_') and source['file_name'].endswith('.csv.gz')
    start = last_log = time.monotonic()
    matches, found, rows = [], set(), 0
    csv.field_size_limit(16 * 1024 * 1024)
    print(json.dumps({'event': 'start', 'file': source['file_name'], 'target_ids': len(targets), 'max_files': 1}), flush=True)
    # Separate storage client: never forward the Dewey credential to signed storage.
    with httpx.Client(timeout=httpx.Timeout(60, read=120), follow_redirects=True) as client:
        with client.stream('GET', source['link'], headers={'Accept-Encoding': 'identity'}) as response:
            response.raise_for_status()
            raw = StreamReader(response)
            with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BufferedReader(raw)), encoding='utf-8-sig', newline='') as text:
                reader = csv.reader(text)
                header = next(reader)
                assert len(header) == 57 and {'PERSON_ID', 'SEX', 'JOB_TITLE', 'JOB_COMPANY_NAME'}.issubset(header)
                selected = [(field, header.index(field)) for field in FIELDS if field in header]
                id_index = header.index('PERSON_ID')
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError('CSV row width does not match header')
                    rows += 1
                    if row[id_index] in targets:
                        matches.append({field: row[index] for field, index in selected})
                        found.add(row[id_index])
                    now = time.monotonic()
                    if now - last_log >= 30:
                        print(json.dumps({'event': 'progress', 'rows': rows, 'compressed_bytes': raw.bytes_read, 'elapsed_seconds': round(now-start, 1), 'matched_ids': len(found), 'remaining_ids': len(targets-found)}), flush=True)
                        last_log = now
    elapsed = time.monotonic() - start
    assert raw.bytes_read == source['file_size_bytes']
    prefix = 'audit/person-enrichment/one-file-stream-test/'
    def upload(key, body, content_type):
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
        assert s3.head_object(Bucket=bucket, Key=key)['ContentLength'] == len(body)
    # Keep all matching rows, including duplicates, with raw string values unchanged.
    matches_key = prefix + 'matched_person_rows.json'
    upload(matches_key, json.dumps(matches, ensure_ascii=False).encode(), 'application/json')
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {'source_file': source['file_name'], 'files_processed': 1, 'source_file_count': meta['total_files'],
              'elapsed_seconds': elapsed, 'compressed_bytes_read': raw.bytes_read, 'rows_parsed': rows,
              'target_ids': len(targets), 'matched_distinct_ids': len(found), 'matching_rows': len(matches),
              'duplicate_matching_rows': len(matches)-len(found), 'ids_remaining': len(targets-found),
              'peak_process_memory_bytes': peak if sys.platform == 'darwin' else peak * 1024,
              'source_saved_locally': False, 'selected_fields': [f for f, _ in selected],
              'all_files_estimated_seconds_by_bytes': elapsed * meta['total_size'] / raw.bytes_read,
              'all_files_estimated_seconds_by_file_count': elapsed * meta['total_files'],
              'estimate_caveat': 'One-file extrapolation; network and parsing throughput can vary.',
              'matches_key': matches_key, 'stopped_after_one_file': True}
    body = json.dumps(report, indent=2).encode()
    upload(prefix + 'report.json', body, 'application/json')
    Path('person_one_file_test_report.json').write_bytes(body)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Library exceptions may contain signed URLs: emit only the error type.
        print('Streaming test failed: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(1)

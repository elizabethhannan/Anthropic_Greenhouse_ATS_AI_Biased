import datetime as dt
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx


DATASET_ID = "prj_37ga6vtz__fldr_btzpw6hub88mzykfi"
BASE_URL = f"https://api.deweydata.io/api/v1/external/data/{DATASET_ID}"

OUTPUT_DIR = Path("dewey-anthropic-output")
STAGING_DIR = OUTPUT_DIR / "r2-staging-exact-day"
PROGRESS_PATH = OUTPUT_DIR / "r2_exact_day_progress.json"

BATCH_SIZE = int(os.getenv("DEWEY_FILES_PER_PART", "10"))
MAX_BATCHES = int(os.getenv("MAX_BATCHES", "1"))
START_DATE = "2026-04-01"
END_EXCLUSIVE = "2026-10-01"
TARGET_COMPANY = "anthropic"

KEEP_FIELDS = [
    "PERSON_ID",
    "COMPANY_NAME",
    "COMPANY_ID",
    "TITLE_NAME",
    "TITLE_ROLE",
    "TITLE_SUB_ROLE",
    "START_DATE",
    "END_DATE",
    "IS_PRIMARY",
]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value


def dewey_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "X-API-Key": require_env("DEWEY_API_KEY"),
            "User-Agent": "anthropic-r2-pull/1.0",
        },
        timeout=httpx.Timeout(120.0),
        follow_redirects=True,
    )


def get_download_links(client: httpx.Client) -> tuple[list[str], list[dict]]:
    files = []
    page = 1

    while True:
        response = client.get(f"{BASE_URL}/files", params={"page": page})
        response.raise_for_status()
        files_data = response.json()

        files.extend(
            file_info
            for file_info in files_data["download_links"]
            if file_info.get("file_extension") == ".snappy.parquet"
            or file_info.get("file_name", "").endswith(".parquet")
        )

        total_pages = files_data["total_pages"]
        print(f"Fetched file-list page {page} of {total_pages}.")

        if page >= total_pages:
            break
        page += 1

    # Signed URL paths and external_id rotate on every request. Filenames are
    # unique within this dataset; stable ordering preserves batch membership.
    files.sort(key=lambda item: item["file_name"])
    manifest = [
        {field: item.get(field) for field in (
            "file_name", "file_size_bytes", "modified_at", "partition_key"
        )}
        for item in files
    ]
    if len({item["file_name"] for item in files}) != len(files):
        raise RuntimeError("Dewey returned duplicate source filenames.")
    return [item["link"] for item in files], manifest


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def duckdb_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class R2Client:
    def __init__(self) -> None:
        configured_endpoint = os.getenv("R2_ENDPOINT")
        account_id = os.getenv("R2_ACCOUNT_ID")
        self.access_key_id = require_env("R2_ACCESS_KEY_ID")
        self.secret_access_key = require_env("R2_SECRET_ACCESS_KEY")
        self.bucket = require_env("R2_BUCKET")
        self.prefix = os.getenv(
            "R2_PREFIX",
            "anthropic-bias-data/experience-anthropic-2026-04-to-09",
        ).strip("/")

        if configured_endpoint:
            parsed = urlparse(configured_endpoint)
            if not parsed.scheme or not parsed.netloc:
                raise RuntimeError(
                    "R2_ENDPOINT must look like "
                    "https://<account_id>.r2.cloudflarestorage.com"
                )
            self.endpoint = configured_endpoint.rstrip("/")
            self.host = parsed.netloc
        elif account_id:
            self.host = f"{account_id}.r2.cloudflarestorage.com"
            self.endpoint = f"https://{self.host}"
        else:
            raise RuntimeError("Set either R2_ENDPOINT or R2_ACCOUNT_ID.")

        self.region = "auto"
        self.service = "s3"
        self.client = httpx.Client(timeout=httpx.Timeout(120.0))

    def key_for_batch(self, batch_index: int) -> str:
        return f"{self.prefix}/batches/data_batch{batch_index:04d}.parquet"

    def close(self) -> None:
        self.client.close()

    def _sign(
        self,
        *,
        method: str,
        key: str,
        payload_hash: str,
        now: dt.datetime,
    ) -> tuple[str, dict[str, str]]:
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")
        canonical_uri = f"/{quote(self.bucket)}/{quote(key, safe='/')}"
        canonical_headers = (
            f"host:{self.host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                "",
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        credential_scope = (
            f"{datestamp}/{self.region}/{self.service}/aws4_request"
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        signing_key = self._signing_key(datestamp)
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        url = f"{self.endpoint}{canonical_uri}"
        headers = {
            "Authorization": authorization,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        return url, headers

    def _signing_key(self, datestamp: str) -> bytes:
        key_date = hmac.new(
            ("AWS4" + self.secret_access_key).encode("utf-8"),
            datestamp.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        key_region = hmac.new(
            key_date, self.region.encode("utf-8"), hashlib.sha256
        ).digest()
        key_service = hmac.new(
            key_region, self.service.encode("utf-8"), hashlib.sha256
        ).digest()
        return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()

    def object_size(self, key: str) -> int | None:
        payload_hash = hashlib.sha256(b"").hexdigest()
        url, headers = self._sign(
            method="HEAD",
            key=key,
            payload_hash=payload_hash,
            now=dt.datetime.now(dt.UTC),
        )
        response = self.client.head(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return int(response.headers["Content-Length"])

    def upload_file(self, path: Path, key: str) -> None:
        payload = path.read_bytes()
        payload_hash = hashlib.sha256(payload).hexdigest()
        url, headers = self._sign(
            method="PUT",
            key=key,
            payload_hash=payload_hash,
            now=dt.datetime.now(dt.UTC),
        )
        headers["Content-Type"] = "application/vnd.apache.parquet"
        response = self.client.put(url, headers=headers, content=payload)
        response.raise_for_status()


def load_progress(download_links: list[str], manifest: list[dict]) -> dict:
    fingerprint = {
        "data_id": DATASET_ID,
        "batch_size": BATCH_SIZE,
        "n_files": len(download_links),
        "n_batches": len(chunks(download_links, BATCH_SIZE)),
        "company": TARGET_COMPANY,
        "start_date": START_DATE,
        "month_only_dates": "first_day_of_month",
        "end_exclusive": END_EXCLUSIVE,
        "fields": KEEP_FIELDS,
        "source_manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest(),
        "bucket": require_env("R2_BUCKET"),
        "prefix": os.getenv("R2_PREFIX", "anthropic-bias-data/experience-anthropic-2026-04-to-09").strip("/"),
    }
    if not PROGRESS_PATH.exists():
        return {"fingerprint": fingerprint, "source_manifest": manifest, "uploaded": []}

    progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    if progress.get("fingerprint") != fingerprint:
        raise RuntimeError(
            f"{PROGRESS_PATH} is for a different run. "
            "Move it aside or use the same batch settings."
        )
    progress.setdefault("uploaded", [])
    return progress


def save_progress(progress: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    tmp_path = PROGRESS_PATH.with_suffix(".tmp.json")
    tmp_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    tmp_path.replace(PROGRESS_PATH)


def write_batch_parquet(con, links: list[str], output_path: Path) -> int:
    output_path.unlink(missing_ok=True)
    selected_fields = ", ".join(KEEP_FIELDS)
    output_path_sql = duckdb_string_literal(output_path.as_posix())

    con.execute(
        f"""
        copy (
            select {selected_fields}
            from read_parquet(?)
            where lower(trim(COMPANY_NAME)) = ?
              and (case when length(cast(START_DATE as varchar)) = 7
                        then cast(START_DATE as varchar) || '-01'
                        else cast(START_DATE as varchar) end) >= ?
              and (case when length(cast(START_DATE as varchar)) = 7
                        then cast(START_DATE as varchar) || '-01'
                        else cast(START_DATE as varchar) end) < ?
        )
        to {output_path_sql}
        (format parquet, row_group_size 256000, compression zstd)
        """,
        [links, TARGET_COMPANY, START_DATE, END_EXCLUSIVE],
    )

    return con.execute(
        "select count(*) from read_parquet(?)",
        [output_path.as_posix()],
    ).fetchone()[0]


def main() -> None:
    import duckdb

    if BATCH_SIZE < 1 or (MAX_BATCHES is not None and MAX_BATCHES < 1):
        raise ValueError("DEWEY_FILES_PER_PART and MAX_BATCHES must be positive.")
    OUTPUT_DIR.mkdir(exist_ok=True)
    STAGING_DIR.mkdir(exist_ok=True)

    with dewey_client() as client:
        download_links, manifest = get_download_links(client)

    link_batches = chunks(download_links, BATCH_SIZE)
    progress = load_progress(download_links, manifest)
    uploaded = set(progress["uploaded"])

    r2 = R2Client()
    con = duckdb.connect()
    con.execute("set enable_progress_bar = false")
    con.execute("set enable_http_metadata_cache = true")
    con.execute("set memory_limit = '1GB'")
    con.execute("set max_temp_directory_size = '256MB'")
    con.execute("set threads = 2")

    try:
        print(
            f"Processing {'all remaining' if MAX_BATCHES is None else 'at most ' + str(MAX_BATCHES)} batches ({BATCH_SIZE} source files each) of {len(link_batches)} to "
            f"r2://{r2.bucket}/{r2.prefix}/"
        )
        processed = 0
        for batch_index, links in enumerate(link_batches, start=1):
            if MAX_BATCHES is not None and batch_index > MAX_BATCHES:
                print(f"Stopped at batch-number limit MAX_BATCHES={MAX_BATCHES}.")
                break
            batch_id = str(batch_index)
            key = r2.key_for_batch(batch_index)

            if batch_id in uploaded:
                expected = progress["batches"][batch_id]["bytes"]
                if r2.object_size(key) != expected:
                    raise RuntimeError(f"Checkpointed batch {batch_index} failed size verification.")
                print(f"Skipping batch {batch_index}: already checkpointed.")
                continue

            local_path = STAGING_DIR / f"data_batch{batch_index:04d}.parquet"
            batch_started = time.monotonic()
            print(f"Writing local staging batch {batch_index}/{len(link_batches)}.")
            row_count = write_batch_parquet(con, links, local_path)
            local_size = local_path.stat().st_size
            if local_size <= 0:
                raise RuntimeError("Staging Parquet is empty.")

            print(f"Uploading batch {batch_index} ({row_count:,} rows) to {key}.")
            r2.upload_file(local_path, key)
            remote_size = r2.object_size(key)
            if remote_size != local_size:
                raise RuntimeError(f"Size mismatch: local={local_size}, R2={remote_size}; retaining staging file.")

            uploaded.add(batch_id)
            progress["uploaded"] = sorted(uploaded, key=int)
            progress.setdefault("batches", {})[batch_id] = {
                "key": key, "bytes": local_size, "rows": row_count,
                "source_files": len(links),
                "elapsed_seconds": round(time.monotonic() - batch_started, 3),
                "verified_at": dt.datetime.now(dt.UTC).isoformat(),
            }
            save_progress(progress)
            local_path.unlink()
            print(f"Batch {batch_index}: verified {remote_size:,} bytes; checkpoint saved; temp file deleted.")
            processed += 1
            if MAX_BATCHES is not None and processed >= MAX_BATCHES:
                print(f"Stopped at MAX_BATCHES={MAX_BATCHES}.")
                break
        if len(uploaded) == len(link_batches):
            progress["completed_at"] = dt.datetime.now(dt.UTC).isoformat()
            save_progress(progress)
            print(f"Complete: {len(uploaded)} batches, {sum(batch['rows'] for batch in progress['batches'].values()):,} rows.")
    finally:
        con.close()
        r2.close()


if __name__ == "__main__":
    main()

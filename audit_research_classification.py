"""Aggregate unresolved employment roles from R2 without reclassifying people."""

import datetime as dt
import json
import os
from urllib.parse import urlparse

import boto3
import duckdb

from build_anthropic_analysis_tables import CHECKPOINT, RESEARCH_KEY, sql_literal


PREFIX = "audit/research-classification/"
COMBINATIONS = "review_needed_title_combinations_2026-04-01_to_2026-09-30"
TITLES = "review_needed_title_names_2026-04-01_to_2026-09-30"


def main():
    checkpoint = json.loads(CHECKPOINT.read_text())
    bucket = checkpoint["fingerprint"]["bucket"]
    endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.path not in ("", "/"):
        raise ValueError("Expected an HTTPS R2 endpoint without a path.")
    s3 = boto3.client(
        "s3", endpoint_url=endpoint, region_name="auto",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    con = duckdb.connect()
    try:
        source_head = s3.head_object(Bucket=bucket, Key=RESEARCH_KEY)
        url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": RESEARCH_KEY}, ExpiresIn=3600)
        con.execute("SET memory_limit='256MB'")
        con.execute("SET temp_directory=''")
        con.execute("CREATE TABLE source AS SELECT * FROM read_parquet(?)", [url])
        con.execute("CREATE TABLE unresolved AS SELECT * FROM source WHERE CLASSIFICATION_STATUS = 'review_needed'")
        rows, people = con.execute("SELECT count(*), count(DISTINCT PERSON_ID) FROM unresolved").fetchone()
        assert rows == 511 and people == 511, "Review population changed; inspect before publishing the audit."
        assert con.execute("SELECT count(*) FROM unresolved WHERE ROLE_CATEGORY IS DISTINCT FROM 'Review Needed' OR IS_RESEARCH_HIRE IS NOT NULL").fetchone()[0] == 0
        con.execute("""CREATE TABLE combinations AS
            SELECT TITLE_NAME AS title_name, TITLE_ROLE AS title_role,
                   TITLE_SUB_ROLE AS title_sub_role,
                   count(*) AS row_count, count(DISTINCT PERSON_ID) AS distinct_people
            FROM unresolved GROUP BY TITLE_NAME, TITLE_ROLE, TITLE_SUB_ROLE""")
        con.execute("""CREATE TABLE titles AS
            SELECT TITLE_NAME AS title_name, count(*) AS row_count,
                   count(DISTINCT PERSON_ID) AS distinct_people
            FROM unresolved GROUP BY TITLE_NAME""")
        n_combinations = con.execute("SELECT count(*) FROM combinations").fetchone()[0]
        n_titles = con.execute("SELECT count(*) FROM titles").fetchone()[0]
        for table in ("combinations", "titles"):
            assert con.execute(f"SELECT sum(row_count) FROM {table}").fetchone()[0] == rows
        con.execute("CREATE SECRET r2_audit (TYPE S3, KEY_ID " + sql_literal(os.environ["R2_ACCESS_KEY_ID"]) +
                    ", SECRET " + sql_literal(os.environ["R2_SECRET_ACCESS_KEY"]) +
                    ", REGION 'auto', ENDPOINT " + sql_literal(parsed.netloc) +
                    ", URL_STYLE 'path', USE_SSL true)")
        order_combinations = "row_count DESC, title_name ASC NULLS LAST, title_role ASC NULLS LAST, title_sub_role ASC NULLS LAST"
        artifacts = []
        for table, stem, ordering in (
            ("combinations", COMBINATIONS, order_combinations),
            ("titles", TITLES, "row_count DESC, title_name ASC NULLS LAST"),
        ):
            for extension in ("parquet", "csv"):
                key = PREFIX + stem + "." + extension
                uri = f"s3://{bucket}/{key}"
                options = "FORMAT PARQUET, COMPRESSION ZSTD" if extension == "parquet" else "FORMAT CSV, HEADER true, NULL '\\N'"
                con.execute(f"COPY (SELECT * FROM {table} ORDER BY {ordering}) TO {sql_literal(uri)} ({options})")
                size = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
                assert size > 0
                remote_url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
                if extension == "parquet":
                    reader = f"read_parquet({sql_literal(remote_url)})"
                else:
                    text_columns = ["title_name", "title_role", "title_sub_role"] if table == "combinations" else ["title_name"]
                    schema = {**{column: "VARCHAR" for column in text_columns}, "row_count": "BIGINT", "distinct_people": "BIGINT"}
                    columns_sql = "{" + ", ".join(sql_literal(k) + ": " + sql_literal(v) for k, v in schema.items()) + "}"
                    reader = f"read_csv({sql_literal(remote_url)}, header=true, nullstr='\\N', columns={columns_sql})"
                con.execute(f"CREATE OR REPLACE TABLE verified AS SELECT * FROM {reader}")
                assert con.execute(f"SELECT count(*) FROM ((SELECT * FROM verified EXCEPT ALL SELECT * FROM {table}) UNION ALL (SELECT * FROM {table} EXCEPT ALL SELECT * FROM verified))").fetchone()[0] == 0
                artifacts.append({"key": key, "bytes": size, "roundtrip_verified": True})
        top = [dict(zip(["title_name", "title_role", "title_sub_role", "row_count", "distinct_people"], row))
               for row in con.execute(f"SELECT * FROM combinations ORDER BY {order_combinations} LIMIT 50").fetchall()]
        assert s3.head_object(Bucket=bucket, Key=RESEARCH_KEY)["ETag"] == source_head["ETag"], "Source changed during audit."
        report = {
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
            "source_key": RESEARCH_KEY, "source_etag": source_head["ETag"],
            "review_rows": rows, "review_distinct_people": people,
            "unique_title_combinations": n_combinations,
            "unique_title_names": n_titles,
            "top_50_rows": sum(item["row_count"] for item in top),
            "top_50_combinations": top,
            "artifacts": artifacts,
            "methodology": "Exact source values grouped without normalization; NULL preserved. Frequency descending with exact-title tie breaks. Person IDs used only to count distinct people; no names, demographics, reclassification, or Dewey queries. CSV encodes NULL as \\N. Source research table unchanged. Data processed in memory and written directly to R2.",
        }
        report_key = PREFIX + "review_needed_audit_summary_2026-04-01_to_2026-09-30.json"
        body = (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode()
        s3.put_object(Bucket=bucket, Key=report_key, Body=body, ContentType="application/json")
        assert s3.head_object(Bucket=bucket, Key=report_key)["ContentLength"] == len(body)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("Summary:", f"s3://{bucket}/{report_key}")
    finally:
        con.close()
        s3.close()


if __name__ == "__main__":
    main()

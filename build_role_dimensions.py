"""Publish orthogonal role dimensions; optionally join an explicit R2 Person extract.

Never retrieves Dewey or infers gender. Person fields are supplied by CLI only
after inspecting the actual schema. Datasets are kept in memory and R2.
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import duckdb

from build_anthropic_analysis_tables import CHECKPOINT, MASTER_KEY, RESEARCH_KEY, FIELDS, classify_role, sql_literal
from role_dimensions import functional, leadership, profile_leadership, source_gender


ANALYSIS_KEY = "filtered/analysis/anthropic_role_dimensions_2026-04-01_to_2026-09-30.parquet"
REPORT_KEY = "audit/research-classification/functional_leadership_summary_2026-04-01_to_2026-09-30.json"


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-key", help="Already-filtered Person Parquet key in the same R2 bucket.")
    parser.add_argument("--person-id-field", default="person_id")
    parser.add_argument("--current-title-field")
    parser.add_argument("--current-company-field")
    parser.add_argument("--headline-field")
    parser.add_argument("--gender-field", help="Actual source gender column; omit when absent.")
    args = parser.parse_args()
    if not args.person_key and any((args.current_title_field, args.current_company_field, args.headline_field, args.gender_field)):
        parser.error("Profile field mappings require --person-key.")
    bucket = json.loads(CHECKPOINT.read_text())["fingerprint"]["bucket"]
    endpoint = urlparse(os.environ["R2_ENDPOINT"])
    if endpoint.scheme != "https" or endpoint.path not in ("", "/"):
        raise ValueError("Expected an HTTPS R2 endpoint without a path.")
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
    con = duckdb.connect()

    def read(key):
        return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)

    def publish(table, key):
        con.execute(f"COPY {table} TO {sql_literal(f's3://{bucket}/{key}')} (FORMAT PARQUET, COMPRESSION ZSTD)")
        size = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
        assert size > 0
        con.execute("CREATE OR REPLACE TABLE verified AS SELECT * FROM read_parquet(?)", [read(key)])
        assert con.execute(f"SELECT count(*) FROM ((SELECT * FROM verified EXCEPT ALL SELECT * FROM {table}) UNION ALL (SELECT * FROM {table} EXCEPT ALL SELECT * FROM verified))").fetchone()[0] == 0
        return {"key": key, "rows": con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], "bytes": size, "roundtrip_verified": True}

    try:
        con.execute("SET temp_directory=''")
        con.execute("SET memory_limit='512MB'")
        master_etag = s3.head_object(Bucket=bucket, Key=MASTER_KEY)["ETag"]
        con.execute("CREATE TABLE master AS SELECT * FROM read_parquet(?)", [read(MASTER_KEY)])
        assert [x[0] for x in con.execute("DESCRIBE master").fetchall()] == FIELDS
        assert con.execute("SELECT count(*), count(DISTINCT PERSON_ID) FROM master").fetchone() == (1097, 1095)
        con.execute("CREATE TABLE old_research AS SELECT * FROM read_parquet(?)", [read(RESEARCH_KEY)])
        con.execute("CREATE TABLE dimensions (TITLE_NAME VARCHAR, TITLE_ROLE VARCHAR, TITLE_SUB_ROLE VARCHAR, ROLE_CATEGORY VARCHAR, CLASSIFICATION_STATUS VARCHAR, IS_RESEARCH_HIRE BOOLEAN, CLASSIFICATION_RULE VARCHAR, CLASSIFICATION_REASON VARCHAR, RESEARCH_AREAS VARCHAR, functional_category VARCHAR, functional_evidence VARCHAR, research_status VARCHAR, leadership_level VARCHAR, leadership_evidence VARCHAR, leadership_source VARCHAR, people_management_status VARCHAR)")
        for title, role, sub in con.execute("SELECT DISTINCT TITLE_NAME, TITLE_ROLE, TITLE_SUB_ROLE FROM master").fetchall():
            label = classify_role(title, role, sub)
            dimension = {**functional(title, role, sub, label), **leadership(title)}
            values = [title, role, sub, *label.values(), *dimension.values()]
            con.execute("INSERT INTO dimensions VALUES (" + ",".join("?" for _ in values) + ")", values)
        con.execute("""CREATE TABLE analysis AS SELECT m.*, d.* EXCLUDE (TITLE_NAME, TITLE_ROLE, TITLE_SUB_ROLE)
            FROM master m JOIN dimensions d ON m.TITLE_NAME IS NOT DISTINCT FROM d.TITLE_NAME
            AND m.TITLE_ROLE IS NOT DISTINCT FROM d.TITLE_ROLE AND m.TITLE_SUB_ROLE IS NOT DISTINCT FROM d.TITLE_SUB_ROLE""")
        matched_people = None
        if args.person_key:
            con.execute("CREATE TABLE profiles AS SELECT * FROM read_parquet(?)", [read(args.person_key)])
            columns = [x[0] for x in con.execute("DESCRIBE profiles").fetchall()]
            requested = [args.person_id_field, args.current_title_field, args.current_company_field, args.headline_field, args.gender_field]
            missing = [x for x in requested if x and x not in columns]
            if missing:
                raise ValueError(f"Explicit profile fields absent from actual schema: {missing}")
            pid = identifier(args.person_id_field)
            assert con.execute(f"SELECT count(*) FROM (SELECT {pid} FROM profiles GROUP BY {pid} HAVING count(*) > 1)").fetchone()[0] == 0, "Resolve duplicate Person IDs before joining."
            assert con.execute(f"SELECT count(*) FROM profiles WHERE {pid} IS NULL").fetchone()[0] == 0
            extra = ", ".join(f"p.{identifier(c)} AS {identifier('profile_' + c)}" for c in columns)
            con.execute(f"CREATE TABLE enriched AS SELECT a.*, {extra} FROM analysis a LEFT JOIN profiles p ON a.PERSON_ID = p.{pid}")
            assert con.execute("SELECT count(*) FROM enriched").fetchone()[0] == 1097
            matched_people = con.execute(f"SELECT count(DISTINCT a.PERSON_ID) FROM analysis a JOIN profiles p ON a.PERSON_ID = p.{pid}").fetchone()[0]
            con.execute("DROP TABLE analysis")
            con.execute("ALTER TABLE enriched RENAME TO analysis")
            con.execute("CREATE TABLE person_labels (person_label_id VARCHAR, current_leadership_level VARCHAR, current_leadership_evidence VARCHAR, demographic_gender VARCHAR)")
            for row in con.execute("SELECT * FROM profiles").fetchall():
                profile = dict(zip(columns, row))
                current = profile_leadership(profile.get(args.current_title_field), profile.get(args.headline_field), profile.get(args.current_company_field))
                gender = source_gender(profile.get(args.gender_field)) if args.gender_field else "Unknown / Unclassified"
                con.execute("INSERT INTO person_labels VALUES (?, ?, ?, ?)", [profile[args.person_id_field], current["leadership_level"], current["leadership_evidence"], gender])
            con.execute("""CREATE TABLE enriched AS SELECT a.*, coalesce(p.current_leadership_level, 'Unclear Leadership Level') AS current_leadership_level,
                coalesce(p.current_leadership_evidence, 'No matching Person record.') AS current_leadership_evidence,
                coalesce(p.demographic_gender, 'Unknown / Unclassified') AS demographic_gender
                FROM analysis a LEFT JOIN person_labels p ON a.PERSON_ID = p.person_label_id""")
            con.execute("DROP TABLE analysis")
            con.execute("ALTER TABLE enriched RENAME TO analysis")
        con.execute("CREATE TABLE researchers AS SELECT * FROM analysis WHERE CLASSIFICATION_STATUS IN ('research', 'review_needed')")
        assert con.execute("SELECT count(*) FROM researchers").fetchone()[0] == 551
        original_columns = FIELDS + ["ROLE_CATEGORY", "CLASSIFICATION_STATUS", "IS_RESEARCH_HIRE", "CLASSIFICATION_RULE", "CLASSIFICATION_REASON", "RESEARCH_AREAS"]
        cols = ", ".join(identifier(c) for c in original_columns)
        assert con.execute(f"SELECT count(*) FROM ((SELECT {cols} FROM researchers EXCEPT ALL SELECT {cols} FROM old_research) UNION ALL (SELECT {cols} FROM old_research EXCEPT ALL SELECT {cols} FROM researchers))").fetchone()[0] == 0, "Research membership or original fields changed."
        con.execute("CREATE SECRET r2_dimensions (TYPE S3, KEY_ID " + sql_literal(os.environ["R2_ACCESS_KEY_ID"]) +
                    ", SECRET " + sql_literal(os.environ["R2_SECRET_ACCESS_KEY"]) + ", REGION 'auto', ENDPOINT " + sql_literal(endpoint.netloc) + ", URL_STYLE 'path', USE_SSL true)")
        artifacts = [publish("analysis", ANALYSIS_KEY), publish("researchers", RESEARCH_KEY)]
        crosstabs = []
        if args.person_key and args.gender_field:
            for dimension in ("functional_category", "leadership_level", "current_leadership_level"):
                con.execute(f"""CREATE OR REPLACE TABLE crosstab AS WITH person_categories AS (
                    SELECT DISTINCT PERSON_ID, {dimension}, demographic_gender FROM analysis)
                    SELECT {dimension}, count(*) FILTER (WHERE demographic_gender='Men') AS men,
                    count(*) FILTER (WHERE demographic_gender='Women') AS women,
                    count(*) FILTER (WHERE demographic_gender='Unknown / Unclassified') AS unknown_unclassified,
                    count(*) FILTER (WHERE demographic_gender='Other / Source-reported') AS other_source_reported,
                    count(*) AS total,
                    100.0 * count(*) FILTER (WHERE demographic_gender='Women') / count(*) AS pct_women_all,
                    100.0 * count(*) FILTER (WHERE demographic_gender='Women') / nullif(count(*) FILTER (WHERE demographic_gender IN ('Men', 'Women')), 0) AS pct_women_men_women
                    FROM person_categories GROUP BY {dimension} ORDER BY total DESC, {dimension}""")
                crosstabs.append(publish("crosstab", f"audit/demographics/anthropic_{dimension}_2026.parquet"))
        report = {
            "created_at": dt.datetime.now(dt.UTC).isoformat(), "all_hires_rows": 1097, "distinct_people": 1095,
            "research_classification_changed": False,
            "person_enrichment_complete": args.person_key is not None, "matched_person_ids": matched_people,
            "source_gender_field": args.gender_field, "gender_crosstabs_generated": bool(crosstabs),
            "functional_categories": [dict(zip(("functional_category", "research_status", "rows", "distinct_people"), x)) for x in con.execute("SELECT functional_category, research_status, count(*), count(DISTINCT PERSON_ID) FROM analysis GROUP BY ALL ORDER BY count(*) DESC").fetchall()],
            "leadership_levels": [dict(zip(("leadership_level", "rows", "distinct_people"), x)) for x in con.execute("SELECT leadership_level, count(*), count(DISTINCT PERSON_ID) FROM analysis GROUP BY leadership_level ORDER BY count(*) DESC").fetchall()],
            "generic_mts": con.execute("SELECT count(*) FROM analysis WHERE TITLE_NAME='member of technical staff' AND TITLE_ROLE='engineering' AND TITLE_SUB_ROLE IS NULL AND functional_category='Engineering - General / Unspecified' AND research_status='Insufficient Evidence'").fetchone()[0],
            "mts_manager_rows": con.execute("SELECT count(*) FROM analysis WHERE lower(TITLE_NAME) LIKE '%technical staff%' AND leadership_level='Manager' AND research_status='Insufficient Evidence'").fetchone()[0],
            "methodology": [
                "Function, research evidence and leadership are separate dimensions. Leadership is not a functional category.",
                "Historical leadership uses exact employment TITLE_NAME. Current-profile leadership stays separate and requires an explicit Anthropic current employer; ambiguous headlines are evidence for review, not automatic historical promotions.",
                "Manager and other seniority labels reflect title terms, not verified direct-report responsibilities. Product/account/project manager titles do not prove people management.",
                "Research classification and source titles remain unchanged; generic MTS has engineering function and insufficient research evidence.",
                "Gender cross-tabs require an actual explicitly mapped Person gender field. No names or employment fields are used to infer gender.",
                "Cross-tabs count distinct people within each category. A person with distinct employment functions or levels can appear in multiple categories; category totals are not additive.",
                "Percent women among all people and among source-reported men/women are separate denominators. Unknown and other source-reported values are retained.",
                "Data processed in memory and written directly to R2; no permanent local datasets.",
            ], "artifacts": artifacts, "demographic_artifacts": crosstabs,
        }
        assert report["generic_mts"] == 318
        assert s3.head_object(Bucket=bucket, Key=MASTER_KEY)["ETag"] == master_etag
        body = (json.dumps(report, indent=2) + "\n").encode()
        s3.put_object(Bucket=bucket, Key=REPORT_KEY, Body=body, ContentType="application/json")
        assert s3.head_object(Bucket=bucket, Key=REPORT_KEY)["ContentLength"] == len(body)
        print(json.dumps(report, indent=2))
    finally:
        con.close()
        s3.close()


if __name__ == "__main__":
    main()

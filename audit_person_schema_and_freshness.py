"""Publish confirmed catalog schema and snapshot audits without Person retrieval."""
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import duckdb

from build_anthropic_analysis_tables import CHECKPOINT, sql_literal
from build_role_dimensions import ANALYSIS_KEY


def main():
    catalog = json.loads(Path("dewey_person_catalog_metadata.json").read_text())
    checkpoint = json.loads(CHECKPOINT.read_text())
    bucket = checkpoint["fingerprint"]["bucket"]
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto", aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
    con = duckdb.connect()
    artifacts = []

    def json_to_r2(key, value):
        body = (json.dumps(value, indent=2, default=str) + "\n").encode()
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
        assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] == len(body)
        artifacts.append(key)

    try:
        con.execute("SET temp_directory=''")
        con.execute("SET memory_limit='256MB'")
        url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": ANALYSIS_KEY}, ExpiresIn=3600)
        con.execute("CREATE TABLE analysis AS SELECT * FROM read_parquet(?)", [url])
        assert con.execute("SELECT count(*), count(DISTINCT PERSON_ID) FROM analysis").fetchone() == (1097, 1095)
        con.execute("""CREATE TABLE monthly AS WITH months AS (
            SELECT '2026-' || lpad(CAST(i AS VARCHAR),2,'0') AS start_month FROM range(4,10) t(i))
            SELECT m.start_month, count(a.PERSON_ID) AS employment_rows,
                count(DISTINCT a.PERSON_ID) AS distinct_people,
                count(DISTINCT a.PERSON_ID) FILTER (WHERE a.research_status='Research') AS confirmed_research_people,
                count(DISTINCT a.PERSON_ID) FILTER (WHERE a.functional_category='Engineering - General / Unspecified') AS engineering_general_people,
                count(DISTINCT a.PERSON_ID) FILTER (WHERE a.leadership_level IN ('Lead','Manager','Senior Manager','Director','Senior Director','Head','VP / SVP / EVP','C-Suite / Executive','Founder / Co-founder')) AS leadership_title_people
            FROM months m LEFT JOIN analysis a ON substr(CAST(a.START_DATE AS VARCHAR),1,7)=m.start_month
            GROUP BY m.start_month ORDER BY m.start_month""")
        columns = [c[0] for c in con.execute("DESCRIBE monthly").fetchall()]
        monthly = [dict(zip(columns, row)) for row in con.execute("SELECT * FROM monthly ORDER BY start_month").fetchall()]
        precision = dict(con.execute("""SELECT CASE
            WHEN START_DATE IS NULL THEN 'missing'
            WHEN regexp_full_match(CAST(START_DATE AS VARCHAR), '[0-9]{4}-[0-9]{2}') THEN 'month'
            WHEN regexp_full_match(CAST(START_DATE AS VARCHAR), '[0-9]{4}-[0-9]{2}-[0-9]{2}') THEN 'day'
            WHEN regexp_full_match(CAST(START_DATE AS VARCHAR), '[0-9]{4}') THEN 'year'
            ELSE 'other' END AS precision, count(*) FROM analysis GROUP BY precision""").fetchall())
        mods = [x["modified_at"] for x in checkpoint["source_manifest"] if x.get("modified_at")]
        experience = catalog["get_dataset_details_experience"]["dataset"]
        person = catalog["get_dataset_details_person"]["dataset"]
        names = {c["name"] for c in catalog["get_dataset_schema_person"]["schema"]["columns"]}
        wanted = {
            "person_id": ["PERSON_ID"], "full_name": ["FULL_NAME"], "first_name": ["FIRST_NAME"],
            "last_name": ["LAST_NAME"], "current_title": ["JOB_TITLE"], "current_company": ["JOB_COMPANY_NAME", "JOB_COMPANY_ID"],
            "headline": ["HEADLINE"], "summary_bio": ["SUMMARY", "BIO"], "skills": ["SKILLS"],
            "personal_profile_url": ["PROFILE_URL", "LINKEDIN_URL", "URL"],
            "location": ["LOCATION_NAME", "LOCATION_LOCALITY", "LOCATION_REGION", "LOCATION_COUNTRY", "LOCATION_CONTINENT", "LOCATION_METRO"],
            "gender": ["GENDER"], "sex": ["SEX"], "inferred_gender": ["INFERRED_GENDER"],
            "gender_method_provenance_confidence": [n for n in names if any(t in n for t in ("GENDER", "SEX")) and n != "SEX"],
            "current_job": ["JOB_TITLE", "JOB_TITLE_ROLE", "JOB_TITLE_SUB_ROLE", "JOB_TITLE_CLASS", "JOB_COMPANY_NAME", "JOB_COMPANY_ID", "JOB_START_DATE", "JOB_LAST_CHANGED", "JOB_LAST_VERIFIED"],
            "job_history": ["EXPERIENCE", "JOB_HISTORY"],
            "version": ["DATASET_VERSION"],
        }
        schema_report = {
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
            "catalog_dataset_id": person["externalId"], "catalog_numeric_id": person["id"], "catalog_slug": person["slug"],
            "project_folder_id": None, "bulk_api_url": None, "file_count": None,
            "catalog_discovery_api_url": "https://api.deweydata.io/mcp",
            "row_count": person["rowsCount"], "version_timestamp": person["versionTimestamp"],
            "version": person["doiVersionString"], "version_doi": person["doi"], "last_refresh_at": person["lastRefreshAt"],
            "catalog_default_format": person["unloadingDefaultFileType"],
            "actual_bulk_file_schema_confirmed": False,
            "fields": {requested: {"present_in_catalog": bool([n for n in candidates if n in names]), "exact_source_names": [n for n in candidates if n in names]} for requested,candidates in wanted.items()},
            "person_schema": catalog["get_dataset_schema_person"]["schema"],
            "profile_schema": catalog["get_dataset_schema_profile"]["schema"],
            "source_demographic_field": "SEX", "source_description": "The person's sex.",
            "demographic_method_provenance_confidence": "Not documented in inspected catalog schema or dataset documentation. PROFILE_SCORE and ACTIVITY_SCORE are not gender confidence fields.",
            "limitations": ["Catalog schema lists no personal names, headline, summary, skills or personal LinkedIn URL. Profile schema exposes only PERSON_ID and NETWORK; general product documentation describes a richer schema than this accessible catalog.", "Person bulk API project/folder URL is required; catalog ID is not a bulk folder ID. Catalog advertises CSV, so Parquet availability must be checked on the actual project file listing.", "SEX must be preserved raw; no demographic counts generated before matching Person records. No gender inferred from names."]
        }
        json_to_r2("audit/person-enrichment/person_schema_discovery_2026.json", schema_report)
        json_to_r2("audit/person-enrichment/dewey_catalog_metadata_2026.json", catalog)
        if Path("dewey_person_documentation.json").exists():
            json_to_r2("audit/person-enrichment/dewey_person_documentation_2026.json", json.loads(Path("dewey_person_documentation.json").read_text()))
        freshness = {
            "created_at": dt.datetime.now(dt.UTC).isoformat(), "population_rows": 1097, "population_distinct_people": 1095,
            "monthly": monthly, "start_date_precision_rows": precision,
            "oldest_source_file_modified_at": min(mods), "newest_source_file_modified_at": max(mods),
            "experience_version_timestamp": experience["versionTimestamp"], "experience_last_refresh_at": experience["lastRefreshAt"],
            "person_version_timestamp": person["versionTimestamp"], "person_last_refresh_at": person["lastRefreshAt"],
            "person_version_doi": person["doi"],
            "interpretation": "Counts describe employment starts recorded in the current Dewey/PDL snapshot, not a complete census of Anthropic hiring. August source refresh predates September; low/zero September counts cannot establish a hiring decline. File modification and catalog refresh dates are not guarantees of observation completeness.",
            "definitions": {"research": "Distinct people with existing research_status = Research; classifications unchanged and provisional.", "engineering": "Distinct people in Engineering - General / Unspecified.", "leadership": "Distinct people with explicit leadership title levels, excluding IC and Unclear; titles do not verify direct reports.", "monthly": "People with multiple start months can be counted in multiple months; monthly distinct counts are not additive."},
        }
        json_to_r2("audit/data-freshness/anthropic_snapshot_freshness_2026.json", freshness)
        con.execute("CREATE SECRET r2_freshness (TYPE S3, KEY_ID " + sql_literal(os.environ["R2_ACCESS_KEY_ID"]) + ", SECRET " + sql_literal(os.environ["R2_SECRET_ACCESS_KEY"]) + ", REGION 'auto', ENDPOINT " + sql_literal(urlparse(os.environ["R2_ENDPOINT"]).netloc) + ", URL_STYLE 'path', USE_SSL true)")
        for ext, options in (("parquet", "FORMAT PARQUET, COMPRESSION ZSTD"), ("csv", "FORMAT CSV, HEADER true")):
            key = f"audit/data-freshness/anthropic_starts_by_month_2026.{ext}"
            con.execute(f"COPY (SELECT * FROM monthly ORDER BY start_month) TO {sql_literal(f's3://{bucket}/{key}')} ({options})")
            assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] > 0
            artifacts.append(key)
        print(json.dumps(freshness, indent=2))
        print("Saved audit objects:", json.dumps(artifacts))
    finally:
        con.close()
        s3.close()


if __name__ == "__main__":
    main()

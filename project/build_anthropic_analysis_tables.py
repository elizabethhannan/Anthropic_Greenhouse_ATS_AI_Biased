"""Build analysis tables from completed R2 batches; never query Dewey.

Data stays in DuckDB memory and R2. Generic MTS and other ambiguous roles are
retained in the research candidate table with IS_RESEARCH_HIRE = NULL.
"""

import datetime as dt
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import boto3
import duckdb


CHECKPOINT = Path(__file__).parent / "dewey-anthropic-output/r2_exact_day_progress.json"
MASTER_KEY = "filtered/all-hires/anthropic_all_hires_2026-04-01_to_2026-09-30.parquet"
RESEARCH_KEY = "filtered/researchers/anthropic_research_hires_2026-04-01_to_2026-09-30.parquet"
REPORT_KEY = "filtered/researchers/anthropic_classification_report_2026-04-01_to_2026-09-30.json"
FIELDS = [
    "PERSON_ID", "COMPANY_NAME", "COMPANY_ID", "TITLE_NAME", "TITLE_ROLE",
    "TITLE_SUB_ROLE", "START_DATE", "END_DATE", "IS_PRIMARY",
]
CATEGORIES = [
    "Research Scientist", "Research Engineer", "Research-oriented MTS", "Fellows Researcher",
    "Alignment / AI Safety", "Interpretability", "Pre-training", "Post-training",
    "Reinforcement Learning", "Evaluations", "Model Behavior",
    "AI/ML Research - Other", "Review Needed", "Non-Research",
]
RULE_VERSION = "1.0.1"
AREAS = [
    ("Interpretability", r"\binterpretability\b|\bmechanistic interpret"),
    ("Pre-training", r"\bpre[ -]?train(?:ing)?\b"),
    ("Post-training", r"\bpost[ -]?train(?:ing)?\b"),
    ("Reinforcement Learning", r"\breinforcement learning\b|\brlhf\b|\brlvr\b"),
    ("Model Behavior", r"\bmodel behavio[u]?r\b"),
    ("Alignment / AI Safety", r"\balignment\b|\b(?:ai|artificial intelligence|model) safety\b"),
    ("Evaluations", r"\bevals?\b|\bevaluations?\b"),
]


def normalized(value):
    value = unicodedata.normalize("NFKC", str(value or "")).lower()
    value = re.sub(r"[\u2010-\u2015]", "-", value).replace("_", " ")
    return re.sub(r"\s+", " ", value).strip()


def classify_role(title_name, title_role, title_sub_role):
    title = normalized(title_name)
    role = normalized(title_role)
    sub = normalized(title_sub_role)
    combined = " | ".join((title, role, sub))
    areas = [name for name, pattern in AREAS if re.search(pattern, combined)]
    mts = bool(re.search(r"\bmember of (?:the )?technical staff\b|\bmts\b", title))

    def result(category, rule, reason):
        status = ("review_needed" if category == "Review Needed" else
                  "non_research" if category == "Non-Research" else "research")
        return {
            "ROLE_CATEGORY": category,
            "CLASSIFICATION_STATUS": status,
            "IS_RESEARCH_HIRE": None if status == "review_needed" else status == "research",
            "CLASSIFICATION_RULE": rule,
            "CLASSIFICATION_REASON": reason,
            "RESEARCH_AREAS": "; ".join(areas),
        }

    # Support/commercial titles take precedence over incidental research/AI words
    # or noisy PDL role labels (e.g. research recruiting or AI safety counsel).
    support_title = re.search(
        r"\b(?:gtm|go[ -]to[ -]market|sales|account executive|accounting|accountant|"
        r"finance|financial|tax|payroll|revenue|recruit\w*|talent|people|human resources|"
        r"counsel|legal|lawyer|compliance|grc|marketing|communications?|communictions|"
        r"copywriter|brand|customer|partnerships?|partner success|business development|"
        r"public policy|policy|government affairs|state and local|facilities|workplace|"
        r"administrative|administrator|business operations|research operations|"
        r"enforcement|safeguards operations|supply chain|procurement|investor|"
        r"ambassador|subscriber|volunteer|student|user|board|advisors?|advisor|"
        r"product manager|product management|product design|design research\w*|"
        r"product engineering|developer experience|technical program|program manager|"
        r"program coordinator|project manager|project development|solutions? architect|"
        r"forward deployed|support|it support|information technology)\b", title
    )
    if support_title:
        return result("Non-Research", "explicit_non_research_function",
                      "Explicit commercial, support, policy, administrative, or non-research function in title: " + support_title.group())
    if mts:
        if re.search(r"\beconom(?:ist|ic|ics)\b|\bhardware\b", title):
            return result("Review Needed", "mts_domain_uncertain", "MTS research domain is not established as AI/ML by these fields.")
        if areas or role == "research" or re.search(r"\bresearch\b", title):
            return result("Research-oriented MTS", "mts_research_evidence", "MTS plus explicit research role or model-research area.")
        return result("Review Needed", "generic_mts", "MTS alone, including engineering or applied AI labels, does not establish research responsibilities.")
    if re.search(r"\bresearch scientist\b", title):
        return result("Research Scientist", "research_scientist", "Explicit research scientist title.")
    if re.search(r"\bresearch engineer\b", title):
        return result("Research Engineer", "research_engineer", "Explicit research engineer title.")
    if re.search(r"\bfellows?\b|\bfellowship\b", title):
        return result("Fellows Researcher", "fellow", "Explicit fellow title; included in the research population per requested scope, not proof of permanent employment.")
    if areas:
        return result(areas[0], "explicit_research_area", "Explicit model-research or AI-safety area in role fields: " + "; ".join(areas))
    if re.search(r"\beconom(?:ist|ic|ics)\b|\bhardware\b", combined) and re.search(r"\bresearch\w*\b", combined):
        return result("Review Needed", "research_domain_uncertain", "Research is stated, but an AI/ML research domain is not established.")
    if re.search(r"\b(?:ai|ml|artificial intelligence|machine learning)\b", combined) and re.search(r"\bresearch\w*\b", combined):
        return result("AI/ML Research - Other", "ai_ml_research", "Explicit AI/ML and research evidence in the role fields.")
    non_research_roles = {
        "sales", "sales engineering", "human resources", "finance", "legal",
        "marketing", "partnerships", "support", "operations", "product",
        "fulfillment", "creative", "advisory", "trade", "public service",
    }
    if role in non_research_roles:
        return result("Non-Research", "non_research_role", "Structured role identifies a non-research function: " + role)
    return result("Review Needed", "insufficient_evidence", "Available title/role/sub-role fields do not establish AI/ML research or a clear non-research function.")


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    checkpoint = json.loads(CHECKPOINT.read_text())
    fp = checkpoint["fingerprint"]
    assert checkpoint.get("completed_at"), "Ingest must be complete."
    assert checkpoint["uploaded"] == [str(i) for i in range(1, 81)]
    assert fp["company"] == "anthropic" and fp["start_date"] == "2026-04-01"
    assert fp["end_exclusive"] == "2026-10-01" and fp["fields"] == FIELDS
    bucket = fp["bucket"]
    endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme != "https" or parsed_endpoint.path not in ("", "/"):
        raise ValueError("Expected an HTTPS R2 endpoint without a path.")
    s3 = boto3.client(
        "s3", endpoint_url=endpoint, region_name="auto",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    expected = {b["key"]: b["bytes"] for b in checkpoint["batches"].values()}
    listed = {o["Key"]: o["Size"]
              for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=fp["prefix"] + "/batches/")
              for o in page.get("Contents", []) if o["Key"].endswith(".parquet")}
    assert listed == expected, "R2 batch objects must match the checkpoint."
    urls = [s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
            for key in sorted(expected)]
    con = duckdb.connect()
    con.execute("SET memory_limit='512MB'")
    con.execute("SET temp_directory=''")  # No disk spill or persistent data files.
    try:
        print("Reading 80 R2 batches directly with DuckDB.", flush=True)
        con.execute("CREATE TABLE source AS SELECT * FROM read_parquet(?)", [urls])
        assert [x[0] for x in con.execute("DESCRIBE source").fetchall()] == FIELDS
        source_rows, source_people = con.execute("SELECT count(*), count(DISTINCT PERSON_ID) FROM source").fetchone()
        assert (source_rows, source_people) == (1097, 1095)
        con.execute("CREATE TABLE master AS SELECT DISTINCT " + ", ".join(FIELDS) + " FROM source")
        master_rows, master_people = con.execute("SELECT count(*), count(DISTINCT PERSON_ID) FROM master").fetchone()
        assert master_people == source_people
        invalid = con.execute("""SELECT count(*) FROM master WHERE NOT coalesce(
            lower(trim(COMPANY_NAME)) = 'anthropic' AND
            (CASE WHEN length(CAST(START_DATE AS VARCHAR)) = 7 THEN CAST(START_DATE AS VARCHAR) || '-01'
                  ELSE CAST(START_DATE AS VARCHAR) END) >= '2026-04-01' AND
            (CASE WHEN length(CAST(START_DATE AS VARCHAR)) = 7 THEN CAST(START_DATE AS VARCHAR) || '-01'
                  ELSE CAST(START_DATE AS VARCHAR) END) < '2026-10-01', false)""").fetchone()[0]
        assert invalid == 0

        duplicate_groups = []
        for person_id, count in con.execute("SELECT PERSON_ID, count(*) FROM master GROUP BY PERSON_ID HAVING count(*) > 1 ORDER BY PERSON_ID").fetchall():
            records = [dict(zip(FIELDS, row)) for row in con.execute("SELECT * FROM master WHERE PERSON_ID = ? ORDER BY START_DATE, TITLE_NAME", [person_id]).fetchall()]
            duplicate_groups.append({
                "person_id": person_id, "employment_rows": count, "records": records,
                "interpretation": "Distinct titles and dates are consistent with a role transition; dates are month-level, so exact overlap cannot be determined. Both records retained.",
            })

        con.execute("""CREATE TABLE role_labels (
            TITLE_NAME VARCHAR, TITLE_ROLE VARCHAR, TITLE_SUB_ROLE VARCHAR,
            ROLE_CATEGORY VARCHAR, CLASSIFICATION_STATUS VARCHAR, IS_RESEARCH_HIRE BOOLEAN,
            CLASSIFICATION_RULE VARCHAR, CLASSIFICATION_REASON VARCHAR, RESEARCH_AREAS VARCHAR)""")
        title_audit = []
        for title, role, sub, count in con.execute("SELECT TITLE_NAME, TITLE_ROLE, TITLE_SUB_ROLE, count(*) FROM master GROUP BY ALL ORDER BY count(*) DESC, TITLE_NAME").fetchall():
            label = classify_role(title, role, sub)
            con.execute("INSERT INTO role_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [title, role, sub, *label.values()])
            title_audit.append({"title_name": title, "title_role": role, "title_sub_role": sub, "rows": count, **label})
        con.execute("""CREATE TABLE classified AS
            SELECT m.*, l.ROLE_CATEGORY, l.CLASSIFICATION_STATUS, l.IS_RESEARCH_HIRE,
                   l.CLASSIFICATION_RULE, l.CLASSIFICATION_REASON, l.RESEARCH_AREAS
            FROM master m JOIN role_labels l
            ON m.TITLE_NAME IS NOT DISTINCT FROM l.TITLE_NAME
            AND m.TITLE_ROLE IS NOT DISTINCT FROM l.TITLE_ROLE
            AND m.TITLE_SUB_ROLE IS NOT DISTINCT FROM l.TITLE_SUB_ROLE""")
        assert con.execute("SELECT count(*) FROM classified").fetchone()[0] == master_rows
        con.execute("CREATE TABLE researchers AS SELECT * FROM classified WHERE CLASSIFICATION_STATUS IN ('research', 'review_needed')")
        category_counts = {category: {"rows": 0, "distinct_people": 0} for category in CATEGORIES}
        for category, rows, people in con.execute("SELECT ROLE_CATEGORY, count(*), count(DISTINCT PERSON_ID) FROM classified GROUP BY ROLE_CATEGORY").fetchall():
            category_counts[category] = {"rows": rows, "distinct_people": people}
        status_counts = {status: {"rows": rows, "distinct_people": people}
                         for status, rows, people in con.execute("SELECT CLASSIFICATION_STATUS, count(*), count(DISTINCT PERSON_ID) FROM classified GROUP BY CLASSIFICATION_STATUS").fetchall()}
        candidates, candidate_people = con.execute("SELECT count(*), count(DISTINCT PERSON_ID) FROM researchers").fetchone()

        # Ephemeral in-memory secret; credentials are never written to a file.
        con.execute("CREATE SECRET r2_analysis (TYPE S3, KEY_ID " + sql_literal(os.environ["R2_ACCESS_KEY_ID"]) +
                    ", SECRET " + sql_literal(os.environ["R2_SECRET_ACCESS_KEY"]) +
                    ", REGION 'auto', ENDPOINT " + sql_literal(parsed_endpoint.netloc) +
                    ", URL_STYLE 'path', USE_SSL true)")
        artifacts = []
        for table, key, count in (("master", MASTER_KEY, master_rows), ("researchers", RESEARCH_KEY, candidates)):
            uri = f"s3://{bucket}/{key}"
            print(f"Writing {table}: {count} rows directly to {uri}", flush=True)
            con.execute(f"COPY (SELECT * FROM {table} ORDER BY PERSON_ID, START_DATE, TITLE_NAME) TO {sql_literal(uri)} (FORMAT PARQUET, COMPRESSION ZSTD)")
            remote_size = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
            assert remote_size > 0
            url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
            con.execute(f"CREATE OR REPLACE TABLE verified AS SELECT * FROM read_parquet({sql_literal(url)})")
            assert con.execute("SELECT count(*) FROM verified").fetchone()[0] == count
            assert con.execute(f"SELECT count(*) FROM ((SELECT * FROM verified EXCEPT ALL SELECT * FROM {table}) UNION ALL (SELECT * FROM {table} EXCEPT ALL SELECT * FROM verified))").fetchone()[0] == 0
            artifacts.append({"key": key, "bytes": remote_size, "rows": count, "roundtrip_verified": True})

        report = {
            "created_at": dt.datetime.now(dt.UTC).isoformat(), "rule_version": RULE_VERSION,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_checkpoint": str(CHECKPOINT), "source_manifest_sha256": fp["source_manifest_sha256"],
            "source_batch_count": len(expected), "source_rows": source_rows,
            "exact_duplicate_rows_removed": source_rows - master_rows,
            "all_hires_rows": master_rows, "all_hires_distinct_people": master_people,
            "multiple_employment_records": duplicate_groups,
            "research_candidate_rows": candidates, "research_candidate_distinct_people": candidate_people,
            "classification_status_counts": status_counts, "role_category_counts": category_counts,
            "artifacts": artifacts, "title_classifications": title_audit,
            "methodology": [
                "Master preserves all nine original source fields and removes only duplicates across all nine fields.",
                "Role classification uses only TITLE_NAME, TITLE_ROLE and TITLE_SUB_ROLE; title-specific non-research duties override incidental research keywords and noisy role labels.",
                "The research Parquet includes confirmed research and review-needed candidates. Filter IS_RESEARCH_HIRE = true for the conservative research count; NULL means unresolved, never assumed research.",
                "Generic MTS, applied AI, software engineering and safeguards labels are not sufficient research evidence; ambiguous records remain available for review.",
                "Research categories are mutually exclusive using rule precedence; RESEARCH_AREAS preserves overlapping domain tags. People can occur in multiple categories, so person counts are not additive.",
                "Fellows are included as requested; source employment records, including fellowships and self-described affiliations, are not independently verified hires.",
                "No Person lookup, demographic inference, or new Dewey Experience query was performed. No datasets were persisted locally.",
            ],
        }
        body = (json.dumps(report, indent=2, default=str) + "\n").encode()
        s3.put_object(Bucket=bucket, Key=REPORT_KEY, Body=body, ContentType="application/json")
        assert s3.head_object(Bucket=bucket, Key=REPORT_KEY)["ContentLength"] == len(body)
        print(json.dumps({k: report[k] for k in (
            "all_hires_rows", "all_hires_distinct_people", "exact_duplicate_rows_removed",
            "research_candidate_rows", "research_candidate_distinct_people", "classification_status_counts",
            "role_category_counts", "artifacts")}, indent=2))
        print("Audit report:", f"s3://{bucket}/{REPORT_KEY}")
    finally:
        con.close()
        s3.close()


if __name__ == "__main__":
    main()

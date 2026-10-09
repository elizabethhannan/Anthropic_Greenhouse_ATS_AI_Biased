import os
from pathlib import Path

import httpx


DATASET_ID = "prj_37ga6vtz__fldr_btzpw6hub88mzykfi"
BASE_URL = f"https://api.deweydata.io/api/v1/external/data/{DATASET_ID}"

START_DATE = "2026-04-01"
END_EXCLUSIVE = "2026-10-01"
TARGET_COMPANY = "anthropic"

OUTPUT_DIR = Path("dewey-anthropic-output")
OUTPUT_CSV = OUTPUT_DIR / "anthropic_experience_2026_04_to_2026_09.csv"
PARTS_DIR = OUTPUT_DIR / "parts-exact-day"
FILES_PER_PART = int(os.getenv("DEWEY_FILES_PER_PART", "10"))

KEEP_FIELDS = [
    "person_id",
    "company_name",
    "company_id",
    "title_name",
    "title_role",
    "title_sub_role",
    "start_date",
    "end_date",
    "is_primary",
]


def dewey_client() -> httpx.Client:
    api_key = os.getenv("DEWEY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "DEWEY_API_KEY is not set. "
            "Add it in PyCharm Run Configurations or export it in the terminal."
        )

    return httpx.Client(
        headers={
            "X-API-Key": api_key,
            "User-Agent": "anthropic-pull/1.0",
        },
        timeout=httpx.Timeout(120.0),
        follow_redirects=True,
    )


def require_api_key() -> str:
    api_key = os.getenv("DEWEY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "DEWEY_API_KEY is not set. "
            "Add it in PyCharm Run Configurations or export it in the terminal."
        )

    return api_key


def get_metadata(client: httpx.Client) -> dict:
    response = client.get(f"{BASE_URL}/metadata")
    response.raise_for_status()
    return response.json()


def require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "duckdb is not installed in this Python environment. "
            "Install it with: python -m pip install duckdb"
        ) from exc

    return duckdb


def duckdb_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def get_download_links(client: httpx.Client) -> list[str]:
    links = []
    page = 1

    while True:
        response = client.get(f"{BASE_URL}/files", params={"page": page})
        response.raise_for_status()
        files_data = response.json()

        links.extend(
            file_info["link"]
            for file_info in files_data["download_links"]
            if file_info.get("file_extension") == ".snappy.parquet"
            or file_info.get("file_name", "").endswith(".parquet")
        )

        total_pages = files_data["total_pages"]
        print(f"Fetched file-list page {page} of {total_pages}.")

        if page >= total_pages:
            break

        page += 1

    return links


def write_part_csv(con, part_links: list[str], part_path: Path) -> int:
    selected_fields = ", ".join(KEEP_FIELDS)
    tmp_path = part_path.with_suffix(".tmp.csv")
    tmp_path.unlink(missing_ok=True)
    tmp_path_sql = duckdb_string_literal(tmp_path.as_posix())

    con.execute(
        f"""
        copy (
            select {selected_fields}
            from read_parquet(?)
            where lower(trim(company_name)) = ?
              and (case when length(cast(start_date as varchar)) = 7
                        then cast(start_date as varchar) || '-01'
                        else cast(start_date as varchar) end) >= ?
              and (case when length(cast(start_date as varchar)) = 7
                        then cast(start_date as varchar) || '-01'
                        else cast(start_date as varchar) end) < ?
        )
        to {tmp_path_sql}
        with (header true, delimiter ',')
        """,
        [part_links, TARGET_COMPANY, START_DATE, END_EXCLUSIVE],
    )

    row_count = con.execute(
        "select count(*) from read_csv_auto(?)",
        [tmp_path.as_posix()],
    ).fetchone()[0]

    tmp_path.replace(part_path)

    return row_count


def combine_part_csvs(part_paths: list[Path]) -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)

    total_rows = 0
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as output_file:
        wrote_header = False

        for part_path in part_paths:
            with part_path.open("r", encoding="utf-8", newline="") as part_file:
                header = part_file.readline()

                if not wrote_header:
                    output_file.write(header)
                    wrote_header = True

                for line in part_file:
                    output_file.write(line)
                    total_rows += 1

    return total_rows


def write_output_csv(download_links: list[str]) -> int:
    if not download_links:
        raise RuntimeError("No Parquet download links were returned by Dewey.")

    duckdb = require_duckdb()

    OUTPUT_DIR.mkdir(exist_ok=True)
    PARTS_DIR.mkdir(exist_ok=True)

    con = duckdb.connect()
    con.execute("set enable_progress_bar = false")
    con.execute("set enable_http_metadata_cache = true")

    link_parts = chunks(download_links, FILES_PER_PART)
    part_paths = []

    for index, part_links in enumerate(link_parts, start=1):
        part_path = PARTS_DIR / f"anthropic_part_{index:04d}.csv"
        part_paths.append(part_path)

        if part_path.exists():
            print(f"Skipping existing part {index} of {len(link_parts)}: {part_path}")
            continue

        print(
            f"Writing part {index} of {len(link_parts)} "
            f"({len(part_links)} Parquet file(s)): {part_path}"
        )
        row_count = write_part_csv(con, part_links, part_path)
        print(f"Part {index} wrote {row_count:,} row(s).")

    return combine_part_csvs(part_paths)


def main():
    require_api_key()

    with dewey_client() as client:
        metadata = get_metadata(client)

        print("Connected to Dewey.")
        print("Metadata:")
        print(metadata)

        print()
        print(
            "Dewey reports this dataset as unpartitioned, so this script will not "
            "download the full dataset."
        )
        print("Querying the signed Parquet URLs directly with DuckDB instead.")

        download_links = get_download_links(client)

    print()
    print(
        f"Querying {len(download_links)} Parquet file(s) "
        f"in batches of {FILES_PER_PART}."
    )

    row_count = write_output_csv(download_links)

    print()
    print(f"Wrote {row_count:,} Anthropic row(s) to {OUTPUT_CSV}.")


if __name__ == "__main__":
    main()

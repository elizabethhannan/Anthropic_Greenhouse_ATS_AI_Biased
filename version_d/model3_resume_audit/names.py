"""Name lists for Model 3 (pre-registered rule; see model3_plan.md section 2).

Source: U.S. Social Security Administration birth counts, via the `babynames`
dataset (Wickham, 2019), file data/babynames.rda from github.com/hadley/babynames.
``make_table`` derives data/names_ssa_1985_2000.csv from that file; ``select_names``
applies the rule to the committed table.

Rule: births 1985–2000; rank names by count within sex; keep names with >= 99% of
their births in that sex; take the top 10 per sex.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "data" / "names_ssa_1985_2000.csv"
YEARS = (1985, 2000)
MIN_SHARE = 0.99
TOP = 10

SURNAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones",
            "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]  # 2010 Census top 10


def make_table(rda_path: str | Path, keep: int = 40) -> dict:
    """Write the derived table (top ``keep`` names per sex). Needs pyreadr."""
    import pyreadr

    rda_path = Path(rda_path)
    sha = hashlib.sha256(rda_path.read_bytes()).hexdigest()
    df = list(pyreadr.read_r(str(rda_path)).values())[0]
    df = df[(df.year >= YEARS[0]) & (df.year <= YEARS[1])]
    d = df.groupby(["sex", "name"]).n.sum().reset_index()
    total = d.groupby("name").n.sum()
    rows = []
    for sex in ("F", "M"):
        s = d[d.sex == sex].sort_values(["n", "name"], ascending=[False, True]).head(keep)
        for rank, (name, n) in enumerate(zip(s.name, s.n), start=1):
            rows.append({"sex": sex, "rank": rank, "name": name, "births_1985_2000": int(n),
                         "share_this_sex": round(float(n / total[name]), 4)})
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    with open(TABLE, "w", newline="", encoding="utf-8") as fh:
        fh.write(f"# source: babynames data/babynames.rda (SSA), sha256 {sha}; births {YEARS[0]}-{YEARS[1]}\n")
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return {"sha256": sha, "rows": len(rows)}


def read_table(path: Path = TABLE) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def select_names(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else read_table()
    out = {}
    for sex, key in (("F", "women"), ("M", "men")):
        r = sorted((x for x in rows if x["sex"] == sex), key=lambda x: int(x["rank"]))
        out[key] = [x["name"] for x in r if float(x["share_this_sex"]) >= MIN_SHARE][:TOP]
    return out


if __name__ == "__main__":
    import sys
    print(make_table(sys.argv[1]))
    print(select_names())

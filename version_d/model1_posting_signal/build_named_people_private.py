"""Assemble outputs/private/named_people_gender.csv (PRIVATE; git-ignored; never published).

Inputs (all private):
  outputs/private/inputs/fellows_posting_versions.csv   from version_d/01_fellows_named_people.py (8 versions)
  outputs/private/gender_batch_*.json                    public self-identification coding (URL, verbatim quote, date)
  outputs/private/inputs/apr26_economics_named.json      April 26 Economics capture: listed mentors and credits
The ninth version, the April 26, 2026 Economics capture (job 5183053008), is added from the project
evidence note (2 listed mentors, 7 past-project credits; OCR of Elizabeth's screen capture).

One row per (person, version, role). Unknown stays Unknown.
"""

from __future__ import annotations

import csv
import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIV = HERE / "outputs" / "private"

# The April 26 Economics capture's named people are kept in a private input file (names never committed):
APR26_FILE = PRIV / "inputs" / "apr26_economics_named.json"

VERSION_LABELS = {
    "652e5eb5ba": "AI Security Fellow (Apr 2)",
    "c37171d129": "AI Safety Fellow (Apr 3)",
    "afbc103366": "ML Systems & Performance (Apr 15)",
    "6ed2e1bac0": "AI Safety & Security, combined (Sep 29)",
    "2d6b03a6a9": "ML Systems & RL, combined (Sep 29)",
    "756c3269da": "STEM Fellow (Apr 18)",
    "a4cd2d7f38": "Economics & Policy, Anthropic Institute (Sep 29)",
    "843a375d9a": "Reinforcement Learning (Jun 10)",
}


def split(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(";") if x.strip()]


def main():
    codes = {}
    for f in sorted(glob.glob(str(PRIV / "gender_batch_*.json"))):
        for r in json.loads(Path(f).read_text(encoding="utf-8")):
            codes[r["person"]] = r
    rows = []
    with open(PRIV / "inputs" / "fellows_posting_versions.csv", newline="", encoding="utf-8") as fh:
        versions = list(csv.DictReader(fh))
    entries = [(VERSION_LABELS.get(v["version_id"], v["title"]), split(v["listed_mentors"]), split(v["project_credits"]))
               for v in versions]
    apr26 = json.loads(APR26_FILE.read_text(encoding="utf-8"))
    entries.append((apr26["version"], apr26["mentors"], apr26["credits"]))
    missing = set()
    for label, mentors, credits in entries:
        for role, names in (("mentor", mentors), ("credit", credits)):
            for n in names:
                c = codes.get(n)
                if c is None:
                    missing.add(n)
                    c = {"code": "unknown", "source_url": "", "quote": "", "date_accessed": ""}
                rows.append({"person": n, "version": label, "role": role, "code": c["code"],
                             "source_url": c.get("source_url") or "", "quote": c.get("quote") or "",
                             "date_accessed": c.get("date_accessed") or ""})
    with open(PRIV / "named_people_gender.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["person", "version", "role", "code", "source_url", "quote", "date_accessed"])
        w.writeheader()
        w.writerows(rows)
    people = {r["person"] for r in rows}
    print(f"rows {len(rows)}; people {len(people)}; mentor listings {sum(r['role']=='mentor' for r in rows)}; "
          f"credit listings {sum(r['role']=='credit' for r in rows)}; versions {len(entries)}; uncoded {sorted(missing)}")


if __name__ == "__main__":
    main()

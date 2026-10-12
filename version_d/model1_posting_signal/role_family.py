"""Step 2: map posting titles to role families with pre-registered rules.

Rules are applied in order to the title; the first match wins:
  Fellows (contains "Fellow") -> Research-titled (contains "Research") ->
  Engineering (Engineer, Developer, Software, Infrastructure, Reliability) -> Other.

Version C also carries ``posting_classification`` (title + department rules, plus a
description-based research signal). The analysis plan records which one is primary;
``version_c_family`` gives the mapping so both can be compared.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

RULES = [
    ("Fellows", re.compile(r"fellow", re.I)),
    ("Research-titled", re.compile(r"research", re.I)),
    ("Engineering", re.compile(r"engineer|developer|software|infrastructure|reliability", re.I)),
]
DEFAULT = "Other"
FAMILIES = ["Fellows", "Research-titled", "Engineering", "Other"]

VERSION_C_MAP = {
    "Fellows Researcher": "Fellows",
    "Research Scientist": "Research-titled",
    "Research Engineer": "Research-titled",
    "Research-oriented MTS": "Research-titled",
    "Alignment / AI Safety": "Research-titled",
    "Interpretability": "Research-titled",
    "Pre-training": "Research-titled",
    "Post-training": "Research-titled",
    "Reinforcement Learning": "Research-titled",
    "Evaluations": "Research-titled",
    "Model Behavior": "Research-titled",
    "AI/ML Research - Other": "Research-titled",
    "Engineering - Non-Research": "Engineering",
    "Other / Non-Research": "Other",
    "Review Needed": "Other",
}


def assign_family(title: str) -> str:
    for fam, pat in RULES:
        if pat.search(title or ""):
            return fam
    return DEFAULT


def version_c_family(classification: str | None) -> str | None:
    if classification is None:
        return None
    return VERSION_C_MAP.get(classification, "Other")


def family_report(records: list[dict], n_samples: int = 20, seed: int = 20261011) -> dict:
    """Counts per family and up to n sample titles per family (deterministic)."""
    import random
    rnd = random.Random(seed)
    by = defaultdict(list)
    for r in records:
        by[assign_family(r["title"])].append(r["title"])
    out = {"counts": {f: len(by.get(f, [])) for f in FAMILIES}, "samples": {}}
    for f in FAMILIES:
        titles = sorted(set(by.get(f, [])))
        out["samples"][f] = sorted(rnd.sample(titles, min(n_samples, len(titles))))
    vc = Counter((assign_family(r["title"]), version_c_family(r.get("version_c_classification")))
                 for r in records if r.get("version_c_classification"))
    out["agreement_with_version_c"] = {f"{a} | {b}": n for (a, b), n in sorted(vc.items())}
    return out

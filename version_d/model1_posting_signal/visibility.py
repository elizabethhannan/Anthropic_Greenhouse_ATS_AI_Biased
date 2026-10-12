"""T6: who Fellows postings make visible, and their gender.

Gender of named people comes ONLY from public self-identification (pronouns or
explicit self-description in an official bio, faculty page, personal site or
published interview), recorded with URL, exact quote and date accessed in
outputs/private/named_people_gender.csv. Never inferred from names, photos or
voice. Unknown stays Unknown and is reported with bounds.

Only aggregates leave this module. Names never appear in any output.
"""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import binomtest, fisher_exact, norm

CODES = ("woman", "man", "nonbinary", "unknown")
PRIVATE_COLUMNS = ["person", "version", "role", "code", "source_url", "quote", "date_accessed"]


def wilson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Wilson (1927) score interval."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = norm.ppf(1 - (1 - level) / 2)
    ph = k / n
    den = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (centre - half, centre + half)


def unknown_bounds(women: int, men: int, unknown: int, nonbinary: int = 0) -> tuple[float, float]:
    """Share of women among ALL named people if every Unknown were not a woman (low) or a woman (high).
    Nonbinary people count in the total and never as women."""
    total = women + men + unknown + nonbinary
    if total == 0:
        return (float("nan"), float("nan"))
    return (women / total, (women + unknown) / total)


def load_private(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    missing = set(PRIVATE_COLUMNS) - set(rows[0].keys() if rows else PRIVATE_COLUMNS)
    if missing:
        raise ValueError(f"private file missing columns: {sorted(missing)}")
    for r in rows:
        if r["code"] not in CODES:
            raise ValueError(f"invalid code {r['code']!r}")
        if r["code"] != "unknown" and not (r["source_url"] and r["quote"] and r["date_accessed"]):
            raise ValueError("a known code requires source_url, quote and date_accessed")
    return rows


def person_codes(rows: list[dict]) -> dict:
    """One code per distinct person (rows repeat across versions/roles)."""
    codes = {}
    for r in rows:
        prev = codes.get(r["person"])
        if prev and prev != r["code"]:
            raise ValueError("conflicting codes for the same person")
        codes[r["person"]] = r["code"]
    return codes


def _counts(counter) -> dict:
    """Every code, always present, so totals reconcile (women + men + nonbinary + unknown)."""
    return {"women": counter.get("woman", 0), "men": counter.get("man", 0),
            "nonbinary": counter.get("nonbinary", 0), "unknown": counter.get("unknown", 0)}


def analyze(rows: list[dict], fellows_hires_women: int, fellows_hires_known: int, parity: float = 0.5) -> dict:
    """Women's share 'among known' compares women with men (the binary sex categories of the hire data);
    nonbinary people are reported separately and included in every total and in the bounds."""
    codes = person_codes(rows)
    c = Counter(codes.values())
    w, m, u, nb = c.get("woman", 0), c.get("man", 0), c.get("unknown", 0), c.get("nonbinary", 0)
    known = w + m
    share = w / known if known else float("nan")
    # T6b listing-weighted: each appearance counts
    lw = Counter(r["code"] for r in rows)
    lw_known = lw.get("woman", 0) + lw.get("man", 0)
    by_version = defaultdict(lambda: defaultdict(set))
    for r in rows:
        by_version[r["version"]][r["code"]].add(r["person"])
        by_version[r["version"]]["all"].add(r["person"])
    roles = {}
    for role in ("mentor", "credit"):
        people = {r["person"] for r in rows if r["role"] == role}
        roles[role + "s"] = _counts(Counter(codes[p] for p in people))
    comparisons = []
    if known:
        comparisons.append({"vs": "parity 50%", "test": "exact binomial",
                            "p": binomtest(w, known, parity).pvalue})
        table = [[w, m], [fellows_hires_women, fellows_hires_known - fellows_hires_women]]
        comparisons.append({"vs": f"Fellows hires {fellows_hires_women}/{fellows_hires_known}",
                            "test": "Fisher exact", "p": fisher_exact(table).pvalue})
    return {
        "named_people": len(codes),
        "coded": _counts(c),
        "women_share_known": {"value": share, "ci": list(wilson(w, known)) if known else [None, None],
                              "bounds": list(unknown_bounds(w, m, u, nb))},
        "listing_weighted_women_share": (lw.get("woman", 0) / lw_known) if lw_known else None,
        "listings": _counts(lw),
        "by_version": [{"version": v, "named": len(d["all"]), "women": len(d["woman"]), "men": len(d["man"]),
                        "nonbinary": len(d["nonbinary"]), "unknown": len(d["unknown"])}
                       for v, d in sorted(by_version.items())],
        "mentors_vs_credits": roles,
        "comparisons": comparisons,
    }

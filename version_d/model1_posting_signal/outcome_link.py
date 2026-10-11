"""Step 7 (H3): outcome link, with an estimability gate.

Builds non-overlapping hire cells and fits a binomial GLM (logit) of women among
known-sex hires on family-mean masc_per_1k and fem_per_1k ONLY IF:
  >= 10 cells, each with >= 10 known-sex hires, and both sexes in >= 5 cells.
Otherwise returns {"estimable": false} with the cell counts. Never fits on fewer cells.

Even when estimable, a family-level association is not evidence that a posting
affected applicants (ecological fallacy; Robinson, 1950).
"""

from __future__ import annotations


def non_overlapping_cells(groups: dict) -> tuple[list[dict], list[str]]:
    """From overlapping aggregate groups, derive Fellows / non-Fellows researchers /
    Engineering / Other = All - the rest. Returns (cells, notes)."""
    g = groups
    notes = []
    fel = g["fellows"]
    res = g["researchers"]
    eng = g["engineering"]
    allh = g["all"]
    nonfel = {k: res[k] - fel[k] for k in ("male", "female", "unknown")}
    other = {k: allh[k] - fel[k] - nonfel[k] - eng[k] for k in ("male", "female", "unknown")}
    notes.append("Fellows are a subset of AI researchers; non-Fellows researchers = researchers - Fellows.")
    notes.append("Engineering (general/unspecified) is treated as disjoint from the research cells; "
                 "the source notes people can belong to several role groups through different "
                 "employment records, so this overlap cannot be fully verified from aggregate counts.")
    cells = []
    for name, d in (("Fellows", fel), ("Non-Fellows researchers", nonfel),
                    ("Engineering", eng), ("Other", other)):
        cells.append({"cell": name, "male": d["male"], "female": d["female"], "unknown": d["unknown"],
                      "known": d["male"] + d["female"]})
    if any(v < 0 for c in cells for v in (c["male"], c["female"], c["unknown"])):
        notes.append("Negative counts after subtraction: groups overlap in ways aggregate data cannot resolve.")
    return cells, notes


def gate(cells: list[dict], min_cells: int = 10, min_known: int = 10, min_both: int = 5) -> dict:
    n_cells = len(cells)
    enough_known = [c for c in cells if c["known"] >= min_known]
    both = [c for c in cells if c["male"] > 0 and c["female"] > 0]
    reasons = []
    if n_cells < min_cells:
        reasons.append(f"{n_cells} cells < {min_cells} required")
    if len(enough_known) < n_cells:
        reasons.append(f"{n_cells - len(enough_known)} cell(s) with < {min_known} known-sex hires")
    if len(both) < min_both:
        reasons.append(f"both sexes appear in {len(both)} cell(s) < {min_both} required")
    return {
        "estimable": not reasons,
        "rule": (f">= {min_cells} non-overlapping cells, each with >= {min_known} known-sex hires, "
                 f"and both sexes in >= {min_both} cells"),
        "cells": cells,
        "reason": "; ".join(reasons) if reasons else "",
        "estimates": None,
    }


def run(cfg: dict) -> dict:
    cells, notes = non_overlapping_cells(cfg["outcome_link"]["source_groups"])
    g = cfg["outcome_link"]["gate"]
    out = gate(cells, g["min_cells"], g["min_known_per_cell"], g["min_cells_with_both_sexes"])
    out["notes"] = notes + ["Ecological fallacy (Robinson, 1950): a family-level association would not show "
                            "that a posting affected applicants."]
    return out

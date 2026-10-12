"""Model 1 tests (pytest). If a test fails, report it; do not edit it to pass.

Tests 7 and 8 need the scored outputs; until the corpus is built and the plan is
approved they run on what exists and SKIP (not pass) the parts that need outputs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import bias_tests as bt  # noqa: E402
import build_corpus as bc  # noqa: E402
import model1b_estimator as m1b  # noqa: E402
import outcome_link as ol  # noqa: E402
from lexicon import load_lexicon, score_text  # noqa: E402
from visibility import wilson  # noqa: E402

CFG = yaml.safe_load((HERE / "config.yaml").read_text())
OUT = HERE / "outputs"
PRIVATE = OUT / "private" / "named_people_gender.csv"


def test_0_wordlist_pinned():
    import hashlib
    lex = load_lexicon()
    exp = CFG["wordlist"]["expected_counts"]
    assert (len(lex.masculine), len(lex.feminine), len(lex.hyphenated)) == (
        exp["masculine"], exp["feminine"], exp["hyphenated"])
    digest = hashlib.sha256((HERE / CFG["wordlist"]["file"]).read_bytes()).hexdigest()
    assert digest == CFG["wordlist"]["sha256"]


# 1 -----------------------------------------------------------------------------
def test_1_lexicon_arithmetic():
    s = score_text("We want an ambitious, supportive leader.")
    assert sorted(s.masc_stems) == ["ambitio", "lead"]
    assert s.fem_stems == ["support"]
    # "We want an ambitious supportive leader" = 6 words. (The first draft of this test
    # asserted 7, a miscount in the test itself; the scoring code was not changed.)
    assert s.n_words == 6
    # exact per-1,000 math on a 1,000-word fixture: 7 masculine, 3 feminine tokens
    words = ["ambitious"] * 4 + ["leader"] * 3 + ["supportive"] * 3 + ["table"] * 990
    s2 = score_text(" ".join(words))
    assert s2.n_words == 1000
    assert s2.masc_per_1k == 7.0 and s2.fem_per_1k == 3.0 and s2.net_per_1k == 4.0


# 2 -----------------------------------------------------------------------------
def test_2_word_start_rule():
    s = score_text("Do not mislead users.")
    assert "lead" not in s.masc_stems and s.masc == 0


# 3 -----------------------------------------------------------------------------
def test_3_boilerplate_removal():
    common = "About us: we build safe systems."
    half = "We offer generous benefits."        # in exactly 2 of 4 records (50%) -> removed
    rare = "This role is on the data team."      # in 1 of 4 records (25%) -> kept
    texts = [
        f"{common} {half} Unique alpha sentence here.",
        f"{common} {half} Unique beta sentence here.",
        f"{common} {rare} Unique gamma sentence here.",
        f"{common} Unique delta sentence here.",
    ]
    recs = [{"text": t} for t in texts]
    removed, table = bc.boilerplate(recs, 0.50)
    assert removed == {bc.sentence_key(common), bc.sentence_key(half)}
    cleaned = [bc.remove_sentences(t, removed) for t in texts]
    assert all(common not in c and half not in c for c in cleaned)
    assert rare in cleaned[2]


# 4 -----------------------------------------------------------------------------
def test_4_wilson_ci():
    lo, hi = wilson(8, 22)
    assert round(lo * 100, 1) == 19.7 and round(hi * 100, 1) == 57.0


# 5 -----------------------------------------------------------------------------
def test_5_estimability_gate_current_cells():
    out = ol.run(CFG)
    assert out["estimable"] is False
    assert len(out["cells"]) == 4
    assert out["estimates"] is None


# 6 -----------------------------------------------------------------------------
def test_6_model1b_recovery():
    res = m1b.validate(CFG)
    assert res["coverage_in_simulation"] >= CFG["model1b"]["coverage_target"], res


# 7 -----------------------------------------------------------------------------
def _public_texts():
    files = [OUT / "model1_results.json", OUT / "model_card.md", OUT / "dashboard_updates.md",
             OUT / "methods_appendix.md"]
    files += sorted((OUT / "figures").glob("*.svg"))
    return {p: p.read_text(encoding="utf-8", errors="ignore") for p in files if p.exists()}


def test_7_privacy():
    if not PRIVATE.exists():
        pytest.skip("private named-people file not created yet (T6 coding pending)")
    import csv
    with open(PRIVATE, newline="", encoding="utf-8") as fh:
        names = {r["person"].strip() for r in csv.DictReader(fh) if r["person"].strip()}
    texts = _public_texts()
    if not texts:
        pytest.skip("no public outputs written yet")
    for path, txt in texts.items():
        for name in names:
            assert name not in txt, f"name leaked into {path.name}"


# 8 -----------------------------------------------------------------------------
def test_8_reproducible():
    """Same inputs and seed give identical results, apart from run_date.
    Runs the full analysis twice when the (private, local) corpus and labels exist."""
    a = np.array([3.0, 5.0, 7.0, 9.0, 4.0])
    b = np.array([1.0, 2.0, 2.5, 3.0, 4.0, 2.0])
    scores = {"raw": {"masc_per_1k": {"X": a, "Other": b}}}
    r1 = bt.family_comparisons(scores, ["X", "Other"], "Other", ["masc_per_1k"], ["raw"], 500, 500, CFG["seed"])
    r2 = bt.family_comparisons(scores, ["X", "Other"], "Other", ["masc_per_1k"], ["raw"], 500, 500, CFG["seed"])
    assert json.dumps(r1) == json.dumps(r2)
    needed = [OUT / "corpus" / "corpus_primary.jsonl", HERE / "labels" / "sense_audit_labels.csv",
              HERE / "labels" / "convergent_labels.csv", PRIVATE]
    if not all(p.exists() for p in needed):
        pytest.skip("component check passed; full pipeline needs the local corpus, labels and private file")
    import analyze
    x = analyze.main(write=False, run_date="X")
    y = analyze.main(write=False, run_date="X")
    assert json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)
    saved = json.loads((OUT / "model1_results.json").read_text(encoding="utf-8"))
    saved["run_date"] = "X"
    assert json.dumps(saved, sort_keys=True) == json.dumps(x, sort_keys=True)


def test_holm_and_cliffs():
    assert bt.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert bt.cliffs_delta([2, 3], [1, 1]) == 1.0
    assert bt.cliffs_delta([1, 2], [1, 2]) == 0.0


# Review follow-ups (Codex review on PR #1) ------------------------------------
def test_corpus_records_without_id_stay_distinct(tmp_path):
    words = " ".join(["word"] * 200)
    recs = [{"exact_title": "Role A", "description_text": "Alpha posting. " + words},
            {"exact_title": "Role B", "description_text": "Beta posting. " + words}]
    f = tmp_path / "noid.json"
    f.write_text(json.dumps({"records": recs}), encoding="utf-8")
    res = bc.build([f], 0.99, 10)
    ids = [r["posting_id"] for r in res["primary"]]
    assert len(ids) == 2 and len(set(ids)) == 2
    assert all(i.startswith("noid:") for i in ids)
    assert res["counts"]["records_without_posting_id"] == 2


def _cells(n):
    return [{"cell": f"c{i}", "male": 20 + i, "female": 10 + (i % 4), "unknown": 3, "known": 30 + i + (i % 4)}
            for i in range(n)]


def test_outcome_gate_fits_glm_when_gate_passes():
    cells = _cells(12)
    cov = {c["cell"]: {"masc_per_1k": 5.0 + i, "fem_per_1k": 8.0 + (i % 3)} for i, c in enumerate(cells)}
    out = ol.run(CFG, cov, cells=cells)
    assert out["estimable"] is True and out["fitted"] is True
    assert [t["term"] for t in out["estimates"]["terms"]] == ["intercept", "masc_per_1k", "fem_per_1k"]


def test_outcome_gate_passing_without_covariates_is_flagged():
    out = ol.run(CFG, None, cells=_cells(12))
    assert out["estimable"] is True and out["fitted"] is False and out["estimates"] is None
    assert "covariates are missing" in out["reason"]


def test_visibility_nonbinary_totals_reconcile():
    import visibility as vis
    rows = [{"person": p, "version": "V1", "role": r, "code": c, "source_url": "u" if c != "unknown" else "",
             "quote": "q" if c != "unknown" else "", "date_accessed": "d" if c != "unknown" else ""}
            for p, r, c in (("A", "mentor", "woman"), ("B", "mentor", "man"), ("C", "credit", "nonbinary"),
                            ("D", "credit", "unknown"))]
    out = vis.analyze(rows, 8, 22)
    assert sum(out["coded"].values()) == out["named_people"] == 4
    assert out["coded"]["nonbinary"] == 1
    assert sum(out["listings"].values()) == len(rows)
    assert out["women_share_known"]["bounds"] == [0.25, 0.5]
    v = out["by_version"][0]
    assert v["women"] + v["men"] + v["nonbinary"] + v["unknown"] == v["named"]

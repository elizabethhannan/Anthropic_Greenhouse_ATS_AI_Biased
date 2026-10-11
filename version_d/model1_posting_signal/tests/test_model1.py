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
def test_8_reproducible_components():
    """Deterministic components give identical results for the same seed.
    The full-pipeline check runs once the corpus exists (see run_model1.py)."""
    a = np.array([3.0, 5.0, 7.0, 9.0, 4.0])
    b = np.array([1.0, 2.0, 2.5, 3.0, 4.0, 2.0])
    scores = {"raw": {"masc_per_1k": {"X": a, "Other": b}}}
    r1 = bt.family_comparisons(scores, ["X", "Other"], "Other", ["masc_per_1k"], ["raw"], 500, 500, CFG["seed"])
    r2 = bt.family_comparisons(scores, ["X", "Other"], "Other", ["masc_per_1k"], ["raw"], 500, 500, CFG["seed"])
    assert json.dumps(r1) == json.dumps(r2)
    full = OUT / "model1_results.json"
    if not full.exists():
        pytest.skip("component check passed; full-pipeline reproducibility pending corpus")


def test_holm_and_cliffs():
    assert bt.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert bt.cliffs_delta([2, 3], [1, 1]) == 1.0
    assert bt.cliffs_delta([1, 2], [1, 2]) == 0.0

"""Model 3 tests 1–7 (pre-registered in model3_plan.md). If a test fails, report
it; do not edit it to pass.

Run from version_d/model3_resume_audit/:  pytest -q tests/test_model3.py
"""

from __future__ import annotations

import json
import re
import sys
from math import comb
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import audit  # noqa: E402
import run_model3  # noqa: E402
from build_resumes import WORD_TEST_ITEMS, build_base, render, word_test_line  # noqa: E402
from names import read_table, select_names  # noqa: E402
from screeners import TfidfScreener, cosine  # noqa: E402

CFG = run_model3.load_config()
BASE = build_base(CFG["seed"])
NAMES = select_names(read_table())
ALL = NAMES["women"] + NAMES["men"]
GENDERED = {"he", "she", "his", "her", "him", "hers", "woman", "women", "man", "men", "female", "male",
            "girl", "boy", "wife", "husband", "mother", "father", "sorority", "fraternity"}


def _words(text):
    return set(re.findall(r"[a-z]+", text.lower()))


# 1 -----------------------------------------------------------------------------
def test_1_paired_construction():
    for r in BASE:
        variants = [render(r, n) for n in ALL] + [render(r, None)]
        bodies = {"\n".join(v.split("\n")[2:]) for v in variants}
        assert len(bodies) == 1, r["resume_id"]
        for v, n in zip(variants, ALL + [None]):
            line1, line2 = v.split("\n")[:2]
            rest2 = line2.split(" | ", 1)[1]
            assert rest2 == f"{r['phone']} | {r['city']}"
            if n:
                assert line1 == f"{n} {r['surname']}"
                assert line2.startswith(f"{n.lower()}.{r['surname'].lower()}@example.com")


# 2 -----------------------------------------------------------------------------
def test_2_no_gendered_words():
    for r in BASE:
        assert not (_words(render(r, None)) & GENDERED), r["resume_id"]
        for item in WORD_TEST_ITEMS:
            plain = render(r, None, activity=word_test_line(item, "plain"))
            assert not (_words(plain) & GENDERED)
            for form, word in (("women", "women"), ("men", "men")):
                v = render(r, None, activity=word_test_line(item, form))
                assert _words(v) - _words(plain) == {word, "s"} - _words(plain)
                assert (_words(v) & GENDERED) == {word}


# 3 -----------------------------------------------------------------------------
def test_3_name_rule():
    assert NAMES["women"] == ["Jessica", "Ashley", "Amanda", "Sarah", "Emily", "Samantha", "Jennifer",
                              "Brittany", "Elizabeth", "Stephanie"]
    assert NAMES["men"] == ["Michael", "Christopher", "Matthew", "Joshua", "Daniel", "Andrew", "David",
                            "James", "Joseph", "Nicholas"]


# 4 -----------------------------------------------------------------------------
def test_4_exact_permutation():
    splits = audit.all_splits(20, 10)
    assert len(splits) == comb(20, 10) == 184756
    E = np.r_[np.ones(10), np.zeros(10)]
    res = audit.exact_permutation(E, list(range(10)), splits)
    assert res["G"] == pytest.approx(1.0)
    assert res["p_exact"] == pytest.approx(2 / 184756)
    # A screener that ignores the header (scores the body only) gives G = 0, p = 1
    rng = np.random.default_rng(0)
    body = rng.normal(size=(30, 1, 5))
    S = np.repeat(body, 21, axis=1)
    E0 = audit.name_effects(S).mean(axis=1)
    res0 = audit.exact_permutation(E0, list(range(10)), splits)
    assert res0["G"] == 0.0 and res0["p_exact"] == 1.0


# 5 -----------------------------------------------------------------------------
def test_5_validity_metrics():
    S = np.tile(np.arange(30, dtype=float)[:, None], (1, 4))
    tiers = np.repeat([1, 2, 3], 10)
    assert np.allclose(audit.tier_validity(S, tiers), np.corrcoef(np.argsort(np.argsort(tiers)), np.arange(30))[0, 1]) or \
        np.all(audit.tier_validity(S, tiers) > 0.9)
    S_ordered = np.tile(np.repeat([1.0, 2.0, 3.0], 10)[:, None], (1, 3))
    assert np.allclose(audit.tier_validity(S_ordered, tiers), 1.0)
    assert np.allclose(audit.family_auc(np.ones((10, 3)) * 2, np.ones((20, 3))), 1.0)


# 6 -----------------------------------------------------------------------------
def test_6_tfidf_control_is_name_blind():
    postings = run_model3.load_postings(CFG)
    scr = TfidfScreener([p["text"] for p in postings])
    sub = [r for r in BASE if r["family"] == "engineering"][:20]
    P = scr.embed([p["text"] for p in postings if p["family"] == "engineering"][:30])
    S = np.stack([cosine(scr.embed([render(r, n) for n in ALL + [None]]), P) for r in sub])
    G = audit.posting_gaps(S, range(10), range(10, 20))
    assert np.all(G == 0.0)


# 7 -----------------------------------------------------------------------------
def _strip(b: bytes) -> bytes:
    return re.sub(rb'"run_date": "[0-9-]+"', b'"run_date": ""', b)


def test_7_reproducible(tmp_path):
    run_model3.main(tmp_path / "a", quick=True)
    run_model3.main(tmp_path / "b", quick=True)
    a = (tmp_path / "a" / "model3_results.json").read_bytes()
    b = (tmp_path / "b" / "model3_results.json").read_bytes()
    assert _strip(a) == _strip(b)
    r = json.loads(a)
    assert {e["id"] for e in r["screeners"]} == {"SC0", "SC1"}

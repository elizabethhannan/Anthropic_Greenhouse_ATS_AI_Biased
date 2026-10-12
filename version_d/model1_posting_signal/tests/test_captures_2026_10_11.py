"""Tests for the October 11, 2026 capture addendum. Skips the corpus/private checks when those
git-ignored inputs are absent (they are rebuilt locally; see README)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import captures_2026_10_11 as cap  # noqa: E402

CORPUS_OK = (HERE / "outputs" / "corpus" / "corpus_versions.jsonl").exists()
PRIVATE_OK = cap.PRIVATE.exists()


def test_a_checksums_match_manifest():
    m = json.loads((cap.CAP / "manifest.json").read_text(encoding="utf-8"))
    assert len(m["files"]) == 8
    for f in m["files"]:
        assert cap.sha256(cap.CAP / f["file"]) == f["sha256_pdf"]
        assert cap.sha256(cap.CAP / f["text_file"]) == f["sha256_text"]


def test_b_form_facts():
    t = lambda stem: (cap.CAP / f"{stem}.txt").read_text(encoding="utf-8")
    assert cap.form_facts(t("fellows_ai_safety_security_5183044008"))["application_route"] == "Constellation partner form"
    assert cap.form_facts(t("head_policy_design_societal_harms_5407418008"))["self_identification_survey"]
    assert not cap.form_facts(t("fellows_institute_econ_policy_5183053008"))["self_identification_survey"]


@pytest.mark.skipif(not (CORPUS_OK and PRIVATE_OK), reason="corpus or private list not present")
def test_c_classification_and_no_names_in_outputs():
    r = cap.main()
    st = {p["title"]: p["status"] for p in r["postings"]}
    assert st["Head of Policy Design, Societal Harms"] == "unchanged"
    assert st["Head of Technical Training"] == "unchanged"
    assert st["Conceptual Reasoning Fellow"].startswith("new")
    assert r["summary"]["new_named_people"] == 0
    names = {row["person"] for row in csv.DictReader(cap.PRIVATE.open(encoding="utf-8"))}
    public = (cap.OUT / "captures_2026-10-11_update.json").read_text(encoding="utf-8") + \
        (cap.OUT / "captures_2026-10-11_update.md").read_text(encoding="utf-8")
    assert not [n for n in names if n in public]

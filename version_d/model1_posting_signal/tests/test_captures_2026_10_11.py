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


def test_d_refuses_without_private_inputs(tmp_path, monkeypatch):
    """Without the git-ignored corpus or private list, main() stops and leaves the committed outputs untouched."""
    outs = [cap.OUT / "captures_2026-10-11_update.json", cap.OUT / "captures_2026-10-11_update.md"]
    before = {p: (p.read_bytes() if p.exists() else None) for p in outs}
    for attr in ("CORPUS", "PRIVATE"):
        with monkeypatch.context() as mp:
            mp.setattr(cap, attr, tmp_path / "missing")
            with pytest.raises(SystemExit):
                cap.main()
    assert {p: (p.read_bytes() if p.exists() else None) for p in outs} == before


def test_e_new_person_sharing_a_known_name_is_flagged():
    """Synthetic names only. Masking is by full name, so a shared first name does not hide a new person."""
    raw = "Mentors include Alex Example and Alex Newname. Read Scaling Laws. Apply for this job Jordan Formfield"
    found = cap.name_candidates(raw, {"Alex Example"})
    assert "Alex Newname" in found
    assert not any("Example" in c for c in found)
    assert not any("Formfield" in c for c in found)       # application form text is excluded


@pytest.mark.skipif(not (CORPUS_OK and PRIVATE_OK), reason="corpus or private list not present")
def test_c_classification_and_no_names_in_outputs():
    r = cap.main()
    st = {p["title"]: p["status"] for p in r["postings"]}
    assert st["Head of Policy Design, Societal Harms"] == "unchanged"
    assert st["Head of Technical Training"] == "unchanged"
    assert st["Conceptual Reasoning Fellow"].startswith("new")
    assert r["summary"]["unreviewed_name_candidates"] == 0
    assert r["summary"]["new_named_people"] == 0
    names = {row["person"] for row in csv.DictReader(cap.PRIVATE.open(encoding="utf-8"))}
    public = (cap.OUT / "captures_2026-10-11_update.json").read_text(encoding="utf-8") + \
        (cap.OUT / "captures_2026-10-11_update.md").read_text(encoding="utf-8")
    assert not [n for n in names if n in public]

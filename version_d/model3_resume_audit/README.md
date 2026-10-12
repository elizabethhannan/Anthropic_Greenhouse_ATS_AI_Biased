# Model 3 — Paired-résumé audit of stand-in AI screeners

**AUDIT OF STAND-IN AI SCREENERS — synthetic résumés scored against Anthropic's public postings; not Greenhouse's or Anthropic's system.**

Would an off-the-shelf AI matching model score **identical résumés** differently when the name on top is a woman's rather than a man's? 300 synthetic technical résumés were each printed with 10 women's names, 10 men's names and no name, then scored against 442 of Anthropic's public technical postings by four screeners. Pre-registered in [`model3_plan.md`](model3_plan.md) and committed before any scoring.

- Results: [`outputs/model3_results.json`](outputs/model3_results.json), [`outputs/name_effects.csv`](outputs/name_effects.csv), [`outputs/posting_gaps.csv`](outputs/posting_gaps.csv)
- Model card: [`outputs/model_card.md`](outputs/model_card.md)
- Methods appendix: [`outputs/methods_appendix.md`](outputs/methods_appendix.md)
- Figures h1–h5: [`outputs/figures/`](outputs/figures/)

## Screeners

| ID | Screener | Role |
|---|---|---|
| SC1 | WordLlama `l2_supercat` (embeddings taken from large language models) | Primary |
| SC2 | GloVe 300-d | Robustness |
| SC3 | fastText 300-d | Robustness (failed the validity check) |
| SC0 | TF-IDF keyword matcher | Design control |

## Files

| File | Role |
|---|---|
| `config.yaml` | Every parameter, fixed before scoring |
| `names.py`, `data/names_ssa_1985_2000.csv` | SSA name table and the pre-registered name rule |
| `build_resumes.py`, `data/resumes_base.json` | Résumé generator (seeded) and the 300 base résumés |
| `screeners.py` | The four screeners (text in, unit vectors out) |
| `audit.py` | Validity, exact name-level permutation test, selection impact ratio, word test, Model 1 link |
| `run_model3.py` | Runs everything → `outputs/` |
| `findings_m3.py`, `make_figures.py`, `write_docs.py` | Text, figures and documents from the numbers |
| `tests/test_model3.py` | Pre-registered tests 1–7 |

## Run it

```bash
cd version_d/model3_resume_audit
python -m pip install numpy scipy scikit-learn matplotlib pyyaml pytest wordllama==0.4.0.post1
# Postings come from Model 1's corpus (build it first with ../model1_posting_signal/build_corpus.py).
# GloVe and fastText: download glove-wiki-gigaword-300.gz and fasttext-wiki-news-subwords-300.gz
# from the gensim-data GitHub releases into one folder (checksums are verified).
MODEL3_VECTORS_DIR=/path/to/vectors python run_model3.py      # about 80 seconds
python make_figures.py && python write_docs.py
python -m pytest -q tests/test_model3.py
```

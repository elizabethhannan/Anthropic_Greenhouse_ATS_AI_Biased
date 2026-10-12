# Model 1 data addendum: captures of October 11, 2026

**OBSERVED MEASUREMENT — posting text and application forms; describes wording, not intent.** Addendum to `model1_results.json`; the pre-registered results are not re-run. Sources: `captures/2026-10-11/` (PDFs saved by Elizabeth Hannan, text extracted with pdftotext, SHA-256 in `manifest.json`), compared with the latest version of each posting in the Model 1 corpus (September 29, 2026).

## Summary

- Postings compared: 6 — unchanged 2, changed (new version) 3, new 1.
- Fellows posting versions: 9 → 13. Distinct named people before: 50. New named people: 0 (Every capitalized two- or three-word phrase on the captured postings is either a known person or listed in captures/2026-10-11/names_review.json as reviewed and not a person's name.)
- Non-Fellows postings naming people: 0. The new Conceptual Reasoning Fellow page names no one.
- Application route: Anthropic Fellows Program, AI Safety & Security → Constellation partner form; all others → Greenhouse form.
- Voluntary self-identification survey (gender, Hispanic/Latino, race and ethnicity, veteran status, "for government reporting purposes"): present on 3 forms (Head of Technical Training; Conceptual Reasoning Fellow; Head of Policy Design, Societal Harms); absent on 3 (Anthropic Fellows Program, ML Systems & Reinforcement Learning; Anthropic Fellows Program, AI Safety & Security; Anthropic Fellows Program, The Anthropic Institute (Economics & Policy)). The Constellation form itself was not captured. This describes the forms only, not how any data is stored or used.

## By posting

| Posting | Status vs. Sept 29 | Real text change | Named people incl. past-project credits (found / Sept 29) | Application route | Self-ID survey on form |
|---|---|---|---|---|---|
| Head of Technical Training | unchanged | — | none | Greenhouse form | yes |
| Anthropic Fellows Program, ML Systems & Reinforcement Learning | changed (new version) | "reference check technical" → ""; "and a research discussion" → "we may ask for references later in the process as well" | 9 of 9 | Greenhouse form | no |
| Conceptual Reasoning Fellow | new posting (not in the Sept 29 corpus) | — | none | Greenhouse form | yes |
| Anthropic Fellows Program, AI Safety & Security | changed (new version) | "" → "by october 18"; "" → "by october 18" | 30 of 30 | Constellation partner form | no |
| Anthropic Fellows Program, The Anthropic Institute (Economics & Policy) | changed (new version) | "and a research discussion" → "we may ask for references later in the process as well" | 12 of 12 | Greenhouse form | no |
| Head of Policy Design, Societal Harms | unchanged | — | none | Greenhouse form | yes |

## New posting scored with the Model 1 lexicon (information only)

Conceptual Reasoning Fellow (1147 words after boilerplate removal): raw 5.23 masculine-coded and 7.85 feminine-coded words per 1,000 (feminine-coded); sense-filtered 0.87 and 2.62 (feminine-coded). Approximate: PDF line breaks can keep some shared boilerplate sentences that the corpus removes. Not added to the pre-registered tests.

## Method

- Word-level comparison after restoring dropped ligatures (for example "o#ers" → "offers"), removing the saved page's header and job-alert lines, and ignoring chunks that repeat text found elsewhere on the page (page-break duplicates). A chunk of three or more words that remains is a real change.
- Named people are matched against the private list by full name; only counts leave the private folder, and any change chunk containing a known-name token or an unreviewed name-like phrase is redacted.
- New names: every capitalized two- or three-word phrase that is not a known person must appear in `captures/2026-10-11/names_review.json` (reviewed, not a person's name); otherwise the count reads "needs review", never zero.
- The script refuses to run, and writes nothing, when the git-ignored corpus or private list is missing.

## APA 7

Anthropic. (2026). *Job postings and application forms* [Greenhouse job board; captures by E. Hannan, October 11, 2026]. Greenhouse. https://job-boards.greenhouse.io/anthropic

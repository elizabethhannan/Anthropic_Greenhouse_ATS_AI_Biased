# Dashboard updates from Model 1 (paste into `data.js`)

Generated from `model1_results.json` (run date 2026-10-11). Aggregates only; no names.

## `DATA.tests` T6

```js
result: "Fellows: 50 named people across 9 versions; all other postings: 0 across 2,252 records. Public self-identification: 3 women, 25 men, 22 Unknown. Women 10.7% of known (95% CI 3.7%–27.2%); vs. parity p < .001; vs. Fellows hires 8/22 p = .042.",
meaning: "The only postings that show candidates who they would work with show mostly men among people with known self-identification. With 22 Unknown, the share of all named people could be 6.0%–50.0%. This measures visibility, not its effect on who applied.",
status: "observed"
```

## `DATA.tests` T7

```js
result: "Raw lexicon, masculine-coded per 1,000: Fellows 2.83 vs. Other 12.59 (diff -9.77, Holm p = .025); research-titled 9.30 (Holm p = .001). Lexicon weakly valid here: 21.0% trait-sense precision; κ = 0.24.",
meaning: "No reliable masculine-coded excess in Fellows or research postings. The standard word lists mostly match technical terms in this text, so wording scores describe words, not intent, and carry little signal here.",
status: "observed"
```

## `DATA.models.m1`

```js
statusMeasure: "MEASURED — wording scored (lexicon weakly valid, κ = 0.24); named people coded: 3 women, 25 men, 22 Unknown",
statusOutcome: "NOT ESTIMABLE — 4 non-overlapping hire cells (10 required); Model 1b ready for internal applicant data"
```

## `DATA.thesisFrame.researchQuestions` status strings

```js
// n:1 Representation
status: "Observed; origin not established. Posting visibility: women 10.7% of named people with known self-ID"
// n:3 Human decision-making
status: "Recruiting stage observed (postings); later stages not observed"
// n:5 Governance
status: "Evidence supports further investigation; posting audit and Model 1b estimator ready"
```

## New row for `DATA.thesisFrame.researchLayers`

```js
{ layer:"Posting signals", conclusion:"Observable" }
```

## Replit Agent prompt (paste into Replit)

> Add `model1_results.json` to the project root. In section 07, under the Model 1 card, fetch it on load; if it fails, show a dashed panel "Model 1 results pending." If it loads, render: (1) **F1**, a dot-and-interval chart of `wording.by_family` (masculine-coded in navy `#24406b`, feminine-coded in green `#4f7a3a`; these are word counts, not people), with a toggle for `by_family_sense_filtered`; (2) **F2**, a stacked horizontal bar per entry of `visibility.by_version` using women `#4f7fb3`, men `#d97757`, unknown `#b0aea5`, counts only, never names; (3) the `findings` list and the `limitations` list verbatim; (4) a pill "OBSERVED MEASUREMENT" (green observed style), never a SIMULATION tag. Each chart gets a CSV button and the caption "Observed measurement — posting text; describes wording, not intent. (Anthropic, 2026)". Use the existing observed styling, fonts and minimum 14px text; no yellow or gold.

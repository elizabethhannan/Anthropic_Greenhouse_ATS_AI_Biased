# Research-hire derivation

Derive a separate research-hire subset from the canonical all-hires master using
`title_name`, `title_role`, and `title_sub_role`, including Research Scientist,
Research Engineer, research-oriented MTS, Fellows Researcher, Alignment/Safety,
Interpretability, Pre-training, Post-training, Reinforcement Learning,
Evaluations, Model Behavior, and other AI/ML research roles, with a
`review_needed` classification for ambiguous titles. Do not require the literal
word “research.” Do not query Dewey Experience again for this derivation.

Use these category labels:

- Research Scientist
- Research Engineer
- Research-oriented MTS
- Fellows Researcher
- Alignment / AI Safety
- Interpretability
- Pre-training
- Post-training
- Reinforcement Learning
- Evaluations
- Model Behavior
- AI/ML Research - Other
- Review Needed
- Non-Research

Fellowship records are included in the research population under
`Fellows Researcher`. Preserve original source titles. Generic MTS and other
ambiguous titles remain review candidates unless the three role fields provide
sufficient research evidence. Retain classification reasons and distinguish
research-classified records from unresolved review candidates.

## Independent functional and leadership dimensions

For unresolved technical records, do not force a research/non-research
conclusion. When evidence establishes only engineering, set
`functional_category = Engineering - General / Unspecified` and
`research_status = Insufficient Evidence`. Keep exact original titles.

Classify `leadership_level` independently as Individual Contributor, Manager,
Senior Manager, Lead, Director, Senior Director, Head, VP / SVP / EVP,
C-Suite / Executive, Founder / Co-founder, or Unclear Leadership Level.
Explicit MTS manager titles receive Manager even with unresolved research
status. Preserve `leadership_evidence` and its source. A title-level Manager
classification does not independently verify direct reports.

Use `build_role_dimensions.py` to publish the provisional employment-based
dimensions. Once a filtered Person extract exists in R2, pass `--person-key`
and explicit field mappings from its actual schema. Keep historical
employment leadership separate from current-profile leadership; do not assign
a past hire a current or former leadership title from an unattributed headline.

Generate demographic cross-tabs only when a real Person gender field is
available and explicitly selected with `--gender-field`. Retain its original
value, Unknown / Unclassified, and other source-reported genders. Never infer
gender from names or employment records. Count people within each category,
document overlapping category membership, and distinguish percentage women
among all people from percentage among source-reported men/women.

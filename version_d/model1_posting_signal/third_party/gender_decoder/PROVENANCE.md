# Provenance: gender-decoder word lists

- Source repository: https://github.com/lovedaybrooke/gender-decoder
- Pinned commit: `7cb4a6d6a3b0a84a46eae8a6a312b5732cb363fd` (committed 2025-10-31T10:47:48+01:00)
- File: `app/wordlists.py`, copied verbatim on 2026-10-11 (not retyped).
- Counts at this commit: `masculine_coded_words` 52, `feminine_coded_words` 50, `hyphenated_coded_words` 7, `non_coded_exceptions` 1.
- License: MIT (see `LICENSE.md` in this folder, copied from the same commit).

The tool implements the Gaucher, Friesen, and Kay (2011) lists **with some additions**
(for example `agree`, `collab`). Gaucher et al.'s appendix has not yet been obtained, so stems
are not yet marked as "original" vs. "addition"; Model 1 records this as a limitation and scores
the full list. If the appendix is obtained, `lexicon.py` can score an original-only variant.

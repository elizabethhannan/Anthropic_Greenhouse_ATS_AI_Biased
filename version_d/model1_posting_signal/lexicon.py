"""Gender-coded wording scores (Gaucher et al., 2011 lists as implemented in gender-decoder).

Wording describes wording. A score is never evidence of intent, preference, or
discrimination.

Rules (pre-registered in analysis_plan.md):
- Lowercase; transliterate to ASCII; tokenize on non-letters, keeping hyphenated
  forms so the hyphenated list can match ("self-confident", "co-operate").
- A hyphenated token that does not start with a hyphenated coded stem is split
  into its parts (as gender-decoder does).
- A stem matches a token only at the token's start ("mislead" never matches "lead").
- Each token counts at most once per list; the longest matching stem is recorded.
- Tokens in ``non_coded_exceptions`` never match.
"""

from __future__ import annotations

import ast
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDLIST_FILE = HERE / "third_party" / "gender_decoder" / "wordlists.py"
TOKEN_RE = re.compile(r"[a-z]+(?:-[a-z]+)*")


@dataclass(frozen=True)
class Lexicon:
    masculine: tuple
    feminine: tuple
    hyphenated: tuple
    exceptions: tuple


@lru_cache(maxsize=None)
def load_lexicon(path: str | None = None) -> Lexicon:
    """Parse the vendored word lists without executing the file."""
    src = Path(path or WORDLIST_FILE).read_text(encoding="utf-8")
    lists = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            lists[node.targets[0].id] = tuple(ast.literal_eval(node.value))
    return Lexicon(masculine=lists["masculine_coded_words"],
                   feminine=lists["feminine_coded_words"],
                   hyphenated=lists["hyphenated_coded_words"],
                   exceptions=lists.get("non_coded_exceptions", tuple()))


def to_ascii_lower(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = t.encode("ascii", "ignore").decode("ascii")
    return t.lower()


def tokenize(text: str, lex: Lexicon | None = None) -> list[str]:
    lex = lex or load_lexicon()
    out = []
    for tok in TOKEN_RE.findall(to_ascii_lower(text)):
        if "-" in tok and not any(tok.startswith(h) for h in lex.hyphenated):
            out.extend(p for p in tok.split("-") if p)
        else:
            out.append(tok)
    return out


def match_stem(token: str, stems: tuple, exceptions: tuple = ()) -> str | None:
    """Longest stem that the token starts with, or None."""
    if token in exceptions:
        return None
    best = None
    for s in stems:
        if token.startswith(s) and (best is None or len(s) > len(best)):
            best = s
    return best


@dataclass
class Score:
    n_words: int
    masc: int
    fem: int
    masc_stems: list
    fem_stems: list

    @property
    def masc_per_1k(self) -> float:
        return 1000.0 * self.masc / self.n_words if self.n_words else float("nan")

    @property
    def fem_per_1k(self) -> float:
        return 1000.0 * self.fem / self.n_words if self.n_words else float("nan")

    @property
    def net_per_1k(self) -> float:
        return self.masc_per_1k - self.fem_per_1k

    @property
    def decoder_label(self) -> str:
        """gender-decoder's categorical rule, applied to these token counts."""
        d = self.fem - self.masc
        if d == 0:
            return "neutral" if self.fem else "empty"
        if d > 3:
            return "strongly feminine-coded"
        if d > 0:
            return "feminine-coded"
        if d < -3:
            return "strongly masculine-coded"
        return "masculine-coded"


def score_text(text: str, lex: Lexicon | None = None, drop_stems: frozenset = frozenset()) -> Score:
    """Score one text. ``drop_stems`` removes stems (sense-filtered variant)."""
    lex = lex or load_lexicon()
    masc_list = tuple(s for s in lex.masculine if s not in drop_stems)
    fem_list = tuple(s for s in lex.feminine if s not in drop_stems)
    toks = tokenize(text, lex)
    ms, fs = [], []
    for t in toks:
        m = match_stem(t, masc_list, lex.exceptions)
        if m:
            ms.append(m)
        f = match_stem(t, fem_list, lex.exceptions)
        if f:
            fs.append(f)
    return Score(n_words=len(toks), masc=len(ms), fem=len(fs), masc_stems=ms, fem_stems=fs)


def sentence_label(text: str, lex: Lexicon | None = None, drop_stems: frozenset = frozenset()) -> str:
    """Lexicon's sentence-level label for the convergent check."""
    s = score_text(text, lex, drop_stems)
    if s.masc > s.fem:
        return "agentic"
    if s.fem > s.masc:
        return "communal"
    return "neutral"


def keyword_in_context(text: str, lex: Lexicon | None = None, window: int = 8):
    """Yield (list, stem, token, context) for every match, for the sense audit."""
    lex = lex or load_lexicon()
    toks = tokenize(text, lex)
    for i, t in enumerate(toks):
        for lname, stems in (("masculine", lex.masculine), ("feminine", lex.feminine)):
            s = match_stem(t, stems, lex.exceptions)
            if s:
                lo, hi = max(0, i - window), min(len(toks), i + window + 1)
                ctx = " ".join(toks[lo:i] + [f"[[{t}]]"] + toks[i + 1:hi])
                yield lname, s, t, ctx

"""Stand-in AI screeners for Model 3. Each turns texts into unit vectors; the
match score is the cosine similarity between a résumé and a posting.

Screeners receive text only. No gender label is ever passed to them: the only
gender signal is the first name printed on the résumé (or, in M3-3, one word).
"""

from __future__ import annotations

import gzip
import hashlib
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

TOKEN_RE = re.compile(r"[a-z0-9]+[+#]*")


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in ENGLISH_STOP_WORDS]


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _unit(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


class StaticScreener:
    """Unweighted mean of pre-trained word vectors (GloVe, fastText)."""

    def __init__(self, path: Path, vocab: set[str], checksum: str | None = None):
        path = Path(path)
        self.path = path
        self.checksum_ok = None
        if checksum:
            self.checksum_ok = md5sum(path) == checksum
            if not self.checksum_ok:
                raise ValueError(f"checksum mismatch for {path.name}")
        self.vectors: dict[str, np.ndarray] = {}
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            first = fh.readline().split()
            self.dim = int(first[1]) if len(first) == 2 else len(first) - 1
            if len(first) != 2 and first[0] in vocab:
                self.vectors[first[0]] = np.asarray(first[1:], dtype=np.float32)
            for line in fh:
                word, _, rest = line.partition(" ")
                if word in vocab and word not in self.vectors:
                    self.vectors[word] = np.asarray(rest.split(), dtype=np.float32)

    def coverage(self, tokens: list[str]) -> float:
        return float(np.mean([t in self.vectors for t in tokens])) if tokens else float("nan")

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float64)
        for i, t in enumerate(texts):
            vs = [self.vectors[w] for w in tokenize(t) if w in self.vectors]
            if vs:
                out[i] = np.mean(vs, axis=0)
        return _unit(out)


class WordLlamaScreener:
    """WordLlama l2_supercat (weights bundled in the wordllama package; offline)."""

    def __init__(self, dim: int = 256):
        import shutil

        import wordllama
        from wordllama import WordLlama

        # The 0.4.0.post1 wheel ships its tokenizer under wordllama/tokenizers/ but looks
        # for it under wordllama/tokenizer/ or the cache; copy the bundled file to the cache.
        uri = WordLlama._wordllama.l2_supercat
        fn = WordLlama.get_tokenizer_filename(uri)
        src = Path(wordllama.__file__).parent / "tokenizers" / fn
        dst = WordLlama.get_file_path("tokenizer", None) / fn
        if not dst.exists() and src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
        self.model = WordLlama.load(dim=dim, disable_download=True)
        w = Path(wordllama.__file__).parent / "weights" / f"l2_supercat_{dim}.safetensors"
        self.weights_sha256 = hashlib.sha256(w.read_bytes()).hexdigest() if w.exists() else None
        self.version = getattr(wordllama, "__version__", "0.4.0.post1")

    def embed(self, texts: list[str]) -> np.ndarray:
        return _unit(np.asarray(self.model.embed(texts, norm=True), dtype=np.float64))


class TfidfScreener:
    """Keyword matcher: TF-IDF fit on the postings only (design control)."""

    def __init__(self, posting_texts: list[str]):
        self.vec = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        self.vec.fit(posting_texts)

    def embed(self, texts: list[str]):
        return self.vec.transform(texts)  # rows are L2-normalized


def cosine(a, b) -> np.ndarray:
    """a: n x d, b: m x d (dense unit rows or sparse L2-normalized) -> n x m."""
    m = a @ b.T
    return np.asarray(m.todense()) if hasattr(m, "todense") else np.asarray(m)

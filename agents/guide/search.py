"""BM25 search over the guide corpus.

The corpus is a few dozen short documents, where plain lexical ranking is as good as
embeddings and needs no model, index service or vector database.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from agents.guide.corpus import Doc

_TOKEN = re.compile(r"[a-z0-9]+(?:[.+#][a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be but by can did do does for from has have he his how i in is it its "
    "me of on or show tell than that the their them there this to was what when where which "
    "who why will with you your about any chirag batra".split()
)


def stem(token: str) -> str:
    """A deliberately tiny stemmer: plurals and the commonest verb endings."""
    # Short words, "-ss" words and tech names like node.js or c# are left alone.
    if len(token) <= 4 or token.endswith("ss") or any(ch in token for ch in ".+#"):
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    for suffix in ("ing", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


@dataclass(frozen=True)
class Hit:
    doc: Doc
    score: float


class Index:
    """Okapi BM25 (k1=1.5, b=0.75); titles count twice."""

    def __init__(self, docs: Sequence[Doc], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = list(docs)
        self.k1 = k1
        self.b = b
        self.terms = [Counter(tokenize(f"{d.title} {d.title} {d.text}")) for d in self.docs]
        self.lengths = [sum(t.values()) for t in self.terms]
        self.avg_length = sum(self.lengths) / max(len(self.lengths), 1)
        df: Counter[str] = Counter()
        for terms in self.terms:
            df.update(terms.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4) -> list[Hit]:
        query_terms = set(tokenize(query))
        hits: list[Hit] = []
        for doc, terms, length in zip(self.docs, self.terms, self.lengths, strict=True):
            score = 0.0
            for term in query_terms:
                tf = terms.get(term, 0)
                if tf:
                    norm = tf + self.k1 * (1 - self.b + self.b * length / self.avg_length)
                    score += self.idf[term] * tf * (self.k1 + 1) / norm
            if score > 0:
                hits.append(Hit(doc, score))
        hits.sort(key=lambda h: (-h.score, h.doc.id))
        return hits[:k]

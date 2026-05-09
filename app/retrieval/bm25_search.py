from __future__ import annotations

import math
import pickle
from collections import Counter
from pathlib import Path
from typing import Sequence

from app.config import get_settings
from app.utils.helpers import minmax_normalize, tokenize
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SimpleBM25:
    def __init__(self, tokenized_docs: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = [list(doc) for doc in tokenized_docs]
        self.k1 = k1
        self.b = b
        self.doc_freq: Counter[str] = Counter()
        self.term_freqs: list[Counter[str]] = []
        for doc in self.docs:
            tf = Counter(doc)
            self.term_freqs.append(tf)
            self.doc_freq.update(tf.keys())
        self.doc_lengths = [len(doc) for doc in self.docs]
        self.avgdl = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)
        self.n_docs = len(self.docs)

    def get_scores(self, query_tokens: Sequence[str]) -> list[float]:
        scores: list[float] = []
        for tf, doc_len in zip(self.term_freqs, self.doc_lengths):
            score = 0.0
            for term in query_tokens:
                if term not in tf:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
                score += idf * (freq * (self.k1 + 1)) / denom
            scores.append(score)
        return scores


class BM25Search:
    def __init__(self, texts: Sequence[str], path: Path | None = None) -> None:
        self.texts = list(texts)
        self.path = path or get_settings().bm25_path
        self.tokens = [tokenize(text) for text in self.texts]
        self.backend_name = "simple"
        self.model = self._load_or_build()

    def _load_or_build(self):
        if self.path.exists():
            try:
                with self.path.open("rb") as handle:
                    payload = pickle.load(handle)
                if payload.get("tokens") == self.tokens:
                    self.backend_name = payload.get("backend", "simple")
                    return payload["model"]
            except Exception as exc:
                logger.warning("Ignoring stale BM25 artifact: %s", exc)
        try:
            from rank_bm25 import BM25Okapi

            self.backend_name = "rank_bm25"
            return BM25Okapi(self.tokens)
        except Exception:
            self.backend_name = "simple"
            return SimpleBM25(self.tokens)

    def persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as handle:
            pickle.dump({"backend": self.backend_name, "tokens": self.tokens, "model": self.model}, handle)

    def search(self, query: str, top_k: int = 80) -> dict[int, float]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return {}
        scores = list(self.model.get_scores(query_tokens))
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)[:top_k]
        return minmax_normalize({idx: float(score) for idx, score in ranked if score > 0})

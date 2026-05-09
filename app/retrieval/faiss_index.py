from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Sequence

import numpy as np

from app.config import get_settings
from app.utils.helpers import minmax_normalize, tokenize
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LocalHashEmbedder:
    """Deterministic 384-d fallback used when MiniLM weights are unavailable."""

    dim = 384

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype="float32")
        for row, text in enumerate(texts):
            for token in tokenize(text):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vectors[row, bucket] += sign
            norm = np.linalg.norm(vectors[row])
            if norm > 0:
                vectors[row] /= norm
        return vectors


class EmbeddingProvider:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._model = None
        self._local = LocalHashEmbedder()
        self.dim = self._local.dim
        self.backend = "local"
        if not self.settings.force_local_embeddings:
            self._load_sentence_transformer()

    def _load_sentence_transformer(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            kwargs = {"local_files_only": True}
            if os.getenv("SHL_ALLOW_MODEL_DOWNLOAD", "").lower() in {"1", "true", "yes"}:
                kwargs = {}
            try:
                self._model = SentenceTransformer(self.settings.embedding_model, **kwargs)
            except TypeError:
                self._model = SentenceTransformer(self.settings.embedding_model)
            self.dim = int(self._model.get_sentence_embedding_dimension())
            self.backend = "minilm"
            logger.info("Loaded embedding model %s", self.settings.embedding_model)
        except Exception as exc:  # pragma: no cover - depends on local model cache
            logger.warning("Using local hash embeddings because MiniLM is unavailable: %s", exc)
            self._model = None

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self._model is None:
            return self._local.encode(texts)
        embeddings = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype="float32")


class FaissSemanticIndex:
    def __init__(self, texts: Sequence[str], index_path: Path | None = None) -> None:
        self.texts = list(texts)
        self.provider = EmbeddingProvider()
        self.index_path = index_path or get_settings().faiss_index_path
        self._matrix: np.ndarray | None = None
        self._faiss_index = None
        self._load_or_build()

    def _load_or_build(self) -> None:
        try:
            import faiss

            if self.provider.backend == "local" and self.index_path.exists():
                index = faiss.read_index(str(self.index_path))
                if index.ntotal == len(self.texts) and index.d == self.provider.dim:
                    self._faiss_index = index
                    return
            vectors = self.provider.encode(self.texts)
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            self._faiss_index = index
            self._matrix = vectors
        except Exception as exc:  # pragma: no cover - faiss optional in local tests
            logger.warning("FAISS unavailable; semantic search will use numpy dot products: %s", exc)
            self._matrix = self.provider.encode(self.texts)

    def persist(self) -> None:
        if self._faiss_index is None:
            return
        try:
            import faiss

            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self._faiss_index, str(self.index_path))
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to persist FAISS index: %s", exc)

    def search(self, query: str, top_k: int = 80) -> dict[int, float]:
        if not query.strip() or not self.texts:
            return {}
        vector = self.provider.encode([query])
        top_k = min(top_k, len(self.texts))
        if self._faiss_index is not None:
            distances, indices = self._faiss_index.search(vector, top_k)
            scores = {
                int(idx): float(score)
                for idx, score in zip(indices[0], distances[0])
                if int(idx) >= 0
            }
            return minmax_normalize(scores)
        assert self._matrix is not None
        raw = self._matrix @ vector[0]
        best = np.argsort(raw)[::-1][:top_k]
        return minmax_normalize({int(idx): float(raw[idx]) for idx in best})

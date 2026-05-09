from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retrieval.hybrid_search import get_hybrid_engine


def main() -> None:
    engine = get_hybrid_engine()
    engine.persist_indices()
    print("Built retrieval artifacts:")
    print(f"- FAISS index: {engine.semantic.index_path}")
    print(f"- BM25 index: {engine.keyword.path}")


if __name__ == "__main__":
    main()

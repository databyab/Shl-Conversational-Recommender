from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """App settings from environment variables."""

    root_dir: Path
    catalog_path: Path
    processed_catalog_path: Path
    faiss_index_path: Path
    bm25_path: Path
    groq_api_key: str | None
    groq_base_url: str
    groq_model: str
    embedding_model: str
    force_local_embeddings: bool
    allowed_origins: list[str]
    api_title: str = "SHL Conversational Assessment Recommender"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment variables."""
    root = Path(os.getenv("SHL_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
    except Exception:
        pass
    data_dir = root / "data"
    
    allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000")
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
    
    return Settings(
        root_dir=root,
        catalog_path=Path(os.getenv("SHL_CATALOG_PATH", root / "catalogue.json")),
        processed_catalog_path=Path(
            os.getenv("SHL_PROCESSED_CATALOG_PATH", data_dir / "processed_catalog.json")
        ),
        faiss_index_path=Path(os.getenv("SHL_FAISS_INDEX_PATH", data_dir / "faiss.index")),
        bm25_path=Path(os.getenv("SHL_BM25_PATH", data_dir / "bm25.pkl")),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        embedding_model=os.getenv("SHL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        force_local_embeddings=os.getenv("SHL_FORCE_LOCAL_EMBEDDINGS", "").lower()
        in {"1", "true", "yes"},
        allowed_origins=allowed_origins,
    )

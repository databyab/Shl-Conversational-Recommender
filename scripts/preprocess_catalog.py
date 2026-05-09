from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.preprocessing.normalize_catalog import normalize_catalog


def main() -> None:
    settings = get_settings()
    records = normalize_catalog(settings.catalog_path, settings.processed_catalog_path)
    print(f"Processed {len(records)} catalog records -> {settings.processed_catalog_path}")


if __name__ == "__main__":
    main()

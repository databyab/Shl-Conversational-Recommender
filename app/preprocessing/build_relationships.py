from __future__ import annotations

from app.utils.constants import FAMILY_PATTERNS
from app.utils.helpers import normalize_text


def detect_family(name: str, description: str = "") -> str:
    text = normalize_text(f"{name} {description}")
    for family, patterns in FAMILY_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return family
    if "java" in text:
        return "Java"
    if "sql" in text:
        return "SQL"
    if "excel" in text or "word" in text:
        return "Microsoft Office"
    return "Other"


def family_relationships(records: list[dict]) -> dict[str, list[str]]:
    families: dict[str, list[str]] = {}
    for record in records:
        families.setdefault(record.get("family", "Other"), []).append(record["name"])
    return {family: sorted(names) for family, names in sorted(families.items())}

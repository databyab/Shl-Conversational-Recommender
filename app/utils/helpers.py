from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.utils.constants import KEY_TO_CODE


TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def compact_ws(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_text(value: str | None) -> str:
    text = compact_ws(value).lower()
    text = text.replace("–", "-").replace("—", "-").replace("&", " and ")
    return re.sub(r"[^a-z0-9+#.]+", " ", text).strip()


def tokenize(value: str | None) -> list[str]:
    return TOKEN_RE.findall(normalize_text(value))


def safe_json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.loads(handle.read(), strict=False)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def parse_duration_minutes(value: str | None) -> float | None:
    text = normalize_text(value)
    if not text or "untimed" in text or "variable" in text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def minmax_normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


def codes_for_keys(name: str, keys: Iterable[str]) -> str:
    lower_name = normalize_text(name)
    key_list = list(keys)
    if "development report" in lower_name or "360" in lower_name:
        return "D"
    if "opq" in lower_name and "report" in lower_name:
        return "P"
    codes: list[str] = []
    for key in key_list:
        code = KEY_TO_CODE.get(key)
        if code and code not in codes:
            codes.append(code)
    return ",".join(codes) or "K"


def display_name(raw_name: str, link: str) -> str:
    name = compact_ws(raw_name)
    if link.endswith("/microsoft-excel-365-new/"):
        return "Microsoft Excel 365 (New)"
    name = name.replace("Serv-Retail", "Serv - Retail")
    return name


def short_description(text: str, max_chars: int = 260) -> str:
    text = compact_ws(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rsplit(" ", 1)[0] + "."


@dataclass(frozen=True)
class CatalogItem:
    id: str
    raw_name: str
    name: str
    url: str
    description: str
    keys: tuple[str, ...]
    test_type: str
    job_levels: tuple[str, ...] = field(default_factory=tuple)
    languages: tuple[str, ...] = field(default_factory=tuple)
    duration: str = ""
    duration_minutes: float | None = None
    remote: bool = False
    adaptive: bool = False
    family: str = "Other"
    derived_tags: tuple[str, ...] = field(default_factory=tuple)
    search_text: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogItem":
        return cls(
            id=str(data.get("id") or data.get("entity_id") or data.get("name")),
            raw_name=compact_ws(data.get("raw_name") or data.get("name")),
            name=compact_ws(data.get("name")),
            url=data.get("url") or data.get("link") or "",
            description=compact_ws(data.get("description")),
            keys=tuple(data.get("keys") or ()),
            test_type=data.get("test_type") or codes_for_keys(data.get("name", ""), data.get("keys") or ()),
            job_levels=tuple(data.get("job_levels") or ()),
            languages=tuple(data.get("languages") or ()),
            duration=compact_ws(data.get("duration")),
            duration_minutes=data.get("duration_minutes"),
            remote=str(data.get("remote", "")).lower() == "yes"
            if isinstance(data.get("remote"), str)
            else bool(data.get("remote")),
            adaptive=str(data.get("adaptive", "")).lower() == "yes"
            if isinstance(data.get("adaptive"), str)
            else bool(data.get("adaptive")),
            family=data.get("family") or "Other",
            derived_tags=tuple(data.get("derived_tags") or ()),
            search_text=data.get("search_text") or "",
        )

    def to_recommendation(self) -> dict[str, str]:
        return {"name": self.name, "url": self.url, "test_type": self.test_type}

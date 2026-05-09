from __future__ import annotations

from pathlib import Path

from app.preprocessing.build_relationships import detect_family
from app.preprocessing.derive_tags import derive_tags
from app.utils.helpers import (
    codes_for_keys,
    compact_ws,
    display_name,
    parse_duration_minutes,
    safe_json_load,
    write_json,
)


def normalize_record(raw: dict) -> dict:
    link = raw.get("link") or raw.get("url") or ""
    raw_name = raw.get("name") or ""
    name = display_name(raw_name, link)
    keys = list(raw.get("keys") or [])
    record = {
        "id": str(raw.get("entity_id") or link.rstrip("/").split("/")[-1] or name),
        "raw_name": compact_ws(raw_name),
        "name": name,
        "url": link,
        "description": compact_ws(raw.get("description")),
        "keys": keys,
        "test_type": codes_for_keys(name, keys),
        "job_levels": list(raw.get("job_levels") or []),
        "languages": list(raw.get("languages") or []),
        "duration": compact_ws(raw.get("duration")),
        "duration_minutes": parse_duration_minutes(raw.get("duration")),
        "remote": str(raw.get("remote", "")).lower() == "yes",
        "adaptive": str(raw.get("adaptive", "")).lower() == "yes",
    }
    record["family"] = detect_family(record["name"], record["description"])
    record["derived_tags"] = derive_tags(record)
    record["search_text"] = " ".join(
        [
            record["name"],
            record["description"],
            " ".join(record["keys"]),
            " ".join(record["job_levels"]),
            " ".join(record["languages"]),
            " ".join(record["derived_tags"]),
            record["family"],
        ]
    )
    return record


def normalize_catalog(catalog_path: Path, output_path: Path) -> list[dict]:
    raw_records = safe_json_load(catalog_path)
    records = [normalize_record(record) for record in raw_records if record.get("status") == "ok"]
    records = [record for record in records if record["name"] and record["url"]]
    write_json(output_path, records)
    return records

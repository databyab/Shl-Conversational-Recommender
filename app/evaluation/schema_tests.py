from __future__ import annotations

from pydantic import ValidationError

from app.models.response_models import ChatResponse


def validate_response_schema(payload: dict) -> bool:
    try:
        ChatResponse(**payload)
        return True
    except ValidationError:
        return False


def hallucination_names(payload: dict, catalog_names: set[str]) -> list[str]:
    bad: list[str] = []
    for recommendation in payload.get("recommendations", []):
        name = recommendation.get("name")
        if name not in catalog_names:
            bad.append(name)
    return bad

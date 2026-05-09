from __future__ import annotations

from app.models.response_models import ChatResponse


def is_clarification(response: ChatResponse) -> bool:
    return not response.recommendations and "?" in response.reply


def is_refusal(response: ChatResponse) -> bool:
    return not response.recommendations and "I can" in response.reply and "SHL" in response.reply


def has_max_ten(response: ChatResponse) -> bool:
    return len(response.recommendations) <= 10

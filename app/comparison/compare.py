"""Grounded product comparison from catalog."""

from __future__ import annotations

from app.orchestrator.state_extractor import HiringState
from app.retrieval.hybrid_search import CatalogStore
from app.utils.helpers import CatalogItem, normalize_text, short_description


def _resolve_comparison_items(state: HiringState, store: CatalogStore) -> list[CatalogItem]:
    text = state.latest_user_message
    items = store.resolve_mentions(text)
    if len(items) >= 2:
        return items[:4]
    for name in state.mentioned_products + state.prior_recommendations:
        item = store.resolve(name)
        if item and item not in items:
            items.append(item)
        if len(items) >= 4:
            break
    if len(items) >= 2:
        return items[:4]

    query_norm = normalize_text(text)
    candidates: list[CatalogItem] = []
    for item in store.items:
        item_norm = normalize_text(item.name)
        tokens = set(item_norm.split())
        overlap = sum(1 for token in tokens if len(token) > 3 and token in query_norm)
        if overlap:
            candidates.append(item)
    return candidates[:4]


def compare_products(state: HiringState, store: CatalogStore) -> str:
    items = _resolve_comparison_items(state, store)
    if len(items) < 2:
        return (
            "I can compare catalog products, but I need the two SHL assessment names. "
            "Which products should I compare?"
        )

    lines = ["Here is the catalog-grounded difference:"]
    for item in items:
        key_text = ", ".join(item.keys) if item.keys else "not stated"
        duration = item.duration or "not stated"
        lines.append(
            f"- {item.name}: {key_text}; duration {duration}. {short_description(item.description, 220)}"
        )

    first, second = items[0], items[1]
    first_keys, second_keys = set(first.keys), set(second.keys)
    if first_keys != second_keys:
        lines.append(
            f"In short, {first.name} is cataloged under {', '.join(first.keys) or 'unstated keys'}, "
            f"while {second.name} is cataloged under {', '.join(second.keys) or 'unstated keys'}."
        )
    elif first.family != second.family:
        lines.append(
            f"In short, they sit in different product families: {first.family} versus {second.family}."
        )
    else:
        lines.append(
            "In short, they are related catalog products, so the practical difference should be read from "
            "the descriptions, duration, and reporting purpose above."
        )
    return "\n".join(lines)

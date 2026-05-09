from __future__ import annotations

from collections import Counter

from app.orchestrator.state_extractor import HiringState
from app.utils.helpers import CatalogItem, normalize_text


def _excluded(item: CatalogItem, state: HiringState) -> bool:
    name = normalize_text(item.name)
    for product in state.excluded_products:
        if normalize_text(product) in name or name in normalize_text(product):
            return True
    for term in state.exclude_terms:
        term_norm = normalize_text(term)
        if term_norm and term_norm in name:
            return True
    if "opq" in state.exclude_terms and (item.family == "OPQ" or "opq" in name):
        return True
    if "rest" in state.exclude_terms and "rest" in name:
        return True
    if "simulation" in state.exclude_terms and "Simulations" in item.keys:
        return True
    return False


def choose_limit(state: HiringState, scored_count: int) -> int:
    if state.final_list_requested and state.requested_products:
        return min(10, max(1, len(state.requested_products)))
    if state.skills:
        return min(10, max(3, min(7, len(state.skills) + len(state.assessment_types))))
    if state.assessment_types:
        return min(6, max(3, len(state.assessment_types) + 2))
    return min(5, scored_count)


def rerank(
    candidates: list[tuple[CatalogItem, float]],
    state: HiringState,
    requested_items: list[CatalogItem] | None = None,
    max_results: int | None = None,
) -> list[CatalogItem]:
    requested_items = requested_items or []
    requested_names = {item.name for item in requested_items}
    filtered = [(item, score) for item, score in candidates if not _excluded(item, state)]
    filtered.sort(key=lambda pair: pair[1], reverse=True)
    limit = min(10, max(max_results or choose_limit(state, len(filtered)), len(requested_items)))

    selected: list[CatalogItem] = []
    selected_names: set[str] = set()
    family_counts: Counter[str] = Counter()

    for item in requested_items:
        if not _excluded(item, state) and item.name not in selected_names:
            selected.append(item)
            selected_names.add(item.name)
            family_counts[item.family] += 1
            if len(selected) >= limit:
                return selected

    if state.final_list_requested and requested_items:
        return selected[:limit]

    for item, score in filtered:
        if item.name in selected_names:
            continue
        if score < 0.12 and selected:
            continue
        family_cap = 3 if item.family in {"OPQ", "Microsoft Office", "Verify"} else 2
        if family_counts[item.family] >= family_cap and item.name not in requested_names:
            continue
        selected.append(item)
        selected_names.add(item.name)
        family_counts[item.family] += 1
        if len(selected) >= limit:
            break

    return selected[:limit]

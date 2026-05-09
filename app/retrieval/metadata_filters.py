from __future__ import annotations

from app.orchestrator.state_extractor import HiringState
from app.utils.constants import ASSESSMENT_TYPE_TO_KEYS, SENIORITY_TO_LEVELS
from app.utils.helpers import CatalogItem, normalize_text


def metadata_score(item: CatalogItem, state: HiringState) -> float:
    score = 0.15
    key_set = set(item.keys)

    desired_keys: set[str] = set()
    for assessment_type in state.assessment_types:
        desired_keys.update(ASSESSMENT_TYPE_TO_KEYS.get(assessment_type, set()))
    if desired_keys:
        score += 0.35 if key_set & desired_keys else -0.05

    if state.seniority:
        level_targets = SENIORITY_TO_LEVELS.get(state.seniority.lower(), set())
        if level_targets and set(item.job_levels) & level_targets:
            score += 0.18
        elif level_targets and item.job_levels:
            score -= 0.03

    latest = normalize_text(state.latest_user_message or "")
    full = normalize_text(state.latest_user_message or "")
    wants_quick = any(term in full for term in ("quick", "fast", "short", "shorter", "screen"))
    wants_sim = any(term in full for term in ("simulation", "hands on", "capability", "capabilities"))
    if wants_quick and item.duration_minutes is not None:
        if item.duration_minutes <= 12:
            score += 0.12
        elif item.duration_minutes >= 30 and not wants_sim:
            score -= 0.08
    if wants_sim and "Simulations" in key_set:
        score += 0.16
    if state.special_requirements.get("remote") and item.remote:
        score += 0.05
    if "adaptive" in latest and item.adaptive:
        score += 0.08
    if state.languages:
        language_blob = normalize_text(" ".join(item.languages))
        for language in state.languages:
            if language in language_blob:
                score += 0.06
                break
    return max(0.0, min(score, 1.0))

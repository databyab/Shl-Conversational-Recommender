from __future__ import annotations

from enum import Enum

from app.orchestrator.state_extractor import HiringState
from app.refusal.guardrails import refusal_reason
from app.utils.helpers import normalize_text


class Intent(str, Enum):
    RECOMMEND = "recommend"
    CLARIFY = "clarify"
    COMPARE = "compare"
    REFUSE = "refuse"
    CONFIRM = "confirm"
    REFINE = "refine"


def classify_intent(state: HiringState) -> Intent:
    """
    Classify user intent based on state and latest message.
    
    Priority:
    1. REFUSE - Safety/off-topic
    2. COMPARE - Product comparison requests
    3. CONFIRM - End of conversation signal
    4. REFINE - Modifications to existing context
    5. RECOMMEND - Default for retrieval
    """
    latest = state.latest_user_message or ""
    latest_norm = normalize_text(latest)

    # RULE 1: REFUSE - Check for unsafe/off-topic
    if refusal_reason(latest, state):
        return Intent.REFUSE

    # RULE 2: COMPARE - Product comparison (high priority, bypasses clarification)
    comparison_patterns = [
        "difference between",
        "different from",
        "compare",
        "versus",
        " vs ",
        " vs.",
        "which.*better",
        "which.*more",
    ]
    if state.comparison_requested or any(p in latest_norm for p in comparison_patterns):
        return Intent.COMPARE

    # RULE 3: CONFIRM - User explicitly finished or confirmed
    if state.completion_signal:
        return Intent.CONFIRM

    # RULE 4: REFINE - User is modifying or refining earlier context
    refinement_keywords = [
        "actually",
        "also add",
        "also include",
        "add ",
        "drop ",
        "remove ",
        "replace ",
        "instead",
        "change",
        "include",
        "exclude",
        "but also",
        "without",
        "skip",
    ]
    if state.refinements or any(kw in latest_norm for kw in refinement_keywords):
        return Intent.REFINE

    # RULE 5: RECOMMEND - Default
    return Intent.RECOMMEND

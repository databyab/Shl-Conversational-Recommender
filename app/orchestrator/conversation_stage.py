from __future__ import annotations

from enum import Enum

from app.orchestrator.state_extractor import HiringState


class ConversationStage(str, Enum):
    DISCOVERY = "Discovery"
    QUALIFICATION = "Qualification"
    RECOMMENDATION = "Recommendation"
    CONFIRMATION = "Confirmation"


def infer_stage(state: HiringState, has_recommendations: bool = False) -> ConversationStage:
    if state.completion_signal:
        return ConversationStage.CONFIRMATION
    if has_recommendations or state.prior_recommendations:
        return ConversationStage.RECOMMENDATION
    if state.role or state.skills or state.assessment_types:
        return ConversationStage.QUALIFICATION
    return ConversationStage.DISCOVERY

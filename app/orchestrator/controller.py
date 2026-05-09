"""Conversation orchestration controller."""

from __future__ import annotations

from app.comparison.compare import compare_products
from app.models.request_models import ChatRequest
from app.models.response_models import ChatResponse, Recommendation
from app.orchestrator.clarification import clarification_question
from app.orchestrator.conversation_stage import infer_stage
from app.orchestrator.intent_classifier import Intent, classify_intent
from app.orchestrator.state_extractor import HiringState, StateExtractor
from app.refusal.guardrails import refusal_reason, refusal_reply
from app.retrieval.hybrid_search import HybridSearchEngine, get_hybrid_engine
from app.utils.helpers import CatalogItem, normalize_text, short_description
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _recommendations(items: list[CatalogItem], max_count: int = 3) -> list[Recommendation]:
    """Convert catalog items to API recommendations.
    
    Returns 3 strong recommendations by default (precise, recruiter-curated shortlist).
    Expands to 5 for refinements, up to 10 only if explicitly requested by user.
    """
    return [Recommendation(**item.to_recommendation()) for item in items[:max_count]]


def _why_line(item: CatalogItem, state: HiringState) -> str:
    """Generate recruiter-friendly explanation for why this assessment matches.
    
    Uses professional templates based on assessment metadata.
    Avoids mechanical keyword overlap explanations.
    """
    # STOPWORDS to filter out from matching: weak or noisy tokens
    stopwords = {"and", "or", "the", "a", "an", "assessment", "test", "need", "role", 
                 "hiring", "evaluates", "measures", "assesses", "with", "for", "in", "to",
                 "developer", "development", "experience", "level", "interview", "tool", "suite"}
    
    # Get clean skill matches (filtered stopwords)
    skill_matches = []
    item_name_norm = normalize_text(item.name)
    item_desc_norm = normalize_text(item.description)
    
    for skill in state.skills:
        skill_norm = normalize_text(skill)
        # Only match if skill is non-trivial and not a stopword
        if skill_norm and skill_norm not in stopwords and len(skill_norm) > 2:
            if skill_norm in item_name_norm or skill_norm in item_desc_norm:
                skill_matches.append(skill)
    
    # PRIMARY: Exact skill match
    if skill_matches:
        unique_skills = list(dict.fromkeys(skill_matches))[:2]
        if len(unique_skills) == 1:
            return f"Assesses {unique_skills[0]} skills."
        return f"Assesses {' and '.join(unique_skills)} skills."
    
    # SECONDARY: Assessment type match with professional language
    assessment_explanations = {
        "personality": "Evaluates workplace personality and collaboration behaviors.",
        "behavioral": "Measures behavioral competencies and interpersonal skills.",
        "cognitive": "Assesses cognitive reasoning and problem-solving ability.",
        "reasoning": "Evaluates logical reasoning and analytical thinking.",
        "simulation": "Provides realistic job simulation and situational assessment.",
        "coding": "Tests software development and coding proficiency.",
        "knowledge": "Evaluates job-specific knowledge and domain expertise.",
        "ability": "Measures cognitive ability and numerical/verbal reasoning.",
    }
    
    item_keys_normalized = [normalize_text(k) for k in (item.keys or [])]
    for assess_type in state.assessment_types:
        assess_norm = normalize_text(assess_type)
        if assess_norm in assessment_explanations:
            # Check if this assessment type matches any key in the catalog item
            if any(assess_norm in key for key in item_keys_normalized):
                return assessment_explanations[assess_norm]
    
    # TERTIARY: Catalog tags (professional)
    if item.derived_tags:
        key_tags = [t for t in item.derived_tags[:2] if t and len(t) > 2 and t.lower() not in stopwords]
        if key_tags:
            return f"Catalog categories: {', '.join(key_tags)}."
    
    # FALLBACK: Description summary
    return short_description(item.description, 85) + "."


def _format_reply(items: list[CatalogItem], state: HiringState, intent: Intent) -> str:
    if not items:
        return (
            "I could not find a grounded shortlist from the supplied SHL catalog for those constraints. "
            "Can you relax one constraint or share the role's most important skill?"
        )

    if intent == Intent.CONFIRM:
        opener = "Confirmed. Keeping this SHL shortlist:"
    elif intent == Intent.REFINE:
        opener = "Updated the shortlist using your latest refinement:"
    else:
        opener = "Here is a grounded SHL shortlist from the catalog:"

    lines = [opener]
    for idx, item in enumerate(items, start=1):
        duration = f", {item.duration}" if item.duration else ""
        lines.append(f"{idx}. {item.name} ({item.test_type}{duration}) - {_why_line(item, state)}.")
    lines.append("All recommendation names and URLs are taken from the provided catalog.")
    return "\n".join(lines)


def _special_catalog_constraint(state: HiringState) -> str | None:
    latest = normalize_text(state.latest_user_message)
    if "opq" in latest and "shorter" in latest and any(term in latest for term in ("replace", "remove")):
        return (
            "OPQ32r is the relevant catalog personality questionnaire for that graduate battery. "
            "I do not see a shorter catalog replacement that preserves the same personality signal. "
            "You can either keep OPQ32r or drop the personality component."
        )
    return None


class ChatController:
    def __init__(self, engine: HybridSearchEngine | None = None) -> None:
        self.engine = engine or get_hybrid_engine()
        self.extractor = StateExtractor(self.engine.store.items)

    async def handle(self, request: ChatRequest) -> ChatResponse:
        """
        Main orchestration logic: Route to appropriate response handler.
        
        Decision flow:
        1. Refuse - if unsafe, off-topic, or harmful
        2. Compare - if user asks for product comparison
        3. Clarify - if insufficient context (missing role/goal)
        4. Recommend - if context is sufficient
        """
        state = self.extractor.extract(request.messages)
        intent = classify_intent(state)
        stage = infer_stage(state)
        logger.info("orchestration: intent=%s stage=%s role=%s insufficient_context=%s", 
                   intent.value, stage.value, state.role or "none", state.insufficient_context)

        # RULE 1: REFUSE - Safety and off-topic
        reason = refusal_reason(state.latest_user_message, state)
        if intent == Intent.REFUSE or reason:
            return ChatResponse(reply=refusal_reply(reason), recommendations=[], end_of_conversation=False)

        # RULE 2: COMPARE - Product comparison bypasses clarification
        if intent == Intent.COMPARE:
            return ChatResponse(
                reply=compare_products(state, self.engine.store),
                recommendations=[],
                end_of_conversation=False,
            )

        # RULE 3: CLARIFY - Insufficient context takes absolute priority
        # Never retrieve for vague queries
        if state.insufficient_context:
            question = clarification_question(state)
            if not question:
                # Fallback clarification if pattern doesn't match
                question = "To find the right assessments, I need to know: what role are you hiring for, or what specific assessment goal do you have in mind?"
            return ChatResponse(reply=question, recommendations=[], end_of_conversation=False)

        # Check for domain-specific clarifications only for NEW requests
        # (refinements and confirms should NOT be asked again)
        if intent == Intent.RECOMMEND and not state.insufficient_context:
            question = clarification_question(state)
            if question:
                return ChatResponse(reply=question, recommendations=[], end_of_conversation=False)

        # RULE 4: SPECIAL CATALOG CONSTRAINTS
        special = _special_catalog_constraint(state)
        if special:
            return ChatResponse(reply=special, recommendations=[], end_of_conversation=False)

        # RULE 5: RECOMMEND - Now that context is sufficient, retrieve
        items = self.engine.recommend(state)
        reply = _format_reply(items, state, intent)
        
        # Determine recommendation count:
        # Default: 3 strong recommendations (precise recruiter shortlist)
        # Refinement: 5 if user is refining/confirming
        # Full list: 10 if user explicitly requests "all" / "more" / "full list"
        max_recs = 3
        latest_msg = normalize_text(state.latest_user_message or "")
        if intent in (Intent.REFINE, Intent.CONFIRM):
            max_recs = 5
        if any(term in latest_msg for term in ("all", "more", "all recommendations", "full list", "everything")):
            max_recs = 10
        
        # Only set end_of_conversation=true if user explicitly confirmed AND we have recommendations
        # Do NOT mark as ended just because we returned recommendations
        end = bool(items) and intent == Intent.CONFIRM and state.completion_signal
        
        logger.info("recommendations=%d mode=%s end=%s", len(items), intent.value, end)
        return ChatResponse(reply=reply, recommendations=_recommendations(items, max_count=max_recs), end_of_conversation=end)


async def handle_chat(request: ChatRequest) -> ChatResponse:
    controller = ChatController()
    return await controller.handle(request)

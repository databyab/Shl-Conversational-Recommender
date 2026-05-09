"""Two-stage hiring state extraction (deterministic + optional LLM enhancement)."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from app.config import get_settings
from app.utils.constants import ASSESSMENT_TYPE_TO_KEYS
from app.utils.helpers import compact_ws

logger = logging.getLogger(__name__)


@dataclass
class HiringState:
    """Extracted hiring requirements from conversation."""
    role: Optional[str] = None
    seniority: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    personality_traits: list[str] = field(default_factory=list)
    assessment_types: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    domain_expertise: list[str] = field(default_factory=list)
    industry_context: Optional[str] = None
    team_size: Optional[str] = None
    special_requirements: dict[str, bool] = field(default_factory=dict)
    refinements: dict[str, list[str]] = field(default_factory=dict)
    prior_recommendations: list[str] = field(default_factory=list)
    mentioned_products: list[str] = field(default_factory=list)
    requested_products: list[str] = field(default_factory=list)
    excluded_products: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    final_list_requested: bool = False
    completion_signal: bool = False
    clarification_needed: Optional[str] = None
    flags: dict[str, bool] = field(default_factory=dict)
    latest_user_message: Optional[str] = None
    use_case: Optional[str] = None
    comparison_requested: bool = False
    comparison_entities: list[str] = field(default_factory=list)
    off_topic: bool = False
    insufficient_context: bool = False


def _detect_comparison_intent(text: str) -> tuple[bool, list[str]]:
    """Detect if user is asking for product comparison."""
    comp_patterns = [
        r"(?:difference|compare|compare|vs\.?|versus|between).+(?:and|or)",
        r"(?:which|what).+(?:better|different)",
    ]
    entities = []
    is_comparison = any(re.search(p, text, re.IGNORECASE) for p in comp_patterns)
    if is_comparison:
        entity_candidates = re.findall(r"\b(?:OPQ|GSA|Verify|SHL|Amber|Bright|Cut-e)\b", text, re.IGNORECASE)
        entities = list(set(entity_candidates))
    return is_comparison, entities


def _detect_off_topic(text: str) -> bool:
    """Detect off-topic or refusal triggers."""
    off_topic_patterns = [
        r"\b(legal|law|lawsuit|compliance|GDPR|salary|compensation|wage)\b",
        r"(?:AWS|Azure|cloud|DevOps|kubernetes|terraform)",
        r"(?:ignore|disregard).+(?:instruction|prompt|system)",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in off_topic_patterns)


def _detect_use_case(text: str) -> Optional[str]:
    """Detect recruitment use case."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["hire", "hiring", "recruit", "selection", "candidate", "screening"]):
        return "selection"
    if any(w in text_lower for w in ["develop", "development", "learning", "training", "coach"]):
        return "development"
    if any(w in text_lower for w in ["benchmark", "benchmarking", "compare", "comparison"]):
        return "benchmarking"
    if any(w in text_lower for w in ["succession", "pipeline", "talent pool"]):
        return "succession_planning"
    return None


def _check_insufficient_context(state: HiringState, text: str) -> bool:
    """
    Determine if conversation has insufficient context for recommendations.
    
    REQUIRED for retrieval (BLOCKS if missing):
    - Some meaningful hiring signal: role OR assessment goal
    
    OPTIONAL (does NOT block retrieval):
    - use_case
    - seniority
    - skills
    - special requirements
    
    Returns True (insufficient) if:
    - Purely vague message AND no accumulated hiring context
    - No role AND no assessment types AND no skills
    
    Returns False (sufficient) if:
    - Has role (even without seniority or skills)
    - OR has assessment types + hiring intent
    """
    # Vague query patterns that require clarification regardless of history
    vague_patterns = [
        r"^\s*(?:i need|i want|i like|i'm looking for|can you|help me|recommend|suggest)\s+(?:an? |some )?(?:assessment|test|tool)s?\s*$",
        r"^\s*(?:need|want|require)\s+(?:an? |some )?(?:tests?|assessment|evaluation)s?\s*$",
        r"^\s*(?:what|which|can you)\s+(?:test|assessment|tool)\s*$",
        r"^\s*(?:assessment|test|tool)\s*$",
    ]
    
    text_lower = text.lower().strip()
    is_pure_vague = any(re.match(p, text_lower, re.IGNORECASE) for p in vague_patterns)
    
    # If purely vague (matches vague patterns exactly), ask for clarification
    if is_pure_vague:
        return True
    
    # Check if we have meaningful context for retrieval
    has_role = bool(state.role)
    has_assessment_goal = bool(state.assessment_types)
    
    # KEY FIX: Role alone is SUFFICIENT context
    # We don't block retrieval just because use_case/seniority/skills are missing
    if has_role or has_assessment_goal:
        return False
    
    # No role AND no assessment goal = insufficient
    return True


def _seniority(text: str) -> str | None:
    """Extract seniority level from text."""
    if re.search(r"\b(cxo|chief|executive|vp|vice president)\b", text):
        return "executive"
    if re.search(r"\b(director|director-level)\b", text):
        return "director"
    if re.search(r"\b(tech lead|team lead|lead engineer|leadership|manager)\b", text):
        return "lead"
    if re.search(r"\b(senior|sr\.?|5\+|10\+|15\+|advanced)\b", text):
        return "senior"
    if re.search(r"\b(mid-level|mid level|mid professional)\b", text):
        return "mid"
    if re.search(r"\b(graduate|final-year|student|trainee|recent graduates?)\b", text):
        return "graduate"
    if re.search(r"\b(entry-level|entry level|junior|no work experience)\b", text):
        return "entry"
    return None


def _role(raw_text: str, norm_text: str) -> str | None:
    """Extract job role from text."""
    # Pattern-based extraction (highest priority)
    patterns = [
        r"hiring (?:a|an|for)?\s*([^.\n?]+?)(?: for | with | who | what |\.|\?|$)",
        r"screen(?:ing)?\s+([^.\n?]+?)(?: for | with | who |\.|\?|$)",
        r"role\s+is\s+([^.\n?]+)",
        r"assessment\s+(?:for|of)\s+([^.\n?]+?)(?: role| position|\.|\?|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            role = compact_ws(match.group(1).strip(" -:;\""))
            if 2 <= len(role) <= 90:
                return role
    
    # Keyword-based role extraction
    role_keywords = {
        "director": "Director",
        "executive": "Executive",
        "cto": "Chief Technology Officer",
        "cfo": "Chief Financial Officer",
        "coo": "Chief Operating Officer",
        "ceo": "Chief Executive Officer",
        "vp": "Vice President",
        "manager": "Manager",
        "engineer": "Engineer",
        "developer": "Developer",
        "analyst": "Analyst",
        "consultant": "Consultant",
        "specialist": "Specialist",
    }
    
    for keyword, label in role_keywords.items():
        if keyword in norm_text:
            return label
    
    # Domain-specific roles
    if "contact center" in norm_text or "contact centre" in norm_text:
        return "Contact Center Agent"
    if "financial analyst" in norm_text:
        return "Financial Analyst"
    if "management trainee" in norm_text:
        return "Graduate Management Trainee"
    if "admin assistant" in norm_text or "administrative assistant" in norm_text:
        return "Administrative Assistant"
    if "plant operator" in norm_text:
        return "Plant Operator"
    if "healthcare admin" in norm_text:
        return "Healthcare Admin Staff"
    
    return None


def _skills(text: str) -> list[str]:
    """Extract technical skills from text."""
    skills = []
    tokens = re.findall(r"\b\w+(?:\+\+|\.js|\.net|#)?\b", text, flags=re.IGNORECASE)
    for token in tokens:
        token_lower = token.lower()
        if len(token_lower) >= 2:
            skills.append(token_lower)
    return list(set(skills))


def _assessment_types(text: str) -> list[str]:
    """Extract SHL assessment types from text."""
    found = []
    text_lower = text.lower()
    for assessment_key in ASSESSMENT_TYPE_TO_KEYS:
        if assessment_key in text_lower:
            found.append(assessment_key)
    return found


def _traits(text: str) -> list[str]:
    """Extract personality traits from text."""
    traits = ["leadership", "teamwork", "communication", "problem-solving", "resilience"]
    found = []
    text_lower = text.lower()
    for trait in traits:
        if trait in text_lower:
            found.append(trait)
    return found


def _languages(text: str) -> list[str]:
    """Extract required languages from text."""
    languages = ["english", "french", "spanish", "german", "mandarin", "arabic"]
    found = []
    text_lower = text.lower()
    for lang in languages:
        if lang in text_lower:
            found.append(lang)
    return found


def _completion_signal(text: str) -> bool:
    """Check if user has indicated end of conversation."""
    return bool(re.search(r"\b(that['']?s all|that['']?s it|done|finished|no more|thanks)\b", text, flags=re.IGNORECASE))


class StateExtractor:
    """Extract hiring state from full conversation history."""

    def __init__(self, catalog_items: list = None):
        self.settings = get_settings()
        self.catalog_items = catalog_items or []

    def extract(self, messages: list = None) -> HiringState:
        """
        Extract state from full conversation history.
        Parses all turns, merges information, applies refinements.
        """
        if not messages:
            return HiringState()

        try:
            user_messages = [m for m in messages if hasattr(m, "role") and m.role == "user"]
            if not user_messages:
                return HiringState()

            # Start with accumulated state from all turns
            state = HiringState()
            latest_text = ""

            for msg in user_messages:
                latest_text = msg.content
                self._process_turn(state, latest_text)

            state.latest_user_message = latest_text

            # Apply post-processing
            state.off_topic = _detect_off_topic(latest_text)
            is_comp, entities = _detect_comparison_intent(latest_text)
            state.comparison_requested = is_comp
            state.comparison_entities = entities
            
            # PRESERVE use_case from earlier turns, only update if explicitly mentioned
            detected_use_case = _detect_use_case(latest_text)
            if detected_use_case:
                state.use_case = detected_use_case
            elif state.role and not state.use_case:
                # Default to "selection" (hiring) when role exists but use_case not yet set
                # This is safe because most hiring conversations default to selection intent
                state.use_case = "selection"
            
            state.insufficient_context = _check_insufficient_context(state, latest_text)

            # Apply Groq enhancement (optional, after deterministic extraction)
            self._groq_enhance(state, latest_text)

            logger.info(
                "extracted state: role=%s seniority=%s skills=%d assessments=%d use_case=%s",
                state.role,
                state.seniority,
                len(state.skills),
                len(state.assessment_types),
                state.use_case,
            )

            return state

        except Exception as e:
            logger.error("extraction error: %s", e, exc_info=True)
            return HiringState()

    def _process_turn(self, state: HiringState, text: str) -> None:
        """Process single user turn, accumulating state."""
        norm_text = text.lower()

        # Extract role (preserve if already set)
        if not state.role:
            state.role = _role(text, norm_text)

        # Extract seniority (preserve if already set)
        if not state.seniority:
            state.seniority = _seniority(norm_text)

        # Accumulate skills, traits, assessments
        for skill in _skills(text):
            if skill not in state.skills:
                state.skills.append(skill)

        for assessment in _assessment_types(text):
            if assessment not in state.assessment_types:
                state.assessment_types.append(assessment)

        for trait in _traits(text):
            if trait not in state.personality_traits:
                state.personality_traits.append(trait)

        for lang in _languages(text):
            if lang not in state.languages:
                state.languages.append(lang)

        # Track completion signal
        state.completion_signal = _completion_signal(text)

    def _groq_enhance(self, state: HiringState, latest_text: str) -> None:
        """
        Apply Groq LLM enhancement to fill gaps and clarify ambiguity.
        
        This runs AFTER deterministic extraction and only enhances missing fields.
        Regex extractions take priority over LLM inferences.
        """
        if not self.settings.groq_api_key:
            return  # Skip if no API key configured

        try:
            # Only use Groq if we have weak context but the user is clearly trying to hire
            if not state.role and not state.assessment_types:
                # Pure vague query - don't bother with LLM
                return

            # Build context summary
            extracted_info = []
            if state.role:
                extracted_info.append(f"Role: {state.role}")
            if state.seniority:
                extracted_info.append(f"Seniority: {state.seniority}")
            if state.skills:
                extracted_info.append(f"Skills: {', '.join(state.skills[:3])}")
            if state.assessment_types:
                extracted_info.append(f"Assessments: {', '.join(state.assessment_types)}")

            context_str = " | ".join(extracted_info) if extracted_info else "No clear role or assessment goal"

            # Request Groq to enhance understanding
            prompt = f"""Given this hiring/assessment conversation context:
"{latest_text}"

Current extracted state: {context_str}

Respond with JSON (no markdown, just raw JSON):
{{
  "role_clarification": "refined role name if ambiguous, else null",
  "missing_skills": ["any important missing technical skills"],
  "missing_assessment_types": ["personality", "ability", "simulation", "situational"],
  "domain_inferred": "domain/industry if detectable, else null"
}}

Only infer fields that are NOT already extracted above. Keep inferences conservative."""

            headers = {
                "Authorization": f"Bearer {self.settings.groq_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.settings.groq_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert hiring consultant analyzing assessment requirements. Respond ONLY with valid JSON, no markdown.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            }

            response = requests.post(
                f"{self.settings.groq_base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=5,
            )

            if response.status_code != 200:
                logger.debug("Groq enhancement skipped: status %d", response.status_code)
                return

            result = response.json()
            if not result.get("choices"):
                return

            content = result["choices"][0]["message"]["content"].strip()

            # Parse JSON response
            enhanced = json.loads(content)

            # Apply enhancements (only if not already extracted)
            if enhanced.get("role_clarification") and not state.role:
                state.role = enhanced["role_clarification"]
                logger.debug("Groq inferred role: %s", state.role)

            if enhanced.get("missing_skills"):
                for skill in enhanced["missing_skills"]:
                    if skill not in state.skills:
                        state.skills.append(skill)
                        logger.debug("Groq inferred skill: %s", skill)

            if enhanced.get("missing_assessment_types"):
                for assess_type in enhanced["missing_assessment_types"]:
                    if assess_type not in state.assessment_types:
                        state.assessment_types.append(assess_type)
                        logger.debug("Groq inferred assessment: %s", assess_type)

            if enhanced.get("domain_inferred") and not state.industry_context:
                state.industry_context = enhanced["domain_inferred"]
                logger.debug("Groq inferred domain: %s", state.industry_context)

        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            # Groq enhancement is optional - fail silently
            logger.debug("Groq enhancement error (non-fatal): %s", e)

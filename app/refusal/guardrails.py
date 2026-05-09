"""Safety guardrails for refusal detection."""

from __future__ import annotations

import re

from app.orchestrator.state_extractor import HiringState
from app.utils.helpers import normalize_text


def refusal_reason(message: str, state: HiringState | None = None) -> str | None:
    """
    Check if message should be refused.
    
    Returns reason string if refusal is needed, None otherwise.
    
    Refusal categories:
    - prompt_injection: Attempts to override system instructions
    - legal: Legal or compliance advice requests
    - compensation: Salary or compensation advice
    - non_shl: Requests for non-SHL assessments
    - off_topic: Unrelated to assessment recommendations
    """
    text = normalize_text(message)

    # SAFETY: Prompt injection and jailbreak attempts
    injection_patterns = [
        r"ignore\s+(?:previous|all|my|the)\s+(?:instruction|prompt|system)",
        r"forget\s+(?:previous|all|my|the)\s+(?:instruction|prompt|system)",
        r"system\s+prompt",
        r"developer\s+(?:mode|instruction)",
        r"jailbreak",
        r"prompt\s+injection",
        r"break\s+(?:out|the|rules)",
        r"disregard",
        r"override",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in injection_patterns):
        return "prompt_injection"

    # SAFETY: Legal and regulatory advice
    legal_patterns = [
        r"\b(?:legally\s+required|legal\s+requirement|satisfy\s+that\s+requirement)\b",
        r"\blegal\s+advice\b",
        r"\blawsuit\b",
        r"\battorney\b",
        r"\bcounsel\b",
        r"\bemployment\s+law\b",
        r"\bdiscrimination\b",
        r"\bGDPR\b",
        r"\bcompliance\b",
        r"\bregulator\b",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in legal_patterns):
        return "legal"

    # SAFETY: Compensation and salary advice
    compensation_patterns = [
        r"\bsalary\b",
        r"\bcompensation\b",
        r"\bpay\s+(?:band|scale|range)\b",
        r"\boffer\s+(?:amount|package)\b",
        r"\bequity\s+grant\b",
        r"\bbonus\b",
        r"\braises?\b",
        r"\bhow\s+much\s+to\s+(?:pay|offer)\b",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in compensation_patterns):
        return "compensation"

    # SAFETY: Non-SHL assessment requests
    non_shl_patterns = [
        r"\b(?:non\s*-?\s*)?(?:SHL|shl)\b.*(?:competitor|alternative|instead)",
        r"\b(?:outside|non|not)\s+(?:SHL|shl|catalog)\b",
        r"\b(?:AWS|Azure|GCP|Coursera|Udemy|HackerRank|LeetCode|mercer|competera)\b",
        r"(?:kubernetes|terraform|docker|AWS|cloud)\s+(?:certification|assessment)",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in non_shl_patterns):
        return "non_shl"

    # OFF-TOPIC: Unrelated queries
    off_topic_patterns = [
        r"\b(?:weather|recipe|cooking|movie|sports|stock|bitcoin|crypto)\b",
        r"how\s+(?:are|do)\s+you(?:r|'re)",
        r"\bai\b.*(?:model|training|fine.*tun)",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in off_topic_patterns):
        return "off_topic"

    # If user has context (role/skills/prior recommendations), assume they're engaged
    if state and (state.role or state.skills or state.prior_recommendations):
        return None

    # Additional off-topic check for vague + no context
    if any(w in text for w in ("weather", "recipe", "movie", "sports score", "stock price")):
        return "off_topic"

    return None


def refusal_reply(reason: str | None) -> str:
    """Generate appropriate refusal response based on reason."""
    if reason == "legal":
        return (
            "I can help select SHL assessments, but I cannot provide legal or regulatory advice. "
            "Your legal or compliance team should confirm obligations and whether any assessment satisfies them."
        )
    if reason == "compensation":
        return "I can only help with SHL assessment recommendations, not compensation or offer advice."
    if reason == "non_shl":
        return "I can only recommend assessments from the SHL catalog provided for this assignment."
    if reason == "prompt_injection":
        return "I can only follow the SHL assessment recommendation task and the provided catalog."
    if reason == "off_topic":
        return "I can only help with SHL assessment recommendations. Is there a hiring or assessment challenge I can assist with?"
    return "I can only help with SHL assessment recommendations."

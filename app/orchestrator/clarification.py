"""Clarification question generation."""

from __future__ import annotations

from app.orchestrator.state_extractor import HiringState
from app.utils.helpers import normalize_text


def clarification_question(state: HiringState) -> str | None:
    """
    Generate clarification questions based on missing context.
    
    Priority:
    1. Domain-specific follow-ups (Rust, leadership, contact center, etc.)
    2. Structured insufficient context (missing role, skills, or use case)
    3. Smart compound questions (minimize conversation turns)
    4. Fallback for insufficient context
    """
    latest = normalize_text(state.latest_user_message or "")

    # DOMAIN-SPECIFIC CLARIFICATIONS

    if "rust" in latest and len([m for m in latest.split() if m == "yes"]) == 0:
        if not any(term in latest for term in ("go ahead", "yes", "shortlist")):
            return (
                "SHL's catalog does not include a Rust-specific test. I can use the closest "
                "catalog fit: live coding, Linux/systems depth, networking, and optional reasoning. "
                "Want me to build that shortlist?"
            )

    # MISSING CORE CONTEXT

    if not state.role and not state.skills and not state.assessment_types:
        # Complete absence of information
        return "What role or position are you hiring for, and what type of assessments are you considering—technical, behavioral, or leadership?"

    if not state.role and state.assessment_types:
        # Know what we're assessing, not who
        return f"For what role are you using these {len(state.assessment_types)} assessments—and what seniority level?"

    # LEADERSHIP-SPECIFIC

    if "senior leadership" in latest and not state.use_case:
        return "Is this for selecting external candidates, developing leaders already in role, or benchmarking performance?"

    if any(term in latest for term in ("cxo", "director", "executive", "senior leadership")):
        if state.use_case not in {"selection", "development", "audit"}:
            return "Is this for candidate selection against a leadership benchmark, or development feedback for leaders already in role?"

    # DOMAIN-SPECIFIC: CONTACT CENTER

    if any(term in latest for term in ("contact center", "contact centre", "inbound call")):
        if not state.languages:
            return "What language are the calls in? That determines the spoken-language screen."
        if "english" in state.languages and not any(
            accent in state.languages for accent in ("usa", "uk", "australian", "indian")
        ):
            return "Which English accent variant fits the operation best: US, UK, Australian, or Indian?"

    # DOMAIN-SPECIFIC: HEALTHCARE

    if any(term in latest for term in ("healthcare admin", "patient records", "hipaa")):
        if any(term in latest for term in ("spanish", "south texas")) and not state.special_requirements.get("hybrid_language_ok"):
            return (
                "The catalog's HIPAA, medical terminology, and Microsoft Word knowledge tests are English-only, "
                "while OPQ32r and DSI support Spanish variants. Should we run a hybrid battery with knowledge "
                "tests in English and personality in Spanish, or keep it personality-only in Spanish?"
            )

    # FULL STACK AMBIGUITY

    if any(term in latest for term in ("full stack", "full-stack")) and state.flags.get("many_technical_skills"):
        if not (state.flags.get("backend_leaning") or state.flags.get("frontend_leaning") or state.flags.get("balanced_fullstack")):
            return (
                "That stack spans several catalog tests. Is the role backend-leaning, frontend-heavy, "
                "or a balanced full-stack role with significant frontend ownership?"
            )
        if state.seniority == "senior" and not (state.flags.get("senior_ic") or state.flags.get("tech_lead")):
            return (
                "Is the seniority closer to a senior individual contributor who owns services, "
                "or a tech lead who sets architecture across engineers?"
            )

    # MISSING SKILLS/TECHNOLOGIES

    if state.role and not state.skills and "developer" in latest:
        return "Which core technologies should the developer be assessed on, and what seniority level is this?"

    # COMPOUND MISSING INFORMATION

    if state.role and not state.seniority and not state.skills:
        return f"For this {state.role} role, what seniority level and key technical skills matter most?"

    # DO NOT ask about use_case if:
    # - role exists (core context is there)
    # - conversation clearly mentions hiring/recruitment (implies "selection")
    # Only ask if role exists AND conversation is ambiguous about hiring intent
    hiring_keywords = ["hire", "hiring", "recruit", "recruit", "selection", "candidate", "screen", "assess"]
    conversation_text = normalize_text(f"{state.latest_user_message or ''} {' '.join(state.skills)}")
    has_hiring_signal = any(keyword in conversation_text for keyword in hiring_keywords)
    
    if state.role and not state.use_case and not has_hiring_signal:
        # Only ask if hiring intent is genuinely ambiguous
        return "Is this assessment for hiring/selection, development/feedback, or comparing candidates against a benchmark?"

    # FALLBACK: INSUFFICIENT CONTEXT

    if state.insufficient_context:
        # User asked vague question - guide them toward structure
        if state.role:
            return f"Got the {state.role} context. What type of assessments are you targeting—technical, personality, simulation, or a mix?"
        else:
            return "To help you build the right assessment, what role or job level are you hiring for?"

    return None

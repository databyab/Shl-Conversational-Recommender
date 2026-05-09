"""Domain-specific heuristic scoring boosts."""

from __future__ import annotations

from app.orchestrator.state_extractor import HiringState
from app.utils.helpers import CatalogItem, normalize_text


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def heuristic_score(item: CatalogItem, state: HiringState) -> float:
    query = normalize_text(state.latest_user_message or "")
    latest = normalize_text(state.latest_user_message or "")
    name = normalize_text(item.name)
    desc = normalize_text(item.description)
    text = f"{name} {desc} {' '.join(item.derived_tags)}"
    score = 0.0

    for skill in state.skills:
        skill_norm = normalize_text(skill)
        if skill_norm and (skill_norm in name or skill_norm in item.derived_tags):
            score += 0.35
        elif skill_norm and skill_norm in desc:
            score += 0.16

    if "rust" in query:
        if name == "smart interview live coding":
            score += 0.65
        if "linux programming" in name or "networking and implementation" in name:
            score += 0.42

    if _contains_any(query, ("senior leadership", "cxo", "director", "executive", "leadership benchmark")):
        if "occupational personality questionnaire opq32r" in name:
            score += 0.7
        if "opq leadership report" in name or "opq universal competency report" in name:
            score += 0.62

    if _contains_any(query, ("contact center", "contact centre", "inbound call", "customer service")):
        if "svar" in name and "spoken english" in name:
            score += 0.55
            if "us" in query and "us" in name:
                score += 0.35
            if "uk" in query and ("u.k" in name or "uk" in name):
                score += 0.3
            if "indian" in query and "indian" in name:
                score += 0.3
            if "australian" in query or "aus" in query:
                if "aus" in name:
                    score += 0.3
        if "contact center call simulation" in name:
            score += 0.6
        if "customer service phone simulation" in name:
            score += 0.42
        if "entry level customer" in name:
            score += 0.48

    if _contains_any(query, ("graduate financial", "financial analyst", "finance analyst")):
        if "numerical reasoning" in name and "verify interactive" in name:
            score += 0.64
        if "financial accounting" in name:
            score += 0.58
        if "basic statistics" in name:
            score += 0.42
        if "graduate scenarios" == name:
            score += 0.5

    if _contains_any(query, ("graduate management", "management trainee")):
        if "shl verify interactive g+" in name:
            score += 0.65
        if "occupational personality questionnaire opq32r" in name:
            score += 0.58
        if "graduate scenarios" == name:
            score += 0.64

    if _contains_any(query, ("re-skill", "reskill", "talent audit", "sales organization", "sales organisation")):
        if "global skills assessment" == name:
            score += 0.7
        if "global skills development report" == name:
            score += 0.62
        if "opq mq sales report" in name:
            score += 0.54
        if "sales transformation 2.0 - individual contributor" in name:
            score += 0.55
        if "occupational personality questionnaire opq32r" in name:
            score += 0.46

    if _contains_any(query, ("chemical facility", "plant operator", "procedure compliance", "never cutting corners", "safety")):
        if "dependability and safety instrument" in name:
            score += 0.66
        if "safety and dependability 8.0" in name:
            score += 0.68
        if "workplace health and safety" in name:
            score += 0.45

    if _contains_any(query, ("healthcare admin", "patient records", "hipaa")):
        if "hipaa" in name:
            score += 0.72
        if "medical terminology" in name:
            score += 0.54
        if "microsoft word 365 - essentials" in name:
            score += 0.42
        if "dependability and safety instrument" in name:
            score += 0.45
        if "occupational personality questionnaire opq32r" in name:
            score += 0.35

    if _contains_any(query, ("admin assistant", "administrative assistant", "excel", "word")):
        wants_sim = _contains_any(query, ("simulation", "capability", "capabilities", "hands on"))
        if wants_sim:
            if "microsoft excel 365 (new)" in name or "microsoft word 365 (new)" in name:
                score += 0.7
            if "ms excel" in name or "ms word" in name:
                score += 0.38
        else:
            if "ms excel (new)" in name or "ms word (new)" in name:
                score += 0.7
            if "microsoft excel 365" in name or "microsoft word 365" in name:
                score -= 0.08
        if "occupational personality questionnaire opq32r" in name:
            score += 0.3

    if _contains_any(query, ("full-stack", "full stack", "backend", "microservice", "spring")):
        if "core java (advanced level)" in name and _contains_any(query, ("senior", "5+", "advanced", "existing services")):
            score += 0.72
        elif "core java (entry level)" in name and _contains_any(query, ("graduate", "entry")):
            score += 0.55
        if "spring (new)" in name:
            score += 0.66
        if "restful web services" in name and "rest" not in state.exclude_terms:
            score += 0.5
        if "sql (new)" == name:
            score += 0.58
        if "amazon web services" in name and ("aws" in query or "cloud" in query):
            score += 0.58
        if "docker" in name:
            score += 0.54
        if "shl verify interactive g+" in name:
            score += 0.42
        if "occupational personality questionnaire opq32r" in name:
            score += 0.34

    if _contains_any(query, ("stakeholder communication", "communication", "mentor", "architecture")):
        if item.family == "OPQ" or "personality" in item.derived_tags:
            score += 0.14
    if _contains_any(query, ("hands-on coding", "live coding", "coding interview")):
        if "smart interview live coding" in name or "automata" in name:
            score += 0.42
    if _contains_any(query, ("situational", "decision making", "judgement", "judgment")):
        if "Biodata & Situational Judgment" in item.keys:
            score += 0.36
    if _contains_any(query, ("cognitive", "reasoning", "aptitude")):
        if "Ability & Aptitude" in item.keys:
            score += 0.36
    if _contains_any(query, ("personality", "behavioural", "behavioral", "fit")):
        if "Personality & Behavior" in item.keys:
            score += 0.32

    # CONTRADICTION PENALTIES: Domain-specific incompatibilities
    # Backend queries should not recommend frontend-heavy assessments
    if _contains_any(query, ("backend", "java", "spring", "microservice", "server", "database", "sql", "dba")):
        if _contains_any(name, ("front end", "frontend", "html", "css", "javascript", "react", "ui", "browser")):
            score -= 0.45
    
    # Frontend queries should not recommend backend-heavy assessments
    if _contains_any(query, ("frontend", "front end", "ui", "web", "react", "javascript", "css")):
        if _contains_any(name, ("backend", "java", "spring", "microservice", "dba", "database", "sql", "server")):
            score -= 0.45
    
    # Leadership/management queries should not recommend coding-heavy assessments
    if _contains_any(query, ("leadership", "leader", "manager", "director", "executive", "cxo")):
        if _contains_any(name, ("coding", "live coding", "automata", "html", "css", "javascript", "java", "python")):
            score -= 0.35
    
    # Engineering queries should not recommend customer-support assessments
    if _contains_any(query, ("engineer", "engineering", "backend", "frontend", "development", "developer")):
        if _contains_any(name, ("customer service", "contact center", "inbound call", "phone simulation", "spoken english")):
            score -= 0.40
    
    # Prefer primary assessments over report-only variants
    # If user is asking for an assessment (not a report), penalize report-only items
    if not _contains_any(query, ("report", "results", "feedback")):
        if _contains_any(name, (" report", "report")) and not _contains_any(name, ("assessment", "test", "ability", "coding", "verify", "opq32r")):
            score -= 0.25

    if "drop" in latest or "remove" in latest or "exclude" in latest:
        for term in state.exclude_terms:
            if term and term in name:
                score -= 1.0

    return max(0.0, min(score, 1.0))

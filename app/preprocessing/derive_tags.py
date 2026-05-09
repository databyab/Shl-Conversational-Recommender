from __future__ import annotations

from app.utils.helpers import normalize_text, tokenize


TAG_RULES: dict[str, tuple[str, ...]] = {
    "frontend": ("front end", "frontend", "angular", "javascript", "html", "css"),
    "backend": ("backend", "spring", "java", "api", "microservice", "sql"),
    "coding": ("coding", "programming", "developer", "development", "automata", "java", "python"),
    "simulation": ("simulation", "simulations", "interactive", "call simulation", "phone simulation"),
    "personality": ("personality", "behaviour", "behavior", "opq", "dependability"),
    "leadership": ("leadership", "manager", "director", "executive", "cxo", "hipo"),
    "cognitive": ("ability", "aptitude", "reasoning", "verify", "numerical", "deductive", "inductive"),
    "graduate": ("graduate", "student", "trainee", "entry level", "entry-level"),
    "sales": ("sales", "selling", "seller", "account executive"),
    "customer_support": ("customer", "contact center", "contact centre", "call", "retail", "service"),
    "safety": ("safety", "dependability", "reliability", "procedure", "industrial", "manufacturing"),
    "healthcare": ("hipaa", "medical", "patient", "healthcare"),
    "office": ("excel", "word", "powerpoint", "office", "outlook"),
    "finance": ("finance", "financial", "accounting", "statistics", "numerical"),
    "language": ("spoken", "svar", "english", "french", "spanish", "accent"),
    "development": ("development report", "360", "reskill", "re-skill", "skills development"),
}

SKILL_TAGS: dict[str, tuple[str, ...]] = {
    "java": ("java", "core java"),
    "spring": ("spring", "spring boot"),
    "sql": ("sql", "database"),
    "aws": ("aws", "amazon web services"),
    "docker": ("docker", "container"),
    "linux": ("linux",),
    "networking": ("networking", "network"),
    "excel": ("excel",),
    "word": ("word",),
    "hipaa": ("hipaa",),
    "medical_terminology": ("medical terminology",),
}


def derive_tags(record: dict) -> list[str]:
    text = normalize_text(
        " ".join(
            [
                record.get("name", ""),
                record.get("description", ""),
                " ".join(record.get("keys") or []),
                " ".join(record.get("job_levels") or []),
            ]
        )
    )
    token_set = set(tokenize(text))
    tags: set[str] = set()
    for tag, patterns in TAG_RULES.items():
        if any(pattern in text for pattern in patterns):
            tags.add(tag)
    for tag, patterns in SKILL_TAGS.items():
        if any(pattern in text or pattern in token_set for pattern in patterns):
            tags.add(tag)
    return sorted(tags)

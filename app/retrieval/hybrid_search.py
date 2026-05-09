"""Hybrid retrieval engine (semantic + keyword + heuristic)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.orchestrator.state_extractor import HiringState
from app.preprocessing.normalize_catalog import normalize_catalog
from app.retrieval.bm25_search import BM25Search
from app.retrieval.faiss_index import FaissSemanticIndex
from app.retrieval.heuristic_boosts import heuristic_score
from app.retrieval.metadata_filters import metadata_score
from app.retrieval.reranker import rerank
from app.utils.constants import PRODUCT_ALIASES
from app.utils.helpers import CatalogItem, normalize_text, safe_json_load


class CatalogStore:
    def __init__(self, processed_path: Path | None = None) -> None:
        self.settings = get_settings()
        self.processed_path = processed_path or self.settings.processed_catalog_path
        self.items = self._load_items()
        self.by_name = {normalize_text(item.name): item for item in self.items}
        self.by_url = {item.url: item for item in self.items}

    def _load_items(self) -> list[CatalogItem]:
        if not self.processed_path.exists():
            normalize_catalog(self.settings.catalog_path, self.processed_path)
        records = safe_json_load(self.processed_path)
        return [CatalogItem.from_dict(record) for record in records]

    def resolve(self, name_or_alias: str) -> CatalogItem | None:
        needle = normalize_text(name_or_alias)
        if not needle:
            return None
        target_name = PRODUCT_ALIASES.get(needle)
        if target_name:
            found = self.by_name.get(normalize_text(target_name))
            if found:
                return found
        if needle in self.by_name:
            return self.by_name[needle]
        for item in self.items:
            item_name = normalize_text(item.name)
            item_base = item_name.replace(" new", "").strip()
            if needle == item_base or (len(needle) > 5 and needle in item_name):
                return item
        return None

    def resolve_mentions(self, text: str) -> list[CatalogItem]:
        normalized = normalize_text(text)
        found: list[CatalogItem] = []
        seen: set[str] = set()
        for alias, target in sorted(PRODUCT_ALIASES.items(), key=lambda pair: len(pair[0]), reverse=True):
            alias_norm = normalize_text(alias)
            if alias_norm and alias_norm in normalized:
                item = self.resolve(target)
                if item and item.name not in seen:
                    found.append(item)
                    seen.add(item.name)
        for item in self.items:
            item_name = normalize_text(item.name)
            if item.name == "Verify - G+" and "verify g+" in normalized:
                continue
            variants = {item_name, item_name.replace(" new", "").strip()}
            if any(len(variant) > 6 and variant in normalized for variant in variants):
                if item.name not in seen:
                    found.append(item)
                    seen.add(item.name)
        return found


class HybridSearchEngine:
    def __init__(self, store: CatalogStore | None = None) -> None:
        self.store = store or CatalogStore()
        texts = [item.search_text or f"{item.name} {item.description}" for item in self.store.items]
        self.semantic = FaissSemanticIndex(texts)
        self.keyword = BM25Search(texts)

    def persist_indices(self) -> None:
        self.semantic.persist()
        self.keyword.persist()

    def _requested_items(self, state: HiringState) -> list[CatalogItem]:
        items: list[CatalogItem] = []
        seen: set[str] = set()

        def add(name: str) -> None:
            item = self.store.resolve(name)
            if item and item.name not in seen:
                items.append(item)
                seen.add(item.name)

        for name in state.mentioned_products:
            add(name)
        for item in self.store.resolve_mentions(state.latest_user_message or ""):
            if item.name not in seen:
                items.append(item)
                seen.add(item.name)

        query = normalize_text(state.latest_user_message or "")
        wants_sim = any(term in query for term in ("simulation", "hands on", "hands-on", "capability", "capabilities"))
        for skill in state.skills:
            skill_norm = normalize_text(skill)
            if skill_norm == "core java":
                add("Core Java (Advanced Level) (New)" if state.seniority == "senior" else "Core Java (Entry Level) (New)")
            elif skill_norm == "spring":
                add("Spring (New)")
            elif skill_norm == "restful web services" and "rest" not in state.exclude_terms:
                add("RESTful Web Services (New)")
            elif skill_norm == "sql":
                add("SQL (New)")
            elif skill_norm == "aws":
                add("Amazon Web Services (AWS) Development (New)")
            elif skill_norm == "docker":
                add("Docker (New)")
            elif skill_norm == "linux":
                add("Linux Programming (General)" if "programming" in query or "engineer" in query else "Linux Operating System")
            elif skill_norm == "networking":
                add("Networking and Implementation (New)")
            elif skill_norm == "excel":
                if wants_sim:
                    add("Microsoft Excel 365 (New)")
                    add("MS Excel (New)")
                else:
                    add("MS Excel (New)")
            elif skill_norm == "word":
                if "hipaa" in query or "healthcare" in query:
                    add("Microsoft Word 365 - Essentials (New)")
                else:
                    if wants_sim:
                        add("Microsoft Word 365 (New)")
                        add("MS Word (New)")
                    else:
                        add("MS Word (New)")
            elif skill_norm == "hipaa":
                add("HIPAA (Security)")
            elif skill_norm == "medical terminology":
                add("Medical Terminology (New)")
            elif skill_norm == "numerical reasoning":
                add("SHL Verify Interactive – Numerical Reasoning")
            elif skill_norm == "financial accounting":
                add("Financial Accounting (New)")
            elif skill_norm == "basic statistics":
                add("Basic Statistics (New)")

        if "rust" in query:
            add("Smart Interview Live Coding")
            add("Linux Programming (General)")
            add("Networking and Implementation (New)")
        if any(term in query for term in ("cognitive", "reasoning", "aptitude", "senior ic", "architectural")):
            if "numerical reasoning" not in query:
                add("SHL Verify Interactive G+")
        if state.seniority == "senior" and any(term in query for term in ("engineer", "developer", "architect", "mentor", "microservice")):
            add("SHL Verify Interactive G+")
            if "opq" not in state.exclude_terms and "personality" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
        if any(term in query for term in ("personality", "behavioral", "behavioural", "fit", "mentor", "leadership")):
            if "opq" not in state.exclude_terms and "personality" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
        if any(term in query for term in ("situational", "judgement", "judgment", "scenarios")) and (
            state.seniority in {"graduate", "entry"} or "graduate" in query
        ):
            add("Graduate Scenarios")
        if any(term in query for term in ("contact center", "contact centre", "inbound call", "customer service")):
            if "english" in state.languages:
                if "usa" in state.languages:
                    add("SVAR - Spoken English (US) (New)")
                elif "uk" in state.languages:
                    add("SVAR - Spoken English (U.K.)")
                elif "australian" in state.languages:
                    add("SVAR - Spoken English (AUS)")
                elif "indian" in state.languages:
                    add("SVAR - Spoken English (Indian Accent) (New)")
            add("Contact Center Call Simulation (New)")
            add("Entry Level Customer Serv - Retail & Contact Center")
            add("Customer Service Phone Simulation")
        if any(term in query for term in ("graduate financial", "financial analyst")):
            add("SHL Verify Interactive – Numerical Reasoning")
            add("Financial Accounting (New)")
            add("Basic Statistics (New)")
            if "sjt" in state.assessment_types:
                add("Graduate Scenarios")
            if "opq" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
        if any(term in query for term in ("graduate management", "management trainee")):
            add("SHL Verify Interactive G+")
            if "opq" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
            add("Graduate Scenarios")
        if any(term in query for term in ("senior leadership", "cxo", "director", "executive", "leadership benchmark")):
            if "opq" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
                add("OPQ Universal Competency Report 2.0")
                add("OPQ Leadership Report")
        if any(term in query for term in ("talent audit", "re-skill", "reskill", "sales organization", "sales organisation")):
            add("Global Skills Assessment")
            add("Global Skills Development Report")
            if "opq" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
                add("OPQ MQ Sales Report")
            add("Sales Transformation 2.0 - Individual Contributor")
        if any(term in query for term in ("plant operator", "chemical facility", "safety", "procedure compliance")):
            add("Dependability and Safety Instrument (DSI)")
            add("Manufac. & Indust. - Safety & Dependability 8.0")
            add("Workplace Health and Safety (New)")
        if any(term in query for term in ("healthcare admin", "patient records", "hipaa")) and state.special_requirements.get("hybrid_language_ok"):
            add("HIPAA (Security)")
            add("Medical Terminology (New)")
            add("Microsoft Word 365 - Essentials (New)")
            add("Dependability and Safety Instrument (DSI)")
            if "opq" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
        if any(term in query for term in ("admin assistant", "administrative assistant", "admin assistants")):
            if "opq" not in state.exclude_terms and "personality" not in state.exclude_terms:
                add("Occupational Personality Questionnaire OPQ32r")
        return items

    def recommend(self, state: HiringState, max_results: int | None = None) -> list[CatalogItem]:
        requested = self._requested_items(state)
        # Build search query from state
        search_parts = [
            state.role or "",
            state.seniority or "",
            " ".join(state.skills),
            " ".join(state.personality_traits),
            " ".join(state.assessment_types),
            state.latest_user_message or "",
        ]
        search_query = " ".join(filter(None, search_parts))
        semantic_scores = self.semantic.search(search_query, top_k=110)
        keyword_scores = self.keyword.search(search_query, top_k=110)
        candidate_ids = set(semantic_scores) | set(keyword_scores)
        for idx, item in enumerate(self.store.items):
            if heuristic_score(item, state) >= 0.35:
                candidate_ids.add(idx)
        for item in requested:
            try:
                candidate_ids.add(self.store.items.index(item))
            except ValueError:
                pass

        candidates: list[tuple[CatalogItem, float]] = []
        for idx in candidate_ids:
            item = self.store.items[idx]
            semantic = semantic_scores.get(idx, 0.0)
            keyword = keyword_scores.get(idx, 0.0)
            metadata = metadata_score(item, state)
            heuristic = heuristic_score(item, state)
            final = 0.40 * semantic + 0.25 * keyword + 0.20 * metadata + 0.15 * heuristic
            if item in requested:
                final += 0.35
            candidates.append((item, final))

        return rerank(candidates, state, requested_items=requested, max_results=max_results)


@lru_cache(maxsize=1)
def get_hybrid_engine() -> HybridSearchEngine:
    return HybridSearchEngine()

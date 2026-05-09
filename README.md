# SHL Conversational Assessment Recommender

Stateless FastAPI service for recommending SHL assessments from natural language hiring requirements. Orchestrates clarification, comparison, and grounded retrieval without LLM-generated recommendations.

## Features

- Stateless conversation orchestration (full message history processed each request)
- Hybrid retrieval: FAISS semantic search (40%) + BM25 keyword (25%) + heuristic boosts (20%) + metadata filters (15%)
- Grounded recommendations from `catalogue.json` only (names, URLs, metadata)
- Clarification detection (distinguishes vague queries from actionable hiring context)
- Refinement and comparison support
- Refusal guardrails (prompt injection, legal, compensation, off-topic)
- Optional Groq enhancement for state extraction (graceful degradation if key missing)
- FastAPI REST API with Pydantic validation
- Deterministic orchestration (no agents, LangGraph, or autonomous tool loops)

## Architecture

```
Conversation History
        ↓
State Extraction (regex + optional Groq)
        ↓
Intent Classification
        ↓
Orchestration Controller
├─ REFUSE (safety/off-topic)
├─ COMPARE (product comparison)
├─ CLARIFY (insufficient context)
├─ SPECIAL (catalog constraints)
└─ RECOMMEND (hybrid retrieval)
        ↓
Response Builder
```

## Tech Stack

- **API**: FastAPI 0.115+, Pydantic 2.8+
- **Search**: FAISS (semantic), BM25Okapi (keyword)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2
- **Enhancement**: Groq llama-3.3-70b (optional)
- **Deployment**: Docker, Render

## Project Structure

```
app/
  orchestrator/         # Conversation control
    controller.py       # Main orchestration
    state_extractor.py  # State extraction (deterministic + Groq)
    clarification.py    # Clarification generation
    intent_classifier.py
  retrieval/            # Search and ranking
    hybrid_search.py    # Hybrid retrieval engine
    faiss_index.py
    bm25_search.py
    heuristic_boosts.py
    reranker.py
  refusal/              # Safety guardrails
  comparison/           # Product comparison
  models/               # Pydantic schemas
  routes/               # API endpoints
  utils/                # Helpers

scripts/
  preprocess_catalog.py # Build processed_catalog.json
  build_faiss.py        # Build FAISS index
  evaluate_recall.py    # Replay evaluation

tests/
  test_chat.py
  test_refusal.py
  etc.
```

## Setup

```bash
# Clone and enter
git clone <repo>
cd shl_assignment

# Environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env: set GROQ_API_KEY (optional, system works without it)

# Build artifacts
python scripts/preprocess_catalog.py
python scripts/build_faiss.py

# Run
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| GROQ_API_KEY | No | — |
| GROQ_BASE_URL | No | https://api.groq.com/openai/v1 |
| GROQ_MODEL | No | llama-3.3-70b-versatile |
| EMBEDDING_MODEL | No | sentence-transformers/all-MiniLM-L6-v2 |
| ALLOWED_ORIGINS | No | localhost:3000 |

## API

**Health:**
```bash
GET /health
```

**Chat:**
```bash
POST /chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Hiring senior Java developer with Spring"}
  ]
}
```

**Response:**
```json
{
  "reply": "Here is a grounded SHL shortlist from the catalog:\n1. Core Java (Advanced Level) (New) (K, 30 minutes) - Assesses Java skills.\n2. Spring (New) (K, 9 minutes) - Assesses Spring skills.",
  "recommendations": [
    {"name": "Core Java (Advanced Level) (New)", "url": "...", "test_type": "K"},
    {"name": "Spring (New)", "url": "...", "test_type": "K"}
  ],
  "end_of_conversation": false
}
```

## Example Conversation

**Vague → Clarification:**
```
User: "I need an assessment"
Assistant: "To help you build the right assessment, what role or job level are you hiring for?"
```

**Clear → Retrieval:**
```
User: "Hiring mid-level backend engineer with Python"
Assistant: [5 relevant recommendations with explanations]
```

**Refinement:**
```
User: "Also add personality assessment"
Assistant: [Updated recommendations preserving prior context]
```

## Retrieval Strategy

**Scoring formula:**
```
score = 0.40 * semantic_score 
      + 0.25 * keyword_score 
      + 0.20 * metadata_score 
      + 0.15 * heuristic_score
```

- **Semantic (FAISS)**: Normalized embedding similarity over catalog search text
- **Keyword (BM25)**: Term frequency-inverse document frequency scoring
- **Metadata**: Job level, assessment keys, duration, adaptive, language matches
- **Heuristic**: Domain-specific boosts for Rust, leadership, contact center, healthcare scenarios

Recommendations limited to top 5 (expandable to 10 on user request). Reranker removes exact duplicates and balances assessment families.

## Orchestration

**Clarification triggers only when:**
- No role extracted AND
- No assessment types specified

**Recommends immediately when:**
- Role is clear OR assessment goal is explicit

**Refuses if:**
- Prompt injection, legal advice, compensation, non-SHL products, unrelated topics

**Compares products when:**
- User explicitly asks for comparison (grounded in catalog only)

**Stateless design:**
- Full conversation history sent on every request
- State reconstructed from message history each turn
- No database, no session storage


## Design Decisions

- **Deterministic over generative**: Retrieval is deterministic and auditable; LLM only enhances state extraction
- **Stateless API**: Enables multi-turn replay evaluation and stateless scaling
- **Catalog-grounded**: All recommendations use catalog names/URLs only; no hallucination risk
- **Regex-first extraction**: Fast, reproducible; Groq enhancement is optional fallback
- **Minimal clarification**: Only clarifies when context genuinely insufficient

## Limitations

- Retrieval quality depends on catalog metadata completeness
- Groq enhancement optional (system fully functional without API key)
- No persistent recruiter memory (stateless by design)
- Semantic search depends on query language matching catalog
- Heuristic boosts are catalog-specific and require maintenance



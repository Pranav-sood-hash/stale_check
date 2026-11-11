# StaleCheck — PS6 Stale-Answer Detector

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Enabled-blueviolet.svg)](https://github.com/langchain-ai/langgraph)

StaleCheck detects potentially outdated factual claims in AI-generated answers, retrieves live evidence from the web via Tavily, independently scores claim freshness (0–100) using multi-model evaluation through Maxim AI's Bifrost gateway, and generates surgical, evidence-cited corrections.

---

## Architecture & Data Flow

```mermaid
flowchart TD
    User([User Prompt or AI Answer]) --> Frontend[StaleCheck Dashboard\nDark Theme UI]
    Frontend -->|POST /api/check or /api/ask| FastAPI[FastAPI Backend\nbackend/main.py]
    
    subgraph LangGraph Pipeline
        START([Input Answer]) --> ExtractNode[Extract Node\nIdentifies time-sensitive claims & stable facts]
        ExtractNode -->|Conditional: Claims exist?| SearchNode[Search Node\nConcurrent Tavily Search + SQLite Cache]
        ExtractNode -->|No claims| END([End: Return Overall Null])
        
        SearchNode --> AnalyzeNode[Analyze Node\nStrict evidence verification: current/outdated/unverifiable]
        AnalyzeNode --> JudgeNode[Judge Node\nIndependent LLM freshness score 0-100 & recency decay]
        JudgeNode --> RewriteNode[Rewrite Node\nSurgical replacement with markdown citations]
        RewriteNode --> ResultComp[Build Result Contract]
    end
    
    FastAPI --> LangGraph Pipeline
    LangGraph Pipeline -->|SSE stream: node, done| Frontend
    
    subgraph External Integrations
        SearchNode <-->|Live web queries| Tavily[(Tavily Search API)]
        ExtractNode <-->|Provider proxy| Bifrost[(Bifrost Gateway / Maxim AI)]
        AnalyzeNode <-->|Analyst model| Bifrost
        JudgeNode <-->|Independent judge model| Bifrost
        RewriteNode <-->|Local model| Bifrost
    end
```

---

## Technology Contributions

### How Tavily Contributes
- **Real-Time Factual Grounding**: StaleCheck eliminates LLM hallucination during verification by enforcing strict factual grounding. No LLM is permitted to verify facts from its pre-training weights.
- **Advanced Search Parameters**: Uses `search_depth="advanced"` and caps evidence at the top 5 authoritative results.
- **Domain-Aware Query Routing**: Automatically routes dynamic categories (`pricing`, `version`, `leadership`) with news-oriented searches for fresh updates.
- **Source Deduplication & Date Extraction**: Normalizes URLs and extracts publication dates for freshness decay calculations.

### How Bifrost (Maxim AI) Contributes
- **Unified Multi-Provider Gateway**: Routes requests across diverse model providers (OpenAI, Anthropic, open-source via Ollama) through a single OpenAI-compatible endpoint.
- **Provider Independence for Fair Judging**: Enforces separation of concerns by routing claim extraction/analysis to one provider (e.g., `openai/gpt-4o-mini`) and freshness evaluation to an independent provider (e.g., `anthropic/claude-3-5-sonnet`), preventing self-grading bias.
- **Model Fallback & Resilience**: Provides standardized temperature controls and JSON output structure handling.

---

## 5-Step Quickstart Setup

### Step 1: Clone the repository and navigate into it
```bash
git clone https://github.com/your-org/stalecheck.git
cd stalecheck
```

### Step 2: Set up a Python virtual environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure environment variables
```bash
cp .env.example .env
```
Edit `.env` and add your `TAVILY_API_KEY` and `BIFROST_KEY` (or `OPENAI_API_KEY`).

### Step 5: Start the application
```bash
uvicorn backend.main:api --reload --port 8000
```
Open **http://localhost:8000** in your browser.

---

## Environment Variables Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `TAVILY_API_KEY` | *(Required for live)* | Tavily API key for real-time web search |
| `BIFROST_URL` | `http://localhost:8080/openai/v1` | Bifrost gateway base URL |
| `BIFROST_KEY` | *(Optional)* | Bifrost gateway API authentication key |
| `OPENAI_API_KEY` | *(Optional fallback)* | Direct OpenAI API key |
| `LOCAL_MODEL` | `openai/gpt-4o-mini` | Model for local answering and rewriting |
| `EXTRACT_MODEL` | `openai/gpt-4o-mini` | Model for claim extraction |
| `ANALYST_MODEL` | `openai/gpt-4o-mini` | Model for evidence analysis |
| `JUDGE_MODEL` | `anthropic/claude-3-5-sonnet`| Independent model for freshness judging |
| `ALLOWED_ORIGINS`| `*` | CORS allowed origins |
| `PORT` | `8000` | Server listening port |

---

## API Reference

### `POST /api/check`
Verify an existing text or AI-generated answer.

**Request:**
```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{"text": "GPT-4 was released on March 14, 2023. OpenAI GPT-4 costs $0.03 per 1k prompt tokens."}'
```

**Response Structure:**
```json
{
  "answer": "GPT-4 was released on March 14, 2023. OpenAI GPT-4 costs $0.03 per 1k prompt tokens.",
  "overall": 45,
  "cache_hits": 0,
  "rewritten": "GPT-4 was released on March 14, 2023. OpenAI GPT-4 costs $0.03 per 1k prompt tokens [source](https://openai.com/pricing).",
  "stable_facts": [
    "GPT-4 was released on March 14, 2023."
  ],
  "trace": [
    {"node": "extract", "ms": 420},
    {"node": "search", "ms": 680},
    {"node": "analyze", "ms": 510},
    {"node": "judge", "ms": 490},
    {"node": "rewrite", "ms": 380}
  ],
  "claims": [
    {
      "id": 1,
      "title": "GPT-4 Prompt Pricing",
      "text": "OpenAI GPT-4 costs $0.03 per 1k prompt tokens.",
      "category": "pricing",
      "verdict": "Stale",
      "score": 15,
      "current_fact": "Current GPT-4o pricing is $0.0025 per 1k prompt tokens.",
      "reason": "Directly contradicted by current official pricing schedules.",
      "sources": ["https://openai.com/pricing"],
      "evidence": [
        {
          "title": "OpenAI Pricing",
          "url": "https://openai.com/pricing",
          "date": "2024-05-13",
          "snippet": "Pricing overview for GPT-4o and legacy GPT-4 models..."
        }
      ],
      "cached": false
    }
  ]
}
```

### `POST /api/check/stream`
Same as `/api/check`, returning Server-Sent Events (SSE) with `node`, `done`, and `error` events for live pipeline stage indicators.

### `POST /api/ask` & `POST /api/ask/stream`
Generates an initial answer to a question using `LOCAL_MODEL`, then runs the full StaleCheck verification pipeline on the response.

### `GET /api/health`
Returns system status and presence of configured API keys.

---

## Docker Deployment

Run with Docker Compose:
```bash
docker compose up --build -d
```

---

## Team

- **Pranav Sood** — Team Leader, AI & LangGraph Architect (`backend/graph.py`)
- **Sidak Singh** — Frontend Engineer (`frontend/index.html`)
- **Aradhaya Kaul** — Backend Engineer (`backend/main.py`)
- **Dhruv Sharma** — Integration & Delivery Engineer (`backend/llm.py`, `backend/search.py`, `backend/memory.py`, Docker, CI)

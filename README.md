# StaleCheck

StaleCheck extracts time-sensitive claims from an answer, searches for evidence, assesses each claim, and suggests cited corrections. It also offers an “Ask & Check” mode that generates an answer before checking it.

## Run locally

Requires Python 3.10 or later, a Tavily API key, and an OpenAI API key (or an OpenAI-compatible Bifrost endpoint and key).

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `TAVILY_API_KEY` and `OPENAI_API_KEY` in `.env`. Alternatively set `BIFROST_API_KEY` and `BIFROST_BASE_URL` for Bifrost. Never commit `.env`.

```sh
uvicorn backend.main:api --reload --port 8000
```

Open http://127.0.0.1:8000. API documentation is at http://127.0.0.1:8000/docs. The `/api/health` endpoint reports whether configuration values are present; it does not validate keys or connectivity.

Optional model settings are `EXTRACT_MODEL`, `ANALYST_MODEL`, `JUDGE_MODEL`, and `LOCAL_MODEL`. Defaults are suitable for OpenAI's API; when using Bifrost, configure model identifiers supported by your gateway. The judge is only independent if configured to use a different provider.

## API

- `POST /api/check`: check an existing answer, with JSON `{"text":"..."}`.
- `POST /api/ask`: generate and check an answer, with the same input shape.
- `POST /api/check/stream` and `/api/ask/stream`: stream node updates and the final result as server-sent events.

Text must be 3–6000 characters. An `overall` value of `null` means no time-sensitive claims were extracted; it does not mean the answer has been verified. If search is unavailable, claims are marked unverifiable. The dashboard's `?mock=1` view uses illustrative data only.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests use mocked services; they do not validate real API credentials or provider connectivity. Check a representative mix of current, outdated, conflicting, and unverified claims with real services before deployment. Model-generated assessments can be wrong and should be reviewed against their sources.

The app uses an in-process workflow when LangGraph is not installed and an in-memory search cache. Rate limits and cache are per process, so production deployments need shared infrastructure and proxy-aware rate limiting.

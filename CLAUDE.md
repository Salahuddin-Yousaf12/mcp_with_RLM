# Reddit Scraper + RLM — Architecture & Flow

Ask a plain-English question → Reddit is searched and scraped → an LLM reads the
comments and answers you. Everything runs in Docker.

---

## High-Level Flow

```
You (terminal)
     │
     │  "how to escape waterfowl dance?"
     ▼
┌─────────────────────────────────┐
│  mcp-server/main.py  (REPL)     │  ← you run this directly on your machine
│  python main.py                 │
└────────────┬────────────────────┘
             │ POST /ask  { "q": "..." }
             ▼
┌─────────────────────────────────┐   port 8003
│  mcp-server/api.py              │  ← Docker container: mcp-service
│  (orchestrator / FastAPI)       │
└──────┬──────────────────┬───────┘
       │                  │
       │ Step 1           │ Step 3
       │ GET /google      │ POST /query
       ▼                  ▼
┌─────────────┐    ┌──────────────────┐
│ reddit-     │    │  RLM/api.py      │  port 8002
│ scraper     │    │  (rlm-service)   │  ← Docker container
│ port 8001   │    └────────┬─────────┘
└──────┬──────┘             │
       │                    │ RLMTools.query(question, context)
       │ saves JSON         ▼
       │ to /data/   ┌──────────────────────────────────┐
       │             │  RLM/rlm/tools/orchestrator.py   │
       │             │  ToolsOrchestrator               │
       │             │                                  │
       │             │  loops: send → get tool call     │
       │             │         → execute tool           │
       │             │         → send results back      │
       │             └────────────────┬─────────────────┘
       │                              │ POST /api/chat
       │                              ▼
       │                    ┌─────────────────────┐
       │                    │  Ollama server       │
       │                    │  llama3.1:8b         │
       │                    │  (remote, shared)    │
       │                    └─────────────────────┘
       │
       │ Step 2 (inside mcp-service)
       ▼
 mcp-server/api.py reads the saved JSON from the shared
 Docker volume (/data/) and builds a context string
 (POST TITLE + comments sorted by score)
```

---

## Step-by-Step Walkthrough

### Step 1 — Scrape Reddit

`mcp-service` calls `reddit-scraper`:
```
GET http://reddit-scraper:8000/google?q=<query>
```

**Inside `reddit-scraper`:**

```
app/main.py  (FastAPI endpoint /google)
     │
     ▼
app/scraper.py: scrape_via_google(query)
     │
     ├─ search_google_for_reddit(query)    → parse HTML, find reddit.com URL
     │     if fails ↓
     ├─ search_duckduckgo_for_reddit(query) → fallback
     │     if fails ↓
     ├─ search_bing_for_reddit(query)       → fallback
     │     if fails ↓
     └─ search_reddit_api(query)            → reddit.com/search.json (most reliable)
          │
          ▼
     scrape_single_post(reddit_url)
          │  fetches <url>.json from Reddit
          ▼
     parse_post() + parse_comment()  (recursive, up to 20 levels deep)
          │
          ▼
     saves to /data/reddit_google_<query>.json
     returns: { "saved_to": "/data/reddit_google_<query>.json" }
```

`app/models.py` defines the Pydantic schemas: `Post`, `Comment`, `SavedResult`.

---

### Step 2 — Build Context

Back in `mcp-server/api.py`, the saved JSON is read from the shared volume:

```python
# _build_context(saved_to)
data = json.loads(Path(saved_to).read_text())
posts → extract all comments recursively → sort by score (desc)
→ join as:
  "POST TITLE: ...\n\nCOMMENT 1:\n...\n\nCOMMENT 2:\n..."
```

This context string is the Reddit discussion, highest-voted comments first.

---

### Step 3 — Answer with RLM

`mcp-service` calls `rlm-service`:
```
POST http://rlm-service:8002/query
{ "query": "...", "context": "<context string>" }
```

**Inside `RLM/api.py`:**
```python
mode = os.getenv("RLM_MODE", "tools")   # "tools" (current)
rlm = RLMTools(...)
answer = rlm.query(req.query, req.context)
```

**Inside `RLM/rlm/tools/orchestrator.py` — ToolsOrchestrator:**

```
context string → ContextTools (stores it locally, splits into chunks)

System message sent to llama3.1:8b:
  "You are a helpful assistant. The context contains Reddit posts...
   CONTEXT: 3500 chars in 2 chunks.
   RULES: read_chunk(0) first, then answer from what you find."

Loop (max 10 iterations):
  ┌─ send messages to llama3.1:8b via Ollama /api/chat
  │
  ├─ model calls read_chunk(0)
  │     → ContextTools._handle_read_chunk()
  │     → returns chunk text as tool result
  │
  ├─ model calls search("dodge timing")   [optional]
  │     → ContextTools._handle_search()
  │     → regex search, returns excerpts
  │
  └─ model calls final_answer("Sprint away from...")
        → returns answer, loop ends
```

**Inside `RLM/rlm/tools/handlers.py` — ContextTools:**

| Tool | Handler | What it does |
|------|---------|--------------|
| `read_chunk(index)` | `_handle_read_chunk` | Returns the Nth chunk of the context |
| `read_range(start, end)` | `_handle_read_range` | Returns chars start→end |
| `search(query)` | `_handle_search` | Regex search, returns excerpts with positions |
| `get_context_info` | `_handle_get_context_info` | Returns length, chunk count, preview |
| `ask_about_chunk(index, question)` | `_handle_ask_about_chunk` | Calls SUB LLM on that chunk |
| `final_answer(answer)` | `_handle_final_answer` | Returns answer, terminates loop |

**Inside `RLM/rlm/clients/ollama.py` — OllamaChatClient:**

Sends POST to `https://ollama-ijcare-gpt.sheikhibrar.com/api/chat` with:
- `model`: llama3.1:8b
- `messages`: conversation history
- `tools`: the 6 tool definitions (from `RLM/rlm/tools/definitions.py`)
- `stream`: false

---

## File Map

```
BERTopic/
│
├── docker-compose.yml          ← defines all 3 containers + shared volume
├── .env                        ← model switching config (edit here to change models)
│
├── mcp-server/                 ═══ Container: mcp-service (port 8003) ═══
│   ├── Dockerfile
│   ├── api.py                  ← ACTIVE: FastAPI orchestrator (/ask endpoint)
│   │                              Steps 1→2→3, builds context from scraped JSON
│   ├── main.py                 ← ACTIVE: REPL — run this to use the system
│   │                              Reads input, POSTs to mcp-service, prints answer
│   ├── mcp_server.py           ← MCP server for Claude Desktop integration (stdio)
│   │                              Exposes google_search_reddit() as an MCP tool
│   │
│   │   ── OLD ARCHITECTURE (not used in current flow) ──
│   ├── executor.py             ← Old: called Reddit API + ran extract_comments.py
│   ├── parser.py               ← Old: parsed raw LLM text into ParsedCall objects
│   ├── function_registry.py    ← Old: defined available API functions
│   └── ollama_client.py        ← Old: sent queries to Ollama generate endpoint
│
├── reddit-scraper/             ═══ Container: reddit-scraper (port 8001) ═══
│   ├── Dockerfile
│   └── app/
│       ├── main.py             ← FastAPI: /search and /google endpoints
│       ├── scraper.py          ← All scraping logic:
│       │                          - Google/DDG/Bing/Reddit API search chain
│       │                          - scrape_single_post() via Reddit JSON API
│       │                          - parse_post() / parse_comment() (recursive)
│       └── models.py           ← Pydantic: Post, Comment, SavedResult
│
└── RLM/                        ═══ Container: rlm-service (port 8002) ═══
    ├── Dockerfile
    ├── api.py                  ← FastAPI: /query endpoint, wraps RLM
    ├── config.py               ← Loads .env, exposes ROOT_LLM / SUB_LLM config
    ├── .env                    ← LLM config (baked into image on build)
    └── rlm/
        ├── __init__.py         ← Exports: RLM (REPL mode), RLMTools (tools mode)
        ├── clients/
        │   ├── ollama.py       ← OllamaClient (/api/generate)
        │   │                      OllamaChatClient (/api/chat + tools) ← ACTIVE
        │   ├── vllm.py         ← VLLMClient (OpenAI-compatible /v1/chat)
        │   └── __init__.py     ← create_client() factory
        ├── tools/              ← ACTIVE MODE (RLM_MODE=tools)
        │   ├── orchestrator.py ← ToolsOrchestrator: main LLM loop
        │   ├── handlers.py     ← ContextTools: executes each tool call
        │   └── definitions.py  ← Tool JSON schemas sent to the LLM
        ├── repl/               ← INACTIVE (RLM_MODE=repl, used with vLLM)
        │   ├── orchestrator.py ← REPLOrchestrator: LLM writes Python code
        │   └── executor.py     ← Sandboxed Python REPL environment
        └── core/
            └── prompts.py      ← System prompts
```

---

## Docker Setup

```
docker-compose.yml
│
├── reddit-scraper  (port 8001→8000)
│     dns: 8.8.8.8, 8.8.4.4      ← required: Docker's internal DNS can't resolve reddit.com
│     volume: scraper-data:/data  ← writes scraped JSON here
│
├── rlm-service  (port 8002→8002)
│     ROOT_PROVIDER=ollama
│     ROOT_MODEL=llama3.1:8b      ← orchestrates tools, fast, native tool calling
│     SUB_MODEL=llama3.1:8b       ← used by ask_about_chunk tool
│     CALL_TIMEOUT=300            ← seconds per LLM call (high to support thinking models)
│     RLM_MODE=tools
│
└── mcp-service  (port 8003→8003)
      volume: scraper-data:/data  ← reads the same JSON that reddit-scraper wrote
      REDDIT_SCRAPER_URL=http://reddit-scraper:8000
      RLM_SERVICE_URL=http://rlm-service:8002
```

All containers communicate over the internal `mcp-net` bridge network.
The `scraper-data` volume is shared between `reddit-scraper` (writes) and `mcp-service` (reads).

---

## Configuration — Switching Models

Edit `BERTopic/.env` (docker-compose variable file), then restart `rlm-service`:

```bash
# BERTopic/.env

# llama3.1:8b — fast, native tool calling (recommended)
ROOT_MODEL=llama3.1:8b
SUB_MODEL=llama3.1:8b
CALL_TIMEOUT=60

# gpt-oss:20b — thinking model, does NOT call tools, answers from training data
# (would ignore Reddit context; only useful as SUB model for ask_about_chunk)
# ROOT_MODEL=gpt-oss:20b
# SUB_MODEL=gpt-oss:20b
# CALL_TIMEOUT=300
```

To apply:
```bash
cd BERTopic
docker-compose up -d --no-deps rlm-service   # no rebuild needed
```

---

## How to Run

```bash
# 1. Start all containers (first time or after config changes)
cd BERTopic
docker-compose up -d

# 2. Run the REPL (on your machine, not in Docker)
cd BERTopic/mcp-server
python main.py

# 3. Ask questions
>>> how to escape waterfowl dance?
>>> best build for strength faith?
>>> is rivers of blood overpowered?
```

---

## Ollama Server

Remote server at `https://ollama-ijcare-gpt.sheikhibrar.com`

Available models:
| Model | Size | Tool Calling | Notes |
|-------|------|-------------|-------|
| `llama3.1:8b` | 8B | ✅ Yes | Current ROOT — fast, reliable |
| `gpt-oss:20b` | 20B | ❌ No | Thinking model, slow (~2 min/call) |
| `llama3.3:70b` | 70B | ✅ Yes | Large, not currently used |
| `qwen3:1.7b` | 2B | ✅ Yes | Tiny, fast |
| `nomic-embed-text` | 137M | — | Embeddings only |

---

## Known Issues / Design Notes

- **Google search returns no Reddit URLs**: Google's HTML is JS-rendered so the parser
  finds nothing. DuckDuckGo or Reddit API fallback handles this automatically.
- **`gpt-oss:20b` as ROOT doesn't work**: It ignores tool calls and answers from
  training data, bypassing the scraped Reddit context entirely.
- **Integer tool args come as strings**: `llama3.1:8b` sometimes serializes integer
  tool arguments as strings (e.g. `"chunk_index": "0"`). Fixed with `int()` coercion
  in `handlers.py`.
- **Docker DNS**: The `reddit-scraper` container uses `dns: 8.8.8.8` because Docker's
  internal resolver (`127.0.0.11`) fails to resolve `reddit.com` and `duckduckgo.com`.

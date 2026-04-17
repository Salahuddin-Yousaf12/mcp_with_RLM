# Reddit Scraper + RLM — Architecture & Technical Reference

Ask a plain-English question → Reddit is searched and scraped → an LLM reads the
discussion and answers you. Two deployment modes: standalone (1 container) or
full stack (3 containers).

---

## Deployment Modes

### Mode A — Standalone RLM (recommended)

Single container. RLM's `AgentOrchestrator` uses registered functions to search and
scrape Reddit internally. No external services needed (except the Ollama server).

```
User
 │  POST /ask {"query": "..."}
 ▼
┌──────────────────────────────────────────────┐
│  RLM Container (port 8002)                   │
│                                              │
│  api.py → AgentOrchestrator                  │
│    │                                         │
│    ├─ LLM writes: search_reddit("query")     │
│    │   → functions/reddit.py executes        │
│    │   → Google/DDG/Bing/Reddit API search   │
│    │   → scrapes post + comments             │
│    │   → returns formatted text to REPL      │
│    │                                         │
│    ├─ LLM reads output, analyzes             │
│    │                                         │
│    └─ LLM writes: FINAL("answer")            │
│       → returned to user                     │
│                                              │
│  LLM calls ──► Ollama server (remote)        │
└──────────────────────────────────────────────┘
```

```bash
# Build & run
docker build -t rlm-standalone ./RLM
docker run -p 8002:8002 \
  -e ROOT_PROVIDER=ollama \
  -e ROOT_BASE_URL=https://ollama-ijcare-gpt.sheikhibrar.com \
  -e ROOT_MODEL=llama3.1:8b \
  --dns 8.8.8.8 \
  rlm-standalone

# Query
curl -X POST http://localhost:8002/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "how to dodge waterfowl dance"}'
```

### Mode B — Full 3-Container Stack

Scraper, RLM, and orchestrator as separate services. The orchestrator coordinates
the pipeline. Use this if you want modular services or the MCP integration with
Claude Desktop.

```
User (terminal)
     │
     │  python main.py  →  type question
     ▼
orchestrator/main.py (REPL client)
     │  POST /ask {"q": "..."}
     ▼
┌─ mcp-service (port 8003) ─── orchestrator/api.py ──┐
│                                                      │
│  Step 1: GET reddit-scraper:8000/google?q=...        │
│          → scraper searches + scrapes                │
│          → saves JSON to shared volume /data/        │
│                                                      │
│  Step 2: Read /data/reddit_google_<q>.json           │
│          → extract comments recursively              │
│          → sort by score descending                  │
│          → build context string                      │
│                                                      │
│  Step 3: POST rlm-service:8002/query                 │
│          → RLM explores context via tool calls       │
│          → returns final answer                      │
└──────────────────────────────────────────────────────┘

docker-compose up -d --build
```

---

## Repository Structure

```
mcp/
├── docker-compose.yml              ← 3-container orchestration
├── setup.py                        ← One-time MCP installer for Claude Desktop
├── claude_desktop_config.json      ← Claude Desktop MCP server config template
├── CLAUDE.md                       ← This file
│
├── orchestrator/                   ═══ Container: mcp-service (port 8003) ═══
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api.py                      ← FastAPI: POST /ask orchestrator
│   ├── main.py                     ← Interactive REPL (thin client)
│   └── mcp_server.py               ← MCP stdio server for Claude Desktop
│
├── services/
│   ├── scraper/                    ═══ Container: reddit-scraper (port 8001) ═══
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← FastAPI: /search and /google endpoints
│   │       ├── scraper.py          ← Search + scrape logic
│   │       └── models.py           ← Pydantic: Post, Comment, SavedResult
│   │
│   └── viewer/                     ← Static frontend (HTML/JS/CSS)
│       ├── index.html
│       ├── app.js
│       └── styles.css
│
├── RLM/                            ═══ Container: rlm-service (port 8002) ═══
│   ├── Dockerfile
│   ├── requirements.txt            ← requests, openai, python-dotenv, httpx
│   ├── api.py                      ← FastAPI: POST /ask + POST /query
│   ├── config.py                   ← Config loader from .env
│   ├── main.py                     ← CLI: --agent, --tools, --repl modes
│   ├── .env                        ← LLM provider/model configuration
│   ├── .env.example                ← Config template
│   ├── context.txt                 ← Example context for testing
│   ├── 2512.24601v1.pdf            ← Original MIT CSAIL paper
│   ├── examples/
│   │   ├── simple_query.py         ← Basic RLM usage example
│   │   └── document_search.py      ← Multi-document search example
│   └── rlm/                        ← Core Python package
│       ├── __init__.py             ← Exports: RLM, RLMTools, RLMAgent
│       ├── agent.py                ← AgentOrchestrator (standalone mode)
│       ├── clients/                ← LLM API abstraction layer
│       │   ├── __init__.py         ← create_client() factory
│       │   ├── base.py             ← BaseLLMClient ABC, LLMResponse, UsageStats
│       │   ├── ollama.py           ← OllamaClient + OllamaChatClient
│       │   └── vllm.py             ← VLLMClient (OpenAI SDK wrapper)
│       ├── core/                   ← Shared utilities
│       │   ├── __init__.py
│       │   └── prompts.py          ← System prompt templates
│       ├── functions/              ← Registered callable functions
│       │   ├── __init__.py         ← Auto-registers all functions on import
│       │   ├── registry.py         ← FunctionRegistry decorator system
│       │   └── reddit.py           ← search_reddit, scrape_reddit_url, list_reddit_posts
│       ├── repl/                   ← REPL mode implementation
│       │   ├── __init__.py
│       │   ├── executor.py         ← REPLExecutor: sandboxed Python runtime
│       │   └── orchestrator.py     ← REPLOrchestrator: REPL-based RLM loop
│       └── tools/                  ← Tools mode implementation
│           ├── __init__.py
│           ├── definitions.py      ← Tool JSON schemas (OpenAI/Ollama format)
│           ├── handlers.py         ← ContextTools: tool execution handlers
│           └── orchestrator.py     ← ToolsOrchestrator: tool-calling RLM loop
│
├── _legacy/                        ← Dead code from old architecture
│   ├── executor.py
│   ├── parser.py
│   ├── function_registry.py
│   └── ollama_client.py
│
└── awesome-claude-code-subagents/  ← External: 127+ Claude Code agent definitions
```

---

## RLM — Detailed Technical Reference

### Three Modes of Operation

| Mode | Class | Alias | How it works | Best for |
|------|-------|-------|-------------|----------|
| Agent | `AgentOrchestrator` | `RLMAgent` | LLM calls registered functions in REPL | Standalone queries, no context needed |
| REPL | `REPLOrchestrator` | `RLM` | LLM writes Python code to explore context | vLLM / OpenAI backends |
| Tools | `ToolsOrchestrator` | `RLMTools` | LLM uses native tool calling on context | Ollama with tool-calling models |

### API Endpoints (`RLM/api.py`)

| Endpoint | Request | Mode | Description |
|----------|---------|------|-------------|
| `POST /ask` | `{"query": "..."}` | Agent | Standalone — functions fetch data automatically |
| `POST /query` | `{"query": "...", "context": "..."}` | Tools/REPL | Context-based — you provide the text to analyze |
| `GET /health` | — | — | Returns `{"status": "ok"}` |

### Configuration (`RLM/config.py`)

Loads from `RLM/.env` via `python-dotenv`. Exposes typed dataclasses:

**`LLMConfig`** — provider, base_url, api_key, model for one LLM endpoint.

**`SafeguardsConfig`** — execution limits:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `MAX_ITERATIONS` | 30 | Max LLM interaction loops per query |
| `MAX_SUB_LLM_CALLS` | 20 | Total sub-LLM calls allowed per query |
| `MAX_RECURSION_DEPTH` | 1 | Sub-LLMs cannot spawn sub-sub-LLMs |
| `CALL_TIMEOUT` | 60s | Timeout per individual API call |
| `TOTAL_TIMEOUT` | 600s | Timeout for entire query |

**Two LLM slots:**
- `ROOT_LLM` — main orchestrating model (writes code / calls tools)
- `SUB_LLM` — used for recursive sub-calls via `llm_query()` / `ask_about_chunk()`. Falls back to ROOT config if `SUB_*` env vars are not set.

---

### Client Layer (`rlm/clients/`)

Unified interface for different LLM backends. All clients implement `BaseLLMClient` (ABC)
with two methods: `generate(prompt, system_prompt)` and `chat(messages, tools)`. Both
return `LLMResponse(content, tool_calls, usage)`.

**`OllamaChatClient`** (`ollama.py`)
POSTs to Ollama's `/api/chat` endpoint. Supports native tool calling via the `tools`
parameter. This is what Tools mode uses. Reads `message.content` and `message.tool_calls`
from the response.

**`OllamaClient`** (`ollama.py`)
POSTs to Ollama's `/api/generate` endpoint. Does NOT support tool calling. The `chat()`
method manually formats messages into a text prompt. Legacy — only useful for models
without tool support.

**`VLLMClient`** (`vllm.py`)
Wraps the official `openai` Python SDK with a custom `base_url`. Works with vLLM,
OpenAI API, or any OpenAI-compatible endpoint. Normalizes tool calls from SDK typed
objects into plain dicts.

**`create_client()` factory** (`__init__.py`)
- `"vllm"` or `"openai"` → `VLLMClient`
- `"ollama"` with `use_chat=True` → `OllamaChatClient`
- `"ollama"` without → `OllamaClient`

`ToolsOrchestrator` always passes `use_chat=True`; `AgentOrchestrator` and
`REPLOrchestrator` use `generate()` (no tool calling needed).

---

### Function Registry (`rlm/functions/`)

Decorator-based system for registering functions the LLM can call in agent mode.

**`registry.py` — `FunctionRegistry`**
- `@registry.register(description="...")` — decorator to register a function
- `registry.get_namespace()` → `{name: callable}` dict for REPL injection
- `registry.get_descriptions()` → formatted string for the system prompt
- `registry.list_names()` → list of registered function names

**`reddit.py` — registered functions:**

| Function | Signature | What it does |
|----------|-----------|-------------|
| `search_reddit` | `(query: str) -> str` | Full pipeline: Google/DDG/Bing/Reddit API search → scrape top post → extract comments sorted by score → return formatted text |
| `scrape_reddit_url` | `(url: str) -> str` | Scrape a specific Reddit post URL, return formatted comments |
| `list_reddit_posts` | `(query: str) -> str` | Quick search via Reddit API, return post titles + scores (no comments) |

**Search chain in `search_reddit()`:**
1. `_search_google()` — parse Google HTML for reddit.com links
2. `_search_duckduckgo()` — fallback, DuckDuckGo HTML search
3. `_search_bing()` — fallback, Bing HTML search
4. `_search_reddit_api()` — final fallback, Reddit's `/search.json` endpoint (most reliable)

**Adding new functions:** Create a new file in `rlm/functions/`, import it in
`__init__.py`, and use the `@registry.register()` decorator. The function
automatically appears in the agent's system prompt and REPL namespace.

```python
# rlm/functions/my_source.py
from .registry import registry

@registry.register(description="Fetch and summarize a web page")
def fetch_webpage(url: str) -> str:
    ...
```

---

### Agent Mode (`rlm/agent.py` — `AgentOrchestrator`)

Standalone mode. No pre-loaded context. The LLM uses registered functions to fetch
its own data.

**Flow:**

```
1. Create REPLExecutor with empty context
2. Inject all registered functions into REPL namespace:
   namespace = {search_reddit: fn, scrape_reddit_url: fn, list_reddit_posts: fn,
                llm_query: fn, re, json, math, ...}
3. Build system prompt listing all available functions
4. user_message = "QUERY: {query}\n\nCall functions, then FINAL(answer)"

Loop (max 15 iterations):
  → client.generate(prompt, system_prompt) → LLM response
  → Check for FINAL(answer) or FINAL_VAR(varname)
    → if found: return answer
  → Extract ```python``` code blocks
    → Execute each in REPL (120s timeout for HTTP calls)
    → Capture stdout output
    → Feed output back as next prompt
  → If no code blocks + short response: treat as direct answer
```

**LLM call chain:**
- Main loop: `self.client.generate()` → ROOT LLM
- Sub-LLM: `llm_query()` in REPL namespace → SUB LLM (depth-limited)
- Functions: `search_reddit()` etc. → HTTP calls to Reddit/Google (no LLM involved)

---

### REPL Mode (`rlm/repl/` — `REPLOrchestrator`)

Context-based mode where the LLM writes Python code to explore provided text.

**`executor.py` — `REPLExecutor`:**
Sandboxed Python runtime with a persistent namespace across executions.

Namespace contents:
- `context` — the full document (string/list/dict)
- `llm_query(prompt)` — sub-LLM function (tracked, depth-limited)
- `re`, `json`, `math`, `collections`, `itertools`, `functools` — pre-imported
- `__builtins__` — full Python builtins

Execution: `exec(code, self.namespace)` in a daemon thread with configurable timeout
(default 30s). stdout/stderr captured via `StringIO` redirect. Output truncated to
10,000 chars. Variables persist across calls — iteration N can access variables set
in iteration 1.

**`orchestrator.py` — `REPLOrchestrator`:**

```
1. Create REPLExecutor with context + llm_query_fn(depth=0)
2. System prompt: context type, total length, available tools
3. User message: query + context preview (first 2000 chars)

Loop (max 30 iterations):
  → client.generate(prompt, system_prompt)
  → Check FINAL_VAR(varname) → lookup in namespace
  → Check FINAL(answer) → return directly
  → Extract ```python``` / ```repl``` code blocks
  → Execute each block in REPL
  → Build continuation prompt with execution output
  → If no code blocks + short response → treat as direct answer
```

---

### Tools Mode (`rlm/tools/` — `ToolsOrchestrator`)

Context-based mode using native LLM tool calling (Ollama `/api/chat`).

**`definitions.py`:**
Returns 6 tool schemas in OpenAI/Ollama JSON format:

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `get_context_info` | none | Returns total length, chunk count, 500-char preview |
| `read_chunk` | `chunk_index: int` | Returns a pre-split chunk by index |
| `read_range` | `start: int, end: int` | Returns raw char slice (max 5000 chars) |
| `search` | `query: str, max_results: int` | Regex/literal search, returns excerpts with positions |
| `ask_about_chunk` | `chunk_index: int, question: str` | Sends chunk to sub-LLM with a question |
| `final_answer` | `answer: str` | Signals completion, returns the answer |

**`handlers.py` — `ContextTools`:**

Owns the full context string. On construction, splits into chunks with **20% overlap**
(capped at 200 chars) to prevent information loss at boundaries.

- `_handle_search()` — tries `re.compile(query)` first (supports regex). Falls back to
  `str.lower().find()` on regex error. Returns up to `max_results` excerpts with 50-char
  context on each side and character positions.
- `_handle_ask_about_chunk()` — the recursive part. Retrieves chunk, sends to sub-LLM
  via `llm_query_fn()`. Depth and call limits enforced in the closure.
- `handle_tool_call(name, args)` → `(result: str, is_final: bool)`. Only
  `final_answer` returns `is_final=True`.

**`orchestrator.py` — `ToolsOrchestrator`:**

```
1. Create ContextTools (chunks context)
2. Build system message with context stats
3. messages = [system, user(query)]

Loop (max iterations):
  → client.chat(messages, tools=tool_definitions)
  → If tool_calls in response:
      → Append assistant message with tool_calls
      → For each tool call:
          → Parse args (JSON-decode if string)
          → ctx_tools.handle_tool_call(name, args) → (result, is_final)
          → If final_answer: return result
          → Append {"role": "tool", "content": result}
  → If text response (no tools):
      → If >200 chars + prior tool calls: treat as implicit answer
      → Otherwise: prompt to call final_answer()
```

Conversation history grows each iteration — the LLM sees all prior tool calls
and results in its context window.

---

### Prompts (`rlm/core/prompts.py`)

| Function | Used by | Purpose |
|----------|---------|---------|
| `get_rlm_system_prompt(type, length, chunks)` | REPLOrchestrator | System prompt with context metadata + REPL instructions |
| `get_continuation_prompt(output, iteration)` | REPLOrchestrator | Wraps REPL output for the next iteration |
| `get_error_prompt(error)` | (available) | Error recovery prompt |

The `AgentOrchestrator` builds its own system prompt inline via `_build_system_prompt()`,
embedding `registry.get_descriptions()` to list all available functions.

The `ToolsOrchestrator` builds its system prompt inline with context stats and tool
usage instructions.

---

## Orchestrator Service (`orchestrator/`)

Thin FastAPI service that coordinates the scraper and RLM in the 3-container setup.

**`api.py`** — `POST /ask {"q": "..."}`:
1. `GET reddit-scraper:8000/google?q=...` → scraper searches + scrapes
2. Reads saved JSON from shared Docker volume `/data/`
3. `_extract_recursive()` flattens nested comments, `_build_context()` sorts by
   score and joins as `"POST TITLE: ...\nCOMMENT 1:\n..."` context string
4. `POST rlm-service:8002/query {"query": q, "context": context}` → RLM answers

**`main.py`** — interactive REPL. Reads stdin, POSTs to mcp-service at port 8003.

**`mcp_server.py`** — MCP stdio server for Claude Desktop / Cursor integration.
Exposes a single tool `google_search_reddit(q)` that delegates to the mcp-service
container. Registered via `setup.py` which patches `claude_desktop_config.json`.

---

## Scraper Service (`services/scraper/`)

Standalone FastAPI service for Reddit search and scraping.

**`app/scraper.py`:**

| Function | Purpose |
|----------|---------|
| `search_google_for_reddit(query)` | Parse Google HTML for reddit.com URLs (4 regex patterns) |
| `search_duckduckgo_for_reddit(query)` | Fallback: DuckDuckGo HTML search |
| `search_bing_for_reddit(query)` | Fallback: Bing HTML search |
| `search_reddit_api(query)` | Final fallback: Reddit `/search.json` (most reliable) |
| `scrape_via_google(query)` | Full chain: tries all 4 search methods, scrapes top result |
| `scrape_single_post(url)` | Fetches `<url>.json`, parses post + comments |
| `scrape_search(query)` | Scrapes all posts from Reddit search (paginated) |
| `parse_post(data)` | Parses Reddit JSON into Post object |
| `parse_comment(data, depth)` | Recursively parses comments (up to 20 levels deep) |
| `get_json(url)` | HTTP GET with 10 retries, rate limit handling, IPv4-forced |
| `get_html(url)` | HTTP GET for HTML with 5 retries |

IPv4 is forced via monkey-patching `socket.getaddrinfo` because Docker containers
typically lack IPv6 routing.

**`app/main.py`:**

| Endpoint | Response | Description |
|----------|----------|-------------|
| `GET /google?q=...` | `SavedResult` | Google→DDG→Bing→Reddit search chain, scrape top post, save to `/data/` |
| `GET /search?q=...` | `SavedResult` | Direct Reddit search, scrape all results, save to `/data/` |
| `GET /health` | `{"status": "ok"}` | Health check |

**`app/models.py`:**
- `Comment` — id, author, body, score, created_utc, parent_id, is_submitter, replies (recursive)
- `Post` — id, title, url, permalink, score, num_comments, subreddit, author, selftext, comments
- `SavedResult` — query, count, saved_to (file path inside container)

---

## Docker Configuration

### docker-compose.yml (3-container mode)

```
services:
  reddit-scraper    (port 8001→8000)
    build: ./services/scraper
    dns: 8.8.8.8          ← Docker internal DNS can't resolve reddit.com
    volume: scraper-data:/data

  rlm-service       (port 8002→8002)
    build: ./RLM
    dns: 8.8.8.8          ← needed for agent mode HTTP calls
    env: ROOT_PROVIDER=ollama, ROOT_MODEL=llama3.1:8b

  mcp-service       (port 8003→8003)
    build: ./orchestrator
    volume: scraper-data:/data    ← reads JSON written by scraper
    depends_on: reddit-scraper, rlm-service

network: mcp-net (bridge)
volume: scraper-data (shared between scraper and orchestrator)
```

### Build & Run

```bash
# Full stack
cd mcp
docker-compose build
docker-compose up -d

# Rebuild single service
docker-compose build rlm-service
docker-compose up -d --no-deps rlm-service

# Standalone RLM
docker build -t rlm-standalone ./RLM
docker run -p 8002:8002 \
  -e ROOT_PROVIDER=ollama \
  -e ROOT_BASE_URL=https://ollama-ijcare-gpt.sheikhibrar.com \
  -e ROOT_MODEL=llama3.1:8b \
  --dns 8.8.8.8 \
  rlm-standalone
```

### CLI Usage

```bash
# Agent mode (standalone, no context needed)
cd RLM
python main.py "how to dodge waterfowl dance" --agent -v

# Tools mode (with context file)
python main.py "find the magic number" -f document.txt --tools

# REPL mode (with context file)
python main.py "summarize this" -f notes.txt --repl -v --stats
```

---

## Ollama Server

Remote server at `https://ollama-ijcare-gpt.sheikhibrar.com`

| Model | Size | Tool Calling | Notes |
|-------|------|-------------|-------|
| `llama3.1:8b` | 8B | Yes | Current ROOT — fast, reliable tool calling |
| `gpt-oss:20b` | 20B | No | Thinking model, ignores tool calls |
| `llama3.3:70b` | 70B | Yes | Large, not currently used |
| `qwen3:1.7b` | 2B | Yes | Tiny, fast |
| `nomic-embed-text` | 137M | — | Embeddings only |

---

## Known Issues

- **Google search often fails**: Google's HTML is JS-rendered, regex parsers find nothing.
  DuckDuckGo or Reddit API fallback handles this automatically.
- **`gpt-oss:20b` as ROOT doesn't work for tools/agent mode**: It ignores tool calls and
  answers from training data, bypassing the scraped context entirely. Only usable as
  SUB model for `ask_about_chunk` / `llm_query()`.
- **Integer tool args come as strings**: `llama3.1:8b` sometimes serializes integer tool
  arguments as strings (e.g. `"chunk_index": "0"`). Fixed with `int()` coercion in
  `handlers.py`.
- **Docker DNS**: Both `reddit-scraper` and `rlm-service` use `dns: 8.8.8.8` because
  Docker's internal resolver (`127.0.0.11`) fails to resolve `reddit.com`,
  `duckduckgo.com`, and `google.com`.

# Project: Reddit Scraper MCP Server

A natural-language-to-Reddit-scraper adapter. The user types a plain English query,
an Ollama LLM figures out which API function to call, and the system:
1. Searches Google/Reddit for the topic
2. Scrapes the Reddit post + comments
3. Extracts title + comments to `temp.json`

## Project Structure

```
BERTopic/
├── mcp-server/           # MCP Server (API Dispatcher)
│   ├── main.py           # REPL loop — ties everything together
│   ├── function_registry.py  # Reddit scraper API endpoints
│   ├── ollama_client.py  # HTTP client for the Ollama model endpoint
│   ├── parser.py         # Parses raw LLM output into a structured ParsedCall
│   ├── executor.py       # Calls Reddit API + extracts comments
│   └── requirements.txt  # Python dependencies
├── reddit-scraper/       # Reddit Scraper FastAPI Service
│   ├── app/main.py       # FastAPI endpoints (/search, /google)
│   ├── app/scraper.py    # Reddit scraping logic
│   └── app/models.py     # Pydantic models
├── reddit-viewer/        # Frontend for viewing scraped posts
├── extract_comments.py   # Extracts title + comments from JSON
├── temp.json             # Output file with extracted comments
└── CLAUDE.md             # This file
```

## Flow

```
User query (natural language)
        │
        ▼
ollama_client.py   →  sends query + function registry to Ollama LLM
        │              gets back: google_search_reddit("elden ring weapons")
        ▼
parser.py          →  extracts function name + args
        │              produces a ParsedCall object
        ▼
executor.py        →  calls Reddit scraper API
        │              waits for scrape to complete
        │              runs extract_comments.py
        ▼
temp.json          →  { "title": "...", "comments": [...] }
```

## Running the System

### 1. Start the Reddit Scraper API
```bash
cd reddit-scraper
docker-compose up
# OR for local dev:
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Start the MCP Server
```bash
cd mcp-server
pip install -r requirements.txt
python main.py
```

### 3. Use it!
```
============================================================
Reddit Scraper MCP Server
============================================================
Ask me to search Reddit for any topic!
Examples:
  - 'search reddit for elden ring weapons'
  - 'find reddit posts about python tutorials'
  - 'google search reddit for best coffee makers'

Type 'exit' to quit
============================================================

>>> search reddit for vyke's war spear
  [ollama] sending query...
  [ollama] raw response: 'google_search_reddit("vyke's war spear")'
  [parser] → google_search_reddit(args=["vyke's war spear"], kwargs={})
  [executor] calling API...
  [result] ✅ Success!
           Posts found: 1
           Saved to: /data/reddit_google_vyke_s_war_spear.json
           Comments extracted to: temp.json
```

## Available Functions

| Function | Description |
|----------|-------------|
| `search_reddit(q)` | Search Reddit directly for posts |
| `google_search_reddit(q)` | Search Google for Reddit posts, scrape top result |

## Configuration

| Variable | File | Default |
|----------|------|---------|
| `OLLAMA_BASE_URL` | `ollama_client.py` | `https://ollama-ijcare-gpt.sheikhibrar.com` |
| `OLLAMA_MODEL` | `ollama_client.py` | `llama3.2` |
| `REDDIT_SCRAPER_URL` | `function_registry.py` | `http://localhost:8000` |

## Agent Usage

For AI-based tasks (LLM integration, model serving, inference pipelines) use the `ai-engineer` agent.
For Data Science tasks (analysis, modeling, statistical work, ML pipelines) use the `data-scientist` agent.

## Output Format (temp.json)

```json
{
  "title": "Post title here",
  "comments": [
    "First comment body...",
    "Second comment body...",
    "..."
  ]
}
```

# RLM - Recursive Language Models

Implementation of the Recursive Language Models approach from MIT CSAIL paper (arXiv:2512.24601).

## Project Structure

```
RLM/
├── .env                    # Configuration (copy from .env.example)
├── .env.example            # Configuration template
├── config.py               # Configuration loader
├── main.py                 # CLI interface
├── context.txt             # Example context file
├── requirements.txt        # Dependencies
└── rlm/                    # Core package
    ├── __init__.py         # Package exports
    ├── clients/            # LLM API layer
    │   ├── __init__.py     # Factory function + exports
    │   ├── base.py         # Abstract BaseLLMClient
    │   ├── vllm.py         # vLLM/OpenAI-compatible client
    │   └── ollama.py       # Ollama API clients
    ├── repl/               # REPL-based implementation
    │   ├── __init__.py
    │   ├── executor.py     # Python REPL environment
    │   └── orchestrator.py # REPL-based RLM loop
    ├── tools/              # Tool-based implementation
    │   ├── __init__.py
    │   ├── definitions.py  # Tool JSON schemas
    │   ├── handlers.py     # Tool execution handlers
    │   └── orchestrator.py # Tool-based RLM loop
    └── core/               # Shared utilities
        ├── __init__.py
        └── prompts.py      # System prompts
```

## Configuration

All configuration is done via `.env` file. Copy `.env.example` to `.env` and edit:

```bash
# ROOT LLM (main LLM that writes code/uses tools)
ROOT_PROVIDER=vllm              # vllm, ollama, or openai
ROOT_BASE_URL=http://localhost:8000/v1
ROOT_API_KEY=abc
ROOT_MODEL=openai/gpt-oss-20b

# SUB LLM (helper LLMs for chunk analysis)
# Leave empty to use same as ROOT
SUB_PROVIDER=
SUB_BASE_URL=
SUB_API_KEY=
SUB_MODEL=

# Mode: 'repl' (recommended) or 'tools' (for Ollama)
DEFAULT_MODE=repl

# Safeguards
MAX_ITERATIONS=30               # Max ROOT LLM loops
MAX_SUB_LLM_CALLS=20           # Max sub-LLM calls per query
MAX_RECURSION_DEPTH=1          # Sub-LLMs can't spawn sub-sub-LLMs
CALL_TIMEOUT=60                # Seconds per API call
TOTAL_TIMEOUT=600              # Total seconds for entire query

# Chunking
DEFAULT_CHUNK_SIZE=4000        # Characters per chunk
```

---

## Understanding the Recursive Logic (Visual Guide)

### The Problem: LLMs Have Limited Context Windows

```
┌─────────────────────────────────────────────────────────────┐
│                YOUR DOCUMENT (e.g., 2MB file)               │
│                                                             │
│  ████████████████████████████████████████████████████████   │
│  ████████████████████████████████████████████████████████   │
│  ████████████████████████████████████████████████████████   │
│  ████████████████████████████████████████████████████████   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM CONTEXT WINDOW (limited!)                  │
│  ┌────────────────────┐                                     │
│  │  Can only fit      │   ← What if document is 10x bigger? │
│  │  THIS much         │      Or 100x? LLM chokes.           │
│  └────────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

### Traditional Approach: Stuff It All In (FAILS)

```
    YOU: "Hey LLM, here's a 2MB document, find the magic number"

         ┌──────────────────────────────────┐
         │  2MB OF TEXT                     │
         │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
         │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │──────► LLM
         │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
         └──────────────────────────────────┘
                                                     │
                                                     ▼
                                              ❌ FAILS!
                                              - Doesn't fit
                                              - "Context rot"
                                              - Forgets stuff
```

### RLM Approach: LLM as EXPLORER, Not READER

**Key insight:** Don't send the document. Send TOOLS to explore it.

```
┌─────────────────────────────────────────────────────────────────┐
│                      YOUR MACHINE (local)                        │
│                                                                  │
│   ┌────────────────────────────────────────────────────────┐    │
│   │  context = "A decoder-only transformer begins..."       │    │
│   │           (FULL 2MB document stored as a variable)      │    │
│   │           ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   │    │
│   │           ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   │    │
│   └────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              │  LLM can only see SMALL pieces    │
│                              ▼  at a time via code               │
│   ┌────────────────────────────────────────────────────────┐    │
│   │  PYTHON REPL                                            │    │
│   │                                                         │    │
│   │  >>> print(len(context))                                │    │
│   │  76543                                                  │    │
│   │                                                         │    │
│   │  >>> print(context[0:500])     ◄── LLM "peeks" at start │    │
│   │  "A decoder-only transformer..."                        │    │
│   │                                                         │    │
│   │  >>> print(context.find("attention"))  ◄── LLM searches │    │
│   │  1842                                                   │    │
│   └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Only SMALL outputs go to LLM
                              ▼
                    ┌───────────────────┐
                    │       LLM         │
                    │  "Ah! Attention   │
                    │   is at position  │
                    │   1842. Let me    │
                    │   read around it" │
                    └───────────────────┘
```

### THE RECURSIVE PART: Sub-LLMs

The main LLM can **spawn helper LLMs** to analyze chunks:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ROOT LLM (the boss)                           │
│                                                                         │
│   "This document is 76,000 chars. Too big to understand at once.        │
│    I'll split it into chunks and ask SUB-LLMs to analyze each."         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Writes code:
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  for i in range(0, len(context), 10000):                                │
│      chunk = context[i:i+10000]                                         │
│      answer = llm_query(f"What's this chunk about? {chunk}")  ◄─────────│
│      results.append(answer)                                    │        │
└────────────────────────────────────────────────────────────────│────────┘
                                                                 │
                    ┌────────────────────────────────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                     SUB-LLM CALLS (depth=1)                   │
    │                                                               │
    │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
    │   │  Sub-LLM 1  │  │  Sub-LLM 2  │  │  Sub-LLM 3  │   ...    │
    │   │             │  │             │  │             │          │
    │   │ "Chunk 1 is │  │ "Chunk 2 is │  │ "Chunk 3 is │          │
    │   │  about      │  │  about      │  │  about      │          │
    │   │  tokeniza-  │  │  attention  │  │  training"  │          │
    │   │  tion"      │  │  mechanism" │  │             │          │
    │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
    │          │                │                │                 │
    └──────────│────────────────│────────────────│─────────────────┘
               │                │                │
               └────────────────┼────────────────┘
                                │
                                ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                    ROOT LLM AGGREGATES                        │
    │                                                               │
    │   "Based on my sub-LLMs:                                      │
    │    - Chunk 1: tokenization                                    │
    │    - Chunk 2: attention                                       │
    │    - Chunk 3: training                                        │
    │                                                               │
    │    The document explains how transformers work!"              │
    │                                                               │
    │    FINAL("This is a technical explanation of transformers")   │
    └───────────────────────────────────────────────────────────────┘
```

### Why "Recursive"?

```
                    ┌─────────────────┐
                    │    ROOT LLM     │  ◄── Main "brain"
                    │   (depth = 0)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Sub-LLM  │   │ Sub-LLM  │   │ Sub-LLM  │  ◄── "Helper" brains
        │(depth=1) │   │(depth=1) │   │(depth=1) │
        └──────────┘   └──────────┘   └──────────┘

The LLM calls ITSELF (or a smaller version) on sub-problems.
That's the "recursive" part - like a function calling itself!
```

---

## Two Modes

### REPL Mode (Default, Recommended)
The LLM writes Python code to explore context. Works with any model (vLLM, OpenAI, etc.).

```python
# LLM literally writes this:
chunk = context[5000:6000]
answer = llm_query(f"What topic? {chunk}")
print(answer)
```

### Tools Mode (--tools flag)
Uses native tool calling. Best for Ollama which has tool support.

```
LLM calls: search("attention")     → Returns matches
LLM calls: read_chunk(3)           → Returns chunk #3
LLM calls: final_answer("...")     → Done!
```

**Available tools:**
- `get_context_info`: Get overview and preview
- `read_chunk(index)`: Read a specific chunk
- `search(query)`: Find text in context
- `final_answer(answer)`: Provide the final answer

---

## Usage

### CLI
```bash
# REPL mode (default, recommended for vLLM):
python main.py "Find the magic number" -f document.txt

# Tools mode (for Ollama with tool calling):
python main.py "Find the magic number" -f document.txt --tools

# With verbose output and stats:
python main.py "Summarize the key points" -f notes.txt -v --stats

# With custom options:
python main.py "Your query" -f doc.txt --max-iterations 50 --chunk-size 3000
```

### Python
```python
# REPL mode (recommended for vLLM)
from rlm import RLM

rlm = RLM(verbose=True)
answer = rlm.query("Find the answer", context_string)

# Tools mode (for Ollama)
from rlm import RLMTools

rlm = RLMTools(verbose=True)
answer = rlm.query("Find the answer", context_string)

# With custom client
from rlm import VLLMClient, REPLOrchestrator

client = VLLMClient(
    base_url="http://localhost:8000/v1",
    api_key="abc",
    model="openai/gpt-oss-20b"
)
rlm = REPLOrchestrator(client=client, verbose=True)
answer = rlm.query("Your question", context)
```

---

## Architecture

### Client Layer (`rlm/clients/`)
Unified interface for different LLM providers:

| Provider | Client Class | Use Case |
|----------|-------------|----------|
| vLLM | `VLLMClient` | OpenAI-compatible APIs |
| OpenAI | `VLLMClient` | OpenAI API |
| Ollama | `OllamaClient` | Ollama generate endpoint |
| Ollama | `OllamaChatClient` | Ollama chat with tools |

### REPL Layer (`rlm/repl/`)
- `REPLExecutor`: Sandboxed Python execution
- `REPLOrchestrator`: Main loop for code-based exploration

### Tools Layer (`rlm/tools/`)
- `definitions.py`: Tool JSON schemas
- `handlers.py`: Tool execution (ContextTools class)
- `orchestrator.py`: Main loop for tool-based exploration

---

## Safeguards

Built-in protections against runaway execution:

| Safeguard | Default | Purpose |
|-----------|---------|---------|
| `MAX_ITERATIONS` | 30 | Limits ROOT LLM interaction loops |
| `MAX_SUB_LLM_CALLS` | 20 | Limits total sub-LLM calls |
| `MAX_RECURSION_DEPTH` | 1 | Prevents sub-sub-LLM calls |
| `CALL_TIMEOUT` | 60s | Timeout per API call |
| `TOTAL_TIMEOUT` | 600s | Timeout for entire query |

---

## Code Flow

```
orchestrator.py                 clients/              LLM Server
     │                              │                     │
     │  Create REPL/Tools          │                     │
     │                              │                     │
     ├──► client.generate() ───────►├──► API call ───────►│
     │                              │                     │
     │◄── LLMResponse ◄────────────┤◄── response ◄───────┤
     │                              │                     │
     │  Parse code/tool calls       │                     │
     │  Execute locally             │                     │
     │                              │                     │
     ├──► client.generate() ───────►├──► API call ───────►│
     │    (with results)            │                     │
     │                              │                     │
    ... repeats until FINAL() ...
```

---

## Paper Reference

Based on: "Recursive Language Models" (arXiv:2512.24601, Dec 2025)
- Authors: Alex L. Zhang, Tim Kraska, Omar Khattab (MIT CSAIL)
- Key result: RLMs handle inputs up to 10M+ tokens (100x beyond context windows)
- Performance: 91.3% on BrowseComp+ vs 0% for base GPT-5 (can't fit in context)

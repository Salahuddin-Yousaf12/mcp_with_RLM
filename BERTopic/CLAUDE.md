# Project: API Dispatcher

A natural-language-to-API-call adapter. The user types a plain English query,
an Ollama LLM figures out which API function to call and with what arguments,
and the system fires the corresponding HTTP request.

## Flow

```
User query (natural language)
        │
        ▼
ollama_client.py   →  sends query + function registry to Ollama LLM
        │              gets back raw text like: insert_student_marks("ahmed", 20)
        ▼
parser.py          →  extracts function name + args from the raw LLM response
        │              produces a ParsedCall object
        ▼
executor.py        →  looks up the FunctionSpec in the registry
        │              builds the HTTP request (path/query/body/header params)
        │              fires it with httpx
        ▼
result printed in REPL (main.py)
```

## File Map

| File                    | Responsibility                                              |
|-------------------------|-------------------------------------------------------------|
| `main.py`               | REPL loop — ties everything together                        |
| `function_registry.py`  | All API endpoints defined as FunctionSpec entries           |
| `ollama_client.py`      | HTTP client for the Ollama model endpoint                   |
| `parser.py`             | Parses raw LLM output into a structured ParsedCall          |
| `executor.py`           | Binds args and fires the actual HTTP API call               |

## Adding a New API Endpoint

Only `function_registry.py` needs to change. Add a `FunctionSpec` to `REGISTRY`:

```python
FunctionSpec(
    name="your_function_name",        # what the LLM will call
    description="What it does.",      # shown to the LLM in the prompt
    method="POST",
    url="https://your-api.com/resource/{path_param}",
    params=[
        ParamSpec("path_param", "str", "description", location="path"),
        ParamSpec("body_field", "int", "description", location="body"),
    ],
)
```

### Param locations

| Location | Where it goes in the request         |
|----------|--------------------------------------|
| `path`   | Substituted into the URL `{param}`   |
| `query`  | Appended as `?key=value`             |
| `body`   | Sent as JSON body `{"key": value}`   |
| `header` | Sent as an HTTP header               |

## Configuration

| Variable        | File               | Default                                        |
|-----------------|--------------------|------------------------------------------------|
| `OLLAMA_BASE_URL` | `ollama_client.py` | `https://ollama-ijcare-gpt.sheikhibrar.com`  |
| `OLLAMA_MODEL`    | `ollama_client.py` | `llama3.2`                                   |

## Dependencies

```
httpx>=0.27.0
```

Install: `pip install -r requirements.txt`

## Running

```bash
python main.py
```

## Key Design Decisions

- **LLM is only a dispatcher** — it only decides *which function* to call and *what args* to pass. All actual logic lives in the registry + executor.
- **ast.literal_eval for parsing** — safe, no `eval()`. Only parses Python literals (strings, ints, floats, bools, lists, dicts).
- **Registry is the single source of truth** — the LLM prompt is auto-generated from it, so the LLM always knows exactly what's available.
- **Platform-independent** — HTTP calls via httpx work identically on Windows and Linux.

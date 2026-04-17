"""
Ollama Client
-------------
Sends a prompt to the deployed Ollama endpoint and returns the raw text response.
"""

import httpx
from function_registry import describe_registry

OLLAMA_BASE_URL = "https://ollama-ijcare-gpt.sheikhibrar.com"
OLLAMA_MODEL    = "gpt-oss:20b"   # Model deployed on your server

SYSTEM_PROMPT = """\
You are a function dispatcher. Given a user query, you must respond with ONLY \
a single function call that best matches the intent of the query.

Available functions:
{functions}

Rules:
- Respond with ONLY the function call — no explanation, no markdown, no extra text.
- Use this exact format: function_name(arg1, arg2, ...)
- String arguments must be quoted with double quotes.
- If no function matches, respond with: NO_MATCH
"""


def build_prompt(user_query: str) -> str:
    functions_block = describe_registry()
    system = SYSTEM_PROMPT.format(functions=functions_block)
    return f"{system}\n\nUser query: {user_query}\nFunction call:"


def call_ollama(user_query: str) -> str:
    """Send user_query to Ollama, return the raw model response string."""
    prompt = build_prompt(user_query)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1,
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return data.get("response", "").strip()

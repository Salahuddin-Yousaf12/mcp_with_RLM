"""
Main — REPL
-----------
Ties everything together.

Loop:
  1. Read user query
  2. Call Ollama  →  raw LLM response
  3. Parse        →  ParsedCall
  4. Execute      →  result
  5. Print result
"""

from ollama_client import call_ollama
from parser import parse_llm_response
from executor import execute, UnknownFunctionError


def repl():
    print("Function Dispatcher REPL  (type 'exit' to quit)\n")

    while True:
        try:
            query = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            print("Bye.")
            break

        # ── Step 1: Ask the LLM which function to call ──────────────────────
        print("  [ollama] sending query...")
        try:
            raw_response = call_ollama(query)
        except Exception as e:
            print(f"  [error] Ollama call failed: {e}\n")
            continue

        print(f"  [ollama] raw response: {raw_response!r}")

        # ── Step 2: Parse the LLM output into a structured call ──────────────
        parsed = parse_llm_response(raw_response)

        if parsed is None:
            print("  [parser] could not extract a function call (NO_MATCH or unparseable)\n")
            continue

        print(f"  [parser] → {parsed.func_name}(args={parsed.args}, kwargs={parsed.kwargs})")

        # ── Step 3: Execute ──────────────────────────────────────────────────
        try:
            result = execute(parsed)
            print(f"  [result] {result}\n")
        except UnknownFunctionError as e:
            print(f"  [error] {e}\n")
        except Exception as e:
            print(f"  [error] execution failed: {e}\n")


if __name__ == "__main__":
    repl()

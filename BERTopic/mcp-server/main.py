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
    print("=" * 60)
    print("Reddit Scraper MCP Server")
    print("=" * 60)
    print("Ask me to search Reddit for any topic!")
    print("Examples:")
    print("  - 'search reddit for elden ring weapons'")
    print("  - 'find reddit posts about python tutorials'")
    print("  - 'google search reddit for best coffee makers'")
    print("")
    print("Type 'exit' to quit")
    print("=" * 60)
    print("")

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
            print("  [executor] calling API...")
            result = execute(parsed)
            
            # Pretty print the result
            status = result.get("status_code", "unknown")
            body = result.get("body", {})
            
            if status == 200:
                print(f"  [result] ✅ Success!")
                
                # Show Reddit-specific info
                if "count" in body:
                    print(f"           Posts found: {body['count']}")
                if "saved_to" in body:
                    print(f"           Saved to: {body['saved_to']}")
                if "extracted_to" in result:
                    print(f"           Comments extracted to: {result['extracted_to']}")
            else:
                print(f"  [result] ❌ Status: {status}")
                print(f"           {body}")
            print("")
            
        except UnknownFunctionError as e:
            print(f"  [error] {e}\n")
        except Exception as e:
            print(f"  [error] execution failed: {e}\n")


if __name__ == "__main__":
    repl()

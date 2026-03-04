"""
Main — REPL (thin client)

Delegates all work to the mcp-service container.
Set MCP_SERVICE_URL env var if the container runs on a non-default port.
"""

import os
import httpx

MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://localhost:8003")
TIMEOUT = 300.0


def repl():
    print("=" * 60)
    print("Reddit Scraper")
    print("=" * 60)
    print("Ask me anything — I'll search Reddit and answer you.")
    print("Type 'exit' to quit")
    print("=" * 60)
    print()

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

        print("  [searching Reddit + asking model...]")
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                r = client.post(f"{MCP_SERVICE_URL}/ask", json={"q": query})

            if r.status_code == 200:
                print(f"\n{r.json()['answer']}\n")
            else:
                print(f"  [error] HTTP {r.status_code}: {r.text}\n")
        except Exception as e:
            print(f"  [error] {e}\n")


if __name__ == "__main__":
    repl()

"""
MCP Server — Reddit Scraper (stdio transport for Claude Desktop / Cursor)

Thin client: delegates all work to the mcp-service container.
Set MCP_SERVICE_URL env var if the container runs on a non-default port.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from mcp.server.fastmcp import FastMCP

MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://localhost:8003")
TIMEOUT = 300.0

mcp = FastMCP("reddit-scraper")


@mcp.tool()
def google_search_reddit(q: str) -> str:
    """
    Search Google for a Reddit post about a topic, scrape the top result,
    and return a direct answer to the query based on the Reddit discussion.
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{MCP_SERVICE_URL}/ask", json={"q": q})

    if r.status_code == 200:
        return r.json()["answer"]
    return f"Service error (HTTP {r.status_code}): {r.text}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

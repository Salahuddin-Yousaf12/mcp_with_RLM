"""
Function Registry
-----------------
Maps function names to API endpoints.

Each FunctionSpec describes:
  - the function name the LLM will call
  - which HTTP endpoint it maps to
  - what parameters it takes and where they go in the request

Param locations:
  "path"   →  substituted into the URL  e.g. /students/{student_name}
  "query"  →  appended as ?key=value
  "body"   →  sent as JSON body
  "header" →  sent as a request header
"""

from dataclasses import dataclass, field
from typing import Literal


ParamLocation = Literal["path", "query", "body", "header"]


@dataclass
class ParamSpec:
    name: str
    type: str                    # "int", "str", "float", "bool"
    description: str
    location: ParamLocation      # where it goes in the HTTP request
    required: bool = True
    default: object = None


@dataclass
class FunctionSpec:
    name: str
    description: str
    method: str                  # "GET", "POST", "PUT", "DELETE", etc.
    url: str                     # full URL, path params as {param_name}
    params: list[ParamSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Reddit Scraper API URL (change this to your deployed URL)
REDDIT_SCRAPER_URL = "http://localhost:8001"


# ---------------------------------------------------------------------------
# Registry  — add your API-backed functions here
# ---------------------------------------------------------------------------

REGISTRY: list[FunctionSpec] = [

    FunctionSpec(
        name="search_reddit",
        description="Search Reddit directly for posts about a topic. Returns posts and comments from Reddit's search API.",
        method="GET",
        url=f"{REDDIT_SCRAPER_URL}/search",
        params=[
            ParamSpec("q", "str", "Search query (e.g., 'elden ring weapons', 'python tutorials')", location="query"),
        ],
    ),

    FunctionSpec(
        name="google_search_reddit",
        description="Search Google for a Reddit post about a topic, then scrape the top result. Best for finding the most relevant Reddit discussion.",
        method="GET",
        url=f"{REDDIT_SCRAPER_URL}/google",
        params=[
            ParamSpec("q", "str", "Search query (e.g., 'best python tutorials', 'elden ring boss tips')", location="query"),
        ],
    ),

    # ← add more endpoints here

]


# Lookup by name
REGISTRY_MAP: dict[str, FunctionSpec] = {fn.name: fn for fn in REGISTRY}


def describe_registry() -> str:
    """Plain-text summary injected into the LLM prompt."""
    lines = []
    for fn in REGISTRY:
        param_strs = ", ".join(
            f"{p.name}: {p.type}" + ("" if p.required else f" = {p.default!r}")
            for p in fn.params
        )
        lines.append(f"- {fn.name}({param_strs})")
        lines.append(f"    {fn.description}")
    return "\n".join(lines)

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
# Registry  — add your API-backed functions here
# ---------------------------------------------------------------------------

REGISTRY: list[FunctionSpec] = [

    FunctionSpec(
        name="insert_student_marks",
        description="Insert exam marks for a student.",
        method="POST",
        url="https://your-api.com/students/{student_name}/marks",
        params=[
            ParamSpec("student_name", "str", "Name of the student",  location="path"),
            ParamSpec("marks",        "int", "Mark value to insert", location="body"),
        ],
    ),

    FunctionSpec(
        name="get_student_marks",
        description="Get exam marks for a student.",
        method="GET",
        url="https://your-api.com/students/{student_name}/marks",
        params=[
            ParamSpec("student_name", "str", "Name of the student", location="path"),
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

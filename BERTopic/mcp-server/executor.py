"""
Executor
--------
Takes a ParsedCall, finds its FunctionSpec, builds the HTTP request, fires it.
For Reddit scraper calls, automatically extracts comments to temp.json.
"""

import json
import subprocess
import sys
from pathlib import Path

import httpx
from parser import ParsedCall
from function_registry import REGISTRY_MAP, FunctionSpec, ParamSpec


class UnknownFunctionError(Exception):
    pass


class MissingArgumentError(Exception):
    pass


# Path to extract_comments.py (relative to this file's parent)
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
EXTRACT_SCRIPT = PROJECT_DIR / "extract_comments.py"
TEMP_JSON = PROJECT_DIR / "temp.json"


def execute(parsed_call: ParsedCall) -> dict:
    spec = REGISTRY_MAP.get(parsed_call.func_name)
    if spec is None:
        raise UnknownFunctionError(
            f"'{parsed_call.func_name}' is not registered. "
            f"Known: {list(REGISTRY_MAP.keys())}"
        )

    bound = _bind_arguments(spec, parsed_call.args, parsed_call.kwargs)
    result = _fire(spec, bound)
    
    # If this was a Reddit scraper call, extract comments to temp.json
    if spec.name in ("search_reddit", "google_search_reddit"):
        result = process_reddit_result(result)
    
    return result


def process_reddit_result(result: dict) -> dict:
    """After Reddit scrape, extract title + comments to temp.json."""
    body = result.get("body", {})
    
    # Check if scrape was successful
    if result.get("status_code") != 200:
        return result
    
    saved_path = body.get("saved_to")
    if not saved_path:
        return result
    
    # The saved_path is the Docker container path (/data/...)
    # But the file is actually in the local BERTopic/ folder
    # Try to find the file locally
    filename = Path(saved_path).name
    local_path = PROJECT_DIR / filename
    
    # If not found locally, try the original path
    if not local_path.exists():
        local_path = Path(saved_path)
    
    if not local_path.exists():
        result["extraction_status"] = f"failed: file not found at {local_path}"
        return result
    
    # Run extract_comments.py
    try:
        subprocess.run(
            [sys.executable, str(EXTRACT_SCRIPT), str(local_path), str(TEMP_JSON)],
            check=True,
            capture_output=True,
            text=True
        )
        result["extracted_to"] = str(TEMP_JSON)
        result["extraction_status"] = "success"
    except subprocess.CalledProcessError as e:
        result["extraction_status"] = f"failed: {e.stderr}"
    except Exception as e:
        result["extraction_status"] = f"failed: {e}"
    
    return result


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _bind_arguments(spec: FunctionSpec, args: list, kwargs: dict) -> dict:
    """Map positional + keyword args onto param names, apply defaults."""
    bound = {}

    # positional args match params in order
    for i, value in enumerate(args):
        if i >= len(spec.params):
            break
        bound[spec.params[i].name] = value

    # keyword args
    bound.update(kwargs)

    # apply defaults / check required
    for param in spec.params:
        if param.name not in bound:
            if param.required:
                raise MissingArgumentError(
                    f"Required argument '{param.name}' missing for '{spec.name}'"
                )
            bound[param.name] = param.default

    return bound


def _fire(spec: FunctionSpec, bound: dict) -> dict:
    """Build and send the HTTP request."""
    url        = spec.url
    path_params  = {}
    query_params = {}
    body_params  = {}
    headers      = {}

    for param in spec.params:
        value = bound.get(param.name)
        if value is None:
            continue
        if param.location == "path":
            path_params[param.name] = value
        elif param.location == "query":
            query_params[param.name] = value
        elif param.location == "body":
            body_params[param.name] = value
        elif param.location == "header":
            headers[param.name] = str(value)

    # substitute path params into URL
    url = url.format(**path_params)

    # Use longer timeout for Reddit scraper (can take a while)
    timeout = 120.0 if "reddit" in spec.name else 30.0

    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method=spec.method.upper(),
            url=url,
            params=query_params if query_params else None,
            json=body_params   if body_params   else None,
            headers=headers    if headers        else None,
        )

    return {
        "status_code": response.status_code,
        "body": _try_json(response),
    }


def _try_json(response: httpx.Response):
    try:
        return response.json()
    except Exception:
        return response.text

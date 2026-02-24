"""
Executor
--------
Takes a ParsedCall, finds its FunctionSpec, builds the HTTP request, fires it.
"""

import httpx
from parser import ParsedCall
from function_registry import REGISTRY_MAP, FunctionSpec, ParamSpec


class UnknownFunctionError(Exception):
    pass


class MissingArgumentError(Exception):
    pass


def execute(parsed_call: ParsedCall) -> dict:
    spec = REGISTRY_MAP.get(parsed_call.func_name)
    if spec is None:
        raise UnknownFunctionError(
            f"'{parsed_call.func_name}' is not registered. "
            f"Known: {list(REGISTRY_MAP.keys())}"
        )

    bound = _bind_arguments(spec, parsed_call.args, parsed_call.kwargs)
    return _fire(spec, bound)


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

    with httpx.Client(timeout=30) as client:
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

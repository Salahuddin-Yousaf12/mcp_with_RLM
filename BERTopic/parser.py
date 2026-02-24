"""
Parser
------
Extracts a structured function call from the raw LLM response string.

The LLM is prompted to output something like:
    insert_marks_into_student_exams("ahmed", 20)

But it might add noise, so we use a regex to find the first valid call.
"""

import re
import ast
from dataclasses import dataclass


@dataclass
class ParsedCall:
    func_name: str
    args: list        # positional args (Python values)
    kwargs: dict      # keyword args  (Python values)


# Matches:  some_function_name(   ...anything...   )
_CALL_RE = re.compile(r"([a-zA-Z_]\w*)\s*\(([^)]*)\)")


def parse_llm_response(raw: str) -> ParsedCall | None:
    """
    Try to extract a function call from the LLM's raw output.
    Returns None if nothing parseable is found, or the string is 'NO_MATCH'.
    """
    raw = raw.strip()

    if raw.upper() == "NO_MATCH" or not raw:
        return None

    match = _CALL_RE.search(raw)
    if not match:
        return None

    func_name   = match.group(1)
    args_string = match.group(2).strip()

    args, kwargs = _parse_arguments(args_string)
    return ParsedCall(func_name=func_name, args=args, kwargs=kwargs)


def _parse_arguments(args_string: str) -> tuple[list, dict]:
    """
    Parse the argument string into positional args and keyword args.
    Uses ast.literal_eval for safe evaluation of Python literals.
    """
    if not args_string:
        return [], {}

    # Wrap in a tuple so ast can parse the whole arg list at once
    try:
        tree = ast.parse(f"f({args_string})", mode="eval")
    except SyntaxError:
        # Fallback: treat the whole thing as a single string arg
        return [args_string], {}

    call_node = tree.body  # ast.Call

    args   = [ast.literal_eval(a)        for a in call_node.args]
    kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call_node.keywords}

    return args, kwargs

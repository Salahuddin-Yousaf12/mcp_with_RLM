"""
Function Registry — register functions with clear names for the LLM to call.

Usage:
    from rlm.functions import registry

    @registry.register(description="Search Reddit for a topic and return the discussion")
    def search_reddit(query: str) -> str:
        ...
"""

import inspect
from typing import Callable, Dict


class FunctionRegistry:
    """Registry of callable functions available to the LLM in the REPL."""

    def __init__(self):
        self._functions: Dict[str, dict] = {}

    def register(self, description: str = ""):
        """Decorator to register a function."""
        def decorator(fn: Callable) -> Callable:
            self._functions[fn.__name__] = {
                "fn": fn,
                "description": description,
                "signature": str(inspect.signature(fn)),
            }
            return fn
        return decorator

    def get_namespace(self) -> Dict[str, Callable]:
        """Return {name: callable} dict for injection into the REPL namespace."""
        return {name: info["fn"] for name, info in self._functions.items()}

    def get_descriptions(self) -> str:
        """Return a formatted string listing all functions and their descriptions."""
        lines = []
        for name, info in self._functions.items():
            lines.append(f"  - {name}{info['signature']}: {info['description']}")
        return "\n".join(lines)

    def list_names(self) -> list:
        return list(self._functions.keys())


# Global registry instance
registry = FunctionRegistry()

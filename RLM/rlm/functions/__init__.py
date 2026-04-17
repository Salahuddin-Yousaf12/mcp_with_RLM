"""
Functions — registry of callable functions for the LLM.

Import this package to auto-register all built-in functions.
"""

from .registry import registry, FunctionRegistry
from . import reddit  # auto-registers Reddit functions on import

__all__ = ["registry", "FunctionRegistry"]

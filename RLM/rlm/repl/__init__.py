"""
REPL-based RLM implementation

This module provides the REPL-based approach where the LLM writes Python code
to explore the context. Recommended for vLLM and other providers without
native tool calling support.
"""

from .executor import REPLExecutor
from .orchestrator import REPLOrchestrator

__all__ = ["REPLExecutor", "REPLOrchestrator"]

"""
Tool-based RLM implementation

This module provides the tool-calling approach where the LLM uses
predefined functions to explore the context. Recommended for Ollama
and other providers with native tool calling support.
"""

from .definitions import get_tool_definitions
from .handlers import ContextTools
from .orchestrator import ToolsOrchestrator

__all__ = ["get_tool_definitions", "ContextTools", "ToolsOrchestrator"]

"""
RLM - Recursive Language Models

Three modes:
- REPL mode:  LLM writes Python code to explore context (for vLLM/OpenAI)
- Tools mode: LLM uses native tool calling (for Ollama)
- Agent mode: LLM calls registered functions to fetch its own data (standalone)
"""

# Client layer
from .clients import (
    BaseLLMClient,
    LLMResponse,
    VLLMClient,
    OllamaClient,
    OllamaChatClient,
    create_client,
)

# REPL-based implementation
from .repl import REPLExecutor, REPLOrchestrator

# Tool-based implementation
from .tools import ContextTools, ToolsOrchestrator, get_tool_definitions

# Agent implementation (standalone, function-based)
from .agent import AgentOrchestrator

# Function registry
from .functions import registry

# Core utilities
from .core import get_rlm_system_prompt, get_continuation_prompt

# Convenience aliases
RLM = REPLOrchestrator
RLMTools = ToolsOrchestrator
RLMAgent = AgentOrchestrator

__version__ = "0.3.0"
__all__ = [
    # Orchestrators
    "RLM",
    "RLMTools",
    "RLMAgent",
    "REPLOrchestrator",
    "ToolsOrchestrator",
    "AgentOrchestrator",
    # Clients
    "BaseLLMClient",
    "LLMResponse",
    "VLLMClient",
    "OllamaClient",
    "OllamaChatClient",
    "create_client",
    # Components
    "REPLExecutor",
    "ContextTools",
    "get_tool_definitions",
    "registry",
    # Utilities
    "get_rlm_system_prompt",
    "get_continuation_prompt",
]

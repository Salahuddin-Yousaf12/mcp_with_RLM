"""
Abstract base class for LLM clients
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""
    content: str
    raw_response: Any = None
    tool_calls: Optional[List[Dict]] = None
    usage: Optional[Dict[str, int]] = None

    @property
    def has_tool_calls(self) -> bool:
        return self.tool_calls is not None and len(self.tool_calls) > 0


@dataclass
class UsageStats:
    """Track API usage statistics"""
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    def add(self, prompt_tokens: int = 0, completion_tokens: int = 0):
        self.total_calls += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_calls": self.total_calls,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens
        }


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    def __init__(self, base_url: str, model: str, **kwargs):
        self.base_url = base_url
        self.model = model
        self.stats = UsageStats()
        self.timeout = kwargs.get("timeout", 60)

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """
        Generate a completion for the given prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Returns:
            LLMResponse with the generated content
        """
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Chat completion with message history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions for tool calling
            **kwargs: Provider-specific options

        Returns:
            LLMResponse with the generated content and optional tool_calls
        """
        pass

    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics"""
        return self.stats.to_dict()

    def reset_stats(self):
        """Reset usage statistics"""
        self.stats = UsageStats()

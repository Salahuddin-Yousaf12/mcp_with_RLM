"""
LLM Client layer - provides unified interface for different LLM providers
"""

from .base import BaseLLMClient, LLMResponse
from .vllm import VLLMClient
from .ollama import OllamaClient, OllamaChatClient

__all__ = [
    "BaseLLMClient",
    "LLMResponse",
    "VLLMClient",
    "OllamaClient",
    "OllamaChatClient",
    "create_client",
]


def create_client(provider: str, base_url: str, api_key: str, model: str, **kwargs) -> BaseLLMClient:
    """
    Factory function to create the appropriate LLM client.

    Args:
        provider: One of 'vllm', 'ollama', 'openai'
        base_url: API endpoint URL
        api_key: API key for authentication
        model: Model name/identifier
        **kwargs: Additional provider-specific options

    Returns:
        BaseLLMClient instance
    """
    provider = provider.lower()

    if provider in ("vllm", "openai"):
        return VLLMClient(base_url=base_url, api_key=api_key, model=model, **kwargs)
    elif provider == "ollama":
        use_chat = kwargs.pop("use_chat", False)
        if use_chat:
            return OllamaChatClient(base_url=base_url, model=model, **kwargs)
        return OllamaClient(base_url=base_url, model=model, **kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported: vllm, ollama, openai")

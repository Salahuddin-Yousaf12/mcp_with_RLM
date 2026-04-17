"""
vLLM/OpenAI-compatible API client
"""

from typing import Optional, List, Dict, Any
from openai import OpenAI

from .base import BaseLLMClient, LLMResponse


class VLLMClient(BaseLLMClient):
    """
    Client for vLLM and OpenAI-compatible APIs.
    Uses the OpenAI Python SDK for compatibility.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        **kwargs
    ):
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        self.api_key = api_key

        # Initialize OpenAI client with custom base URL
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate completion using chat completions API"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, **kwargs)

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Chat completion with message history.

        Note: vLLM may not support tool calling. Use REPL mode instead.
        """
        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        # Only add tools if provided and supported
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = kwargs.get("tool_choice", "auto")

        response = self.client.chat.completions.create(**request_params)

        # Extract response content
        choice = response.choices[0]
        content = choice.message.content or ""

        # Extract tool calls if present
        tool_calls = None
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in choice.message.tool_calls
            ]

        # Track usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            self.stats.add(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens
            )

        return LLMResponse(
            content=content,
            raw_response=response,
            tool_calls=tool_calls,
            usage=usage
        )

"""
Ollama API clients - supports both generate and chat endpoints
"""

import json
import requests
from typing import Optional, List, Dict, Any

from .base import BaseLLMClient, LLMResponse


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama generate endpoint.
    Use this for REPL-based mode where LLM writes code.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 60,
        **kwargs
    ):
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        # Ensure URL ends with /api/generate
        self.generate_url = base_url.rstrip("/")
        if not self.generate_url.endswith("/api/generate"):
            self.generate_url = f"{self.generate_url}/api/generate"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate completion using Ollama generate endpoint"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        response = requests.post(
            self.generate_url,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        # Track usage (Ollama provides eval_count and prompt_eval_count)
        usage = None
        if "eval_count" in data or "prompt_eval_count" in data:
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            self.stats.add(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

        return LLMResponse(
            content=data.get("response", ""),
            raw_response=data,
            usage=usage
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Chat using generate endpoint by formatting messages into a prompt.
        For proper chat with tools, use OllamaChatClient instead.
        """
        # Format messages into a single prompt
        prompt_parts = []
        system_prompt = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        prompt = "\n\n".join(prompt_parts)
        if prompt_parts:
            prompt += "\n\nAssistant:"

        return self.generate(prompt, system_prompt=system_prompt, **kwargs)


class OllamaChatClient(BaseLLMClient):
    """
    Client for Ollama chat endpoint with tool calling support.
    Use this for tool-based mode where LLM calls predefined functions.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 60,
        **kwargs
    ):
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        # Ensure URL ends with /api/chat
        self.chat_url = base_url.rstrip("/")
        if not self.chat_url.endswith("/api/chat"):
            self.chat_url = f"{self.chat_url}/api/chat"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """Generate using chat endpoint"""
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
        """Chat completion with optional tool calling"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            }
        }

        if tools:
            payload["tools"] = tools

        response = requests.post(
            self.chat_url,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        # Extract message content
        message = data.get("message", {})
        content = message.get("content", "")

        # Extract tool calls
        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = message["tool_calls"]

        # Track usage
        usage = None
        if "eval_count" in data or "prompt_eval_count" in data:
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            self.stats.add(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

        return LLMResponse(
            content=content,
            raw_response=data,
            tool_calls=tool_calls,
            usage=usage
        )

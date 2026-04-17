"""
Tools Orchestrator - Main RLM loop using native tool calling

This orchestrator uses the LLM's native tool calling capability
to let it explore large contexts programmatically.
"""

import json
from typing import Any, Optional

from ..clients import BaseLLMClient, create_client
from .definitions import get_tool_definitions
from .handlers import ContextTools


class ToolsOrchestrator:
    """
    Tool-Based Recursive Language Model Orchestrator

    Uses native tool calling to let the LLM explore large contexts
    without hitting context window limits.
    """

    def __init__(
        self,
        client: BaseLLMClient = None,
        provider: str = None,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        verbose: bool = False,
        max_iterations: int = 30,
        max_sub_llm_calls: int = 20,
        max_recursion_depth: int = 1,
        call_timeout: int = 60,
        chunk_size: int = 2000
    ):
        """
        Initialize the Tools Orchestrator.

        Args:
            client: Pre-configured LLM client (optional)
            provider: LLM provider ('vllm', 'ollama', 'openai')
            base_url: API base URL
            api_key: API key
            model: Model name
            verbose: Enable verbose output
            max_iterations: Maximum LLM interaction loops
            max_sub_llm_calls: Maximum sub-LLM calls allowed
            max_recursion_depth: Maximum depth for sub-LLM calls
            call_timeout: Timeout for each API call
            chunk_size: Size of context chunks
        """
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.max_sub_llm_calls = max_sub_llm_calls
        self.max_recursion_depth = max_recursion_depth
        self.chunk_size = chunk_size

        # Use provided client or create one from config
        if client:
            self.client = client
        else:
            from config import config as cfg
            self.client = create_client(
                provider=provider or cfg.root_llm.provider,
                base_url=base_url or cfg.root_llm.base_url,
                api_key=api_key or cfg.root_llm.api_key,
                model=model or cfg.root_llm.model,
                timeout=call_timeout or cfg.safeguards.call_timeout,
                use_chat=True  # Tools mode needs chat endpoint
            )

        # For sub-LLM calls
        self._sub_client = None
        self._total_sub_llm_calls = 0

        # Stats
        self.last_iteration_count = 0
        self.last_tool_calls = 0

    def _log(self, msg: str, prefix: str = "RLM"):
        if self.verbose:
            print(f"[{prefix}] {msg}")

    def _get_sub_client(self) -> BaseLLMClient:
        """Get or create the sub-LLM client"""
        if self._sub_client is None:
            from config import config as cfg
            self._sub_client = create_client(
                provider=cfg.sub_llm.provider,
                base_url=cfg.sub_llm.base_url,
                api_key=cfg.sub_llm.api_key,
                model=cfg.sub_llm.model,
                timeout=cfg.safeguards.call_timeout
            )
        return self._sub_client

    def _create_llm_query_fn(self, depth: int):
        """Create function for sub-LLM queries"""
        def llm_query(prompt: str) -> str:
            if depth >= self.max_recursion_depth:
                return f"[Max recursion depth ({self.max_recursion_depth}) reached]"

            if self._total_sub_llm_calls >= self.max_sub_llm_calls:
                return f"[Max sub-LLM calls ({self.max_sub_llm_calls}) reached]"

            self._total_sub_llm_calls += 1
            self._log(f"Sub-LLM call #{self._total_sub_llm_calls} at depth {depth + 1}", "SUB-LLM")

            sub_client = self._get_sub_client()
            response = sub_client.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant. Answer concisely."
            )
            return response.content

        return llm_query

    def query(self, query: str, context: Any) -> str:
        """
        Process a query against the given context using tool-based exploration.

        Args:
            query: The user's question
            context: The context to search (string, list, or dict)

        Returns:
            The final answer string
        """
        self._log(f"Starting tool-based RLM query")
        self._log(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        # Reset counters
        self._total_sub_llm_calls = 0

        # Initialize context tools
        llm_query_fn = self._create_llm_query_fn(depth=0)
        ctx_tools = ContextTools(
            context=context,
            llm_query_fn=llm_query_fn,
            chunk_size=self.chunk_size,
            verbose=self.verbose
        )

        tool_definitions = get_tool_definitions()
        stats = ctx_tools.get_stats()
        self._log(f"Context: {stats['context_length']:,} chars, {stats['num_chunks']} chunks")

        # Build initial system message
        system_content = f"""You are a helpful assistant. The context below contains Reddit posts and comments that are directly relevant to the user's question. Your job is to read the context and answer based on what it contains.

CONTEXT: {stats['context_length']:,} characters in {stats['num_chunks']} chunks (indices 0-{stats['num_chunks']-1})

RULES:
1. Use read_chunk(0) to read the context first, then answer from what you find.
2. If you need more detail, use search(query) to find specific sections.
3. ALWAYS base your final_answer on the context content — never say you cannot find information.
4. Call final_answer(answer) with a helpful, specific answer drawn from the context.

TOOLS:
- read_chunk(chunk_index): Read chunk 0-{stats['num_chunks']-1}
- search(query): Find text, get excerpts with positions
- final_answer(answer): REQUIRED - call this with your answer based on the context"""

        # Initialize conversation
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query}
        ]

        # Main loop
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            self._log(f"=== Iteration {iteration}/{self.max_iterations} ===")

            # Get LLM response with tools
            response = self.client.chat(messages, tools=tool_definitions)

            # Check for tool calls
            if response.has_tool_calls:
                self._log(f"Processing {len(response.tool_calls)} tool call(s)")

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": response.tool_calls
                })

                # Process each tool call
                for tc in response.tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", {})

                    # Handle arguments that might be strings (JSON)
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            args = {}

                    result, is_final = ctx_tools.handle_tool_call(name, args)

                    if is_final:
                        self._log(f"Final answer received after {iteration} iterations")
                        self.last_iteration_count = iteration
                        self.last_tool_calls = ctx_tools.tool_call_count
                        return result

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": result
                    })

            else:
                # No tool calls - check if there's a text response
                content = response.content.strip()

                if content:
                    self._log(f"Got text response ({len(content)} chars) without tool call")

                    # If we've done some exploration and got a substantive response, accept it
                    if ctx_tools.tool_call_count > 0 and len(content) > 200:
                        self._log("Treating as implicit final answer (after exploration)")
                        self.last_iteration_count = iteration
                        self.last_tool_calls = ctx_tools.tool_call_count
                        return content

                    # Otherwise, prompt to call final_answer
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": "Now call final_answer(answer) with your complete answer."
                    })
                else:
                    # Empty response - prompt for action
                    messages.append({
                        "role": "user",
                        "content": "Use search(query) to find relevant information, then call final_answer(answer)."
                    })

        # Max iterations reached
        self._log(f"Max iterations ({self.max_iterations}) reached")
        self.last_iteration_count = iteration
        self.last_tool_calls = ctx_tools.tool_call_count

        return f"[Max iterations reached. Could not find definitive answer.]"

    def get_stats(self) -> dict:
        return {
            "last_iteration_count": self.last_iteration_count,
            "last_tool_calls": self.last_tool_calls,
            "client_stats": self.client.get_stats()
        }

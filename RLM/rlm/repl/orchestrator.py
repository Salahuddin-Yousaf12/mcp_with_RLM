"""
REPL Orchestrator - Main RLM loop using code execution

This orchestrator ties together:
- LLM client for generating code
- REPL executor for running code
- Iterative loop for processing queries
"""

import re
from typing import Any, Optional

from ..clients import BaseLLMClient, create_client
from ..core.prompts import get_rlm_system_prompt, get_continuation_prompt
from .executor import REPLExecutor


class REPLOrchestrator:
    """
    REPL-based Recursive Language Model Orchestrator

    Processes arbitrarily long contexts by treating them as external
    environment variables that the LLM can programmatically interact with
    via Python code execution.
    """

    # Regex patterns for parsing LLM responses
    CODE_PATTERN = re.compile(r"```(?:repl|python)\n(.*?)```", re.DOTALL)
    FINAL_PATTERN = re.compile(r"FINAL\((.*?)\)", re.DOTALL)
    FINAL_VAR_PATTERN = re.compile(r"FINAL_VAR\((\w+)\)")

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
        call_timeout: int = 60
    ):
        """
        Initialize the REPL Orchestrator.

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
        """
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.max_sub_llm_calls = max_sub_llm_calls
        self.max_recursion_depth = max_recursion_depth

        # Use provided client or create one from config
        if client:
            self.client = client
        else:
            # Load defaults from config
            from config import config as cfg
            self.client = create_client(
                provider=provider or cfg.root_llm.provider,
                base_url=base_url or cfg.root_llm.base_url,
                api_key=api_key or cfg.root_llm.api_key,
                model=model or cfg.root_llm.model,
                timeout=call_timeout or cfg.safeguards.call_timeout
            )

        # For sub-LLM calls, we might use a different client
        self._sub_client = None

        # Track statistics
        self.last_iteration_count = 0
        self.last_sub_llm_calls = 0
        self._total_sub_llm_calls = 0

    def _log(self, message: str, prefix: str = "RLM"):
        """Print a log message if verbose mode is enabled"""
        if self.verbose:
            print(f"[{prefix}] {message}")

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
        """
        Create a llm_query function for a given recursion depth.

        Args:
            depth: Current recursion depth

        Returns:
            A function that can be used for sub-LLM queries
        """
        def llm_query(prompt: str) -> str:
            # Check recursion depth
            if depth >= self.max_recursion_depth:
                return f"[ERROR: Maximum recursion depth ({self.max_recursion_depth}) reached. Cannot make more sub-LLM calls.]"

            # Check total sub-LLM call limit
            if self._total_sub_llm_calls >= self.max_sub_llm_calls:
                return f"[ERROR: Maximum sub-LLM calls ({self.max_sub_llm_calls}) reached.]"

            self._total_sub_llm_calls += 1
            self._log(f"Sub-LLM call #{self._total_sub_llm_calls} at depth {depth + 1}", "SUB-LLM")

            # Use sub-LLM client for sub-calls
            sub_client = self._get_sub_client()
            response = sub_client.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant. Answer the question concisely and accurately."
            )

            return response.content

        return llm_query

    def _extract_code_blocks(self, response: str) -> list:
        """Extract code blocks from LLM response"""
        matches = self.CODE_PATTERN.findall(response)
        return matches

    def _check_final_answer(self, response: str, repl: REPLExecutor) -> tuple:
        """
        Check if the response contains a final answer.

        Returns:
            Tuple of (is_final, answer)
        """
        # Check for FINAL_VAR first (more specific)
        var_match = self.FINAL_VAR_PATTERN.search(response)
        if var_match:
            var_name = var_match.group(1)
            var_value = repl.get_variable(var_name)
            if var_value is not None:
                self._log(f"Final answer from variable '{var_name}'")
                return True, str(var_value)
            else:
                self._log(f"Warning: FINAL_VAR referenced undefined variable '{var_name}'")

        # Check for FINAL()
        final_match = self.FINAL_PATTERN.search(response)
        if final_match:
            answer = final_match.group(1).strip()
            self._log(f"Final answer provided directly")
            return True, answer

        return False, None

    def query(self, query: str, context: Any) -> str:
        """
        Process a query with the given context using the RLM approach.

        Args:
            query: The user's question/query
            context: The context (string, list, dict, etc.)

        Returns:
            The final answer string
        """
        self._log(f"Starting REPL-based RLM query")
        self._log(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")

        # Reset sub-LLM call counter
        self._total_sub_llm_calls = 0

        # Create the REPL environment
        llm_query_fn = self._create_llm_query_fn(depth=0)
        repl = REPLExecutor(
            context=context,
            llm_query_fn=llm_query_fn,
            verbose=self.verbose
        )

        # Get context metadata
        context_info = repl.get_context_info()
        self._log(f"Context: {context_info['type']}, {context_info['total_length']:,} chars")

        # Build the initial prompt
        system_prompt = get_rlm_system_prompt(
            context_type=context_info["type"],
            context_total_length=context_info["total_length"],
            context_lengths=context_info.get("chunks")
        )

        # Construct the user message
        context_str = str(context)
        if len(context_str) < 5000:
            context_preview = context_str
        else:
            context_preview = context_str[:2000] + f"\n\n[... {len(context_str) - 2000} more characters ...]"

        user_message = f"""QUERY: {query}

CONTEXT PREVIEW (use 'context' variable in code for full access):
{context_preview}

Write Python code in ```python blocks to analyze the context, then FINAL(your answer)."""

        # Main iteration loop
        iteration = 0
        conversation_context = ""

        while iteration < self.max_iterations:
            iteration += 1
            self._log(f"=== Iteration {iteration}/{self.max_iterations} ===")

            # Build the full prompt
            if iteration == 1:
                full_prompt = user_message
                if conversation_context:
                    full_prompt += f"\n\n{conversation_context}"
            else:
                full_prompt = conversation_context

            # Call the LLM
            response = self.client.generate(
                prompt=full_prompt,
                system_prompt=system_prompt
            )
            response_text = response.content

            self._log(f"LLM response length: {len(response_text)} chars")

            # Check for final answer
            is_final, answer = self._check_final_answer(response_text, repl)
            if is_final:
                self.last_iteration_count = iteration
                self.last_sub_llm_calls = repl.llm_call_count
                self._log(f"Completed in {iteration} iterations with {repl.llm_call_count} sub-LLM calls")
                return answer

            # Extract and execute code blocks
            code_blocks = self._extract_code_blocks(response_text)

            if code_blocks:
                self._log(f"Found {len(code_blocks)} code block(s)")

                all_outputs = []
                for i, code in enumerate(code_blocks):
                    self._log(f"Executing code block {i + 1}")
                    output, success = repl.execute(code)

                    status = "SUCCESS" if success else "ERROR"
                    all_outputs.append(f"[Code Block {i + 1} - {status}]\n{output}")

                # Update conversation context with execution results
                execution_output = "\n\n".join(all_outputs)
                conversation_context = get_continuation_prompt(
                    previous_output=execution_output,
                    iteration=iteration
                )

            else:
                # No code blocks found
                self._log("No code blocks found in response")

                # Check if response seems like a final answer
                if len(response_text) < 500 and not any(keyword in response_text.lower() for keyword in ["```", "code", "execute", "let me"]):
                    self._log("Response appears to be a direct answer (no FINAL tag)")
                    self.last_iteration_count = iteration
                    self.last_sub_llm_calls = repl.llm_call_count
                    return response_text.strip()

                # Prompt the LLM to continue
                conversation_context = f"""Your previous response did not contain any code blocks or a FINAL() answer.

Previous response:
{response_text[:2000]}{'...' if len(response_text) > 2000 else ''}

Please either:
1. Write code in ```python``` blocks to explore the context
2. Provide your final answer with FINAL(your answer here)

What would you like to do?"""

        # Max iterations reached
        self._log(f"Warning: Max iterations ({self.max_iterations}) reached without final answer")
        self.last_iteration_count = iteration
        self.last_sub_llm_calls = repl.llm_call_count

        return f"[Max iterations reached. Last LLM response:]\n{response_text[:1000]}"

    def get_stats(self) -> dict:
        """Get statistics from the last query"""
        return {
            "last_iteration_count": self.last_iteration_count,
            "last_sub_llm_calls": self.last_sub_llm_calls,
            "client_stats": self.client.get_stats()
        }

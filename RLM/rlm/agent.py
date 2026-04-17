"""
Agent Orchestrator — LLM uses registered functions to answer queries.

No pre-loaded context needed. The LLM calls functions (like search_reddit)
to fetch its own data, analyzes the results in the REPL, and returns an answer.
"""

import re
from typing import Optional

from .clients import BaseLLMClient, create_client
from .repl.executor import REPLExecutor
from .functions import registry


class AgentOrchestrator:
    """
    Agent mode: the LLM decides which functions to call, executes them
    in the REPL, and synthesizes an answer.

    Usage:
        agent = AgentOrchestrator(verbose=True)
        answer = agent.ask("What do people think about the new iPhone?")
    """

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
        max_iterations: int = 15,
        max_sub_llm_calls: int = 10,
        max_recursion_depth: int = 1,
        call_timeout: int = 120,
    ):
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.max_sub_llm_calls = max_sub_llm_calls
        self.max_recursion_depth = max_recursion_depth

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
            )

        self._sub_client = None
        self._total_sub_llm_calls = 0

        # Stats
        self.last_iteration_count = 0
        self.last_function_calls = 0

    def _log(self, msg: str, prefix: str = "AGENT"):
        if self.verbose:
            print(f"[{prefix}] {msg}")

    def _get_sub_client(self) -> BaseLLMClient:
        if self._sub_client is None:
            from config import config as cfg
            self._sub_client = create_client(
                provider=cfg.sub_llm.provider,
                base_url=cfg.sub_llm.base_url,
                api_key=cfg.sub_llm.api_key,
                model=cfg.sub_llm.model,
                timeout=cfg.safeguards.call_timeout,
            )
        return self._sub_client

    def _create_llm_query_fn(self, depth: int):
        def llm_query(prompt: str) -> str:
            if depth >= self.max_recursion_depth:
                return f"[Max recursion depth ({self.max_recursion_depth}) reached]"
            if self._total_sub_llm_calls >= self.max_sub_llm_calls:
                return f"[Max sub-LLM calls ({self.max_sub_llm_calls}) reached]"
            self._total_sub_llm_calls += 1
            self._log(f"Sub-LLM call #{self._total_sub_llm_calls}", "SUB-LLM")
            sub_client = self._get_sub_client()
            response = sub_client.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant. Answer concisely.",
            )
            return response.content
        return llm_query

    def _build_system_prompt(self) -> str:
        fn_descriptions = registry.get_descriptions()
        return f"""You are an AI agent that answers questions by calling functions and analyzing their output.

AVAILABLE FUNCTIONS:
{fn_descriptions}

OTHER TOOLS IN REPL:
  - llm_query(prompt): Ask a sub-LLM to analyze text
  - print(): See output from your code
  - re, json, math, collections: Standard Python modules

HOW TO RESPOND:
1. Write Python code in ```python blocks to call functions and explore results
2. Use print() to see what the functions return
3. Analyze the output — call more functions if needed
4. When you have enough info, write FINAL(your answer here)

EXAMPLE:
```python
result = search_reddit("best mechanical keyboard 2024")
print(result[:2000])  # preview the discussion
```

Then after reading the output:

FINAL(Based on the Reddit discussion, the top recommendations are...)

IMPORTANT:
- Always call a function first — do NOT answer from your own knowledge
- Read the function output carefully before answering
- Base your answer on what the functions return, not assumptions"""

    def _check_final_answer(self, response: str, repl: REPLExecutor) -> tuple:
        var_match = self.FINAL_VAR_PATTERN.search(response)
        if var_match:
            var_name = var_match.group(1)
            val = repl.get_variable(var_name)
            if val is not None:
                return True, str(val)

        final_match = self.FINAL_PATTERN.search(response)
        if final_match:
            return True, final_match.group(1).strip()

        return False, None

    def ask(self, query: str) -> str:
        """
        Answer a query by letting the LLM use registered functions.

        Args:
            query: The user's question

        Returns:
            The final answer string
        """
        self._log(f"Query: {query}")
        self._total_sub_llm_calls = 0

        # Create REPL with empty context + injected functions
        llm_query_fn = self._create_llm_query_fn(depth=0)
        repl = REPLExecutor(
            context="",
            llm_query_fn=llm_query_fn,
            verbose=self.verbose,
            execution_timeout=120,  # functions may take time (HTTP calls)
        )

        # Inject registered functions into the REPL namespace
        for name, fn in registry.get_namespace().items():
            repl.namespace[name] = fn

        system_prompt = self._build_system_prompt()
        user_message = f"QUERY: {query}\n\nCall the appropriate function(s) to find information, then FINAL(your answer)."

        iteration = 0
        conversation_context = ""

        while iteration < self.max_iterations:
            iteration += 1
            self._log(f"=== Iteration {iteration}/{self.max_iterations} ===")

            if iteration == 1:
                full_prompt = user_message
            else:
                full_prompt = conversation_context

            response = self.client.generate(
                prompt=full_prompt,
                system_prompt=system_prompt,
            )
            response_text = response.content
            self._log(f"LLM response: {len(response_text)} chars")

            # Check for final answer
            is_final, answer = self._check_final_answer(response_text, repl)
            if is_final:
                self.last_iteration_count = iteration
                self._log(f"Done in {iteration} iterations")
                return answer

            # Extract and execute code blocks
            code_blocks = self.CODE_PATTERN.findall(response_text)

            if code_blocks:
                self._log(f"Executing {len(code_blocks)} code block(s)")
                all_outputs = []
                for i, code in enumerate(code_blocks):
                    output, success = repl.execute(code)
                    status = "OK" if success else "ERROR"
                    all_outputs.append(f"[Block {i+1} - {status}]\n{output}")

                execution_output = "\n\n".join(all_outputs)
                conversation_context = (
                    f"[Iteration {iteration}] Your code ran. Output:\n\n"
                    f"{execution_output}\n\n"
                    f"Continue: write more code to explore, or FINAL(your answer) if ready."
                )
            else:
                # No code blocks — check if it's a short direct answer
                if len(response_text) < 500 and not any(
                    kw in response_text.lower()
                    for kw in ["```", "code", "let me", "i'll"]
                ):
                    self.last_iteration_count = iteration
                    return response_text.strip()

                conversation_context = (
                    f"Your response had no code blocks.\n\n"
                    f"Please either:\n"
                    f"1. Write code in ```python``` blocks to call a function\n"
                    f"2. Write FINAL(your answer) if you already have enough info"
                )

        self.last_iteration_count = iteration
        return f"[Max iterations ({self.max_iterations}) reached without a final answer]"

    def get_stats(self) -> dict:
        return {
            "last_iteration_count": self.last_iteration_count,
            "last_sub_llm_calls": self._total_sub_llm_calls,
            "client_stats": self.client.get_stats(),
        }

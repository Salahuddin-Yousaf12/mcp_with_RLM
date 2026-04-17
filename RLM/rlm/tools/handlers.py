"""
Tool Handlers for Tool-Based RLM

Implements the actual logic for each tool that the LLM can call.
Context is stored locally, only relevant chunks are sent when requested.
"""

import re
from typing import Any, Callable, Optional, Tuple


class ContextTools:
    """
    Manages context and provides tool handlers for the LLM.

    The key insight: context is stored locally, and only relevant
    chunks are sent to the LLM when requested via tools.
    This bypasses context window limitations.
    """

    def __init__(
        self,
        context: Any,
        llm_query_fn: Callable[[str], str] = None,
        chunk_size: int = 2000,
        verbose: bool = False
    ):
        """
        Args:
            context: The full context (string, list, or dict)
            llm_query_fn: Function to make sub-LLM queries
            chunk_size: Default size for pre-chunking
            verbose: Print debug info
        """
        self.verbose = verbose
        self.llm_query_fn = llm_query_fn
        self.chunk_size = chunk_size

        # Normalize context to string
        if isinstance(context, str):
            self.context = context
        elif isinstance(context, list):
            self.context = "\n\n---\n\n".join(str(item) for item in context)
        elif isinstance(context, dict):
            self.context = "\n\n".join(f"{k}: {v}" for k, v in context.items())
        else:
            self.context = str(context)

        # Pre-chunk for indexed access
        self.chunks = self._create_chunks()

        # Track tool usage
        self.tool_call_count = 0
        self.sub_llm_calls = 0

    def _create_chunks(self) -> list:
        """Split context into manageable chunks with overlap"""
        chunks = []
        text = self.context
        overlap = min(200, self.chunk_size // 5)

        i = 0
        while i < len(text):
            end = min(i + self.chunk_size, len(text))
            chunks.append(text[i:end])
            i += self.chunk_size - overlap

        return chunks

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Tools] {msg}")

    def handle_tool_call(self, name: str, arguments: dict) -> Tuple[str, bool]:
        """
        Execute a tool call and return the result.

        Returns:
            Tuple of (result_string, is_final_answer)
        """
        self.tool_call_count += 1
        self._log(f"Tool call #{self.tool_call_count}: {name}({arguments})")

        handlers = {
            "get_context_info": self._handle_get_context_info,
            "read_chunk": self._handle_read_chunk,
            "read_range": self._handle_read_range,
            "search": self._handle_search,
            "ask_about_chunk": self._handle_ask_about_chunk,
            "final_answer": self._handle_final_answer,
        }

        handler = handlers.get(name)
        if not handler:
            return f"Unknown tool: {name}", False

        return handler(arguments)

    def _handle_get_context_info(self, args: dict) -> Tuple[str, bool]:
        preview = self.context[:500] + "..." if len(self.context) > 500 else self.context
        info = (
            f"Context Info:\n"
            f"- Total length: {len(self.context):,} characters\n"
            f"- Number of chunks: {len(self.chunks)}\n"
            f"- Chunk size: ~{self.chunk_size} chars each\n"
            f"\nPreview (first 500 chars):\n{preview}"
        )
        return info, False

    def _handle_read_chunk(self, args: dict) -> Tuple[str, bool]:
        idx = int(args.get("chunk_index", 0) or 0)
        if idx < 0 or idx >= len(self.chunks):
            return f"Invalid chunk index {idx}. Valid range: 0-{len(self.chunks)-1}", False

        chunk = self.chunks[idx]
        return f"[Chunk {idx}/{len(self.chunks)-1}] ({len(chunk)} chars):\n\n{chunk}", False

    def _handle_read_range(self, args: dict) -> Tuple[str, bool]:
        start = max(0, int(args.get("start", 0) or 0))
        end = min(len(self.context), int(args.get("end", len(self.context)) or len(self.context)))

        if start >= end:
            return "Invalid range: start must be less than end", False

        # Limit to reasonable size
        if end - start > 5000:
            end = start + 5000
            truncated = " (truncated to 5000 chars)"
        else:
            truncated = ""

        text = self.context[start:end]
        return f"[Range {start}-{end}]{truncated}:\n\n{text}", False

    def _handle_search(self, args: dict) -> Tuple[str, bool]:
        query = args.get("query", "")
        max_results = min(int(args.get("max_results", 5) or 5), 20)

        if not query:
            return "Search query cannot be empty", False

        results = []
        try:
            # Try regex first, fall back to literal
            pattern = re.compile(query, re.IGNORECASE)
            for match in pattern.finditer(self.context):
                if len(results) >= max_results:
                    break
                start = max(0, match.start() - 50)
                end = min(len(self.context), match.end() + 50)
                excerpt = self.context[start:end]
                results.append(f"[Position {match.start()}]: ...{excerpt}...")
        except re.error:
            # Literal search
            idx = 0
            while len(results) < max_results:
                pos = self.context.lower().find(query.lower(), idx)
                if pos == -1:
                    break
                start = max(0, pos - 50)
                end = min(len(self.context), pos + len(query) + 50)
                excerpt = self.context[start:end]
                results.append(f"[Position {pos}]: ...{excerpt}...")
                idx = pos + 1

        if not results:
            return f"No matches found for: {query}", False

        return f"Found {len(results)} match(es):\n\n" + "\n\n".join(results), False

    def _handle_ask_about_chunk(self, args: dict) -> Tuple[str, bool]:
        idx = int(args.get("chunk_index", 0) or 0)
        question = args.get("question", "")

        if idx < 0 or idx >= len(self.chunks):
            return f"Invalid chunk index {idx}", False

        if not question:
            return "Question cannot be empty", False

        if not self.llm_query_fn:
            return "Sub-LLM queries not available", False

        self.sub_llm_calls += 1
        chunk = self.chunks[idx]
        prompt = f"Context:\n{chunk}\n\nQuestion: {question}\n\nAnswer concisely:"

        try:
            answer = self.llm_query_fn(prompt)
            return f"[Analysis of chunk {idx}]:\n{answer}", False
        except Exception as e:
            return f"Sub-LLM query failed: {e}", False

    def _handle_final_answer(self, args: dict) -> Tuple[str, bool]:
        answer = args.get("answer", "")
        return answer, True

    def get_stats(self) -> dict:
        return {
            "context_length": len(self.context),
            "num_chunks": len(self.chunks),
            "tool_calls": self.tool_call_count,
            "sub_llm_calls": self.sub_llm_calls
        }

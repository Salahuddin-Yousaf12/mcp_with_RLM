"""
Tool Definitions for Tool-Based RLM

JSON Schema definitions for tools that the LLM can call to explore context.
"""


def get_tool_definitions() -> list:
    """
    Return tool definitions in OpenAI/Ollama format.

    These tools allow the LLM to:
    - Get context metadata (get_context_info)
    - Read specific chunks (read_chunk)
    - Read character ranges (read_range)
    - Search for patterns (search)
    - Ask sub-LLMs about chunks (ask_about_chunk)
    - Provide final answer (final_answer)
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_context_info",
                "description": "Get metadata about the context: total length, number of chunks, and a brief preview. Call this first to understand the context size.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_chunk",
                "description": "Read a specific chunk of the context by index. Chunks are pre-split portions of the document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunk_index": {
                            "type": "integer",
                            "description": "The chunk index (0-based)"
                        }
                    },
                    "required": ["chunk_index"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_range",
                "description": "Read a specific character range from the context. Use for precise access.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "integer",
                            "description": "Start character position"
                        },
                        "end": {
                            "type": "integer",
                            "description": "End character position"
                        }
                    },
                    "required": ["start", "end"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search for a text pattern in the context. Returns matching excerpts with their positions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text or regex pattern to search for"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return (default 5)"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ask_about_chunk",
                "description": "Ask a specific question about a chunk of context. Uses a sub-LLM call to analyze.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunk_index": {
                            "type": "integer",
                            "description": "The chunk index to analyze"
                        },
                        "question": {
                            "type": "string",
                            "description": "Question to ask about this chunk"
                        }
                    },
                    "required": ["chunk_index", "question"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "final_answer",
                "description": "Provide the final answer to the user's query. Call this when you have found the answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer": {
                            "type": "string",
                            "description": "The final answer"
                        }
                    },
                    "required": ["answer"]
                }
            }
        }
    ]

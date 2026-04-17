#!/usr/bin/env python3
"""
RLM CLI - Command Line Interface for Recursive Language Models

Usage:
    python main.py "Your query here" --context-file document.txt
    python main.py "Your query here" --context "Inline context here"
    python main.py "Your query here" -f document.txt -v --repl
"""

import argparse
import sys
import os

# Handle Unicode output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from rlm import RLM, RLMTools, RLMAgent


def main():
    parser = argparse.ArgumentParser(
        description="RLM - Recursive Language Models CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # REPL mode (default, recommended for vLLM):
  python main.py "Find the magic number" -f document.txt

  # Tools mode (for Ollama with tool calling):
  python main.py "Find the magic number" -f document.txt --tools

  # With verbose output and stats:
  python main.py "Summarize the key points" -f notes.txt -v --stats
        """
    )

    # Required: Query
    parser.add_argument(
        "query",
        type=str,
        help="The question or query to answer"
    )

    # Context input (optional — not needed for agent mode)
    context_group = parser.add_mutually_exclusive_group(required=False)
    context_group.add_argument(
        "-f", "--context-file",
        type=str,
        help="Path to a file containing the context"
    )
    context_group.add_argument(
        "-c", "--context",
        type=str,
        help="Inline context string"
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--repl",
        action="store_true",
        help="Use REPL mode (LLM writes Python code)"
    )
    mode_group.add_argument(
        "--tools",
        action="store_true",
        help="Use Tools mode (native tool calling, for Ollama)"
    )
    mode_group.add_argument(
        "--agent",
        action="store_true",
        help="Use Agent mode (standalone, uses functions like search_reddit)"
    )

    # Optional settings
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output showing execution details"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=config.MAX_ITERATIONS,
        help=f"Maximum number of LLM interaction loops (default: {config.MAX_ITERATIONS})"
    )
    parser.add_argument(
        "--max-sub-calls",
        type=int,
        default=config.MAX_SUB_LLM_CALLS,
        help=f"Maximum sub-LLM calls allowed (default: {config.MAX_SUB_LLM_CALLS})"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=config.MAX_RECURSION_DEPTH,
        help=f"Maximum recursion depth for sub-LLM calls (default: {config.MAX_RECURSION_DEPTH})"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics after completion"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=config.DEFAULT_CHUNK_SIZE,
        help=f"Chunk size for context splitting (default: {config.DEFAULT_CHUNK_SIZE})"
    )

    args = parser.parse_args()

    # Determine mode
    use_agent = args.agent
    use_tools = args.tools

    if use_agent:
        mode_name = "Agent"
    elif use_tools:
        mode_name = "Tools"
    else:
        mode_name = "REPL"

    # Load context (not needed for agent mode)
    context = None
    if not use_agent:
        if args.context_file:
            try:
                with open(args.context_file, "r", encoding="utf-8") as f:
                    context = f.read()
                if args.verbose:
                    print(f"[CLI] Loaded context from {args.context_file} ({len(context):,} chars)")
            except FileNotFoundError:
                print(f"Error: File not found: {args.context_file}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error reading file: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.context:
            context = args.context
        else:
            print("Error: --context-file or --context is required for REPL/Tools mode", file=sys.stderr)
            print("       Use --agent mode for standalone queries without context", file=sys.stderr)
            sys.exit(1)

    if args.verbose:
        print(f"[CLI] Initializing RLM ({mode_name} mode)...")
        print(f"[CLI] Provider: {config.ROOT_LLM['provider']}")
        print(f"[CLI] Model: {config.ROOT_LLM['model']}")
        print(f"[CLI] Base URL: {config.ROOT_LLM['base_url']}")
        print(f"[CLI] Max iterations: {args.max_iterations}")
        print()

    # Initialize orchestrator
    if use_agent:
        rlm = RLMAgent(
            verbose=args.verbose,
            max_iterations=args.max_iterations,
            max_sub_llm_calls=args.max_sub_calls,
            max_recursion_depth=args.max_depth,
        )
    elif use_tools:
        rlm = RLMTools(
            verbose=args.verbose,
            max_iterations=args.max_iterations,
            max_sub_llm_calls=args.max_sub_calls,
            max_recursion_depth=args.max_depth,
            chunk_size=args.chunk_size,
        )
    else:
        rlm = RLM(
            verbose=args.verbose,
            max_iterations=args.max_iterations,
            max_sub_llm_calls=args.max_sub_calls,
            max_recursion_depth=args.max_depth,
        )

    # Run the query
    try:
        if args.verbose:
            print("=" * 60)
            print(f"STARTING RLM QUERY ({mode_name} mode)")
            print("=" * 60)
            print()

        if use_agent:
            answer = rlm.ask(args.query)
        else:
            answer = rlm.query(args.query, context)

        print()
        print("=" * 60)
        print("ANSWER:")
        print("=" * 60)
        print(answer)
        print()

        if args.stats:
            stats = rlm.get_stats()
            print("=" * 60)
            print("STATISTICS:")
            print("=" * 60)
            print(f"  Iterations: {stats['last_iteration_count']}")
            print(f"  Client stats: {stats['client_stats']}")
            print()

    except KeyboardInterrupt:
        print("\n[CLI] Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

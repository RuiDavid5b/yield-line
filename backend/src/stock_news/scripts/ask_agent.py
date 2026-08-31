"""
CLI entrypoint for querying the agent - mirrors the __main__ pattern
used by pipelines/*.py, for manual use and eventual DAG/tool invocation.
"""

from __future__ import annotations

import argparse
import logging

from langchain_core.messages import AIMessage, ToolMessage

from stock_news.agent.graph import build_agent_graph

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask the stock_news agent a question.")
    parser.add_argument("question")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print tool calls, their results, and per-turn token usage",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    agent = build_agent_graph()
    result = agent.invoke({"messages": [("user", args.question)]})

    total_input_tokens = 0
    total_output_tokens = 0

    for message in result["messages"]:
        usage = getattr(message, "usage_metadata", None)
        turn_input = usage.get("input_tokens", 0) if usage else 0
        turn_output = usage.get("output_tokens", 0) if usage else 0
        total_input_tokens += turn_input
        total_output_tokens += turn_output

        if not args.verbose:
            continue

        if isinstance(message, AIMessage) and message.tool_calls:
            for call in message.tool_calls:
                print(f"→ calling {call['name']}({call['args']})")
            if usage:
                print(
                    f"  [tokens this turn] input: {turn_input}, output: {turn_output}"
                )
        elif isinstance(message, ToolMessage):
            print(f"← {message.name} returned: {message.content}\n")
        elif isinstance(message, AIMessage) and message.content:
            if usage:
                print(
                    f"  [tokens this turn] input: {turn_input}, output: {turn_output}"
                )

    print(result["messages"][-1].content)
    print(
        (
            f"\n[tokens total] input: {total_input_tokens}, "
            f"output: {total_output_tokens}, "
            f"total: {total_input_tokens + total_output_tokens}"
        )
    )

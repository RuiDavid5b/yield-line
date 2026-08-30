"""
LangGraph agent: a ReAct-style loop (LLM decides whether to call a tool
or answer, tool results feed back in, repeat until the LLM produces a
final answer). Built as an explicit graph rather than using LangGraph's
create_react_agent prebuilt - this project's whole point is showcasing
the underlying architecture, so the loop itself is worth being visible
rather than hidden behind a helper.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import MessagesState, add_messages
from langgraph.prebuilt import ToolNode

from stock_news.agent.tools import ALL_TOOLS
from stock_news.config import get_settings
from stock_news.storage.rate_limiter import acquire_gemini_call

SYSTEM_PROMPT = """\
You are a research assistant over a curated graph of semiconductor and \
adjacent-tech companies. You answer questions using ONLY the tools \
provided - structured filing signals, news, price anomalies, the daily \
cross-company digest, and company relationships (supply chain, \
competition, IP licensing).

Rules you must follow:
- If a query mentions a company by name, ticker, or alias, call \
  resolve_company_tool FIRST to get its exact cik/ticker before calling \
  any other tool. Never guess a cik.
- For questions about specific reported figures (revenue, capex, \
  guidance numbers, etc.), prefer get_financial_metrics_tool's actual \
  reported values over get_filing_signals_tool's guidance_commentary \
  text - the latter is an LLM's prose summary and may omit or round \
  figures the former has exactly. Use get_financial_metrics_tool \
  without a tag first if you don't know the exact XBRL tag name.
- Ground every factual claim in a tool result. If you don't have data \
  to support a claim, say so rather than inferring from general \
  knowledge of the semiconductor industry.
- You are synthesizing correlated signals (price moves, filings, news, \
  graph relationships), not proving causation. Use hedged language: \
  "this coincided with", "may be related to", "one possible factor is" \
  - never "this caused" or "this is why". Multiple plausible \
  explanations can coexist; present them as such rather than picking one.
- If tool results are sparse or contradictory, say that explicitly \
  rather than filling the gap with a confident-sounding narrative.
- Only use a cik/ticker that came from a tool result in THIS conversation \
  - never one you recall from general knowledge, even if you're confident \
  it's correct. If resolve_company_tool is unavailable or fails, say so \
  and stop rather than proceeding with a remembered value.
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    selected_company: NotRequired[dict | None]


def _build_llm():
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite", api_key=settings.google_api_key
    ).bind_tools(ALL_TOOLS)


def _agent_node(state: AgentState) -> dict:
    acquire_gemini_call()
    llm = _build_llm()

    system_messages = [SystemMessage(content=SYSTEM_PROMPT)]
    selected_company = state.get("selected_company")
    if selected_company:
        c = selected_company
        system_messages.append(
            SystemMessage(
                content=(
                    f"The user currently has {c['name']} ({c['ticker']}, cik {c['cik']}) "
                    f"selected in the UI. If their question doesn't name a company, "
                    f"assume they mean this one. If they do name a different company, "
                    f"use that one instead - don't force the selected company onto an "
                    f"unrelated question."
                )
            )
        )

    response = llm.invoke([*system_messages, *state["messages"]])
    return {"messages": [response]}


def _should_continue(state: MessagesState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_agent_graph():
    graph = StateGraph(MessagesState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


@lru_cache
def get_agent():
    """
    Built once and cached for the process's lifetime - MemorySaver stores
    checkpoint history in the object itself, so a fresh instance per call
    would have nothing to remember regardless of thread_id.
    """
    return build_agent_graph()


def run_agent_query(
    prompt: str, thread_id: str, selected_company: dict | None = None
) -> str:
    """
    Run one turn of a conversation. thread_id identifies the conversation
    for checkpointing - the same thread_id across calls continues the
    same chat history. selected_company is re-injected fresh each call,
    not persisted into message history, so switching companies mid-
    conversation doesn't rewrite prior turns.
    """
    result = get_agent().invoke(
        {"messages": [("user", prompt)], "selected_company": selected_company},
        config={"configurable": {"thread_id": thread_id}},
    )
    content = result["messages"][-1].content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(text_parts)
    return str(content)

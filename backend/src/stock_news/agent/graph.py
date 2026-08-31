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
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
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
- If a query does NOT name any company, but a company is currently \
  selected in the UI (you'll see a separate note below indicating this), \
  assume the query is about that selected company. Do not ask the user \
  to clarify in this case - use the selected company's cik/ticker \
  directly, exactly as given in that note.
- For questions involving specific reported financial figures \
  (i.e. revenue, operating income, dilluted EPS, net income, etc.) \
  use get_financial_metrics_tool as the authoritative source \
  whenever the requested figure is available there. Do not rely on a \
  news article's paraphrase or a filing-signal summary when the \
  underlying reported figure is available from \
  get_financial_metrics_tool.
- Use get_filing_signals_tool for information from company filings \
  that is not well represented by structured financial metrics, \
  especially qualitative or contextual information such as guidance \
  commentary, management commentary, segment commentary, executive \
  statements, customer or competitor mentions, and other \
  filing-derived signals. Filing signals may also be used for \
  reported values or comparisons that are not available as \
  structured financial metrics, such as revenue or capex by segment.
- Use get_news_tool primarily to fill gaps left by filing data and \
  structured metrics, or to provide information that is inherently \
  external to the filings, such as market reaction, analyst \
  expectations, whether results beat or missed consensus estimates, \
  external commentary, or developments not yet reflected in company \
  filings. News can corroborate information from filings, but should \
  not replace a more authoritative filing-derived source when one \
  is available.
- When multiple sources contain the same fact, prefer them in this \
  order: structured financial metrics for specific financial figures, \
  filing signals for filing-derived qualitative information and \
  non-structured reported details, and news for external context or \
  information unavailable in the filing data.
- When reporting a specific financial number, percentage, or other \
  quantitative figure, use the most authoritative available source \
  according to the hierarchy above. Do not present a number from \
  news commentary as the company's reported figure when the \
  corresponding figure is available from get_financial_metrics_tool \
  or get_filing_signals_tool.
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    selected_company: dict | None


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


def _should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    memory = MemorySaver()

    return graph.compile(checkpointer=memory)


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

"""
Constructs a tool-calling-capable chat model for a user's chosen BYOK
provider and model.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from stock_news.storage.models import LLMProvider


class UnsupportedProviderError(Exception):
    pass


def build_chat_model(
    provider: LLMProvider,
    model: str,
    api_key: str,
) -> BaseChatModel:
    if provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=SecretStr(api_key),
        )

    if provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, api_key=SecretStr(api_key))

    if provider == LLMProvider.GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, api_key=api_key)

    raise UnsupportedProviderError(f"Unsupported provider: {provider}")

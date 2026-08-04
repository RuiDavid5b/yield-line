from unittest.mock import MagicMock, patch

from stock_news.processing.edgar.routing.classifier import FilingClassification
from stock_news.processing.edgar.signals import (
    DEFAULT_MODEL,
    ExtractedFilingSignal,
    extract_filing_signal,
)


def _classification(
    should_extract: bool, sections: dict[str, str]
) -> FilingClassification:
    return FilingClassification(
        form="10-Q",
        should_extract=should_extract,
        sections=sections,
        item_codes=[],
        item_descriptions=[],
    )


def test_returns_none_without_calling_model_when_should_extract_is_false():
    classification = _classification(should_extract=False, sections={})

    with patch(
        "stock_news.processing.edgar.signals.ChatGoogleGenerativeAI"
    ) as mock_chat_groq:
        result = extract_filing_signal(classification)

    assert result is None
    mock_chat_groq.assert_not_called()


@patch("stock_news.processing.edgar.signals.ChatGoogleGenerativeAI")
def test_calls_model_with_structured_output_schema_when_should_extract_is_true(
    mock_chat_groq,
):
    mock_model = MagicMock()
    mock_structured_model = MagicMock()
    expected_result = ExtractedFilingSignal(
        guidance_commentary="Expects continued demand growth next quarter.",
        mentioned_customers=["AMD Inc"],
    )
    mock_structured_model.invoke.return_value = expected_result
    mock_model.with_structured_output.return_value = mock_structured_model
    mock_chat_groq.return_value = mock_model

    classification = _classification(
        should_extract=True,
        sections={"mdna": "Revenue grew due to strong customer demand."},
    )

    result = extract_filing_signal(classification)

    assert result is expected_result
    mock_model.with_structured_output.assert_called_once_with(ExtractedFilingSignal)
    mock_structured_model.invoke.assert_called_once()


@patch("stock_news.processing.edgar.signals.ChatGoogleGenerativeAI")
def test_combined_text_includes_all_sections_with_labels(mock_chat_groq):
    mock_model = MagicMock()
    mock_structured_model = MagicMock()
    mock_structured_model.invoke.return_value = ExtractedFilingSignal()
    mock_model.with_structured_output.return_value = mock_structured_model
    mock_chat_groq.return_value = mock_model

    classification = _classification(
        should_extract=True,
        sections={
            "mdna": "Revenue commentary here.",
            "market_risk": "Currency exposure commentary here.",
        },
    )

    extract_filing_signal(classification)

    prompt_sent = mock_structured_model.invoke.call_args[0][0]
    assert "[mdna]" in prompt_sent
    assert "Revenue commentary here." in prompt_sent
    assert "[market_risk]" in prompt_sent
    assert "Currency exposure commentary here." in prompt_sent


@patch("stock_news.processing.edgar.signals.ChatGoogleGenerativeAI")
def test_uses_default_model_name_unless_overridden(mock_chat_groq):
    mock_model = MagicMock()
    mock_structured_model = MagicMock()
    mock_structured_model.invoke.return_value = ExtractedFilingSignal()
    mock_model.with_structured_output.return_value = mock_structured_model
    mock_chat_groq.return_value = mock_model

    classification = _classification(should_extract=True, sections={"mdna": "text"})

    extract_filing_signal(classification)

    _, kwargs = mock_chat_groq.call_args
    assert kwargs["model"] == DEFAULT_MODEL


@patch("stock_news.processing.edgar.signals.ChatGoogleGenerativeAI")
def test_respects_explicit_model_override(mock_chat_groq):
    mock_model = MagicMock()
    mock_structured_model = MagicMock()
    mock_structured_model.invoke.return_value = ExtractedFilingSignal()
    mock_model.with_structured_output.return_value = mock_structured_model
    mock_chat_groq.return_value = mock_model

    classification = _classification(should_extract=True, sections={"mdna": "text"})

    extract_filing_signal(classification, model_name="llama-3.1-8b-instant")

    _, kwargs = mock_chat_groq.call_args
    assert kwargs["model"] == "llama-3.1-8b-instant"


def test_extracted_filing_signal_defaults_are_empty_not_none():
    signal = ExtractedFilingSignal()

    assert signal.guidance_commentary == ""
    assert signal.segment_commentary == ""
    assert signal.executive_quote_summary == ""
    assert signal.mentioned_customers == []
    assert signal.mentioned_competitors == []

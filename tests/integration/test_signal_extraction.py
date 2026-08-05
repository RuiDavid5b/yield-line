"""
Live integration test for processing.signals.
"""

import pytest

from stock_news.processing.edgar.routing.classifier import classify_filing
from stock_news.processing.edgar.signals import extract_filing_signal

pytestmark = pytest.mark.requires_env("GOOGLE_API_KEY")

# Mirrors the real structure/content style pulled from an actual NVIDIA
# earnings-related filing
Example_10Q_TEXT = """
Item 2. Management's Discussion and Analysis of Financial Condition and
Results of Operations

Revenue for the quarter was $68.1 billion, up 20% sequentially and up 73%
year-over-year, driven primarily by record Data Center revenue of $62.3
billion. Growth was led by continued strong demand for our latest-generation
AI accelerators from major hyperscale cloud customers, including Cyberion
Cloud Services and Meridian Compute, as both companies significantly
expanded their AI infrastructure deployments during the quarter.

Gaming segment revenue was relatively flat as consumer demand normalized
following prior periods of elevated channel inventory.

Our CEO commented that demand for next-generation AI infrastructure
continues to outpace supply, and that the company is working closely with
its foundry and packaging partners to expand capacity through the next
fiscal year. He also noted increasing competitive pressure from Altera
Compute Systems in the datacenter accelerator market, particularly in
cost-sensitive inference workloads.

Looking ahead, we expect Data Center revenue to continue growing in the
next quarter, though we anticipate gross margins may moderate slightly due
to a higher mix of newer, lower-margin product configurations during the
initial production ramp.

Item 3. Quantitative and Qualitative Disclosures About Market Risk

Our primary market risk exposure relates to foreign currency fluctuations
on international sales and interest rate risk on our investment portfolio.
"""


def test_extracts_meaningful_signal_from_realistic_10q_text():
    classification = classify_filing(Example_10Q_TEXT, form="10-Q")
    assert classification.should_extract
    assert "mdna" in classification.sections

    signal = extract_filing_signal(classification)

    assert signal is not None

    assert signal.guidance_commentary != ""
    assert any(
        keyword in signal.guidance_commentary.lower()
        for keyword in ("data center", "margin", "grow")
    )

    assert signal.segment_commentary != ""
    assert signal.executive_quote_summary != ""
    assert (
        "demand for next-generation AI infrastructure continues to outpace supply"
        not in signal.executive_quote_summary.lower()
    )

    # Named customers and competitor should be found
    assert any(
        "cyberion" in c.lower() or "meridian" in c.lower()
        for c in signal.mentioned_customers
    )
    assert any("altera" in c.lower() for c in signal.mentioned_competitors)

    # A company shouldn't be classified as both a customer and a
    # competitor from the same filing text
    customer_names = {c.lower() for c in signal.mentioned_customers}
    competitor_names = {c.lower() for c in signal.mentioned_competitors}
    assert not (
        customer_names & competitor_names
    ), f"Company appears in both lists: {customer_names & competitor_names}"


def test_low_signal_8k_never_calls_model():
    """Confirms the gating actually holds against the real classifier too,
    not just the mocked version in test_signals.py."""
    low_signal_text = "Item 9.01 Financial Statements and Exhibits\n\n[exhibit list]"

    classification = classify_filing(low_signal_text, form="8-K")
    assert not classification.should_extract

    signal = extract_filing_signal(classification)
    assert signal is None

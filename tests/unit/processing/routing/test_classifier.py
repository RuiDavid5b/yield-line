from stock_news.processing.edgar.routing._periodic import extract_section
from stock_news.processing.edgar.routing.classifier import classify_filing

# Mirrors real 10-Q structure: a Table of Contents lists section headers
# with page numbers, THEN the actual sections appear later in the document
# with the same header text repeated.
TENQ_WITH_TOC_TEXT = """
TABLE OF CONTENTS

PART I - FINANCIAL INFORMATION
Item 1. Financial Statements .................... 4
Item 2. Management's Discussion and Analysis of Financial Condition and Results of Operations .................... 22
Item 3. Quantitative and Qualitative Disclosures About Market Risk .................... 35
Item 4. Controls and Procedures .................... 36

PART II - OTHER INFORMATION
Item 1A. Risk Factors .................... 37
Item 2. Unregistered Sales of Equity Securities .................... 40

PART I - FINANCIAL INFORMATION

Item 1. Financial Statements
[balance sheet, income statement tables here]

Item 2. Management's Discussion and Analysis of Financial Condition and Results of Operations
Revenue grew 20% year over year, driven primarily by strong demand in our
data center segment. We expect this trend to continue into next quarter,
though supply constraints on advanced packaging capacity remain a risk.

Item 3. Quantitative and Qualitative Disclosures About Market Risk
Our primary market risk exposure relates to foreign currency fluctuations
and interest rate changes on our variable-rate debt.

Item 4. Controls and Procedures
Our disclosure controls and procedures were effective as of the end of
the period covered by this report.

PART II - OTHER INFORMATION

Item 1A. Risk Factors
We have added a new risk factor regarding increased tariff exposure on
components sourced from certain regions, which may increase our costs.

Item 2. Unregistered Sales of Equity Securities
None.
"""

TENK_TEXT = """
Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations
Fiscal year revenue increased 35%, led by continued strength in AI
datacenter demand across our largest hyperscaler customers.

Item 7A. Quantitative and Qualitative Disclosures About Market Risk
We are exposed to market risk from changes in interest rates and foreign
currency exchange rates.

Item 8. Financial Statements and Supplementary Data
[financial statements here]
"""


def test_extract_section_skips_table_of_contents_entry():
    """The core gotcha this module exists to handle: a naive first-match
    would grab the TOC line, not the real section."""
    section = extract_section(
        TENQ_WITH_TOC_TEXT,
        start_pattern=r"Item\s*2\.?\s*Management.s\s+Discussion\s+and\s+Analysis",
        end_pattern=r"Item\s*3\.?\s*Quantitative\s+and\s+Qualitative\s+Disclosures",
    )

    assert section is not None
    assert "Revenue grew 20%" in section
    assert "data center segment" in section
    # must not have grabbed the near-empty text between the TOC's Item 2
    # and Item 3 lines
    assert "...." not in section


def test_extract_section_returns_none_when_pattern_not_found():
    section = extract_section(
        "Just some unrelated filing text.",
        start_pattern=r"Item\s*2\.?\s*Management.s\s+Discussion",
        end_pattern=r"Item\s*3\.?\s*Quantitative",
    )

    assert section is None


def test_extract_section_returns_to_end_of_text_when_no_end_marker():
    text = "Item 2. Management's Discussion and Analysis\nSome commentary here."
    section = extract_section(
        text,
        start_pattern=r"Item\s*2\.?\s*Management.s\s+Discussion\s+and\s+Analysis",
        end_pattern=r"Item\s*99\.?\s*Nonexistent",
    )

    assert section == "Some commentary here."


def test_extract_filing_sections_10q_returns_mdna_market_risk_and_risk_updates():
    classification = classify_filing(
        TENQ_WITH_TOC_TEXT,
        form="10-Q",
    )

    assert classification.should_extract
    assert classification.item_codes == []

    assert "mdna" in classification.sections
    assert "data center segment" in classification.sections["mdna"]

    assert "market_risk" in classification.sections
    assert "risk_factor_updates" in classification.sections


def test_extract_filing_sections_10k_uses_item_7_not_item_2():
    classification = classify_filing(
        TENK_TEXT,
        form="10-K",
    )

    assert classification.should_extract

    assert "mdna" in classification.sections
    assert "hyperscaler customers" in classification.sections["mdna"]

    assert "market_risk" in classification.sections
    assert "risk_factor_updates" not in classification.sections


def test_extract_filing_sections_unknown_form_returns_empty_dict():
    classification = classify_filing(
        TENQ_WITH_TOC_TEXT,
        form="S-1",
    )

    assert classification.should_extract is False
    assert classification.sections == {}
    assert classification.item_codes == []


def test_extract_filing_sections_omits_section_not_found():
    classification = classify_filing(
        "Item 7. Management's Discussion and Analysis\nSome commentary.",
        form="10-K",
    )

    assert "mdna" in classification.sections
    assert "market_risk" not in classification.sections


EIGHTK_RESULTS = """
Item 2.02 Results of Operations and Financial Condition

Revenue exceeded expectations.
"""


def test_classify_8k_results_of_operations():
    classification = classify_filing(EIGHTK_RESULTS, form="8-K")

    assert classification.should_extract
    assert classification.item_codes == ["2.02"]
    assert "Results of Operations" in classification.item_descriptions[0]
    assert "body" in classification.sections


LOW_SIGNAL = """
Item 9.01 Financial Statements and Exhibits
"""


def test_classify_low_signal_8k():
    classification = classify_filing(LOW_SIGNAL, form="8-K")

    assert not classification.should_extract
    assert classification.item_codes == ["9.01"]


MULTI = """
Item 2.02 Results of Operations and Financial Condition

...

Item 5.02 Departure of Directors
"""


def test_multiple_items_are_detected():
    classification = classify_filing(MULTI, form="8-K")

    assert classification.item_codes == ["2.02", "5.02"]
    assert classification.should_extract

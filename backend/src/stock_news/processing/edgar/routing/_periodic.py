"""
Deterministic section extraction for 10-Q/10-K filings.
"""

from __future__ import annotations

from ._section_extraction import extract_section

FORM_SECTION_PATTERNS: dict[str, dict[str, tuple[str, str]]] = {
    "10-Q": {
        "mdna": (
            r"Item\s*2\.?\s*Management.s\s+Discussion\s+and\s+Analysis",
            r"Item\s*3\.?\s*Quantitative\s+and\s+Qualitative\s+Disclosures",
        ),
        "market_risk": (
            r"Item\s*3\.?\s*Quantitative\s+and\s+Qualitative\s+Disclosures",
            r"Item\s*4\.?\s*Controls\s+and\s+Procedures",
        ),
        "risk_factor_updates": (
            r"Item\s*1A\.?\s*Risk\s+Factors",
            r"Item\s*2\.?\s*Unregistered\s+Sales",
        ),
    },
    "10-K": {
        "mdna": (
            r"Item\s*7\.?\s*Management.s\s+Discussion\s+and\s+Analysis",
            r"Item\s*7A\.?\s*Quantitative\s+and\s+Qualitative\s+Disclosures",
        ),
        "market_risk": (
            r"Item\s*7A\.?\s*Quantitative\s+and\s+Qualitative\s+Disclosures",
            r"Item\s*8\.?\s*Financial\s+Statements",
        ),
    },
}


def extract_filing_sections(text: str, form: str) -> dict[str, str]:
    """
    Extract all configured sections for a given form type (10-Q or 10-K).
    """
    patterns = FORM_SECTION_PATTERNS.get(form, {})

    sections: dict[str, str] = {}
    for section_name, (start_pattern, end_pattern) in patterns.items():
        extracted = extract_section(text, start_pattern, end_pattern)
        if extracted:
            sections[section_name] = extracted

    return sections

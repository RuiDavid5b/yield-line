"""
Deterministic section extraction for 20-F filings (annual reports for
foreign private issuers).

Two tiers, tried in order:
1. Item-number patterns - for filers whose body text carries literal
   "Item 5"/"Item 6" style headings (e.g. TSMC). Uses fixed end patterns,
   same as _periodic.py's approach for domestic forms.
2. Bare subsection-title patterns, matched to a fixed-length window - for
   filers that omit Item numbers and letter prefixes from body text
   entirely, and whose subsection headings render identically to chapter
   headings, so no boundary between them can be recovered from rendering
   (e.g. ASML).
Tier 2 only runs if tier 1 finds nothing at all.
"""

from __future__ import annotations

from ._section_extraction import extract_section, extract_section_fixed_window


def _item_pattern(number: str, title_pattern: str) -> str:
    return rf"Item\s*{number}(?:\.?[A-Za-z])?\.?\s*{title_pattern}"


QUALITATIVE_QUANTITATIVE = (
    r"(?:"
    r"Quantitative\s+and\s+Qualitative"
    r"|"
    r"Qualitative\s+and\s+Quantitative"
    r")"
)

FORM_20F_SECTION_PATTERNS: dict[str, tuple[str, str]] = {
    "mdna": (
        _item_pattern("5", r"Operating\s+and\s+Financial\s+Reviews?\s+and\s+Prospects"),
        _item_pattern("6", r"Directors,?\s+Senior\s+Management"),
    ),
    "market_risk": (
        _item_pattern(
            "11",
            rf"{QUALITATIVE_QUANTITATIVE}\s+Disclosures",
        ),
        _item_pattern(
            "12",
            r"Description\s+of\s+Securities",
        ),
    ),
    "risk_factor_updates": (
        _item_pattern("3", r"Key\s+Information"),
        _item_pattern("4", r"Information\s+on\s+the\s+Company"),
    ),
}

FORM_20F_SUBSECTION_PATTERNS: dict[str, str] = {
    "mdna": r"Operating\s+Results",
    "risk_factor_updates": r"Trend\s+Information",
}


def extract_20f_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for section_name, (start_pattern, end_pattern) in FORM_20F_SECTION_PATTERNS.items():
        extracted = extract_section(text, start_pattern, end_pattern)
        if extracted:
            sections[section_name] = extracted

    if not sections:
        for section_name, start_pattern in FORM_20F_SUBSECTION_PATTERNS.items():
            extracted = extract_section_fixed_window(text, start_pattern)
            if extracted:
                sections[section_name] = extracted

    return sections

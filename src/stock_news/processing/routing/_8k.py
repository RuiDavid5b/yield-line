"""
Deterministic classification of 8-K filings by their reported Item number(s).
"""

from __future__ import annotations

import re

# Item number -> (description, is_high_signal). High-signal items are the
# ones worth an LLM extraction call. Low-signal items are still classified
# and stored, just not routed to the LLM extraction step by default.
ITEM_REGISTRY: dict[str, tuple[str, bool]] = {
    "1.01": ("Entry into a Material Definitive Agreement", True),
    "1.02": ("Termination of a Material Definitive Agreement", True),
    "2.01": ("Completion of Acquisition or Disposition of Assets", True),
    "2.02": ("Results of Operations and Financial Condition", True),
    "2.03": ("Creation of a Direct Financial Obligation", True),
    "2.04": ("Triggering Events That Accelerate a Direct Financial Obligation", True),
    "5.02": (
        "Departure of Directors or Principal Officers; Election/Appointment",
        True,
    ),
    "5.03": ("Amendments to Articles of Incorporation or Bylaws", False),
    "5.07": ("Submission of Matters to a Vote of Security Holders", False),
    "7.01": ("Regulation FD Disclosure", True),
    "8.01": ("Other Events", True),
    "9.01": ("Financial Statements and Exhibits", False),
}

_ITEM_PATTERN = re.compile(r"Item\s+(\d+\.\d+)", re.IGNORECASE)

# 10-Q and 10-K use a different heading scheme entirely from 8-Ks (plain
# "Item N" within Part I/II, not the "X.XX" decimal format) - MD&A sits at
# a different item number in each form, so each needs its own start/end
# heading pattern to slice out just that section.
_MDNA_SECTION_BOUNDS: dict[str, tuple[re.Pattern, re.Pattern]] = {
    "10-Q": (
        re.compile(
            r"Item\s+2\.?\s+Management.s\s+Discussion\s+and\s+Analysis",
            re.IGNORECASE,
        ),
        re.compile(
            r"Item\s+3\.?\s+Quantitative\s+and\s+Qualitative\s+Disclosures",
            re.IGNORECASE,
        ),
    ),
    "10-K": (
        re.compile(
            r"Item\s+7\.?\s+Management.s\s+Discussion\s+and\s+Analysis",
            re.IGNORECASE,
        ),
        re.compile(
            r"Item\s+8\.?\s+Financial\s+Statements",
            re.IGNORECASE,
        ),
    ),
}


def extract_item_codes(filing_text: str) -> list[str]:
    """
    Parse all "Item X.XX" references out of raw 8-K text.

    Returns codes in the order first encountered, deduplicated. A single
    8-K can report multiple items (e.g. an acquisition that also triggers
    a material agreement item).
    """
    seen: list[str] = []
    for match in _ITEM_PATTERN.finditer(filing_text):
        code = match.group(1)
        if code not in seen:
            seen.append(code)
    return seen


def is_high_signal(item_codes: list[str]) -> bool:
    """
    True if any of the given item codes is worth an LLM extraction call.

    Unknown item codes (not in ITEM_REGISTRY) default to True - erring
    towards "extract it" for a code this project hasn't seen before,
    rather than silently skipping a potentially-relevant filing type.
    """
    return any(ITEM_REGISTRY.get(code, ("", True))[1] for code in item_codes)


def describe_items(item_codes: list[str]) -> list[str]:
    """Human-readable descriptions for a list of item codes, for logging/debugging."""
    return [ITEM_REGISTRY.get(code, ("Unknown item", True))[0] for code in item_codes]

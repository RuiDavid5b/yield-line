"""
Classification/routing of SEC filings.

Decides which portions of a filing are worth sending to the LLM.
It performs only deterministic parsing; no model calls happen here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._8k import (
    describe_items,
    extract_item_codes,
    is_high_signal,
)
from ._20f import extract_20f_sections
from ._periodic import extract_filing_sections


@dataclass(slots=True)
class FilingClassification:
    form: str

    # Whether an LLM extraction should happen at all.
    should_extract: bool

    # Pieces of text to send to the LLM.
    sections: dict[str, str]

    # 8-K only
    item_codes: list[str]

    item_descriptions: list[str]


def classify_filing(
    filing_text: str,
    form: str,
) -> FilingClassification:
    form = form.upper()

    if form == "8-K":
        items = extract_item_codes(filing_text)

        return FilingClassification(
            form=form,
            should_extract=is_high_signal(items),
            sections={"body": filing_text},
            item_codes=items,
            item_descriptions=describe_items(items),
        )

    if form in {"10-Q", "10-K"}:
        sections = extract_filing_sections(filing_text, form)

        return FilingClassification(
            form=form,
            should_extract=bool(sections),
            sections=sections,
            item_codes=[],
            item_descriptions=[],
        )

    if form == "20-F":
        sections = extract_20f_sections(filing_text)

        return FilingClassification(
            form=form,
            should_extract=bool(sections),
            sections=sections,
            item_codes=[],
            item_descriptions=[],
        )

    return FilingClassification(
        form=form,
        should_extract=False,
        sections={},
        item_codes=[],
        item_descriptions=[],
    )

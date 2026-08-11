"""
Generic section-extraction mechanics, shared across form types (10-Q,
10-K, 20-F, and any future form). Form-specific pattern configuration
lives in each form's own routing module (_periodic.py, _20f.py, etc.).
"""

from __future__ import annotations

import re

from stock_news.processing.edgar.html_cleaning import HEADING_SENTINEL

_INLINE_WHITESPACE_COLLAPSE = re.compile(r"[ \t]+")


def _strip_sentinels(text: str) -> str:
    return _INLINE_WHITESPACE_COLLAPSE.sub(
        " ", text.replace(HEADING_SENTINEL, "")
    ).strip()


def _enclosing_paragraph_length(text: str, pos: int) -> int:
    """
    Length of the paragraph/line containing position pos, bounded by the
    nearest newlines on either side. A real heading sits alone in a short
    paragraph; a cross-reference sits embedded within a long paragraph of
    surrounding prose.
    """
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    end = end if end != -1 else len(text)
    return end - start


def extract_section(
    text: str,
    start_pattern: str,
    end_pattern: str,
    min_length: int = 200,
    max_bounded_length: int = 250_000,
    max_unbounded_length: int = 8000,
    start_match_margin: int = 20,
) -> str | None:
    """
    Extract the text between an occurrence of start_pattern and the next
    end_pattern match, choosing whichever occurrence of start_pattern
    yields the longest bounded span. If no occurrence has a discoverable
    end, only unbounded ("ran to end of document") candidates are used
    as a last resort, and the result is capped at max_length.
    """
    start_matches = list(re.finditer(start_pattern, text, re.IGNORECASE))
    if not start_matches:
        return None

    heading_like_matches = [
        m
        for m in start_matches
        if _enclosing_paragraph_length(text, m.start())
        <= len(m.group()) + start_match_margin
    ]
    candidates_source = heading_like_matches or start_matches

    bounded_candidates: list[str] = []
    unbounded_candidates: list[str] = []

    for match in candidates_source:
        start_pos = match.end()
        end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)
        if end_match:
            bounded_candidates.append(
                text[start_pos : start_pos + end_match.start()].strip()
            )
        else:
            unbounded_candidates.append(
                text[start_pos : start_pos + max_unbounded_length].strip()
            )

    substantial_bounded = [c for c in bounded_candidates if len(c) >= min_length]
    if substantial_bounded:
        return _strip_sentinels(min(substantial_bounded, key=len)[:max_bounded_length])

    substantial_unbounded = [c for c in unbounded_candidates if len(c) >= min_length]
    if substantial_unbounded:
        return _strip_sentinels(min(substantial_unbounded, key=len))

    return None


def extract_section_fixed_window(
    text: str,
    start_pattern: str,
    min_length: int = 200,
    max_length: int = 6000,
    start_match_margin: int = 20,
) -> str | None:
    """
    Extract a fixed-length window starting after the highest-confidence
    occurrence of start_pattern, chosen by associated heading font size
    (prefers a real large-font heading over a same-text but body-sized
    occurrence in a table of contents / cross-reference table).

    Used as a last-resort fallback for filers whose sub-section headings
    can't be distinguished from chapter headings by rendering alone (same
    font size/weight/position), so "stop at the next heading" would
    truncate before capturing real content.
    """
    start_matches = list(re.finditer(start_pattern, text, re.IGNORECASE))
    if not start_matches:
        return None

    heading_like_matches = [
        m
        for m in start_matches
        if _enclosing_paragraph_length(text, m.start())
        <= len(m.group()) + start_match_margin
    ]
    candidates_source = heading_like_matches or start_matches

    best_start_pos: int | None = None
    best_distance = -1
    for match in candidates_source:
        start_pos = match.end()
        next_heading = text.find(HEADING_SENTINEL, start_pos)
        distance = (
            (next_heading - start_pos) if next_heading != -1 else len(text) - start_pos
        )
        if distance > best_distance:
            best_distance = distance
            best_start_pos = start_pos

    candidate = text[best_start_pos : best_start_pos + max_length].strip()
    if len(candidate) >= min_length:
        return _strip_sentinels(candidate)
    return None

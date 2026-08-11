"""
Deterministic HTML -> plain text cleaning for raw EDGAR filing documents.

Walks the parsed tree in document order, so headings and financial-data
tables can be handled differently from ordinary prose.
"""

from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup, Comment, Tag
from bs4.element import NavigableString

_MULTIPLE_BLANK_LINES = re.compile(r"\n\s*\n+")
_INLINE_WHITESPACE = re.compile(r"[ \t\u00a0]+")

HEADING_SENTINEL = "§HEADING§"

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# Heading-shaped text: "Item 5.", "Item 5A.", lettered subsections like "A."
_HEADING_LIKE_PATTERN = re.compile(
    r"^\s*(Item\s+\d+[A-Za-z]?\.?|[A-E]\.\s+\S)", re.IGNORECASE
)
_MAX_HEADING_LENGTH = 150

_NUMERIC_CELL_PATTERN = re.compile(r"^\(?-?\$?\d[\d,]*\.?\d*\)?%?$")
_FINANCIAL_TABLE_THRESHOLD = 0.7
_MIN_CELLS_FOR_FINANCIAL_CHECK = 4
_MAX_CELLS_FOR_HEADING_CHECK = 6

_FONT_SIZE_PATTERN = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)pt", re.IGNORECASE)
_DEFAULT_HEADING_RATIO = 1.15


def _is_heading_text(text: str) -> bool:
    stripped = text.strip()

    if not stripped or len(stripped) > _MAX_HEADING_LENGTH:
        return False
    return bool(_HEADING_LIKE_PATTERN.match(stripped))


def _looks_numeric(text: str) -> bool:
    return bool(_NUMERIC_CELL_PATTERN.match(text.strip()))


def _style_font_size(style: str) -> float | None:
    match = _FONT_SIZE_PATTERN.search(style)
    return float(match.group(1)) if match else None


def _compute_body_font_size(soup: BeautifulSoup) -> float | None:
    """
    Find the most common inline font-size across the document, as a proxy
    for body text size. Returns None if no elements carry a font-size
    style.
    """
    sizes = [_style_font_size(el.get("style", "")) for el in soup.find_all(style=True)]
    sizes = [s for s in sizes if s is not None]
    if not sizes:
        return None
    return Counter(sizes).most_common(1)[0][0]


def _is_large_font_element(node: Tag, body_font_size: float | None) -> bool:
    if body_font_size is None:
        return False
    font_size = _style_font_size(node.get("style", ""))
    return (
        font_size is not None and font_size >= body_font_size * _DEFAULT_HEADING_RATIO
    )


def _find_heading_cell(table: Tag) -> str | None:
    cells = table.find_all(["td", "th"])
    if len(cells) > _MAX_CELLS_FOR_HEADING_CHECK:
        return None
    for cell in cells:
        text = cell.get_text(strip=True)
        if _is_heading_text(text):
            return text
    return None


def _financial_table_ratio(table: Tag) -> tuple[float, int]:
    cells = table.find_all(["td", "th"])
    texts = [c.get_text(strip=True) for c in cells]
    non_empty = [t for t in texts if t]
    if not non_empty:
        return 0.0, len(cells)
    numeric_count = sum(1 for t in non_empty if _looks_numeric(t))
    return numeric_count / len(non_empty), len(cells)


def _handle_table(table: Tag, output: list[str]) -> None:
    heading_text = _find_heading_cell(table)
    if heading_text:
        output.append(f"\n{HEADING_SENTINEL} {heading_text}\n")
        return

    ratio, cell_count = _financial_table_ratio(table)
    if (
        cell_count >= _MIN_CELLS_FOR_FINANCIAL_CHECK
        and ratio >= _FINANCIAL_TABLE_THRESHOLD
    ):
        output.append(f"\n[financial table omitted, {cell_count} cells]\n")
        return

    text = table.get_text(" ", strip=True)
    if text:
        output.append(text)
    output.append("\n")


def _extract_heading_text(
    node: Tag,
    body_font_size: float | None,
    detect_font_headings: bool,
) -> str | None:
    name = node.name.lower()

    if name in _HEADING_TAGS:
        return node.get_text(" ", strip=True)

    if detect_font_headings and _is_large_font_element(node, body_font_size):
        text = node.get_text(" ", strip=True)
        if text and len(text) <= _MAX_HEADING_LENGTH:
            return text

    return None


def _walk(
    node: object,
    output: list[str],
    body_font_size: float | None,
    detect_font_headings: bool,
) -> None:
    if isinstance(node, Comment):
        return

    if isinstance(node, NavigableString):
        text = str(node)
        if text.strip():
            output.append(text.strip())
            output.append(" ")
        return

    if not isinstance(node, Tag):
        return

    name = node.name.lower()

    if name in ("script", "style"):
        return

    if name == "table":
        _handle_table(node, output)
        return

    heading_text = _extract_heading_text(
        node,
        body_font_size,
        detect_font_headings,
    )
    if heading_text:
        output.append(f"\n{HEADING_SENTINEL} {heading_text}\n")
        return

    for child in node.children:
        _walk(child, output, body_font_size, detect_font_headings)

    if name in ("p", "div", "tr", "br"):
        output.append("\n")


def clean_filing_html(raw_html: str, detect_font_headings: bool = False) -> str:
    """
    Keyword arguments:
    detect_font_headings: if True, also treats large-font-relative-to-body
        elements as headings. Enable this for form types whose section
        headings may not carry a text-level marker (currently: 20-F).
        Leave False for 8-K/10-Q/10-K, where headings are reliably
        "Item X"-prefixed.
    """
    soup = BeautifulSoup(raw_html, "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    for tag in soup.find_all("ix:header"):
        tag.decompose()

    for tag in soup.find_all(style=lambda s: s and "display:none" in s.lower()):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    body_font_size = _compute_body_font_size(soup) if detect_font_headings else None

    output: list[str] = []
    _walk(soup.body or soup, output, body_font_size, detect_font_headings)

    text = "".join(output)
    text = _INLINE_WHITESPACE.sub(" ", text)
    text = _MULTIPLE_BLANK_LINES.sub("\n\n", text)

    return text.strip()

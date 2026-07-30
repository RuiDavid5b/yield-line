"""
Deterministic HTML -> plain text cleaning for raw EDGAR filing documents.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment

_MULTIPLE_BLANK_LINES = re.compile(r"\n\s*\n+")
_INLINE_WHITESPACE = re.compile(r"[ \t\u00a0]+")


def clean_filing_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    # Remove inline XBRL metadata/header.
    for tag in soup.find_all("ix:header"):
        tag.decompose()

    for tag in soup.find_all(style=lambda s: s and "display:none" in s.lower()):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    text = soup.get_text(separator="\n")

    text = _INLINE_WHITESPACE.sub(" ", text)
    text = _MULTIPLE_BLANK_LINES.sub("\n\n", text)

    return text.strip()

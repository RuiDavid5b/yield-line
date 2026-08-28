"""
Fuzzy company resolution: turns a free-text mention (ticker, full name,
alias - possibly misspelled) into the tracked company/companies it most
likely refers to.
"""

from __future__ import annotations

import difflib
from typing import Any

from sqlalchemy.orm import Session

from stock_news.storage.loaders import get_all_companies

DEFAULT_CUTOFF = 0.6
SUBSTRING_MATCH_SCORE = 0.95


def _score(query: str, candidate: str) -> float:
    query, candidate = query.lower(), candidate.lower()
    if query in candidate or candidate in query:
        return SUBSTRING_MATCH_SCORE
    return difflib.SequenceMatcher(None, query, candidate).ratio()


def resolve_company(
    session: Session, query: str, limit: int = 3, cutoff: float = DEFAULT_CUTOFF
) -> list[dict[str, Any]]:
    """
    Resolve a free-text company reference to tracked companies, ranked
    by match confidence (0-1). An exact ticker match (case-insensitive)
    always wins outright, confidence 1.0, since a ticker is unambiguous
    when it matches exactly - no fuzzy scoring needed or wanted there.
    """
    companies = get_all_companies(session)
    query_lower = query.strip().lower()

    exact_ticker = [c for c in companies if c["ticker"].lower() == query_lower]
    if exact_ticker:
        return [{**c, "match_confidence": 1.0} for c in exact_ticker]

    scored: list[tuple[float, dict]] = []
    for c in companies:
        candidates = [c["ticker"], c["name"], *c.get("aliases", [])]
        best = max(_score(query_lower, cand) for cand in candidates)
        if best >= cutoff:
            scored.append((best, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**c, "match_confidence": round(score, 2)} for score, c in scored[:limit]]

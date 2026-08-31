"""
Ask the agent to explain recent unexplained price anomalies, and persist
the result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from stock_news.agent.graph import run_agent_query
from stock_news.storage.loaders import (
    get_all_companies,
    get_unexplained_price_anomalies,
    set_price_anomaly_explanation,
)

logger = logging.getLogger(__name__)


@dataclass
class AnomalyExplanationResult:
    anomalies_seen: int = 0
    explained: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _build_prompt(anomaly: dict, company: dict) -> str:
    return (
        f"On {anomaly['date']}, {company['name']} ({company['ticker']}) had an "
        f"unusual daily return of {anomaly['return_pct']:.2%} "
        f"(z-score {anomaly['z_score']:.2f}). Using resolve_company_tool first, "
        f"investigate what may have contributed to this move. Prioritize "
        f"get_financial_metrics_tool for specific reported financial figures "
        f"such as revenue or net income when structured values are available. "
        f"Use get_filing_signals_tool for filing-derived qualitative information "
        f"such as guidance commentary, management commentary, operational developments, "
        f"customer or competitor mentions, and other metrics not captured by structured "
        f"metrics, such as revenue or capex changes in a business segment. Use "
        f"get_news_tool primarily to fill gaps or provide additional context "
        f"not available in the filing data, such as market reaction, analyst expectations "
        f"and whether reported results exceeded or fell short of them, external "
        f"events, or broader industry developments. Use graph-neighbor context when it "
        f"provides meaningful additional evidence. "
        f"If you cite a specific financial figure that is available from "
        f"get_financial_metrics_tool, use that value rather than a news article's "
        f"paraphrase. Build the explanation primarily from filing signals and "
        f"financial metrics, with news and graph context used to fill gaps or "
        f"corroborate the explanation. Give a brief, evidence-based, hedged "
        f"explanation of what may have contributed to the move. Do not claim "
        f"causation unless the evidence establishes it. If you find no supporting "
        f"evidence, say so explicitly rather than guessing."
    )


def run_anomaly_explanation_pipeline(
    session: Session, max_age_days: int = 7
) -> AnomalyExplanationResult:
    """
    Explain every unexplained anomaly within max_age_days, one agent
    query each.
    """
    result = AnomalyExplanationResult()

    anomalies = get_unexplained_price_anomalies(session, max_age_days=max_age_days)
    result.anomalies_seen = len(anomalies)
    if not anomalies:
        return result

    companies_by_cik = {c["cik"]: c for c in get_all_companies(session)}

    for anomaly in anomalies:
        company = companies_by_cik.get(anomaly["cik"])
        if company is None:
            logger.warning("Anomaly for unknown cik %s - skipping", anomaly["cik"])
            result.failed += 1
            result.errors.append(f"{anomaly['id']}: unknown cik {anomaly['cik']}")
            continue

        try:
            explanation = run_agent_query(_build_prompt(anomaly, company))
            set_price_anomaly_explanation(session, anomaly["id"], explanation)
            session.commit()
            result.explained += 1
        except Exception as exc:
            session.rollback()
            logger.exception(
                "Failed explaining anomaly id=%s (cik=%s, date=%s)",
                anomaly["id"],
                anomaly["cik"],
                anomaly["date"],
            )
            result.failed += 1
            result.errors.append(f"{anomaly['id']}: {exc}")

    return result


if __name__ == "__main__":
    import logging as _logging
    import sys

    from stock_news.storage.db import get_session_factory

    _logging.basicConfig(level=_logging.INFO)
    session_factory = get_session_factory()
    with session_factory() as session:
        result = run_anomaly_explanation_pipeline(session)

    logger.info("Anomaly explanation result: %s", result)
    if result.failed and result.failed == result.anomalies_seen:
        sys.exit(1)

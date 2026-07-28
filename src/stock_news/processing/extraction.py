"""
Deterministic processing of raw fetch_company_facts() output into clean rows.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

PeriodType = Literal["quarterly", "annual"]

_DURATION_BOUNDS: dict[PeriodType, tuple[int, int]] = {
    "quarterly": (80, 100),
    "annual": (355, 375),
}


def _is_amendment(form: str) -> bool:
    return form.endswith("/A")


def extract_quarterly_metric(
    facts: dict[str, Any],
    cik: str,
    metric_name: str,
    candidate_tags: list[str],
    period_type: PeriodType = "quarterly",
    unit: str = "USD",
) -> list[dict[str, Any]]:
    """
    Extract a clean time series for one metric from raw XBRL data.

    Keyword arguments:
    facts: raw output of ingestion.edgar.fetch_company_facts()
    cik: company CIK identification.
    metric_name: canonical name to store in the output "tag" field.
    candidate_tags: all known XBRL tags that may hold this concept for some
        period of the company's history.
    period_type: which duration bucket to keep ("quarterly" ~ 3 months,
        "annual" ~ 12 months).
    unit: which XBRL unit key to read values from.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    min_days, max_days = _DURATION_BOUNDS[period_type]

    candidates: list[dict[str, Any]] = []
    for xbrl_tag in candidate_tags:
        tag_data = us_gaap.get(xbrl_tag)
        if not tag_data:
            continue

        for entry in tag_data.get("units", {}).get(unit, []):
            start = entry.get("start")
            end = entry.get("end")
            if not start or not end:
                continue

            start_date = dt.date.fromisoformat(start)
            end_date = dt.date.fromisoformat(end)
            duration_days = (end_date - start_date).days

            if not (min_days <= duration_days <= max_days):
                continue

            candidates.append(
                {
                    "period_start": start_date,
                    "period_end": end_date,
                    "value": entry["val"],
                    "form": entry["form"],
                    "accession_number": entry["accn"],
                    "filed_date": dt.date.fromisoformat(entry["filed"]),
                }
            )

    best_entries = _deduplicate_periods(candidates)

    rows = [
        {
            "cik": cik,
            "tag": metric_name,
            "period_start": entry["period_start"],
            "period_end": entry["period_end"],
            "period_type": period_type,
            "value": entry["value"],
            "form": entry["form"],
            "accession_number": entry["accession_number"],
            "filed_date": entry["filed_date"],
        }
        for entry in best_entries
    ]

    rows.sort(key=lambda r: r["period_end"])
    return rows


def _deduplicate_periods(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    best_by_period: dict[tuple[dt.date, dt.date], dict[str, Any]] = {}

    for entry in candidates:
        key = (entry["period_start"], entry["period_end"])
        existing = best_by_period.get(key)

        if existing is None:
            best_by_period[key] = entry
            continue

        existing_is_amendment = _is_amendment(existing["form"])
        entry_is_amendment = _is_amendment(entry["form"])

        if existing_is_amendment and not entry_is_amendment:
            best_by_period[key] = entry
        elif (
            existing_is_amendment == entry_is_amendment
            and entry["filed_date"] > existing["filed_date"]
        ):
            best_by_period[key] = entry

    return list(best_by_period.values())


# Known candidate tags per canonical metric.
GAAP_TAG_CANDIDATES: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}

# Metrics reported under a unit other than "USD".
GAAP_METRIC_UNITS: dict[str, str] = {
    "eps_diluted": "USD/shares",
}

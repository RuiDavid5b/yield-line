"""
Processes raw financial company fact into clean rows.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Sequence

PeriodType = Literal["quarterly", "annual"]

_DURATION_BOUNDS: dict[PeriodType, tuple[int, int]] = {
    "quarterly": (80, 100),
    "annual": (355, 375),
}


def _is_amendment(form: str) -> bool:
    return form.endswith("/A")


def extract_metric(
    facts: dict[str, Any],
    cik: str,
    metric_name: str,
    candidate_tags: list[str],
    period_type: PeriodType = "quarterly",
    units: Sequence[str] = ("USD",),
    taxonomy: str = "us-gaap",
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
    units: unit keys to try, in priority order (e.g. ("USD", "TWD")).
    taxonomy: which XBRL taxonomy namespace to read from ("us-gaap" or
        "ifrs-full").
    """
    taxonomy_facts = facts.get("facts", {}).get(taxonomy, {})
    min_days, max_days = _DURATION_BOUNDS[period_type]

    chosen_unit: str | None = None
    candidates: list[dict[str, Any]] = []

    for unit in units:
        unit_candidates: list[dict[str, Any]] = []
        for xbrl_tag in candidate_tags:
            tag_data = taxonomy_facts.get(xbrl_tag)
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

                unit_candidates.append(
                    {
                        "period_start": start_date,
                        "period_end": end_date,
                        "value": entry["val"],
                        "form": entry["form"],
                        "accession_number": entry["accn"],
                        "filed_date": dt.date.fromisoformat(entry["filed"]),
                    }
                )

        if unit_candidates:
            chosen_unit = unit
            candidates = unit_candidates
            break

    if chosen_unit is None:
        return []

    best_entries = _deduplicate_periods(candidates)

    rows = [
        {
            "cik": cik,
            "tag": metric_name,
            "period_start": entry["period_start"],
            "period_end": entry["period_end"],
            "period_type": period_type,
            "value": entry["value"],
            "unit": chosen_unit,
            "taxonomy": taxonomy,
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


def build_unit_priority(metric_name: str, currencies: list[str]) -> list[str]:
    suffix = UNIT_SUFFIXES.get(metric_name, "")
    return [f"{currency}{suffix}" for currency in currencies]


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
UNIT_SUFFIXES: dict[str, str] = {
    "eps_diluted": "/shares",
}

# For foreign companies
IFRS_TAG_CANDIDATES: dict[str, list[str]] = {
    "revenue": ["Revenue"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["ProfitLossFromOperatingActivities"],
    "net_income": ["ProfitLoss"],
    "eps_diluted": ["DilutedEarningsLossPerShare"],
    "capex": ["PurchaseOfPropertyPlantAndEquipment"],
}

TAG_CANDIDATES_BY_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "us-gaap": GAAP_TAG_CANDIDATES,
    "ifrs-full": IFRS_TAG_CANDIDATES,
}

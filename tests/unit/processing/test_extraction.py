import datetime as dt

from stock_news.processing.edgar.extraction import (
    GAAP_METRIC_UNITS,
    GAAP_TAG_CANDIDATES,
    extract_quarterly_metric,
)


def _usd_entry(start, end, val, form, accn, filed, **extra):
    entry = {
        "start": start,
        "end": end,
        "val": val,
        "accn": accn,
        "fy": 2026,
        "fp": "Q1",
        "form": form,
        "filed": filed,
    }
    entry.update(extra)
    return entry


def test_extracts_quarterly_periods_and_discards_year_to_date():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            # a real quarter (~90 days) - keep
                            _usd_entry(
                                "2026-02-01",
                                "2026-04-30",
                                100,
                                "10-Q",
                                "0001-01",
                                "2026-05-15",
                            ),
                            # a year-to-date figure tagged the same way
                            # (~270 days) - discard
                            _usd_entry(
                                "2025-08-01",
                                "2026-04-30",
                                500,
                                "10-Q",
                                "0001-01",
                                "2026-05-15",
                            ),
                        ]
                    }
                }
            }
        }
    }

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="revenue",
        candidate_tags=["Revenues"],
    )

    assert len(rows) == 1
    assert rows[0]["value"] == 100
    assert rows[0]["period_start"] == dt.date(2026, 2, 1)
    assert rows[0]["period_end"] == dt.date(2026, 4, 30)
    assert rows[0]["tag"] == "revenue"
    assert rows[0]["period_type"] == "quarterly"


def test_unions_results_across_candidate_tags():
    """Mirrors the real ASC 606 transition: older periods under `Revenues`,
    newer periods under the successor tag - both should appear together."""
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            _usd_entry(
                                "2021-08-01",
                                "2021-10-31",
                                100,
                                "10-Q",
                                "0001-01",
                                "2021-11-15",
                            ),
                        ]
                    }
                },
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            _usd_entry(
                                "2025-08-01",
                                "2025-10-31",
                                500,
                                "10-Q",
                                "2025-11-15",
                                "2025-11-15",
                            ),
                        ]
                    }
                },
            }
        }
    }

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="revenue",
        candidate_tags=GAAP_TAG_CANDIDATES["revenue"],
    )

    assert len(rows) == 2
    assert rows[0]["period_end"] < rows[1]["period_end"]
    assert {r["value"] for r in rows} == {100, 500}


def test_prefers_original_filing_over_amendment_for_same_period():
    """Mirrors the real duplicate seen for a company's FY2008 revenue,
    reported once in a 10-K and again in a 10-K/A."""
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            _usd_entry(
                                "2025-11-01",
                                "2026-01-31",
                                100,
                                "10-Q",
                                "0001-01",
                                "2026-02-15",
                            ),
                            _usd_entry(
                                # same period, restated in an amendment,
                                # filed later - should still lose to the
                                # non-amended original
                                "2025-11-01",
                                "2026-01-31",
                                999,
                                "10-Q/A",
                                "0002-02",
                                "2026-03-01",
                            ),
                        ]
                    }
                }
            }
        }
    }

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="revenue",
        candidate_tags=["Revenues"],
    )

    assert len(rows) == 1
    assert rows[0]["value"] == 100
    assert rows[0]["form"] == "10-Q"


def test_breaks_ties_by_most_recently_filed_when_amendment_status_matches():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            _usd_entry(
                                "2025-11-01",
                                "2026-01-31",
                                100,
                                "10-Q",
                                "0001-01",
                                "2026-02-15",
                            ),
                            _usd_entry(
                                "2025-11-01",
                                "2026-01-31",
                                105,
                                "10-Q",
                                "0002-02",
                                "2026-03-01",
                            ),
                        ]
                    }
                }
            }
        }
    }

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="revenue",
        candidate_tags=["Revenues"],
    )

    assert len(rows) == 1
    assert rows[0]["value"] == 105


def test_missing_tag_returns_empty_list_without_error():
    facts = {"facts": {"us-gaap": {}}}

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="revenue",
        candidate_tags=["Revenues", "SomeOtherTag"],
    )

    assert rows == []


def test_annual_period_type_keeps_twelve_month_durations():
    facts = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            _usd_entry(
                                "2025-01-01",
                                "2025-12-31",
                                1000,
                                "10-K",
                                "0001-01",
                                "2026-02-15",
                            ),
                            _usd_entry(
                                # a quarter under the same tag - should be
                                # excluded when requesting annual
                                "2025-10-01",
                                "2025-12-31",
                                300,
                                "10-Q",
                                "0001-01",
                                "2026-02-15",
                            ),
                        ]
                    }
                }
            }
        }
    }

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="net_income",
        candidate_tags=["NetIncomeLoss"],
        period_type="annual",
    )

    assert len(rows) == 1
    assert rows[0]["value"] == 1000
    assert rows[0]["period_type"] == "annual"


def test_skips_entries_without_start_date():
    """Instantaneous concepts (e.g. balance sheet items) have no `start` -
    should be skipped rather than raising."""
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-01-31",
                                "val": 100,
                                "accn": "0001-01",
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-02-15",
                            }
                        ]
                    }
                }
            }
        }
    }

    rows = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="revenue",
        candidate_tags=["Revenues"],
    )

    assert rows == []


def test_reads_from_specified_unit_key_not_just_usd():
    """EPS-style tags are reported under "USD/shares", not "USD" - a value
    sitting under a non-default unit key should still be found when the
    caller specifies it, and NOT be found under the wrong (default) key."""
    facts = {
        "facts": {
            "us-gaap": {
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            _usd_entry(
                                "2026-02-01",
                                "2026-04-30",
                                1.89,
                                "10-Q",
                                "0001-01",
                                "2026-05-15",
                            ),
                        ]
                    }
                }
            }
        }
    }

    rows_with_correct_unit = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="eps_diluted",
        candidate_tags=["EarningsPerShareDiluted"],
        unit="USD/shares",
    )
    rows_with_default_unit = extract_quarterly_metric(
        facts,
        cik="1234",
        metric_name="eps_diluted",
        candidate_tags=["EarningsPerShareDiluted"],
    )

    assert len(rows_with_correct_unit) == 1
    assert rows_with_correct_unit[0]["value"] == 1.89
    assert rows_with_default_unit == []


def test_gaap_metric_units_has_eps_diluted_override():
    assert GAAP_METRIC_UNITS["eps_diluted"] == "USD/shares"
    assert "revenue" not in GAAP_METRIC_UNITS

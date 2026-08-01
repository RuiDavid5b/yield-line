"""
Tests for pipeline.run_company_pipeline's composition logic: skipping
already-processed filings, continuing past a single filing's failure, and
the summary it returns.
"""

from unittest.mock import MagicMock, patch

from stock_news.pipelines.filings import run_company_pipeline

CIK = "0001045810"
USER_AGENT = "Test test@example.com"


def _filing(accession_number, form="8-K", filing_date="2026-05-15"):
    return {
        "cik": CIK,
        "form": form,
        "filing_date": filing_date,
        "accession_number": accession_number,
        "primary_document": "doc.htm",
        "primary_doc_url": f"https://example.com/{accession_number}.htm",
    }


@patch("stock_news.pipelines.filings.upsert_financial_metrics")
@patch("stock_news.pipelines.filings.upsert_filing_signal")
@patch("stock_news.pipelines.filings.extract_filing_signal")
@patch("stock_news.pipelines.filings.classify_filing")
@patch("stock_news.pipelines.filings.fetch_company_facts")
@patch("stock_news.pipelines.filings.fetch_edgar_filing_text")
@patch("stock_news.pipelines.filings.fetch_edgar_filings")
@patch("stock_news.pipelines.filings._get_already_processed_accessions")
def test_processes_new_filings_and_counts_them(
    mock_already_processed,
    mock_fetch_filings,
    mock_fetch_text,
    mock_fetch_facts,
    mock_classify,
    mock_extract,
    mock_upsert_signal,
    mock_upsert_metrics,
):
    mock_already_processed.return_value = set()
    mock_fetch_filings.return_value = [_filing("0001-01")]
    mock_fetch_text.return_value = "filing text"
    mock_classify.return_value = MagicMock(
        should_extract=True, item_codes=["2.02"], sections={"body": "text"}
    )
    mock_extract.return_value = MagicMock()
    mock_fetch_facts.return_value = {"facts": {"us-gaap": {}}}

    session = MagicMock()
    result = run_company_pipeline(CIK, USER_AGENT, session)

    assert result.filings_seen == 1
    assert result.filings_processed == 1
    assert result.filings_skipped_already_processed == 0
    assert result.filings_failed == 0
    mock_upsert_signal.assert_called_once()


@patch("stock_news.pipelines.filings.upsert_financial_metrics")
@patch("stock_news.pipelines.filings.upsert_filing_signal")
@patch("stock_news.pipelines.filings.extract_filing_signal")
@patch("stock_news.pipelines.filings.classify_filing")
@patch("stock_news.pipelines.filings.fetch_edgar_filing_text")
@patch("stock_news.pipelines.filings.fetch_edgar_filings")
@patch("stock_news.pipelines.filings.fetch_company_facts")
@patch("stock_news.pipelines.filings._get_already_processed_accessions")
def test_skips_already_processed_filings_without_fetching_text(
    mock_already_processed,
    mock_fetch_facts,
    mock_fetch_filings,
    mock_fetch_text,
    mock_classify,
    mock_extract,
    mock_upsert_signal,
    mock_upsert_metrics,
):
    mock_already_processed.return_value = {"0001-01"}
    mock_fetch_filings.return_value = [_filing("0001-01")]
    mock_fetch_facts.return_value = {"facts": {"us-gaap": {}}}

    session = MagicMock()
    result = run_company_pipeline(CIK, USER_AGENT, session)

    assert result.filings_seen == 1
    assert result.filings_skipped_already_processed == 1
    assert result.filings_processed == 0
    mock_fetch_text.assert_not_called()
    mock_classify.assert_not_called()
    mock_extract.assert_not_called()
    mock_upsert_signal.assert_not_called()


@patch("stock_news.pipelines.filings.upsert_financial_metrics")
@patch("stock_news.pipelines.filings.upsert_filing_signal")
@patch("stock_news.pipelines.filings.extract_filing_signal")
@patch("stock_news.pipelines.filings.classify_filing")
@patch("stock_news.pipelines.filings.fetch_company_facts")
@patch("stock_news.pipelines.filings.fetch_edgar_filing_text")
@patch("stock_news.pipelines.filings.fetch_edgar_filings")
@patch("stock_news.pipelines.filings._get_already_processed_accessions")
def test_continues_past_a_single_filing_failure(
    mock_already_processed,
    mock_fetch_filings,
    mock_fetch_text,
    mock_fetch_facts,
    mock_classify,
    mock_extract,
    mock_upsert_signal,
    mock_upsert_metrics,
):
    mock_already_processed.return_value = set()
    mock_fetch_filings.return_value = [_filing("0001-01"), _filing("0002-02")]
    # first filing's text fetch fails, second succeeds
    mock_fetch_text.side_effect = [ConnectionError("boom"), "filing text"]
    mock_classify.return_value = MagicMock(
        should_extract=False, item_codes=[], sections={}
    )
    mock_fetch_facts.return_value = {"facts": {"us-gaap": {}}}

    session = MagicMock()
    result = run_company_pipeline(CIK, USER_AGENT, session)

    assert result.filings_seen == 2
    assert result.filings_failed == 1
    assert result.filings_processed == 1
    assert len(result.errors) == 1
    assert "0001-01" in result.errors[0]


@patch("stock_news.pipelines.filings.upsert_financial_metrics")
@patch("stock_news.pipelines.filings.extract_quarterly_metric")
@patch("stock_news.pipelines.filings.fetch_company_facts")
@patch("stock_news.pipelines.filings.fetch_edgar_filings")
@patch("stock_news.pipelines.filings._get_already_processed_accessions")
def test_counts_upserted_financial_metric_rows(
    mock_already_processed,
    mock_fetch_filings,
    mock_fetch_facts,
    mock_extract_metric,
    mock_upsert_metrics,
):
    mock_already_processed.return_value = set()
    mock_fetch_filings.return_value = []
    mock_fetch_facts.return_value = {"facts": {"us-gaap": {}}}
    mock_extract_metric.return_value = [{"value": 100}, {"value": 200}]

    session = MagicMock()
    result = run_company_pipeline(CIK, USER_AGENT, session)

    # 6 tracked metrics (GAAP_TAG_CANDIDATES), 2 rows each in this mock
    assert result.metrics_upserted == 12


@patch("stock_news.pipelines.filings.fetch_company_facts")
@patch("stock_news.pipelines.filings.fetch_edgar_filings")
@patch("stock_news.pipelines.filings._get_already_processed_accessions")
def test_financial_metrics_failure_is_logged_not_raised(
    mock_already_processed,
    mock_fetch_filings,
    mock_fetch_facts,
):
    mock_already_processed.return_value = set()
    mock_fetch_filings.return_value = []
    mock_fetch_facts.side_effect = ConnectionError("EDGAR is down")

    session = MagicMock()
    result = run_company_pipeline(CIK, USER_AGENT, session)  # should not raise

    assert result.metrics_upserted == 0
    assert any("financial_metrics" in e for e in result.errors)

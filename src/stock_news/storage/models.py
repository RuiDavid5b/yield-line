"""
SQLAlchemy table definitions.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"
    cik: Mapped[str] = mapped_column(String(10), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    subarea: Mapped[str] = mapped_column(String(50), index=True)
    financial_metrics: Mapped[list["FinancialMetric"]] = relationship(
        back_populates="company"
    )
    filing_signals: Mapped[list["FilingSignal"]] = relationship(
        back_populates="company"
    )
    stock_prices: Mapped[list["StockPrice"]] = relationship(back_populates="company")


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"
    __table_args__ = (
        UniqueConstraint(
            "cik",
            "tag",
            "period_start",
            "period_end",
            "form",
            name="uq_financial_metric_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[str] = mapped_column(ForeignKey("companies.cik"), index=True)
    tag: Mapped[str] = mapped_column(String(100), index=True)
    period_start: Mapped[dt.date] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date, index=True)
    period_type: Mapped[str] = mapped_column(String(10))
    value: Mapped[float] = mapped_column(Numeric(20, 2))
    form: Mapped[str] = mapped_column(String(10))
    accession_number: Mapped[str] = mapped_column(String(25))
    filed_date: Mapped[dt.date] = mapped_column(Date)

    company: Mapped["Company"] = relationship(back_populates="financial_metrics")


class FilingSignal(Base):
    __tablename__ = "filing_signals"
    __table_args__ = (
        UniqueConstraint(
            "cik",
            "accession_number",
            name="uq_filing_signal_accession",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[str] = mapped_column(ForeignKey("companies.cik"), index=True)
    accession_number: Mapped[str] = mapped_column(String(25), index=True)
    form: Mapped[str] = mapped_column(String(10))
    item_codes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=list)
    # e.g. ["2.02"], ["1.01", "2.03"] - empty list for 10-Q/10-K
    filed_date: Mapped[dt.date] = mapped_column(Date)

    guidance_commentary: Mapped[str | None] = mapped_column(nullable=True)
    segment_commentary: Mapped[str | None] = mapped_column(nullable=True)
    executive_quote_summary: Mapped[str | None] = mapped_column(nullable=True)
    mentioned_customers: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), default=list
    )
    mentioned_competitors: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), default=list
    )

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="filing_signals")


class PendingEdge(Base):
    """
    LLM-proposed additions to the graph skeleton (e.g. a filing mentions a
    new customer/supplier relationship not currently in the curated YAML
    graph).
    """

    __tablename__ = "pending_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_cik: Mapped[str] = mapped_column(ForeignKey("companies.cik"))
    target_name: Mapped[str] = mapped_column(String(255))
    edge_type: Mapped[str] = mapped_column(String(20))
    evidence_accession_number: Mapped[str] = mapped_column(String(25))
    evidence_snippet: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class StockPrice(Base):
    __tablename__ = "stock_prices"
    __table_args__ = (UniqueConstraint("cik", "date", name="uq_stock_price_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[str] = mapped_column(ForeignKey("companies.cik"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4))
    high: Mapped[float] = mapped_column(Numeric(12, 4))
    low: Mapped[float] = mapped_column(Numeric(12, 4))
    close: Mapped[float] = mapped_column(Numeric(12, 4))
    volume: Mapped[int] = mapped_column(BigInteger)

    company: Mapped["Company"] = relationship(back_populates="stock_prices")

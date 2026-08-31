"""Initial schema

Revision ID: 0653162da6f4
Revises:
Create Date: 2026-07-29 23:56:37.031437

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0653162da6f4"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "companies",
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subarea", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("cik"),
    )
    op.create_index(
        op.f("ix_companies_subarea"), "companies", ["subarea"], unique=False
    )
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=True)
    op.create_table(
        "filing_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("accession_number", sa.String(length=25), nullable=False),
        sa.Column("form", sa.String(length=10), nullable=False),
        sa.Column("item_codes", postgresql.ARRAY(sa.String(length=10)), nullable=False),
        sa.Column("filed_date", sa.Date(), nullable=False),
        sa.Column("guidance_commentary", sa.String(), nullable=True),
        sa.Column("segment_commentary", sa.String(), nullable=True),
        sa.Column("executive_quote_summary", sa.String(), nullable=True),
        sa.Column(
            "mentioned_customers",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
        ),
        sa.Column(
            "mentioned_competitors",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cik", "accession_number", name="uq_filing_signal_accession"
        ),
    )
    op.create_index(
        op.f("ix_filing_signals_accession_number"),
        "filing_signals",
        ["accession_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_filing_signals_cik"), "filing_signals", ["cik"], unique=False
    )
    op.create_table(
        "financial_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_type", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("form", sa.String(length=10), nullable=False),
        sa.Column("accession_number", sa.String(length=25), nullable=False),
        sa.Column("filed_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cik",
            "tag",
            "period_start",
            "period_end",
            "form",
            name="uq_financial_metric_period",
        ),
    )
    op.create_index(
        op.f("ix_financial_metrics_cik"), "financial_metrics", ["cik"], unique=False
    )
    op.create_index(
        op.f("ix_financial_metrics_period_end"),
        "financial_metrics",
        ["period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_metrics_tag"), "financial_metrics", ["tag"], unique=False
    )
    op.create_table(
        "pending_edges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_cik", sa.String(length=10), nullable=False),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("edge_type", sa.String(length=20), nullable=False),
        sa.Column("evidence_accession_number", sa.String(length=25), nullable=False),
        sa.Column("evidence_snippet", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["source_cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("pending_edges")
    op.drop_index(op.f("ix_financial_metrics_tag"), table_name="financial_metrics")
    op.drop_index(
        op.f("ix_financial_metrics_period_end"), table_name="financial_metrics"
    )
    op.drop_index(op.f("ix_financial_metrics_cik"), table_name="financial_metrics")
    op.drop_table("financial_metrics")
    op.drop_index(op.f("ix_filing_signals_cik"), table_name="filing_signals")
    op.drop_index(
        op.f("ix_filing_signals_accession_number"), table_name="filing_signals"
    )
    op.drop_table("filing_signals")
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.drop_index(op.f("ix_companies_subarea"), table_name="companies")
    op.drop_table("companies")

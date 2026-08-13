"""add digest tables

Revision ID: 2c4fb2f285eb
Revises: cd0fe094deff
Create Date: 2026-08-13 13:40:15.462124

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c4fb2f285eb"
down_revision: Union[str, Sequence[str], None] = "cd0fe094deff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "benchmark_returns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("return_pct", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "date", name="uq_benchmark_return_date"),
    )
    op.create_index(
        op.f("ix_benchmark_returns_date"), "benchmark_returns", ["date"], unique=False
    )
    op.create_index(
        op.f("ix_benchmark_returns_ticker"),
        "benchmark_returns",
        ["ticker"],
        unique=False,
    )
    op.create_table(
        "digest_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("return_pct", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column(
            "peer_avg_return_pct", sa.Numeric(precision=10, scale=6), nullable=True
        ),
        sa.Column("vs_peer_avg", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("vs_soxx", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("vs_smh", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("vs_spy", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.ForeignKeyConstraint(
            ["cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", "date", name="uq_digest_result_date"),
    )
    op.create_index(
        op.f("ix_digest_results_cik"), "digest_results", ["cik"], unique=False
    )
    op.create_index(
        op.f("ix_digest_results_date"), "digest_results", ["date"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_digest_results_date"), table_name="digest_results")
    op.drop_index(op.f("ix_digest_results_cik"), table_name="digest_results")
    op.drop_table("digest_results")
    op.drop_index(op.f("ix_benchmark_returns_ticker"), table_name="benchmark_returns")
    op.drop_index(op.f("ix_benchmark_returns_date"), table_name="benchmark_returns")
    op.drop_table("benchmark_returns")

"""add PriceAnomalies table

Revision ID: c34cec7cdadc
Revises: cd06b34783da
Create Date: 2026-08-19 19:31:25.043344

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c34cec7cdadc"
down_revision: Union[str, Sequence[str], None] = "cd06b34783da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "price_anomalies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("return_pct", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("z_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", "date", name="uq_anomaly_date"),
    )
    op.create_index(op.f("ix_anomalies_cik"), "price_anomalies", ["cik"], unique=False)
    op.create_index(
        op.f("ix_anomalies_date"), "price_anomalies", ["date"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_anomalies_date"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_cik"), table_name="anomalies")
    op.drop_table("anomalies")

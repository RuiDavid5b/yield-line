"""update PriceAnomalies with higher precision for z_score

Revision ID: 68959e162e79
Revises: c34cec7cdadc
Create Date: 2026-08-19 22:53:14.757131

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "68959e162e79"
down_revision: Union[str, Sequence[str], None] = "c34cec7cdadc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "price_anomalies",
        "z_score",
        existing_type=sa.NUMERIC(precision=10, scale=4),
        type_=sa.Numeric(precision=12, scale=4),
        existing_nullable=False,
    )
    op.drop_index(op.f("ix_anomalies_cik"), table_name="price_anomalies")
    op.drop_index(op.f("ix_anomalies_date"), table_name="price_anomalies")
    op.create_index(
        op.f("ix_price_anomalies_cik"), "price_anomalies", ["cik"], unique=False
    )
    op.create_index(
        op.f("ix_price_anomalies_date"), "price_anomalies", ["date"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_price_anomalies_date"), table_name="price_anomalies")
    op.drop_index(op.f("ix_price_anomalies_cik"), table_name="price_anomalies")
    op.create_index(
        op.f("ix_anomalies_date"), "price_anomalies", ["date"], unique=False
    )
    op.create_index(op.f("ix_anomalies_cik"), "price_anomalies", ["cik"], unique=False)
    op.alter_column(
        "price_anomalies",
        "z_score",
        existing_type=sa.Numeric(precision=12, scale=4),
        type_=sa.NUMERIC(precision=10, scale=4),
        existing_nullable=False,
    )

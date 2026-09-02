"""add z_score_cross_sectional and update z_score to also be nullable

Revision ID: 1d136ab3306b
Revises: 177ce1111e46
Create Date: 2026-09-02 18:54:41.112912

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1d136ab3306b"
down_revision: Union[str, Sequence[str], None] = "177ce1111e46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "price_anomalies",
        sa.Column(
            "z_score_cross_sectional", sa.Numeric(precision=12, scale=4), nullable=True
        ),
    )
    op.alter_column(
        "price_anomalies",
        "z_score",
        existing_type=sa.NUMERIC(precision=12, scale=4),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "price_anomalies",
        "z_score",
        existing_type=sa.NUMERIC(precision=12, scale=4),
        nullable=False,
    )
    op.drop_column("price_anomalies", "z_score_cross_sectional")

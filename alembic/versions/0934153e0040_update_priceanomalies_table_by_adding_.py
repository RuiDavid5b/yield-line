"""update PriceAnomalies table by adding new fields to store the anomaly explanation

Revision ID: 0934153e0040
Revises: 68959e162e79
Create Date: 2026-08-23 20:39:57.061613

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0934153e0040"
down_revision: Union[str, Sequence[str], None] = "68959e162e79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "price_anomalies", sa.Column("explanation", sa.String(), nullable=True)
    )
    op.add_column(
        "price_anomalies", sa.Column("explained_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("price_anomalies", "explained_at")
    op.drop_column("price_anomalies", "explanation")

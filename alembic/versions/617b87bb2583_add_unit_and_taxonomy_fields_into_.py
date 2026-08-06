"""add unit and taxonomy fields into FinancialMetric table to take into account foreign companies

Revision ID: 617b87bb2583
Revises: 77597a8da63f
Create Date: 2026-08-07 13:18:16.157939

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "617b87bb2583"
down_revision: Union[str, Sequence[str], None] = "77597a8da63f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "financial_metrics", sa.Column("unit", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "financial_metrics", sa.Column("taxonomy", sa.String(length=20), nullable=True)
    )

    op.execute(
        "UPDATE financial_metrics SET unit = 'USD', taxonomy = 'us-gaap' "
        "WHERE unit IS NULL"
    )

    op.alter_column("financial_metrics", "unit", nullable=False)
    op.alter_column("financial_metrics", "taxonomy", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("financial_metrics", "taxonomy")
    op.drop_column("financial_metrics", "unit")

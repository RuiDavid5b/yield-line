"""add reporting_currency field in Companies table

Revision ID: cd0fe094deff
Revises: 617b87bb2583
Create Date: 2026-08-07 17:38:14.179383

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd0fe094deff"
down_revision: Union[str, Sequence[str], None] = "617b87bb2583"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "companies",
        sa.Column("reporting_currency", sa.String(length=3), nullable=True),
    )

    op.execute("""
        UPDATE companies SET reporting_currency = 'USD' WHERE reporting_currency IS NULL
        """)

    op.alter_column(
        "companies",
        "reporting_currency",
        existing_type=sa.String(length=3),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companies", "reporting_currency")

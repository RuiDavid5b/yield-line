"""add is_active column to companies table

Revision ID: 35517d3f900b
Revises: ce0ea596d8d4
Create Date: 2026-10-23 11:11:28.330508

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "35517d3f900b"
down_revision: Union[str, Sequence[str], None] = "ce0ea596d8d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "companies",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companies", "is_active")

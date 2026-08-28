"""added aliases and news_disambiguation fields to Company table

Revision ID: cd06b34783da
Revises: 2c4fb2f285eb
Create Date: 2026-08-18 12:02:34.329694

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd06b34783da"
down_revision: Union[str, Sequence[str], None] = "2c4fb2f285eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "companies",
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "news_disambiguation",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.alter_column("companies", "aliases", server_default=None)
    op.alter_column("companies", "news_disambiguation", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companies", "news_disambiguation")
    op.drop_column("companies", "aliases")

"""add BYOK fields in User table

Revision ID: ce0ea596d8d4
Revises: 21dbc7339025
Create Date: 2026-09-25 19:42:03.183554

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ce0ea596d8d4"
down_revision: Union[str, Sequence[str], None] = "21dbc7339025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("llm_provider", sa.String(length=20), nullable=True)
    )
    op.add_column("users", sa.Column("llm_model", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("encrypted_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "encrypted_api_key")
    op.drop_column("users", "llm_model")
    op.drop_column("users", "llm_provider")

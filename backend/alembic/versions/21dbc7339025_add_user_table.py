"""add User table

Revision ID: 21dbc7339025
Revises: 62d993fca846
Create Date: 2026-09-24 15:06:06.980901

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "21dbc7339025"
down_revision: Union[str, Sequence[str], None] = "62d993fca846"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cognito_sub", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cognito_sub", name="uq_user_cognito_sub"),
    )
    op.create_index(
        op.f("ix_users_cognito_sub"), "users", ["cognito_sub"], unique=False
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_cognito_sub"), table_name="users")
    op.drop_table("users")

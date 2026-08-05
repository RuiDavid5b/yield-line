"""change company's field name from subarea to industry_segment

Revision ID: 77597a8da63f
Revises: 4139c92ba731
Create Date: 2026-08-06 13:45:04.066523

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77597a8da63f"
down_revision: Union[str, Sequence[str], None] = "4139c92ba731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "companies",
        "subarea",
        new_column_name="industry_segment",
    )
    op.drop_index(op.f("ix_companies_subarea"), table_name="companies")
    op.create_index(
        op.f("ix_companies_industry_segment"),
        "companies",
        ["industry_segment"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_companies_industry_segment"), table_name="companies")
    op.alter_column(
        "companies",
        "industry_segment",
        new_column_name="subarea",
    )
    op.create_index(
        op.f("ix_companies_subarea"),
        "companies",
        ["subarea"],
        unique=False,
    )

"""add table for stock prices

Revision ID: fbd284eb40ee
Revises: 0653162da6f4
Create Date: 2026-08-01 17:26:32.935325

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fbd284eb40ee"
down_revision: Union[str, Sequence[str], None] = "0653162da6f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "stock_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", "date", name="uq_stock_price_date"),
    )
    op.create_index(op.f("ix_stock_prices_cik"), "stock_prices", ["cik"], unique=False)
    op.create_index(
        op.f("ix_stock_prices_date"), "stock_prices", ["date"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_stock_prices_date"), table_name="stock_prices")
    op.drop_index(op.f("ix_stock_prices_cik"), table_name="stock_prices")
    op.drop_table("stock_prices")

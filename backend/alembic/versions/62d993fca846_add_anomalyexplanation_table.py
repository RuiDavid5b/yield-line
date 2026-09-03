"""add AnomalyExplanation table

Revision ID: 62d993fca846
Revises: 177ce1111e46
Create Date: 2026-09-04 00:23:15.646119

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "62d993fca846"
down_revision: Union[str, Sequence[str], None] = "177ce1111e46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "anomaly_explanations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column(
            "explained_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cik"],
            ["companies.cik"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", "date", name="uq_anomaly_explanation_date"),
    )
    op.create_index(
        op.f("ix_anomaly_explanations_cik"),
        "anomaly_explanations",
        ["cik"],
        unique=False,
    )
    op.create_index(
        op.f("ix_anomaly_explanations_date"),
        "anomaly_explanations",
        ["date"],
        unique=False,
    )

    op.execute("""
        INSERT INTO anomaly_explanations (cik, date, explanation, explained_at)
        SELECT cik, date, explanation, explained_at
        FROM price_anomalies
        WHERE explanation IS NOT NULL
    """)
    op.drop_column("price_anomalies", "explanation")
    op.drop_column("price_anomalies", "explained_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "price_anomalies", sa.Column("explanation", sa.String(), nullable=True)
    )
    op.add_column(
        "price_anomalies", sa.Column("explained_at", sa.DateTime(), nullable=True)
    )
    op.execute("""
        UPDATE price_anomalies a
        SET explanation = ae.explanation, explained_at = ae.explained_at
        FROM anomaly_explanations ae
        WHERE a.cik = ae.cik AND a.date = ae.date
    """)

    op.drop_index(
        op.f("ix_anomaly_explanations_date"), table_name="anomaly_explanations"
    )
    op.drop_index(
        op.f("ix_anomaly_explanations_cik"), table_name="anomaly_explanations"
    )
    op.drop_table("anomaly_explanations")

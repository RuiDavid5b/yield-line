"""update DigestResult table to add 2 columns for cross-sectional anomalies

Revision ID: 177ce1111e46
Revises: 0934153e0040
Create Date: 2026-08-27 23:19:54.472817

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "177ce1111e46"
down_revision: Union[str, Sequence[str], None] = "0934153e0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "digest_results",
        sa.Column(
            "cross_sectional_z_score", sa.Numeric(precision=10, scale=4), nullable=True
        ),
    )
    op.add_column(
        "digest_results",
        sa.Column(
            "is_cross_sectional_anomaly",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("digest_results", "is_cross_sectional_anomaly")
    op.drop_column("digest_results", "cross_sectional_z_score")

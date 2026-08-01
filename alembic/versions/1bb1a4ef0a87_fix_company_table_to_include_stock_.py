"""fix company table to include stock_prices attribute

Revision ID: 1bb1a4ef0a87
Revises: fbd284eb40ee
Create Date: 2026-08-02 19:15:18.287995

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "1bb1a4ef0a87"
down_revision: Union[str, Sequence[str], None] = "fbd284eb40ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

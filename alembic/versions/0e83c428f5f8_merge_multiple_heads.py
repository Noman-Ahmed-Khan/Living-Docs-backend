"""Merge multiple heads

Revision ID: 0e83c428f5f8
Revises: 7c2d91b9e4c1, b1f7a0c2d8e4
Create Date: 2026-04-20 18:35:20.991685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e83c428f5f8'
down_revision: Union[str, Sequence[str], None] = ('7c2d91b9e4c1', 'b1f7a0c2d8e4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

"""Add full_name to users

Revision ID: b1f7a0c2d8e4
Revises: 1786c97b04b2
Create Date: 2026-04-17 18:24:39.515000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f7a0c2d8e4'
down_revision: Union[str, Sequence[str], None] = '1786c97b04b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('full_name', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'full_name')

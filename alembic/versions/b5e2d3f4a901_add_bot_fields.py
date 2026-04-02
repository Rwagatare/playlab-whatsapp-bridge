"""add bot fields to users and conversations

Revision ID: b5e2d3f4a901
Revises: a3f1c8b72d01
Create Date: 2026-04-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e2d3f4a901'
down_revision: Union[str, None] = 'a3f1c8b72d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('active_bot', sa.String(length=64), nullable=True))
    op.add_column('conversations', sa.Column('bot_key', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'bot_key')
    op.drop_column('users', 'active_bot')

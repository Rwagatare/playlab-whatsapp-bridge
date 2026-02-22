"""add external_id to conversations

Revision ID: a3f1c8b72d01
Revises: d18e0a902e85
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c8b72d01'
down_revision: Union[str, None] = 'd18e0a902e85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('external_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'external_id')

"""add_is_reprocessing_field

Revision ID: c7d9e4f2a1b8
Revises: b6c8af39fe07
Create Date: 2025-11-26 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d9e4f2a1b8'
down_revision = 'b6c8af39fe07'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_reprocessing column to surfing_sessions table
    op.add_column('surfing_sessions', sa.Column('is_reprocessing', sa.String(length=50), nullable=True))


def downgrade() -> None:
    # Drop is_reprocessing column from surfing_sessions
    op.drop_column('surfing_sessions', 'is_reprocessing')

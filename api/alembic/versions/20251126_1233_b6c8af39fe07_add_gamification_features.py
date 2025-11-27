"""add_gamification_features

Revision ID: b6c8af39fe07
Revises:
Create Date: 2025-11-26 12:33:45.420616

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision = 'b6c8af39fe07'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add score column to surfing_sessions table
    op.add_column('surfing_sessions', sa.Column('score', sa.Float(), nullable=True))
    op.create_index(op.f('ix_surfing_sessions_score'), 'surfing_sessions', ['score'], unique=False)

    # Note: session_rankings table already exists in database, skipping creation


def downgrade() -> None:
    # Drop score column from surfing_sessions
    op.drop_index(op.f('ix_surfing_sessions_score'), table_name='surfing_sessions')
    op.drop_column('surfing_sessions', 'score')

    # Note: Not dropping session_rankings table as it was pre-existing

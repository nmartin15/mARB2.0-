"""add_denial_patterns_composite_index

Revision ID: 29e24b6efe05
Revises: b8e3f1615602
Create Date: 2025-12-23 14:03:54.846895

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29e24b6efe05'
down_revision = 'b8e3f1615602'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for denial_patterns: payer_id + denial_reason_code
    # Used in pattern_detector when checking if pattern already exists
    op.create_index(
        'ix_denial_patterns_payer_reason',
        'denial_patterns',
        ['payer_id', 'denial_reason_code'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_denial_patterns_payer_reason', table_name='denial_patterns')


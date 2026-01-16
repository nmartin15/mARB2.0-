"""add_composite_indexes

Revision ID: b8e3f1615602
Revises: 72611b4a3cf5
Create Date: 2025-12-23 14:03:00.678392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e3f1615602'
down_revision = '72611b4a3cf5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for remittances: payer_id + created_at
    # Used in pattern detection queries (pattern_detector.py)
    op.create_index(
        'ix_remittances_payer_created',
        'remittances',
        ['payer_id', 'created_at'],
        unique=False
    )
    
    # Composite index for claim_episodes: status + denial_count
    # Used in pattern detection to find episodes with denials
    op.create_index(
        'ix_claim_episodes_status_denial',
        'claim_episodes',
        ['status', 'denial_count'],
        unique=False
    )
    
    # Composite index for claim_episodes: remittance_id + status
    # Common pattern for querying episodes by remittance and status
    op.create_index(
        'ix_claim_episodes_remittance_status',
        'claim_episodes',
        ['remittance_id', 'status'],
        unique=False
    )
    
    # Index on updated_at for claims (for recently updated queries)
    op.create_index(
        'ix_claims_updated_at',
        'claims',
        ['updated_at'],
        unique=False
    )
    
    # Index on updated_at for remittances (for recently updated queries)
    op.create_index(
        'ix_remittances_updated_at',
        'remittances',
        ['updated_at'],
        unique=False
    )
    
    # Index on updated_at for claim_episodes (for recently updated queries)
    op.create_index(
        'ix_claim_episodes_updated_at',
        'claim_episodes',
        ['updated_at'],
        unique=False
    )
    


def downgrade() -> None:
    # Drop updated_at indexes
    op.drop_index('ix_claim_episodes_updated_at', table_name='claim_episodes')
    op.drop_index('ix_remittances_updated_at', table_name='remittances')
    op.drop_index('ix_claims_updated_at', table_name='claims')
    
    # Drop composite indexes
    op.drop_index('ix_claim_episodes_remittance_status', table_name='claim_episodes')
    op.drop_index('ix_claim_episodes_status_denial', table_name='claim_episodes')
    op.drop_index('ix_remittances_payer_created', table_name='remittances')


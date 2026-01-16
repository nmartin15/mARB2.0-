"""Add performance indexes

Revision ID: 002_performance_indexes
Revises: 001_initial
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_performance_indexes'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Indexes for claims table - frequently queried columns
    op.create_index(
        'ix_claims_payer_id',
        'claims',
        ['payer_id'],
        unique=False
    )
    op.create_index(
        'ix_claims_provider_id',
        'claims',
        ['provider_id'],
        unique=False
    )
    op.create_index(
        'ix_claims_practice_id',
        'claims',
        ['practice_id'],
        unique=False
    )
    op.create_index(
        'ix_claims_created_at',
        'claims',
        ['created_at'],
        unique=False
    )
    
    # Indexes for remittances table
    op.create_index(
        'ix_remittances_payer_id',
        'remittances',
        ['payer_id'],
        unique=False
    )
    op.create_index(
        'ix_remittances_created_at',
        'remittances',
        ['created_at'],
        unique=False
    )
    
    # Indexes for claim_episodes table
    op.create_index(
        'ix_claim_episodes_claim_id',
        'claim_episodes',
        ['claim_id'],
        unique=False
    )
    op.create_index(
        'ix_claim_episodes_remittance_id',
        'claim_episodes',
        ['remittance_id'],
        unique=False
    )
    op.create_index(
        'ix_claim_episodes_created_at',
        'claim_episodes',
        ['created_at'],
        unique=False
    )
    
    # Indexes for claim_lines table
    op.create_index(
        'ix_claim_lines_claim_id',
        'claim_lines',
        ['claim_id'],
        unique=False
    )
    
    # Indexes for risk_scores table
    op.create_index(
        'ix_risk_scores_claim_id',
        'risk_scores',
        ['claim_id'],
        unique=False
    )
    op.create_index(
        'ix_risk_scores_calculated_at',
        'risk_scores',
        ['calculated_at'],
        unique=False
    )
    
    # Indexes for denial_patterns table
    op.create_index(
        'ix_denial_patterns_payer_id',
        'denial_patterns',
        ['payer_id'],
        unique=False
    )
    
    # Composite index for common query pattern: claims by payer and status
    op.create_index(
        'ix_claims_payer_status',
        'claims',
        ['payer_id', 'status'],
        unique=False
    )


def downgrade() -> None:
    # Drop composite index
    op.drop_index('ix_claims_payer_status', table_name='claims')
    
    # Drop denial_patterns indexes
    op.drop_index('ix_denial_patterns_payer_id', table_name='denial_patterns')
    
    # Drop risk_scores indexes
    op.drop_index('ix_risk_scores_calculated_at', table_name='risk_scores')
    op.drop_index('ix_risk_scores_claim_id', table_name='risk_scores')
    
    # Drop claim_lines indexes
    op.drop_index('ix_claim_lines_claim_id', table_name='claim_lines')
    
    # Drop claim_episodes indexes
    op.drop_index('ix_claim_episodes_created_at', table_name='claim_episodes')
    op.drop_index('ix_claim_episodes_remittance_id', table_name='claim_episodes')
    op.drop_index('ix_claim_episodes_claim_id', table_name='claim_episodes')
    
    # Drop remittances indexes
    op.drop_index('ix_remittances_created_at', table_name='remittances')
    op.drop_index('ix_remittances_payer_id', table_name='remittances')
    
    # Drop claims indexes
    op.drop_index('ix_claims_created_at', table_name='claims')
    op.drop_index('ix_claims_practice_id', table_name='claims')
    op.drop_index('ix_claims_provider_id', table_name='claims')
    op.drop_index('ix_claims_payer_id', table_name='claims')


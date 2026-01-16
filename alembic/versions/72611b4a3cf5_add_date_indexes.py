"""add_date_indexes

Revision ID: 72611b4a3cf5
Revises: 002_performance_indexes
Create Date: 2025-12-23 14:00:23.687885

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72611b4a3cf5'
down_revision = '002_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Index for service_date on claims table (frequently filtered by date)
    op.create_index(
        'ix_claims_service_date',
        'claims',
        ['service_date'],
        unique=False
    )
    
    # Index for payment_date on remittances table (frequently filtered by date)
    op.create_index(
        'ix_remittances_payment_date',
        'remittances',
        ['payment_date'],
        unique=False
    )
    
    # Index for service_date on claim_lines table (for line-level date queries)
    op.create_index(
        'ix_claim_lines_service_date',
        'claim_lines',
        ['service_date'],
        unique=False
    )


def downgrade() -> None:
    # Drop claim_lines index
    op.drop_index('ix_claim_lines_service_date', table_name='claim_lines')
    
    # Drop remittances index
    op.drop_index('ix_remittances_payment_date', table_name='remittances')
    
    # Drop claims index
    op.drop_index('ix_claims_service_date', table_name='claims')


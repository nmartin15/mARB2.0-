"""add_audit_logs_table

Revision ID: 307ab2d8c272
Revises: 29e24b6efe05
Create Date: 2025-12-27 18:16:27.423152

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '307ab2d8c272'
down_revision = '29e24b6efe05'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_logs table for HIPAA-compliant audit trail
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('request_identifier', sa.String(length=64), nullable=True),
        sa.Column('response_identifier', sa.String(length=64), nullable=True),
        sa.Column('request_hashed_identifiers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('response_hashed_identifiers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_method'), 'audit_logs', ['method'], unique=False)
    op.create_index(op.f('ix_audit_logs_path'), 'audit_logs', ['path'], unique=False)
    op.create_index(op.f('ix_audit_logs_status_code'), 'audit_logs', ['status_code'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_status_code'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_path'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_method'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    
    # Drop table
    op.drop_table('audit_logs')


"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create providers table
    op.create_table(
        'providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('npi', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('specialty', sa.String(length=100), nullable=True),
        sa.Column('taxonomy_code', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_providers_id'), 'providers', ['id'], unique=False)
    op.create_index(op.f('ix_providers_npi'), 'providers', ['npi'], unique=True)

    # Create payers table
    op.create_table(
        'payers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payer_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('payer_type', sa.String(length=50), nullable=True),
        sa.Column('rules_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payers_id'), 'payers', ['id'], unique=False)
    op.create_index(op.f('ix_payers_payer_id'), 'payers', ['payer_id'], unique=True)

    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payer_id', sa.Integer(), nullable=False),
        sa.Column('plan_name', sa.String(length=255), nullable=True),
        sa.Column('plan_type', sa.String(length=50), nullable=True),
        sa.Column('benefit_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payer_id'], ['payers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create practice_configs table
    op.create_table(
        'practice_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practice_id', sa.String(length=50), nullable=False),
        sa.Column('practice_name', sa.String(length=255), nullable=False),
        sa.Column('segment_expectations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('payer_specific_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_practice_configs_practice_id'), 'practice_configs', ['practice_id'], unique=True)

    # Create claims table
    op.create_table(
        'claims',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_control_number', sa.String(length=50), nullable=False),
        sa.Column('patient_control_number', sa.String(length=50), nullable=True),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('payer_id', sa.Integer(), nullable=True),
        sa.Column('total_charge_amount', sa.Float(), nullable=True),
        sa.Column('facility_type_code', sa.String(length=2), nullable=True),
        sa.Column('claim_frequency_type', sa.String(length=1), nullable=True),
        sa.Column('assignment_code', sa.String(length=1), nullable=True),
        sa.Column('statement_date', sa.DateTime(), nullable=True),
        sa.Column('admission_date', sa.DateTime(), nullable=True),
        sa.Column('discharge_date', sa.DateTime(), nullable=True),
        sa.Column('service_date', sa.DateTime(), nullable=True),
        sa.Column('diagnosis_codes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('principal_diagnosis', sa.String(length=10), nullable=True),
        sa.Column('attending_provider_npi', sa.String(length=10), nullable=True),
        sa.Column('operating_provider_npi', sa.String(length=10), nullable=True),
        sa.Column('referring_provider_npi', sa.String(length=10), nullable=True),
        sa.Column('raw_edi_data', sa.Text(), nullable=True),
        sa.Column('parsed_segments', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSED', 'INCOMPLETE', 'ERROR', name='claimstatus'), nullable=True),
        sa.Column('is_incomplete', sa.Boolean(), nullable=True),
        sa.Column('parsing_warnings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('practice_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
        sa.ForeignKeyConstraint(['payer_id'], ['payers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claims_id'), 'claims', ['id'], unique=False)
    op.create_index(op.f('ix_claims_claim_control_number'), 'claims', ['claim_control_number'], unique=True)
    op.create_index(op.f('ix_claims_patient_control_number'), 'claims', ['patient_control_number'], unique=False)
    op.create_index(op.f('ix_claims_status'), 'claims', ['status'], unique=False)

    # Create claim_lines table
    op.create_table(
        'claim_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.String(length=10), nullable=False),
        sa.Column('revenue_code', sa.String(length=10), nullable=True),
        sa.Column('procedure_code', sa.String(length=10), nullable=True),
        sa.Column('procedure_modifier', sa.String(length=10), nullable=True),
        sa.Column('charge_amount', sa.Float(), nullable=True),
        sa.Column('unit_count', sa.Float(), nullable=True),
        sa.Column('unit_type', sa.String(length=2), nullable=True),
        sa.Column('service_date', sa.DateTime(), nullable=True),
        sa.Column('raw_segment_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create remittances table
    op.create_table(
        'remittances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('remittance_control_number', sa.String(length=50), nullable=False),
        sa.Column('payer_id', sa.Integer(), nullable=True),
        sa.Column('payer_name', sa.String(length=255), nullable=True),
        sa.Column('payment_amount', sa.Float(), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('check_number', sa.String(length=50), nullable=True),
        sa.Column('claim_control_number', sa.String(length=50), nullable=True),
        sa.Column('denial_reasons', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('adjustment_reasons', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_edi_data', sa.Text(), nullable=True),
        sa.Column('parsed_segments', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSED', 'ERROR', name='remittancestatus'), nullable=True),
        sa.Column('parsing_warnings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payer_id'], ['payers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_remittances_id'), 'remittances', ['id'], unique=False)
    op.create_index(op.f('ix_remittances_remittance_control_number'), 'remittances', ['remittance_control_number'], unique=True)
    op.create_index(op.f('ix_remittances_claim_control_number'), 'remittances', ['claim_control_number'], unique=False)
    op.create_index(op.f('ix_remittances_status'), 'remittances', ['status'], unique=False)

    # Create claim_episodes table
    op.create_table(
        'claim_episodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('remittance_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'LINKED', 'COMPLETE', name='episodestatus'), nullable=True),
        sa.Column('linked_at', sa.DateTime(), nullable=True),
        sa.Column('payment_amount', sa.Float(), nullable=True),
        sa.Column('denial_count', sa.Integer(), nullable=True),
        sa.Column('adjustment_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ),
        sa.ForeignKeyConstraint(['remittance_id'], ['remittances.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claim_episodes_id'), 'claim_episodes', ['id'], unique=False)
    op.create_index(op.f('ix_claim_episodes_status'), 'claim_episodes', ['status'], unique=False)

    # Create denial_patterns table
    op.create_table(
        'denial_patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payer_id', sa.Integer(), nullable=True),
        sa.Column('pattern_type', sa.String(length=50), nullable=True),
        sa.Column('pattern_description', sa.Text(), nullable=True),
        sa.Column('denial_reason_code', sa.String(length=10), nullable=True),
        sa.Column('occurrence_count', sa.Integer(), nullable=True),
        sa.Column('frequency', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('conditions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payer_id'], ['payers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create risk_scores table
    op.create_table(
        'risk_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='risklevel'), nullable=False),
        sa.Column('coding_risk', sa.Float(), nullable=True),
        sa.Column('documentation_risk', sa.Float(), nullable=True),
        sa.Column('payer_risk', sa.Float(), nullable=True),
        sa.Column('historical_risk', sa.Float(), nullable=True),
        sa.Column('risk_factors', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('recommendations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('model_confidence', sa.Float(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_risk_scores_id'), 'risk_scores', ['id'], unique=False)
    op.create_index(op.f('ix_risk_scores_risk_level'), 'risk_scores', ['risk_level'], unique=False)

    # Create parser_logs table
    op.create_table(
        'parser_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=10), nullable=True),
        sa.Column('log_level', sa.String(length=20), nullable=True),
        sa.Column('segment_type', sa.String(length=10), nullable=True),
        sa.Column('issue_type', sa.String(length=50), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('claim_control_number', sa.String(length=50), nullable=True),
        sa.Column('practice_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parser_logs_id'), 'parser_logs', ['id'], unique=False)
    op.create_index(op.f('ix_parser_logs_created_at'), 'parser_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('parser_logs')
    op.drop_table('risk_scores')
    op.drop_table('denial_patterns')
    op.drop_table('claim_episodes')
    op.drop_table('remittances')
    op.drop_table('claim_lines')
    op.drop_table('claims')
    op.drop_table('practice_configs')
    op.drop_table('plans')
    op.drop_table('payers')
    op.drop_table('providers')
    
    # Drop enums
    sa.Enum(name='claimstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='remittancestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='episodestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='risklevel').drop(op.get_bind(), checkfirst=True)


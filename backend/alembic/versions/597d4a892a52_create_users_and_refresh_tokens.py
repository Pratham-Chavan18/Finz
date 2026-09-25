"""create_full_schema

Revision ID: 597d4a892a52
Revises: 
Create Date: 2026-09-24 19:19:49.502395

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '597d4a892a52'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('plan', sa.String(length=50), server_default='STARTER', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)

    # 2. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='ADMIN', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)

    # 3. Refresh tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_refresh_tokens_id'), 'refresh_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)

    # 4. Import batches table
    op.create_table(
        'import_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('total_records', sa.Integer(), server_default='0', nullable=False),
        sa.Column('processed_records', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_batches_id'), 'import_batches', ['id'], unique=False)
    op.create_index(op.f('ix_import_batches_tenant_id'), 'import_batches', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_batches_status'), 'import_batches', ['status'], unique=False)

    # 5. Transactions table (with Numeric(15, 2) and JSON raw_data)
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('import_batch_id', sa.Integer(), nullable=True),
        sa.Column('transaction_code', sa.String(length=50), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('counterparty', sa.String(length=255), nullable=True),
        sa.Column('raw_payee', sa.String(length=255), nullable=True),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('method', sa.String(length=100), nullable=True),
        sa.Column('account_name', sa.String(length=100), server_default='Primary Checking', nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('pnl_bucket', sa.String(length=50), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('is_flagged_for_review', sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column('review_status', sa.String(length=50), server_default='pending', nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index(op.f('ix_transactions_tenant_id'), 'transactions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_transactions_import_batch_id'), 'transactions', ['import_batch_id'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_code'), 'transactions', ['transaction_code'], unique=False)
    op.create_index(op.f('ix_transactions_date'), 'transactions', ['date'], unique=False)
    op.create_index(op.f('ix_transactions_category'), 'transactions', ['category'], unique=False)
    op.create_index(op.f('ix_transactions_pnl_bucket'), 'transactions', ['pnl_bucket'], unique=False)
    op.create_index(op.f('ix_transactions_is_flagged_for_review'), 'transactions', ['is_flagged_for_review'], unique=False)

    # 6. Audit logs table (survives transaction deletion with SET NULL)
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), server_default='transaction', nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('action', sa.String(length=50), server_default='category_override', nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('previous_category', sa.String(length=100), nullable=True),
        sa.Column('new_category', sa.String(length=100), nullable=False),
        sa.Column('source', sa.String(length=50), server_default='user', nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_tenant_id'), 'audit_logs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_transaction_id'), 'audit_logs', ['transaction_id'], unique=False)

    # 7. Chart of accounts mappings table
    op.create_table(
        'chart_of_accounts_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('raw_category', sa.String(length=255), nullable=False),
        sa.Column('standard_category', sa.String(length=100), nullable=False),
        sa.Column('pnl_bucket', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'raw_category', name='uq_tenant_raw_category')
    )
    op.create_index(op.f('ix_chart_of_accounts_mappings_id'), 'chart_of_accounts_mappings', ['id'], unique=False)
    op.create_index(op.f('ix_chart_of_accounts_mappings_tenant_id'), 'chart_of_accounts_mappings', ['tenant_id'], unique=False)

    # 8. AI usage table
    op.create_table(
        'ai_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('task_type', sa.String(length=50), server_default='analyst', nullable=True),
        sa.Column('input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('estimated_cost', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_usage_id'), 'ai_usage', ['id'], unique=False)
    op.create_index(op.f('ix_ai_usage_tenant_id'), 'ai_usage', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_user_id'), 'ai_usage', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_request_id'), 'ai_usage', ['request_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_created_at'), 'ai_usage', ['created_at'], unique=False)

    # 9. Chat sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), server_default='Financial Investigation', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_sessions_id'), 'chat_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_chat_sessions_tenant_id'), 'chat_sessions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)

    # 10. Chat messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tools_used', sa.Text(), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('ai_usage')
    op.drop_table('chart_of_accounts_mappings')
    op.drop_table('audit_logs')
    op.drop_table('transactions')
    op.drop_table('import_batches')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    op.drop_table('tenants')

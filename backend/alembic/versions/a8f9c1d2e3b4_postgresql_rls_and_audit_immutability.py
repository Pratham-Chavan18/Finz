"""postgresql_rls_and_audit_immutability

Revision ID: a8f9c1d2e3b4
Revises: 597d4a892a52
Create Date: 2026-09-25 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a8f9c1d2e3b4'
down_revision: Union[str, Sequence[str], None] = '597d4a892a52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 1. AuditLog Database-Level Immutability (Trigger)
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'AuditLog rows are immutable and cannot be updated or deleted.';
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_logs;
            CREATE TRIGGER trg_audit_log_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
        """)

        # 2. PostgreSQL Row-Level Security (RLS) on Tenant-Scoped Tables
        tenant_tables = [
            "transactions",
            "audit_logs",
            "import_batches",
            "ai_usage",
            "chat_sessions",
            "chart_of_accounts_mappings",
        ]

        for table in tenant_tables:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
            op.execute(f"""
                DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};
                CREATE POLICY tenant_isolation_{table} ON {table}
                FOR ALL
                USING (
                    current_setting('app.bypass_rls', true) = 'on'
                    OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
                )
                WITH CHECK (
                    current_setting('app.bypass_rls', true) = 'on'
                    OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
                );
            """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        tenant_tables = [
            "transactions",
            "audit_logs",
            "import_batches",
            "ai_usage",
            "chat_sessions",
            "chart_of_accounts_mappings",
        ]
        for table in tenant_tables:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_logs;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

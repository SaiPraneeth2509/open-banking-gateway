"""add helpful indexes to consents"""
from alembic import op

# revision identifiers.
revision = "0002_consents_indexes"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Use raw SQL so we can leverage Postgres IF NOT EXISTS (safe on existing dev DBs)
    op.execute('CREATE INDEX IF NOT EXISTS idx_consents_tenant       ON consents (tenant_id)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_consents_created_at   ON consents (created_at)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_consents_status       ON consents (status)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_consents_expires_at   ON consents (expires_at)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_consents_tpp_client   ON consents (tpp_client_id)')

def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_consents_tpp_client')
    op.execute('DROP INDEX IF EXISTS idx_consents_expires_at')
    op.execute('DROP INDEX IF EXISTS idx_consents_status')
    op.execute('DROP INDEX IF EXISTS idx_consents_created_at')
    op.execute('DROP INDEX IF EXISTS idx_consents_tenant')

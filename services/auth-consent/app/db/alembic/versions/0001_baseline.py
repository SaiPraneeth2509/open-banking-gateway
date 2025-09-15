"""baseline (no-op for existing DBs)"""
from alembic import op
import sqlalchemy as sa  # noqa

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Existing dev DBs already have the table via create_all; we just stamp this.
    # Fresh DBs: we’ll create the table in a future migration if needed.
    pass

def downgrade() -> None:
    pass
    
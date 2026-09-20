"""0001 initial — schema is created by db/*.sql auto-run; this marks the baseline.

Revision ID: 0001_initial
"""
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # No-op: fresh installs use db/01..04 *.sql (see db/README.md).
    pass


def downgrade():
    pass

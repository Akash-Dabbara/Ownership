"""add LOCAL_FILE and URL to workspace_source_type enum

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: (new)
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside the same
    # transaction as other DDL on older PostgreSQL versions,
    # so this runs in its own autocommit block.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE workspace_source_type ADD VALUE IF NOT EXISTS 'LOCAL_FILE'"
        )
        op.execute(
            "ALTER TYPE workspace_source_type ADD VALUE IF NOT EXISTS 'URL'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # A downgrade would require recreating the enum type without
    # these values, which is intentionally not automated here to
    # avoid accidentally breaking existing rows using them.
    pass
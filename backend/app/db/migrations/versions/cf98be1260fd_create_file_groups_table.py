"""create file groups table

Revision ID: cf98be1260fd
Revises: ed9ff2c4540c
Create Date: (original creation date — restored)

This file was accidentally overwritten with unrelated content.
Restored here to recreate the original file_groups table
creation migration. Since the file_groups table already exists
in the database (this revision was already applied previously),
Alembic will recognize cf98be1260fd as already-applied via the
alembic_version table and will NOT re-run this upgrade() again
on this database — it only repairs the migration history chain.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "cf98be1260fd"
down_revision = "ed9ff2c4540c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_file_groups_workspace_id"),
        "file_groups",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_groups_created_by"),
        "file_groups",
        ["created_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_file_groups_created_by"), table_name="file_groups")
    op.drop_index(op.f("ix_file_groups_workspace_id"), table_name="file_groups")
    op.drop_table("file_groups")
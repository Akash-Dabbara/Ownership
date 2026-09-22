"""create files table

Revision ID: a1b2c3d4e5f6
Revises: 7047d898c0b7
Create Date: (new)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "7047d898c0b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_group_id", sa.Uuid(), nullable=False),
        sa.Column("database_name", sa.String(length=255), nullable=True),
        sa.Column("schema_name", sa.String(length=255), nullable=True),
        sa.Column("table_name", sa.String(length=255), nullable=True),
        sa.Column("source_path", sa.String(length=2048), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["file_group_id"],
            ["file_groups.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_files_file_group_id"),
        "files",
        ["file_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_files_file_group_id"), table_name="files")
    op.drop_table("files")
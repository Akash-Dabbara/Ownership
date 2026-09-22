"""add file_id scoping to permissions/access_requests, new_user_requests table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: (new)

IMPORTANT: run `alembic heads` first to confirm b2c3d4e5f6g7 is
still your actual current head before applying this — if you've
added other migrations since, update down_revision accordingly.
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --------------------------------------------------------
    # PERMISSIONS: add optional file_id (NULL = whole file group)
    # --------------------------------------------------------
    op.add_column(
        "permissions",
        sa.Column("file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_permissions_file_id",
        "permissions",
        "files",
        ["file_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_permissions_file_id"), "permissions", ["file_id"]
    )

    # Replace the old constraint (which didn't account for file_id)
    # with an expression-based unique index. Using COALESCE with a
    # sentinel UUID for NULL, since Postgres treats every NULL as
    # distinct in a plain unique constraint, which would otherwise
    # allow duplicate whole-file-group permissions.
    op.drop_constraint(
        "uq_permission_user_workspace_file_group",
        "permissions",
        type_="unique",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_permission_scope
        ON permissions (
            user_id,
            workspace_id,
            file_group_id,
            COALESCE(file_id, '00000000-0000-0000-0000-000000000000'::uuid)
        )
        """
    )

    # --------------------------------------------------------
    # ACCESS REQUESTS: add optional file_id
    # --------------------------------------------------------
    op.add_column(
        "access_requests",
        sa.Column("file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_access_requests_file_id",
        "access_requests",
        "files",
        ["file_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_access_requests_file_id"), "access_requests", ["file_id"]
    )

# --------------------------------------------------------
    # NEW USER REQUESTS (no account yet — public submission)
    # --------------------------------------------------------
    
    # Safely create enum type in Postgres if it doesn't already exist
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE new_user_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # Tell SQLAlchemy NOT to try to create the type again when building the table
    new_user_request_status = sa.Enum(
        "PENDING", "APPROVED", "REJECTED",
        name="new_user_request_status",
        create_type=False,
    )

    op.create_table(
        "new_user_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("workspace_name_requested", sa.String(length=255), nullable=False),
        sa.Column("file_group_name_requested", sa.String(length=255), nullable=False),
        sa.Column("file_name_requested", sa.String(length=255), nullable=False),
        sa.Column("display_file_name", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", new_user_request_status, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("created_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_new_user_requests_email"), "new_user_requests", ["email"]
    )
    op.create_index(
        op.f("ix_new_user_requests_status"), "new_user_requests", ["status"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_new_user_requests_status"), table_name="new_user_requests")
    op.drop_index(op.f("ix_new_user_requests_email"), table_name="new_user_requests")
    op.drop_table("new_user_requests")
    sa.Enum(name="new_user_request_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_access_requests_file_id"), table_name="access_requests")
    op.drop_constraint("fk_access_requests_file_id", "access_requests", type_="foreignkey")
    op.drop_column("access_requests", "file_id")

    op.drop_index("uq_permission_scope", table_name="permissions")
    op.create_unique_constraint(
        "uq_permission_user_workspace_file_group",
        "permissions",
        ["user_id", "workspace_id", "file_group_id"],
    )
    op.drop_index(op.f("ix_permissions_file_id"), table_name="permissions")
    op.drop_constraint("fk_permissions_file_id", "permissions", type_="foreignkey")
    op.drop_column("permissions", "file_id")
"""add file_id scoping to permissions/access_requests

NOTE: this migration originally also created a new_user_requests
table + new_user_request_status enum, for a "public, no-login
required" access-request feature. That feature was removed from the
app entirely (its route and service are gone), and creating that
enum from inside a CREATE TABLE column definition was hitting a
known SQLAlchemy/Alembic quirk where create_type=False does not
reliably stick for enums used inside op.create_table(), causing a
"type already exists" DuplicateObject error on a clean database.
Since the table was never used, it has been dropped from this
migration rather than worked around.
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # --------------------------------------------------------
    # PERMISSIONS
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
        op.f("ix_permissions_file_id"),
        "permissions",
        ["file_id"],
    )

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
            COALESCE(
                file_id,
                '00000000-0000-0000-0000-000000000000'::uuid
            )
        )
        """
    )

    # --------------------------------------------------------
    # ACCESS REQUESTS
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


def downgrade() -> None:
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
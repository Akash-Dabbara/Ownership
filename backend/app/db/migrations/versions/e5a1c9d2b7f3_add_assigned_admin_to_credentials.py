"""add assigned_admin_id to data_source_credentials

Revision ID: e5a1c9d2b7f3
Revises: c3d4e5f6g7h8
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e5a1c9d2b7f3"
down_revision = "c3d4e5f6g7h8"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_source_credentials",
        sa.Column(
            "assigned_admin_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_data_source_credentials_assigned_admin_id"),
        "data_source_credentials",
        ["assigned_admin_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_data_source_credentials_assigned_admin",
        "data_source_credentials",
        "users",
        ["assigned_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_data_source_credentials_assigned_admin",
        "data_source_credentials",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_data_source_credentials_assigned_admin_id"),
        table_name="data_source_credentials",
    )

    op.drop_column(
        "data_source_credentials",
        "assigned_admin_id",
    )
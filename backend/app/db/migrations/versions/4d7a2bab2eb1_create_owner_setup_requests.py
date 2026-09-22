"""create owner setup requests

Revision ID: 4d7a2bab2eb1
Revises: 7c68d7cc7df2
Create Date: 2026-09-04 23:20:27.267688

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4d7a2bab2eb1"
down_revision: Union[str, Sequence[str], None] = "7c68d7cc7df2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


owner_setup_request_status_enum = postgresql.ENUM(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="owner_setup_request_status",
)


def upgrade() -> None:
    """Upgrade schema."""

    # Create the PostgreSQL enum type explicitly.
    owner_setup_request_status_enum.create(
        op.get_bind(),
        checkfirst=True,
    )

    # Use the already-created PostgreSQL enum when creating the table.
    owner_setup_request_status_column = postgresql.ENUM(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="owner_setup_request_status",
        create_type=False,
    )

    op.create_table(
        "owner_setup_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "status",
            owner_setup_request_status_column,
            nullable=False,
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_owner_setup_requests_email",
        "owner_setup_requests",
        ["email"],
        unique=False,
    )

    op.create_index(
        "ix_owner_setup_requests_status",
        "owner_setup_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_owner_setup_requests_status",
        table_name="owner_setup_requests",
    )

    op.drop_index(
        "ix_owner_setup_requests_email",
        table_name="owner_setup_requests",
    )

    op.drop_table("owner_setup_requests")

    # Remove the PostgreSQL enum type.
    owner_setup_request_status_enum.drop(
        op.get_bind(),
        checkfirst=True,
    )
"""add user role enum

Revision ID: 7c68d7cc7df2
Revises: 7bb0b88e1b61
Create Date: 2026-09-04 22:26:08.464754

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c68d7cc7df2"
down_revision: Union[str, Sequence[str], None] = "7bb0b88e1b61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = sa.Enum(
    "OWNER",
    "ADMIN",
    "USER",
    name="user_role",
)


def upgrade() -> None:
    """Upgrade schema."""

    # Create the PostgreSQL enum type first.
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # Convert the existing role column to the new enum.
    op.alter_column(
        "users",
        "role",
        existing_type=sa.VARCHAR(length=20),
        type_=user_role_enum,
        existing_nullable=False,
        postgresql_using="role::user_role",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Convert the enum column back to VARCHAR.
    op.alter_column(
        "users",
        "role",
        existing_type=user_role_enum,
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
        postgresql_using="role::varchar",
    )

    # Remove the PostgreSQL enum type.
    user_role_enum.drop(op.get_bind(), checkfirst=True)
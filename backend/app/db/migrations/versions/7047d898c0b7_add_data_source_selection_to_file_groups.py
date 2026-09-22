"""add data source selection to file groups

Revision ID: 7047d898c0b7
Revises: c4ef4213ce20
Create Date: 2026-09-08 10:27:39.962195

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7047d898c0b7"
down_revision: Union[str, Sequence[str], None] = "c4ef4213ce20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "file_groups",
        sa.Column(
            "data_source_credential_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    op.add_column(
        "file_groups",
        sa.Column(
            "selected_database",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "file_groups",
        sa.Column(
            "selected_schema",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "file_groups",
        sa.Column(
            "selected_table",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_file_groups_data_source_credential_id",
        "file_groups",
        ["data_source_credential_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_file_groups_data_source_credential_id",
        "file_groups",
        "data_source_credentials",
        ["data_source_credential_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "fk_file_groups_data_source_credential_id",
        "file_groups",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_file_groups_data_source_credential_id",
        table_name="file_groups",
    )

    op.drop_column(
        "file_groups",
        "selected_table",
    )

    op.drop_column(
        "file_groups",
        "selected_schema",
    )

    op.drop_column(
        "file_groups",
        "selected_database",
    )

    op.drop_column(
        "file_groups",
        "data_source_credential_id",
    )
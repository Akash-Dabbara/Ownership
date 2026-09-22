from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Permission(Base):
    __tablename__ = "permissions"

    # NOTE: uniqueness is enforced at the database level by an
    # expression-based unique index (uq_permission_scope, created
    # in the file_id migration), not by a SQLAlchemy-level
    # UniqueConstraint — plain NULLs in file_id are not distinct
    # from each other for that index (via COALESCE), which a
    # normal UniqueConstraint cannot express.

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )

    file_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_groups.id"),
        nullable=False,
        index=True,
    )

    # Optional — NULL means access to the whole File Group.
    # A real value scopes access down to just that one File.
    file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    granted_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
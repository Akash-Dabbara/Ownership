from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FileGroup(Base):
    __tablename__ = "file_groups"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    data_source_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("data_source_credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    selected_database: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    selected_schema: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    selected_table: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
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

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="file_groups",
    )

    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="file_group",
        cascade="all, delete-orphan",
    )
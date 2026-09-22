from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccessRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AccessRequest(Base):
    __tablename__ = "access_requests"

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

    # Optional — NULL means requesting the whole File Group.
    # A real value requests just that one File.
    file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[AccessRequestStatus] = mapped_column(
        SQLEnum(
            AccessRequestStatus,
            name="access_request_status",
            native_enum=True,
        ),
        nullable=False,
        default=AccessRequestStatus.PENDING,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
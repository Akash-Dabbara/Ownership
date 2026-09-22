from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewUserRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class NewUserRequest(Base):
    """
    A request submitted by someone who does NOT have a DataEase
    account yet, asking to be given one plus access to a specific
    file. This is intentionally separate from AccessRequest, which
    is for an EXISTING logged-in User asking for MORE access.
    """

    __tablename__ = "new_user_requests"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Free-text — the requester has no login, so they can't browse
    # real workspaces/file groups. The reviewing Admin/Owner maps
    # this to the actual workspace_id/file_group_id/file_id when
    # approving.
    workspace_name_requested: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_group_name_requested: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_name_requested: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    display_file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[NewUserRequestStatus] = mapped_column(
        SQLEnum(
            NewUserRequestStatus,
            name="new_user_request_status",
            native_enum=True,
        ),
        nullable=False,
        default=NewUserRequestStatus.PENDING,
        index=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # Set once approved and the actual User account is created.
    created_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
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
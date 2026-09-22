from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class File(Base):
    """
    A single imported table or path within a File Group.

    A File Group can hold many Files (the user may import
    one or more tables/paths at a time). No row counts or
    cached data are stored here — this only records WHERE
    the original data lives. The original source is always
    read live from its actual location (database/schema/table
    or storage path), so the same original data is always
    available for as long as the Workspace / File Group /
    File itself has not been deleted.
    """

    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    file_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Used for database-type sources (PostgreSQL, MySQL,
    # MSSQL, Snowflake).
    database_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    schema_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    table_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Used for path-based sources (Local File, URL, AWS S3,
    # Azure Blob).
    source_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    # Name shown to the user in the UI. Defaults to the
    # table name or the last path segment, but can be
    # renamed by the user (Step 4 rename prompt).
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    file_group: Mapped["FileGroup"] = relationship(
        "FileGroup",
        back_populates="files",
    )
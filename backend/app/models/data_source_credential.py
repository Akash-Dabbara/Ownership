from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataSourceType(str, Enum):
    MYSQL = "MYSQL"
    POSTGRESQL = "POSTGRESQL"
    MSSQL = "MSSQL"
    SNOWFLAKE = "SNOWFLAKE"
    AWS_S3 = "AWS_S3"
    AZURE_BLOB = "AZURE_BLOB"
    LOCAL_FILE = "LOCAL_FILE"
    URL = "URL"


class DataSourceCredential(Base):
    __tablename__ = "data_source_credentials"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    source_type: Mapped[DataSourceType] = mapped_column(
        SQLEnum(
            DataSourceType,
            name="data_source_type",
            native_enum=True,
        ),
        nullable=False,
        index=True,
    )

    encrypted_config: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # NEW: the Admin this data source belongs to.
    #   - set  -> only that Admin (and the Owner) can use it
    #   - NULL -> Owner-only
    assigned_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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
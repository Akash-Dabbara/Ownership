import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class WorkspaceSourceType(str, enum.Enum):
    POSTGRESQL = "POSTGRESQL"
    MYSQL = "MYSQL"
    SNOWFLAKE = "SNOWFLAKE"
    AWS_S3 = "AWS_S3"
    LOCAL_FILE = "LOCAL_FILE"
    URL = "URL"


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    source_type = Column(
        SQLEnum(
            WorkspaceSourceType,
            name="workspace_source_type",
            native_enum=True,
            values_callable=lambda enum_class: [
                item.value
                for item in enum_class
            ],
        ),
        nullable=False,
        index=True,
    )

    destination_path = Column(
        Text,
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    data_source_credential_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_source_credentials.id",
            name="fk_workspaces_data_source_credential",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
    )

    # Relationship to allow clean cascade deletion of dependent file groups when a workspace is removed
    file_groups = relationship(
        "FileGroup",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
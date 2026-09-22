from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.data_source_credential import DataSourceType


class DataSourceCredentialCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    source_type: DataSourceType

    config: dict = Field(
        ...,
        min_length=1,
    )

    # Optional: the Admin this data source is set up for.
    # Omit / null = Owner-only.
    assigned_admin_id: UUID | None = None


class DataSourceCredentialUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    source_type: DataSourceType | None = None

    config: dict | None = Field(
        default=None,
        min_length=1,
    )

    # Send a UUID to (re)assign, or an explicit null to make it
    # Owner-only. Leave the field out to keep the current value.
    assigned_admin_id: UUID | None = None


class DataSourceCredentialResponse(BaseModel):
    id: UUID
    name: str
    source_type: DataSourceType
    is_active: bool
    created_by: UUID
    assigned_admin_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class DataSourceCredentialStatusUpdate(BaseModel):
    is_active: bool


class DataSourceCredentialTestResponse(BaseModel):
    success: bool
    message: str
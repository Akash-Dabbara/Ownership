from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.data_source_credential import DataSourceType


class FileGroupCreate(BaseModel):
    """
    Request model for creating a File Group.

    Data source selection is intentionally not required here.
    The File Group is created first, and the data source,
    database, schema, and table are selected afterward.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
    )


class FileGroupUpdate(BaseModel):
    """
    Request model for updating File Group metadata.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
    )


class FileGroupDataSourceSelection(BaseModel):
    """
    Request model for selecting the data source and
    destination path for an existing File Group.

    The selection happens after the File Group has been created.
    """

    data_source_credential_id: UUID = Field(
        ...,
        description="ID of the tested data source credential.",
    )

    selected_database: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Selected database.",
    )

    selected_schema: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Selected schema.",
    )

    selected_table: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Selected table.",
    )


class FileGroupResponse(BaseModel):
    """
    Response model for a File Group.
    """

    file_group_id: UUID
    workspace_id: UUID
    name: str
    description: str | None

    data_source_credential_id: UUID | None
    selected_database: str | None
    selected_schema: str | None
    selected_table: str | None

    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class FileGroupDataSourceSelectionResponse(BaseModel):
    """
    Response returned after selecting a data source
    and table for a File Group.
    """

    success: bool
    message: str
    file_group: FileGroupResponse
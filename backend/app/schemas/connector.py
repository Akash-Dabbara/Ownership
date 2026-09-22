from pydantic import BaseModel, Field


class ConnectorBrowseResponse(BaseModel):
    success: bool
    paths: list[str]


class ConnectorBrowseRequest(BaseModel):
    parent_path: str = Field(
        ...,
        min_length=1,
        description="Currently selected parent path.",
    )
    search_text: str | None = Field(
        default=None,
        description="Optional text used to filter child paths.",
    )
    database_name: str | None = Field(
        default=None,
        min_length=1,
        description="Selected database used when browsing database-specific child paths.",
    )


class ConnectorTableBrowseRequest(BaseModel):
    database_name: str = Field(
        ...,
        min_length=1,
        description="Selected database containing the schema.",
    )
    schema_name: str = Field(
        ...,
        min_length=1,
        description="Selected schema whose tables should be listed.",
    )
    search_text: str | None = Field(
        default=None,
        description="Optional text used to filter table names.",
    )


class ConnectorTableColumnsRequest(BaseModel):
    database_name: str = Field(
        ...,
        min_length=1,
        description="Selected database containing the table.",
    )
    schema_name: str = Field(
        ...,
        min_length=1,
        description="Selected schema containing the table.",
    )
    table_name: str = Field(
        ...,
        min_length=1,
        description="Selected table whose columns should be listed.",
    )


class ConnectorTableColumnResponse(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    ordinal_position: int


class ConnectorTableColumnsResponse(BaseModel):
    success: bool
    columns: list[ConnectorTableColumnResponse]


class ConnectorDestinationValidationRequest(BaseModel):
    path: str = Field(
        ...,
        min_length=1,
        description="Destination path to validate.",
    )
    database_name: str | None = Field(
        default=None,
        min_length=1,
        description="Selected database containing the destination path.",
    )


class ConnectorDestinationValidationResponse(BaseModel):
    success: bool
    valid: bool
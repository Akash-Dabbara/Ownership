from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.data_source_credential import DataSourceCredential
from app.models.file import File
from app.models.file_group import FileGroup
from app.models.user import User
from app.services.connector_service import (
    ConnectorServiceError,
    list_connector_table_columns,
)


def find_file_group_by_name(
    db: Session,
    workspace_id: UUID,
    name: str,
) -> FileGroup | None:
    """
    Find a File Group by name within a specific Workspace.

    Name comparison is case-insensitive.
    """

    normalized_name = name.strip()

    if not normalized_name:
        return None

    statement = (
        select(FileGroup)
        .where(
            FileGroup.workspace_id == workspace_id,
            func.lower(FileGroup.name)
            == normalized_name.lower(),
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


def create_file_group(
    db: Session,
    workspace_id: UUID,
    name: str,
    description: str | None,
    created_by: User,
) -> FileGroup:
    """
    Create a new File Group inside a Workspace.

    Data source selection is intentionally not performed here.
    It happens after the File Group has been created.
    """

    normalized_name = name.strip()

    if not normalized_name:
        raise ValueError(
            "File Group name cannot be empty."
        )

    existing_file_group = find_file_group_by_name(
        db=db,
        workspace_id=workspace_id,
        name=normalized_name,
    )

    if existing_file_group is not None:
        raise ValueError(
            f"FILE_GROUP_NAME_EXISTS:{existing_file_group.id}"
        )

    file_group = FileGroup(
        workspace_id=workspace_id,
        name=normalized_name,
        description=(
            description.strip()
            if description
            else None
        ),
        created_by=created_by.id,
    )

    db.add(file_group)
    db.commit()
    db.refresh(file_group)

    return file_group


def get_all_file_groups(
    db: Session,
    workspace_id: UUID,
) -> list[FileGroup]:
    """
    Return all File Groups belonging to a Workspace.

    Results are ordered by creation time.

    NOTE: this currently returns every File Group in the
    Workspace regardless of the caller's role. Scoping this
    to "only File Groups this User has been granted access
    to" requires the access-grant/permission system, which
    has not been reviewed/built yet.
    """

    statement = (
        select(FileGroup)
        .where(
            FileGroup.workspace_id == workspace_id
        )
        .order_by(FileGroup.created_at.asc())
    )

    return list(
        db.execute(statement).scalars().all()
    )


def get_file_group_by_id(
    db: Session,
    file_group_id: UUID,
) -> FileGroup | None:
    """
    Return a File Group by its unique ID.
    """

    statement = (
        select(FileGroup)
        .where(FileGroup.id == file_group_id)
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


def update_file_group(
    db: Session,
    file_group_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> FileGroup:
    """
    Update File Group metadata.

    Only supplied fields are changed.

    File Group name comparison remains
    case-insensitive within its Workspace.
    """

    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None:
        raise ValueError(
            "File Group was not found."
        )

    if name is not None:
        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "File Group name cannot be empty."
            )

        existing_file_group = find_file_group_by_name(
            db=db,
            workspace_id=file_group.workspace_id,
            name=normalized_name,
        )

        if (
            existing_file_group is not None
            and existing_file_group.id != file_group.id
        ):
            raise ValueError(
                "A File Group with this name "
                "already exists in this Workspace."
            )

        file_group.name = normalized_name

    if description is not None:
        file_group.description = (
            description.strip()
            if description.strip()
            else None
        )

    db.commit()
    db.refresh(file_group)

    return file_group


def select_file_group_data_source(
    db: Session,
    file_group_id: UUID,
    data_source_credential_id: UUID,
    selected_database: str,
    selected_schema: str,
    selected_table: str,
) -> FileGroup:
    """
    Save the selected data source and table location
    for an existing File Group.

    Kept for backward compatibility with the single-table
    selection flow. For importing one or more tables/paths
    at a time, use add_files_to_file_group instead.
    """

    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None:
        raise ValueError(
            "File Group was not found."
        )

    credential = db.execute(
        select(DataSourceCredential)
        .where(
            DataSourceCredential.id
            == data_source_credential_id
        )
        .limit(1)
    ).scalar_one_or_none()

    if credential is None:
        raise ValueError(
            "Data source credential was not found."
        )

    if not credential.is_active:
        raise ValueError(
            "Data source credential is inactive."
        )

    normalized_database = selected_database.strip()
    normalized_schema = selected_schema.strip()
    normalized_table = selected_table.strip()

    if not normalized_database:
        raise ValueError(
            "Selected database cannot be empty."
        )

    if not normalized_schema:
        raise ValueError(
            "Selected schema cannot be empty."
        )

    if not normalized_table:
        raise ValueError(
            "Selected table cannot be empty."
        )

    if len(normalized_database) > 255:
        raise ValueError(
            "Selected database cannot exceed 255 characters."
        )

    if len(normalized_schema) > 255:
        raise ValueError(
            "Selected schema cannot exceed 255 characters."
        )

    if len(normalized_table) > 255:
        raise ValueError(
            "Selected table cannot exceed 255 characters."
        )

    try:
        columns = list_connector_table_columns(
            db=db,
            credential_id=data_source_credential_id,
            database_name=normalized_database,
            schema_name=normalized_schema,
            table_name=normalized_table,
        )
    except ConnectorServiceError as exc:
        raise ValueError(
            "Unable to validate the selected data source."
        ) from exc

    if not columns:
        raise ValueError(
            "The selected table was not found or contains no columns."
        )

    file_group.data_source_credential_id = (
        data_source_credential_id
    )

    file_group.selected_database = normalized_database
    file_group.selected_schema = normalized_schema
    file_group.selected_table = normalized_table

    db.commit()
    db.refresh(file_group)

    return file_group


def add_files_to_file_group(
    db: Session,
    file_group_id: UUID,
    data_source_credential_id: UUID | None,
    selections: list[dict],
) -> list[File]:
    """
    Import one or more tables/paths into a File Group at once.

    data_source_credential_id may be None for source types that
    genuinely have no login (URL, Local File) — in that case,
    path-type selections are saved without connector validation,
    since there is no connector/credential to validate against.

    Each selection is either:
      - a database-type selection:
        {"database_name": ..., "schema_name": ..., "table_name": ...}
      - a path-type selection:
        {"source_path": ..., "display_name": (optional)}

    Database-type selections are always validated against the
    connector before being saved. No row counts or copies of the
    data are stored here — only the location. The same original
    source is read fresh every time the File is opened, so it
    remains available exactly as first imported until the
    Workspace / File Group / File is deleted.
    """

    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None:
        raise ValueError(
            "File Group was not found."
        )

    credential = None

    if data_source_credential_id is not None:
        credential = db.execute(
            select(DataSourceCredential)
            .where(
                DataSourceCredential.id
                == data_source_credential_id
            )
            .limit(1)
        ).scalar_one_or_none()

        if credential is None:
            raise ValueError(
                "Data source credential was not found."
            )

        if not credential.is_active:
            raise ValueError(
                "Data source credential is inactive."
            )

    if not selections:
        raise ValueError(
            "At least one table or path must be selected."
        )

    created_files: list[File] = []

    for selection in selections:
        database_name = (selection.get("database_name") or "").strip()
        schema_name = (selection.get("schema_name") or "").strip()
        table_name = (selection.get("table_name") or "").strip()
        source_path = (selection.get("source_path") or "").strip()

        is_database_selection = bool(
            database_name and schema_name and table_name
        )
        is_path_selection = bool(source_path)

        if not is_database_selection and not is_path_selection:
            raise ValueError(
                "Each selection must include either a "
                "database/schema/table, or a source path."
            )

        if is_database_selection:
            if credential is None:
                raise ValueError(
                    "A data source credential is required to "
                    "import a database table."
                )

            try:
                columns = list_connector_table_columns(
                    db=db,
                    credential_id=data_source_credential_id,
                    database_name=database_name,
                    schema_name=schema_name,
                    table_name=table_name,
                )
            except ConnectorServiceError as exc:
                raise ValueError(
                    f"Unable to validate '{table_name}': "
                    "the selected data source could not be read."
                ) from exc

            if not columns:
                raise ValueError(
                    f"Table '{table_name}' was not found or "
                    "contains no columns."
                )

            display_name = (
                selection.get("display_name") or table_name
            ).strip()

            new_file = File(
                file_group_id=file_group.id,
                database_name=database_name,
                schema_name=schema_name,
                table_name=table_name,
                display_name=display_name,
            )

        else:
            display_name = (
                selection.get("display_name")
                or source_path.rstrip("/").split("/")[-1]
                or source_path
            ).strip()

            new_file = File(
                file_group_id=file_group.id,
                source_path=source_path,
                display_name=display_name,
            )

        db.add(new_file)
        created_files.append(new_file)

    # Record which credential this File Group's imports came from,
    # if it hasn't been set yet. Stays None for URL/Local File
    # File Groups, which is expected.
    if (
        file_group.data_source_credential_id is None
        and data_source_credential_id is not None
    ):
        file_group.data_source_credential_id = data_source_credential_id

    db.commit()

    for created_file in created_files:
        db.refresh(created_file)

    return created_files


def get_files_for_file_group(
    db: Session,
    file_group_id: UUID,
) -> list[File]:
    """
    Return all Files (imported tables/paths) belonging to a
    File Group, ordered by import time.
    """

    statement = (
        select(File)
        .where(File.file_group_id == file_group_id)
        .order_by(File.created_at.asc())
    )

    return list(
        db.execute(statement).scalars().all()
    )


def get_file_by_id(
    db: Session,
    file_id: UUID,
) -> File | None:
    """
    Return a single imported File (table/path) by its ID.
    """

    statement = (
        select(File)
        .where(File.id == file_id)
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


def delete_file_group(
    db: Session,
    file_group_id: UUID,
) -> FileGroup:
    """
    Delete a File Group by ID.

    Its Files are removed automatically via the cascading
    relationship on FileGroup.files.
    """

    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None:
        raise ValueError(
            "File Group was not found."
        )

    db.delete(file_group)
    db.commit()

    return file_group
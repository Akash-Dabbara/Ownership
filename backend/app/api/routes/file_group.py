import io
import os
import re
import uuid
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File as UploadedFile,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import (
    require_admin_or_owner,
    require_any_authenticated_user,
)
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.anonymization.engine import anonymize_dataset
from app.services.access_control import (
    can_manage_workspace,
    can_use_credential,
    get_permitted_file_group_ids,
    get_permitted_file_scope,
    user_has_any_file_group_access,
    user_has_any_workspace_access,
)
from app.services.connector_service import (
    preview_connector_data,
    write_connector_data,
)
from app.services.data_source_credential_service import get_credential_by_id
from app.services.local_data import (
    ensure_upload_storage_dir,
    read_local_or_url_data,
)
from app.services.permission_service import user_has_file_access
from app.services.workspace_service import get_workspace_by_id
from app.services.file_group_service import (
    add_files_to_file_group,
    create_file_group,
    get_all_file_groups,
    get_file_by_id,
    get_file_group_by_id,
    get_files_for_file_group,
    update_file_group,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# WORKSPACE / FILE GROUP / FILE ACCESS GUARD
#
# Runs before EVERY route in this router.
#
#   Owner: may access any Workspace.
#   Admin: may only access Workspaces they created.
#   User:  may only access what a Permission row grants them —
#          a whole File Group, or one specific File.
#
# Anything else raises 404 ("Workspace was not found") rather than
# 403, so IDs the caller has no access to can't be probed.
# ============================================================

def enforce_workspace_scope(
    workspace_id: UUID,
    file_group_id: UUID | None = None,
    file_id: UUID | None = None,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
) -> None:

    workspace = get_workspace_by_id(db=db, workspace_id=workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace was not found.",
        )

    if can_manage_workspace(current_user, workspace):
        return

    if current_user.role == UserRole.USER:
        if file_id is not None and file_group_id is not None:
            allowed = user_has_file_access(
                db=db,
                user_id=current_user.id,
                workspace_id=workspace_id,
                file_group_id=file_group_id,
                file_id=file_id,
            )
        elif file_group_id is not None:
            allowed = user_has_any_file_group_access(
                db=db,
                user_id=current_user.id,
                workspace_id=workspace_id,
                file_group_id=file_group_id,
            )
        else:
            allowed = user_has_any_workspace_access(
                db=db,
                user_id=current_user.id,
                workspace_id=workspace_id,
            )

        if allowed:
            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Workspace was not found.",
    )


router = APIRouter(
    prefix="/workspaces/{workspace_id}/file-groups",
    tags=["File Groups"],
    dependencies=[Depends(enforce_workspace_scope)],
)


# ============================================================
# SCHEMAS
# ============================================================

class FileGroupCreate(BaseModel):
    name: str
    description: str | None = None


class FileGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class FileGroupResponse(BaseModel):
    file_group_id: str
    workspace_id: str
    name: str
    description: str | None = None


class FileSelection(BaseModel):
    # Database-type selection
    database_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    # Path-type selection
    source_path: str | None = None
    display_name: str | None = None


class AddFilesRequest(BaseModel):
    data_source_credential_id: str | None = None
    selections: list[FileSelection]


class ColumnRule(BaseModel):
    algorithm: str
    casing: str | None = "ORIGINAL"
    consistency: bool | None = False


class AnonymizeRequest(BaseModel):
    column_rules: dict[str, ColumnRule]
    preview_limit: int = 100


class ExportRequest(BaseModel):
    column_rules: dict[str, ColumnRule]


class FileResponse(BaseModel):
    file_id: str
    file_group_id: str
    display_name: str
    database_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    source_path: str | None = None


def _serialize_file_group(file_group) -> dict:
    return {
        "file_group_id": str(file_group.id),
        "workspace_id": str(file_group.workspace_id),
        "name": file_group.name,
        "description": file_group.description,
    }


def _serialize_file(file) -> dict:
    return {
        "file_id": str(file.id),
        "file_group_id": str(file.file_group_id),
        "display_name": file.display_name,
        "database_name": file.database_name,
        "schema_name": file.schema_name,
        "table_name": file.table_name,
        "source_path": file.source_path,
    }


# ============================================================
# LIST FILE GROUPS
# ============================================================

@router.get("")
def list_file_groups(
    workspace_id: UUID,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    file_groups = get_all_file_groups(
        db=db,
        workspace_id=workspace_id,
    )

    if current_user.role == UserRole.USER:
        permitted_ids = get_permitted_file_group_ids(
            db=db,
            user_id=current_user.id,
            workspace_id=workspace_id,
        )
        file_groups = [
            fg for fg in file_groups if fg.id in permitted_ids
        ]

    return {
        "file_groups": [
            _serialize_file_group(fg) for fg in file_groups
        ]
    }


# ============================================================
# GET SINGLE FILE GROUP
# ============================================================

@router.get("/{file_group_id}")
def get_file_group(
    workspace_id: UUID,
    file_group_id: UUID,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    return {"file_group": _serialize_file_group(file_group)}


# ============================================================
# CREATE FILE GROUP
# ============================================================

@router.post("")
def create_file_group_route(
    workspace_id: UUID,
    payload: FileGroupCreate,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    try:
        file_group = create_file_group(
            db=db,
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            created_by=current_user,
        )
    except ValueError as exc:
        message = str(exc)

        if message.startswith("FILE_GROUP_NAME_EXISTS:"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A File Group with this name already exists in this Workspace.",
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        ) from exc

    return {
        "message": "File group created successfully.",
        "file_group": _serialize_file_group(file_group),
    }


# ============================================================
# UPDATE FILE GROUP (name / description)
# ============================================================

@router.put("/{file_group_id}")
def update_file_group_route(
    workspace_id: UUID,
    file_group_id: UUID,
    payload: FileGroupUpdate,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    existing = get_file_group_by_id(db=db, file_group_id=file_group_id)

    if existing is None or existing.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    try:
        file_group = update_file_group(
            db=db,
            file_group_id=file_group_id,
            name=payload.name,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "File group updated successfully.",
        "file_group": _serialize_file_group(file_group),
    }


# ============================================================
# ADD FILES (IMPORT ONE OR MORE TABLES/PATHS)
# ============================================================

@router.post("/{file_group_id}/files")
def add_files_route(
    workspace_id: UUID,
    file_group_id: UUID,
    payload: AddFilesRequest,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    credential_uuid = None
    if payload.data_source_credential_id:
        try:
            credential_uuid = UUID(payload.data_source_credential_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data source credential id.",
            ) from exc

    if credential_uuid is not None:
        credential = get_credential_by_id(
            db=db,
            credential_id=credential_uuid,
        )

        if credential is None or not can_use_credential(
            current_user,
            credential,
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data source credential was not found.",
            )

    try:
        created_files = add_files_to_file_group(
            db=db,
            file_group_id=file_group_id,
            data_source_credential_id=credential_uuid,
            selections=[
                selection.model_dump() for selection in payload.selections
            ],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "Data imported successfully.",
        "files": [_serialize_file(f) for f in created_files],
    }


# ============================================================
# UPLOAD A LOCAL FILE (no credential — Local File workspaces)
# ============================================================

@router.post("/{file_group_id}/files/upload")
async def upload_file_route(
    workspace_id: UUID,
    file_group_id: UUID,
    file: UploadFile = UploadedFile(...),
    display_name: str | None = None,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    upload_dir = ensure_upload_storage_dir()
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    stored_path = os.path.join(upload_dir, safe_filename)

    try:
        contents = await file.read()
        with open(stored_path, "wb") as out_file:
            out_file.write(contents)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to save uploaded file: {str(exc)}",
        ) from exc

    try:
        created_files = add_files_to_file_group(
            db=db,
            file_group_id=file_group_id,
            data_source_credential_id=None,
            selections=[
                {
                    "source_path": stored_path,
                    "display_name": display_name or file.filename,
                }
            ],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "File uploaded successfully.",
        "files": [_serialize_file(f) for f in created_files],
    }


# ============================================================
# LIST FILES IN A FILE GROUP
# ============================================================

@router.get("/{file_group_id}/files")
def list_files_route(
    workspace_id: UUID,
    file_group_id: UUID,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    try:
        files = get_files_for_file_group(
            db=db,
            file_group_id=file_group_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to load files: {str(exc)}",
        ) from exc

    if current_user.role == UserRole.USER:
        whole_group, permitted_file_ids = get_permitted_file_scope(
            db=db,
            user_id=current_user.id,
            file_group_id=file_group_id,
        )

        if not whole_group:
            files = [f for f in files if f.id in permitted_file_ids]

    return {"files": [_serialize_file(f) for f in files]}


# ============================================================
# PREVIEW FILE DATA
# ============================================================

ALLOWED_PREVIEW_LIMITS = {100, 150, 200, 500, 1000}


@router.get("/{file_group_id}/files/{file_id}/preview")
def preview_file_route(
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID,
    limit: int = 100,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    file_record = get_file_by_id(db=db, file_id=file_id)

    if file_record is None or file_record.file_group_id != file_group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File was not found.",
        )

    safe_limit = limit if limit in ALLOWED_PREVIEW_LIMITS else 100

    # Credential-less sources (URL / Local File): read directly,
    # no connector involved.
    if file_group.data_source_credential_id is None:
        if not file_record.source_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This File Group has no data source credential configured.",
            )

        try:
            preview = read_local_or_url_data(
                source_path=file_record.source_path,
                limit=safe_limit,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to preview data: {str(exc)}",
            ) from exc

        return {
            "file": _serialize_file(file_record),
            "columns": preview.get("columns", []),
            "rows": preview.get("rows", []),
            "limit": safe_limit,
        }

    try:
        preview = preview_connector_data(
            db=db,
            credential_id=file_group.data_source_credential_id,
            limit=safe_limit,
            database_name=file_record.database_name,
            schema_name=file_record.schema_name,
            table_name=file_record.table_name,
            source_path=file_record.source_path,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to preview data: {str(exc)}",
        ) from exc

    return {
        "file": _serialize_file(file_record),
        "columns": preview.get("columns", []),
        "rows": preview.get("rows", []),
        "limit": safe_limit,
    }


# ============================================================
# RUN ANONYMIZATION
# ============================================================

FULL_DATASET_LIMIT = 1_000_000


@router.post("/{file_group_id}/files/{file_id}/anonymize")
def anonymize_file_route(
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID,
    payload: AnonymizeRequest,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    file_record = get_file_by_id(db=db, file_id=file_id)

    if file_record is None or file_record.file_group_id != file_group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File was not found.",
        )

    if file_group.data_source_credential_id is None and not file_record.source_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This File Group has no data source configured.",
        )

    if not payload.column_rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one column rule is required to run anonymization.",
        )

    safe_preview_limit = (
        payload.preview_limit
        if payload.preview_limit in ALLOWED_PREVIEW_LIMITS
        else 100
    )

    try:
        if file_group.data_source_credential_id is None:
            # Credential-less source (URL / Local File)
            full_data = read_local_or_url_data(
                source_path=file_record.source_path,
                limit=FULL_DATASET_LIMIT,
            )
        else:
            # Read the FULL dataset (up to the practical cap), not just
            # a preview slice — the whole file gets anonymized, only
            # the response back to the browser is trimmed to a preview.
            full_data = preview_connector_data(
                db=db,
                credential_id=file_group.data_source_credential_id,
                limit=FULL_DATASET_LIMIT,
                database_name=file_record.database_name,
                schema_name=file_record.schema_name,
                table_name=file_record.table_name,
                source_path=file_record.source_path,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to read data for anonymization: {str(exc)}",
        ) from exc

    column_rules_dict = {
        column: rule.model_dump()
        for column, rule in payload.column_rules.items()
    }

    try:
        anonymized = anonymize_dataset(
            columns=full_data.get("columns", []),
            rows=full_data.get("rows", []),
            column_rules=column_rules_dict,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anonymization failed: {str(exc)}",
        ) from exc

    total_rows_processed = len(anonymized.get("rows", []))

    return {
        "file": _serialize_file(file_record),
        "columns": anonymized.get("columns", []),
        "rows": anonymized.get("rows", [])[:safe_preview_limit],
        "total_rows_processed": total_rows_processed,
        "preview_limit": safe_preview_limit,
    }


# ============================================================
# EXPORT ANONYMIZED DATA
# ============================================================

DATABASE_SOURCE_TYPES = {"POSTGRESQL", "MYSQL", "SNOWFLAKE"}


@router.post("/{file_group_id}/files/{file_id}/export")
def export_file_route(
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID,
    payload: ExportRequest,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace_by_id(db=db, workspace_id=workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace was not found.",
        )

    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None or file_group.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    file_record = get_file_by_id(db=db, file_id=file_id)

    if file_record is None or file_record.file_group_id != file_group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File was not found.",
        )

    if not payload.column_rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one column rule is required to export data.",
        )

    sanitized_name = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        file_record.display_name.strip().lower(),
    )

    column_rules_dict = {
        column: rule.model_dump()
        for column, rule in payload.column_rules.items()
    }

    # ------------------------------------------------------------
    # CREDENTIAL-LESS SOURCES (URL / Local File): read directly,
    # anonymize, and return the result as a real file download —
    # the browser saves it to the user's own Downloads folder,
    # since the backend has no access to that folder itself.
    # ------------------------------------------------------------

    if file_group.data_source_credential_id is None:
        if not file_record.source_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This File Group has no data source configured.",
            )

        try:
            full_data = read_local_or_url_data(
                source_path=file_record.source_path,
                limit=FULL_DATASET_LIMIT,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to read data for export: {str(exc)}",
            ) from exc

        try:
            anonymized = anonymize_dataset(
                columns=full_data.get("columns", []),
                rows=full_data.get("rows", []),
                column_rules=column_rules_dict,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Anonymization failed during export: {str(exc)}",
            ) from exc

        csv_buffer = io.StringIO()
        columns = anonymized.get("columns", [])
        rows = anonymized.get("rows", [])

        csv_buffer.write(",".join(columns) + "\n")
        for row in rows:
            csv_buffer.write(
                ",".join(
                    "" if value is None else str(value).replace(",", " ")
                    for value in row
                )
                + "\n"
            )
        csv_buffer.seek(0)

        filename = f"{sanitized_name}_anonymized.csv"

        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    # ------------------------------------------------------------
    # CONNECTOR-BASED SOURCES: re-read the full dataset, re-run
    # anonymization fresh, and write to the configured destination
    # using the same credential as the source.
    # ------------------------------------------------------------

    if not workspace.destination_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This Workspace has no destination path configured.",
        )

    try:
        full_data = preview_connector_data(
            db=db,
            credential_id=file_group.data_source_credential_id,
            limit=FULL_DATASET_LIMIT,
            database_name=file_record.database_name,
            schema_name=file_record.schema_name,
            table_name=file_record.table_name,
            source_path=file_record.source_path,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to read data for export: {str(exc)}",
        ) from exc

    try:
        anonymized = anonymize_dataset(
            columns=full_data.get("columns", []),
            rows=full_data.get("rows", []),
            column_rules=column_rules_dict,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anonymization failed during export: {str(exc)}",
        ) from exc

    destination_segments = [
        segment
        for segment in workspace.destination_path.strip().split("/")
        if segment
    ]

    export_table_name = f"{sanitized_name}_anonymized"

    source_type = (
        workspace.source_type.value
        if hasattr(workspace.source_type, "value")
        else str(workspace.source_type)
    )

    try:
        if source_type in DATABASE_SOURCE_TYPES:
            if len(destination_segments) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This workspace's destination path is not in the "
                        "expected 'database/schema' format."
                    ),
                )

            destination_database = destination_segments[0]
            destination_schema = destination_segments[1]

            write_result = write_connector_data(
                db=db,
                credential_id=file_group.data_source_credential_id,
                columns=anonymized.get("columns", []),
                rows=anonymized.get("rows", []),
                database_name=destination_database,
                schema_name=destination_schema,
                table_name=export_table_name,
            )

            export_location = (
                f"{destination_database}.{destination_schema}."
                f"{export_table_name}"
            )

        else:
            # AWS_S3 (or other path-based connector sources)
            destination_key = "/".join(
                destination_segments + [f"{sanitized_name}_anonymized.csv"]
            )

            write_result = write_connector_data(
                db=db,
                credential_id=file_group.data_source_credential_id,
                columns=anonymized.get("columns", []),
                rows=anonymized.get("rows", []),
                destination_path=destination_key,
            )

            export_location = destination_key

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to export data: {str(exc)}",
        ) from exc

    return {
        "message": "Data exported successfully.",
        "export_location": export_location,
        "rows_written": write_result.get("rows_written", 0),
    }
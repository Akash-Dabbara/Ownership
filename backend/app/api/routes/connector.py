from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.api.routes.owner_setup import get_db
from app.core.auth import require_admin_or_owner
from app.models.user import User

from app.services.access_control import can_use_credential
from app.services.data_source_credential_service import get_credential_by_id

from app.services.connector_service import (
    ConnectorCredentialInactiveError,
    ConnectorCredentialNotFoundError,
    ConnectorServiceError,
    test_connector_connection,
    list_connector_root_paths,
    search_connector_child_paths,
    list_connector_tables,
    list_connector_table_columns,
    validate_connector_destination_path,
)


# ============================================================
# REQUEST MODELS
# ============================================================

class BrowseChildrenRequest(BaseModel):

    parent_path: str = Field(
        ...,
        min_length=1,
    )

    search_text: str | None = None

    database_name: str | None = None


class BrowseTablesRequest(BaseModel):

    database_name: str = Field(
        ...,
        min_length=1,
    )

    schema_name: str = Field(
        ...,
        min_length=1,
    )

    search_text: str | None = None


class BrowseColumnsRequest(BaseModel):

    database_name: str = Field(
        ...,
        min_length=1,
    )

    schema_name: str = Field(
        ...,
        min_length=1,
    )

    table_name: str = Field(
        ...,
        min_length=1,
    )


class ValidateDestinationRequest(BaseModel):

    path: str = Field(
        ...,
        min_length=1,
    )

    database_name: str | None = None


class TestConnectionRequest(BaseModel):

    credential_id: UUID


# ============================================================
# CREDENTIAL OWNERSHIP GUARD
#
# Runs before every /connectors/{credential_id}/... route via the
# router-level dependency below, and is also called explicitly
# inside /test since that route takes credential_id in the body,
# not the path.
#
#   Owner: may use any credential.
#   Admin: may only use credentials the Owner assigned to them.
#
# Anything else raises 404 rather than 403, so an Admin can't use
# the response to discover credential IDs that aren't theirs.
# ============================================================

def authorize_credential_access(
    credential_id: UUID | None = None,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
) -> None:

    if credential_id is None:
        return

    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None or not can_use_credential(
        current_user,
        credential,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source credential was not found.",
        )


router = APIRouter(
    prefix="/connectors",
    tags=["Connectors"],
    dependencies=[
        Depends(authorize_credential_access)
    ],
)


# ============================================================
# ERROR HANDLER
# ============================================================

def raise_connector_http_error(
    exc: Exception,
):

    if isinstance(
        exc,
        ConnectorCredentialNotFoundError,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(
        exc,
        ConnectorCredentialInactiveError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if isinstance(
        exc,
        ConnectorServiceError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Connector operation failed.",
    )


# ============================================================
# TEST CONNECTION
#
# credential_id arrives in the request body here, not the path,
# so the router-level dependency (which only reads a path param)
# does not cover it. The ownership check is run explicitly instead.
# ============================================================

@router.post(
    "/test"
)
def test_connection(
    payload: TestConnectionRequest,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
):

    authorize_credential_access(
        credential_id=payload.credential_id,
        current_user=current_user,
        db=db,
    )

    try:

        result = test_connector_connection(
            db=db,
            credential_id=payload.credential_id,
        )

        return {
            "success": True,
            "connected": bool(result),
            "message": (
                "Connection successful."
                if result
                else "Connection failed."
            ),
        }

    except Exception as exc:

        raise_connector_http_error(
            exc
        )


# ============================================================
# LIST ROOT PATHS
# ============================================================

@router.get(
    "/{credential_id}/browse/root"
)
def browse_connector_root(
    credential_id: UUID,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
):

    try:

        paths = list_connector_root_paths(
            db=db,
            credential_id=credential_id,
        )

        return {
            "success": True,
            "paths": paths,
        }

    except Exception as exc:

        raise_connector_http_error(
            exc
        )


# ============================================================
# LIST CHILD PATHS
# ============================================================

@router.post(
    "/{credential_id}/browse/children"
)
def browse_connector_children(
    credential_id: UUID,
    payload: BrowseChildrenRequest,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
):

    try:

        paths = search_connector_child_paths(
            db=db,
            credential_id=credential_id,
            parent_path=payload.parent_path,
            search_text=payload.search_text,
            database_name=payload.database_name,
        )

        return {
            "success": True,
            "paths": paths,
        }

    except Exception as exc:

        raise_connector_http_error(
            exc
        )


# ============================================================
# LIST TABLES
# ============================================================

@router.post(
    "/{credential_id}/browse/tables"
)
def browse_connector_tables(
    credential_id: UUID,
    payload: BrowseTablesRequest,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
):

    try:

        tables = list_connector_tables(
            db=db,
            credential_id=credential_id,
            database_name=payload.database_name,
            schema_name=payload.schema_name,
            search_text=payload.search_text,
        )

        return {
            "success": True,
            "paths": tables,
        }

    except Exception as exc:

        raise_connector_http_error(
            exc
        )


# ============================================================
# LIST TABLE COLUMNS
# ============================================================

@router.post(
    "/{credential_id}/browse/columns"
)
def browse_connector_columns(
    credential_id: UUID,
    payload: BrowseColumnsRequest,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
):

    try:

        columns = list_connector_table_columns(
            db=db,
            credential_id=credential_id,
            database_name=payload.database_name,
            schema_name=payload.schema_name,
            table_name=payload.table_name,
        )

        return {
            "success": True,
            "columns": columns,
        }

    except Exception as exc:

        raise_connector_http_error(
            exc
        )


# ============================================================
# VALIDATE DESTINATION
# ============================================================

@router.post(
    "/{credential_id}/destination/validate"
)
def validate_destination(
    credential_id: UUID,
    payload: ValidateDestinationRequest,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(
        get_db
    ),
):

    try:

        is_valid = validate_connector_destination_path(
            db=db,
            credential_id=credential_id,
            path=payload.path,
            database_name=payload.database_name,
        )

        return {
            "success": True,
            "valid": bool(is_valid),
            "path": payload.path,
        }

    except Exception as exc:

        raise_connector_http_error(
            exc
        )
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.owner_setup import get_db
from app.connectors.base import (
    ConnectorOperationError,
    ConnectorValidationError,
)
from app.core.auth import require_admin_or_owner, require_owner
from app.core.encryption import EncryptionError
from app.models.user import User
from app.schemas.data_source_credential import (
    DataSourceCredentialCreate,
    DataSourceCredentialResponse,
    DataSourceCredentialStatusUpdate,
    DataSourceCredentialTestResponse,
    DataSourceCredentialUpdate,
)
from app.services.access_control import can_use_credential
from app.services.connector_service import (
    ConnectorServiceError,
    test_connector_connection,
)
from app.services.data_source_credential_service import (
    UNSET,
    create_credential,
    delete_credential,
    get_credential_by_id,
    list_credentials,
    set_credential_active_status,
    update_credential,
)


router = APIRouter(
    prefix="/data-source-credentials",
    tags=["Data Source Credentials"],
)


def _credential_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Data source credential was not found.",
    )


def _handle_credential_exists_error(
    exc: ValueError,
) -> HTTPException:
    message = str(exc)

    if message.startswith("CREDENTIAL_EXISTS:"):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A data source credential with this name "
                "already exists for this Admin."
            ),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )


@router.post(
    "",
    response_model=DataSourceCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_data_source_credential(
    payload: DataSourceCredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """
    Create a new encrypted data source credential.

    Only the Owner can create credentials. Set assigned_admin_id to
    set the data source up for a specific Admin; leave it out to keep
    it Owner-only.
    """

    try:
        return create_credential(
            db=db,
            name=payload.name,
            source_type=payload.source_type,
            config=payload.config,
            created_by=current_user,
            assigned_admin_id=payload.assigned_admin_id,
        )

    except ValueError as exc:
        raise _handle_credential_exists_error(exc) from exc

    except EncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to securely store the data source "
                "credential."
            ),
        ) from exc


@router.get(
    "",
    response_model=list[DataSourceCredentialResponse],
)
def get_data_source_credentials(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    """
    List data source credentials (metadata only, never secrets).

    Owner: all credentials.
    Admin: only the credentials assigned to them.
    """

    return list_credentials(
        db=db,
        include_inactive=include_inactive,
        viewer=current_user,
    )


@router.get(
    "/{credential_id}",
    response_model=DataSourceCredentialResponse,
)
def get_data_source_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None or not can_use_credential(
        current_user,
        credential,
    ):
        raise _credential_not_found()

    return credential


@router.put(
    "/{credential_id}",
    response_model=DataSourceCredentialResponse,
)
def update_data_source_credential(
    credential_id: UUID,
    payload: DataSourceCredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """
    Update a credential. Owner only.

    Include assigned_admin_id (a UUID, or null for Owner-only) to
    move the data source to a different Admin.
    """

    assignee_provided = (
        "assigned_admin_id" in payload.model_fields_set
    )

    if (
        payload.name is None
        and payload.source_type is None
        and payload.config is None
        and not assignee_provided
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "At least one field must be provided "
                "for update."
            ),
        )

    try:
        return update_credential(
            db=db,
            credential_id=credential_id,
            name=payload.name,
            source_type=payload.source_type,
            config=payload.config,
            assigned_admin_id=(
                payload.assigned_admin_id
                if assignee_provided
                else UNSET
            ),
        )

    except ValueError as exc:
        if str(exc) == "Credential was not found.":
            raise _credential_not_found() from exc

        raise _handle_credential_exists_error(exc) from exc

    except EncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to securely update the data source "
                "credential."
            ),
        ) from exc


@router.patch(
    "/{credential_id}/status",
    response_model=DataSourceCredentialResponse,
)
def update_data_source_credential_status(
    credential_id: UUID,
    payload: DataSourceCredentialStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    try:
        return set_credential_active_status(
            db=db,
            credential_id=credential_id,
            is_active=payload.is_active,
        )

    except ValueError as exc:
        if str(exc) == "Credential was not found.":
            raise _credential_not_found() from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_data_source_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    try:
        delete_credential(
            db=db,
            credential_id=credential_id,
        )

    except ValueError as exc:
        if str(exc) == "Credential was not found.":
            raise _credential_not_found() from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return None


@router.post(
    "/{credential_id}/test",
    response_model=DataSourceCredentialTestResponse,
)
def test_data_source_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """
    Test the real connection for a stored credential. Owner only.
    Sensitive configuration is never returned.
    """

    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None:
        raise _credential_not_found()

    if not credential.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credential is inactive.",
        )

    try:
        success = test_connector_connection(
            db=db,
            credential_id=credential_id,
        )

        if success:
            return DataSourceCredentialTestResponse(
                success=True,
                message="Data source connection successful.",
            )

        return DataSourceCredentialTestResponse(
            success=False,
            message="Data source connection test failed.",
        )

    except ConnectorOperationError:
        return DataSourceCredentialTestResponse(
            success=False,
            message="Unable to connect to the data source.",
        )

    except ConnectorValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except ConnectorServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.owner_setup import get_db
from app.core.auth import (
    require_admin_or_owner,
    require_any_authenticated_user,
)
from app.models.user import User, UserRole
from app.services.access_request_service import (
    approve_access_request,
    cancel_access_request,
    create_access_request,
    get_access_request_by_id,
    get_admin_access_requests,
    get_all_access_requests,
    get_user_access_requests,
    reject_access_request,
)


router = APIRouter(
    prefix="/access-requests",
    tags=["Access Requests"],
)


def access_request_response(access_request):
    """
    Convert an AccessRequest SQLAlchemy object into
    a JSON-safe response dictionary.
    """

    return {
        "request_id": str(access_request.id),
        "user_id": str(access_request.user_id),
        "workspace_id": str(access_request.workspace_id),
        "file_group_id": str(access_request.file_group_id),
        "admin_id": str(access_request.admin_id),
        "status": access_request.status.value,
        "reason": access_request.reason,
        "created_at": (
            access_request.created_at.isoformat()
            if access_request.created_at
            else None
        ),
        "updated_at": (
            access_request.updated_at.isoformat()
            if access_request.updated_at
            else None
        ),
        "reviewed_at": (
            access_request.reviewed_at.isoformat()
            if access_request.reviewed_at
            else None
        ),
        "reviewed_by": (
            str(access_request.reviewed_by)
            if access_request.reviewed_by
            else None
        ),
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_new_access_request(
    workspace_id: UUID,
    file_group_id: UUID,
    admin_id: UUID,
    reason: str | None = None,
    current_user: User = Depends(
        require_any_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    """
    Create an Access Request.

    A User requests access to a specific File Group
    and selects the Admin who should receive the request.
    """

    if current_user.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only normal Users can create Access Requests.",
        )

    try:
        access_request = create_access_request(
            db=db,
            user=current_user,
            workspace_id=workspace_id,
            file_group_id=file_group_id,
            admin_id=admin_id,
            reason=reason,
        )

        return {
            "message": "Access Request created successfully.",
            "access_request": access_request_response(
                access_request
            ),
        }

    except ValueError as exc:
        error_message = str(exc)

        if error_message.startswith(
            "ACCESS_REQUEST_EXISTS:"
        ):
            existing_request_id = error_message.split(
                ":", 1
            )[1]

            existing_request = get_access_request_by_id(
                db=db,
                request_id=UUID(existing_request_id),
            )

            if existing_request is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "ACCESS_REQUEST_EXISTS",
                        "message": (
                            "A pending Access Request already "
                            "exists for this User, Workspace "
                            "and File Group."
                        ),
                        "existing_access_request":
                            access_request_response(
                                existing_request
                            ),
                    },
                ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        ) from exc


@router.get(
    "/mine",
)
def list_my_access_requests(
    current_user: User = Depends(
        require_any_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    """
    Return Access Requests created by the current User.
    """

    requests = get_user_access_requests(
        db=db,
        user_id=current_user.id,
    )

    return {
        "requests": [
            access_request_response(request)
            for request in requests
        ],
    }


@router.get(
    "/assigned",
)
def list_assigned_access_requests(
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(get_db),
):
    """
    Admin:
        Return requests assigned to the current Admin.

    Owner:
        Return all Access Requests.
    """

    if current_user.role == UserRole.OWNER:
        requests = get_all_access_requests(
            db=db,
        )
    else:
        requests = get_admin_access_requests(
            db=db,
            admin_id=current_user.id,
        )

    return {
        "requests": [
            access_request_response(request)
            for request in requests
        ],
    }


@router.get(
    "/{request_id}",
)
def get_single_access_request(
    request_id: UUID,
    current_user: User = Depends(
        require_any_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    """
    Return one Access Request.

    User:
        Can view only their own request.

    Admin:
        Can view requests assigned to them.

    Owner:
        Can view any request.
    """

    access_request = get_access_request_by_id(
        db=db,
        request_id=request_id,
    )

    if access_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access Request was not found.",
        )

    if current_user.role == UserRole.OWNER:
        pass

    elif current_user.role == UserRole.ADMIN:
        if access_request.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not authorized to view "
                    "this Access Request."
                ),
            )

    else:
        if access_request.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not authorized to view "
                    "this Access Request."
                ),
            )

    return {
        "access_request": access_request_response(
            access_request
        ),
    }


@router.post(
    "/{request_id}/approve",
)
def approve_existing_access_request(
    request_id: UUID,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(get_db),
):
    """
    Approve an Access Request.

    The service verifies that:
    - Admin is the assigned Admin, or
    - current user is Owner.

    Approval creates the corresponding Permission.
    """

    try:
        access_request = approve_access_request(
            db=db,
            request_id=request_id,
            reviewer=current_user,
        )

        return {
            "message": (
                "Access Request approved successfully."
            ),
            "access_request": access_request_response(
                access_request
            ),
        }

    except ValueError as exc:
        error_message = str(exc)

        if error_message == "Access Request was not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            ) from exc

        if (
            error_message
            == "You are not authorized to approve "
            "this Access Request."
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message,
            ) from exc

        if (
            error_message
            == "You are not authorized to approve "
            "Access Requests."
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        ) from exc


@router.post(
    "/{request_id}/reject",
)
def reject_existing_access_request(
    request_id: UUID,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db: Session = Depends(get_db),
):
    """
    Reject an Access Request.

    Rejection does not create a Permission.
    """

    try:
        access_request = reject_access_request(
            db=db,
            request_id=request_id,
            reviewer=current_user,
        )

        return {
            "message": (
                "Access Request rejected successfully."
            ),
            "access_request": access_request_response(
                access_request
            ),
        }

    except ValueError as exc:
        error_message = str(exc)

        if error_message == "Access Request was not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            ) from exc

        if (
            error_message
            == "You are not authorized to reject "
            "this Access Request."
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message,
            ) from exc

        if (
            error_message
            == "You are not authorized to reject "
            "Access Requests."
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        ) from exc


@router.post(
    "/{request_id}/cancel",
)
def cancel_existing_access_request(
    request_id: UUID,
    current_user: User = Depends(
        require_any_authenticated_user
    ),
    db: Session = Depends(get_db),
):
    """
    Cancel an Access Request.

    Only the User who created the request can cancel it.
    """

    if current_user.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the User who created the "
                "Access Request can cancel it."
            ),
        )

    try:
        access_request = cancel_access_request(
            db=db,
            request_id=request_id,
            user=current_user,
        )

        return {
            "message": (
                "Access Request cancelled successfully."
            ),
            "access_request": access_request_response(
                access_request
            ),
        }

    except ValueError as exc:
        error_message = str(exc)

        if error_message == "Access Request was not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            ) from exc

        if (
            error_message
            == "You are not authorized to cancel "
            "this Access Request."
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        ) from exc
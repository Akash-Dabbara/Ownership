import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.routes.owner_setup import get_db
from app.core.auth import require_admin_or_owner
from app.models.user import User
from app.services.mailer_service import send_email
from app.services.permission_service import create_permission
from app.services.user_management import (
    create_user,
    deactivate_user,
    delete_user,
    get_all_users,
    reactivate_user,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/user-management",
    tags=["User Management"],
)


class CreateUserPayload(BaseModel):
    email: EmailStr
    # FIX: this endpoint had no minimum length, unlike users-with-access.
    temporary_password: str = Field(..., min_length=8)


class CreateUserWithAccessPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    workspace_id: UUID
    file_group_id: UUID
    file_id: UUID | None = None


def _service_error(exc: ValueError) -> HTTPException:
    """
    The service layer raises ValueError for both "not found" and
    "conflict" cases. Map "not found" to 404 and the rest to 409.
    """
    message = str(exc)

    code = (
        status.HTTP_404_NOT_FOUND
        if "not found" in message.lower()
        else status.HTTP_409_CONFLICT
    )

    return HTTPException(status_code=code, detail=message)


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
)
def create_new_user(
    payload: CreateUserPayload,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db=Depends(get_db),
):
    try:
        user = create_user(
            db=db,
            email=payload.email,
            temporary_password=payload.temporary_password,
        )

        return {
            "message": "User created successfully.",
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "must_change_password": user.must_change_password,
        }

    except ValueError as exc:
        raise _service_error(exc) from exc


# ============================================================
# CREATE USER + GRANT ACCESS, IN ONE ACTION
#
# Admin/Owner creates a User with a temporary password AND
# immediately grants them access to a chosen Workspace / File
# Group / (optionally) one specific File.
# ============================================================

@router.post(
    "/users-with-access",
    status_code=status.HTTP_201_CREATED,
)
def create_user_with_access(
    payload: CreateUserWithAccessPayload,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db=Depends(get_db),
):
    try:
        user = create_user(
            db=db,
            email=payload.email,
            temporary_password=payload.password,
        )
    except ValueError as exc:
        raise _service_error(exc) from exc

    try:
        create_permission(
            db=db,
            user_id=user.id,
            workspace_id=payload.workspace_id,
            file_group_id=payload.file_group_id,
            file_id=payload.file_id,
            granted_by=current_user,
        )
    except Exception as exc:
        # create_user already committed, so undo the account we just
        # made. Otherwise a bad workspace/file group leaves an orphan
        # User and a retry fails with "already exists".
        db.rollback()

        try:
            delete_user(db=db, user_id=user.id)
        except Exception:
            logger.exception(
                "Could not roll back user %s after a failed "
                "permission grant.",
                user.email,
            )

        if isinstance(exc, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        # FIX: this used to be a bare `raise`, which re-throws the
        # original (non-HTTP) exception unchanged. FastAPI's own
        # exception handling only kicks in for HTTPException; any
        # other exception type falls through to Starlette's outer
        # error handling, which sits OUTSIDE the CORS middleware —
        # so the response never gets an Access-Control-Allow-Origin
        # header, and the browser reports it as a CORS failure
        # instead of showing the real error. Logging the real cause
        # here and returning a normal HTTPException keeps the error
        # visible in the server logs while giving the browser a
        # response it can actually read.
        logger.exception(
            "Unexpected error granting access while creating user %s",
            payload.email,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The user account was not created because granting "
                "access failed unexpectedly. Please try again."
            ),
        ) from exc

    # send_email() returns False (it does not raise) when SMTP is not
    # configured or the send fails, so use its return value.
    email_sent = False

    try:
        email_sent = send_email(
            to_email=user.email,
            subject="DataEase: Your account is ready",
            body=(
                "Your DataEase account has been created.\n\n"
                f"Email: {user.email}\n"
                f"Password: {payload.password}\n\n"
                "You will be asked to set a new password on first login."
            ),
        )
    except Exception:
        logger.exception(
            "Failed to send credentials email to %s",
            user.email,
        )
        email_sent = False

    return {
        "message": (
            "User created and access granted successfully. "
            "Credentials have been emailed."
            if email_sent
            else "User created and access granted successfully."
        ),
        "user_id": str(user.id),
        "email": user.email,
        "email_sent": email_sent,
    }


@router.get(
    "/users",
)
def list_users(
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db=Depends(get_db),
):
    # The service only returns accounts with role USER.
    users = get_all_users(db)

    return {
        "users": [
            {
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role.value,
                "is_active": user.is_active,
                "must_change_password": user.must_change_password,
                "created_at": user.created_at,
            }
            for user in users
        ]
    }


@router.post(
    "/users/{user_id}/deactivate",
)
def deactivate_user_account(
    user_id: UUID,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db=Depends(get_db),
):
    try:
        user = deactivate_user(
            db=db,
            user_id=user_id,
        )

        return {
            "message": "User account deactivated successfully.",
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
        }

    except ValueError as exc:
        raise _service_error(exc) from exc


@router.post(
    "/users/{user_id}/reactivate",
)
def reactivate_user_account(
    user_id: UUID,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db=Depends(get_db),
):
    try:
        user = reactivate_user(
            db=db,
            user_id=user_id,
        )

        return {
            "message": "User account reactivated successfully.",
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
        }

    except ValueError as exc:
        raise _service_error(exc) from exc


@router.delete(
    "/users/{user_id}",
)
def delete_user_account(
    user_id: UUID,
    current_user: User = Depends(
        require_admin_or_owner
    ),
    db=Depends(get_db),
):
    try:
        user = delete_user(
            db=db,
            user_id=user_id,
        )

        return {
            "message": "User account deleted successfully.",
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }

    except ValueError as exc:
        raise _service_error(exc) from exc
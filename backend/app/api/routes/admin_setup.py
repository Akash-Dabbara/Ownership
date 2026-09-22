from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.routes.owner_setup import get_db
from app.core.auth import require_owner
from app.models.user import User
from app.services.admin_bootstrap import (
    approve_admin_setup_request,
    create_admin_setup_request,
    get_pending_admin_requests,
    reject_admin_setup_request,
)


router = APIRouter(
    prefix="/admin-setup",
    tags=["Admin Setup"],
)


class AdminSetupCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class AdminSetupReject(BaseModel):
    rejection_reason: str | None = None


@router.post(
    "/request",
    status_code=status.HTTP_201_CREATED,
)
def request_admin_setup(
    payload: AdminSetupCreate,
    db=Depends(get_db),
):
    try:
        admin_request = create_admin_setup_request(
            db=db,
            email=payload.email,
            password=payload.password,
        )

        return {
            "message": "Admin setup request submitted successfully.",
            "request_id": str(admin_request.id),
            "status": admin_request.status.value,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/requests",
)
def list_pending_admin_requests(
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    requests = get_pending_admin_requests(db)

    return {
        "requests": [
            {
                "request_id": str(request.id),
                "email": request.email,
                "status": request.status.value,
                "created_at": request.created_at,
            }
            for request in requests
        ]
    }


@router.post(
    "/requests/{request_id}/approve",
)
def approve_admin_request(
    request_id: UUID,
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    try:
        admin = approve_admin_setup_request(
            db=db,
            request_id=request_id,
        )

        return {
            "message": "Admin setup request approved successfully.",
            "user_id": str(admin.id),
            "email": admin.email,
            "role": admin.role.value,
            "is_active": admin.is_active,
            "must_change_password": admin.must_change_password,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/requests/{request_id}/reject",
)
def reject_admin_request(
    request_id: UUID,
    payload: AdminSetupReject = AdminSetupReject(),
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    try:
        admin_request = reject_admin_setup_request(
            db=db,
            request_id=request_id,
            rejection_reason=payload.rejection_reason,
        )

        return {
            "message": "Admin setup request rejected successfully.",
            "request_id": str(admin_request.id),
            "status": admin_request.status.value,
            "rejection_reason": admin_request.rejection_reason,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
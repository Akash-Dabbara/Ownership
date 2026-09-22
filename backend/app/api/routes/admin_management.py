from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.owner_setup import get_db
from app.core.auth import require_owner
from app.models.user import User
from app.services.admin_management import (
    deactivate_admin,
    delete_admin,
    get_all_admins,
    reactivate_admin,
)


router = APIRouter(
    prefix="/admin-management",
    tags=["Admin Management"],
)


@router.get("/admins")
def list_admins(
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    admins = get_all_admins(db)

    return {
        "admins": [
            {
                "user_id": str(admin.id),
                "email": admin.email,
                "role": admin.role.value,
                "is_active": admin.is_active,
                "must_change_password": admin.must_change_password,
                "created_at": admin.created_at,
            }
            for admin in admins
        ]
    }


@router.post(
    "/admins/{admin_id}/deactivate",
)
def deactivate_admin_account(
    admin_id: UUID,
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    try:
        admin = deactivate_admin(
            db=db,
            admin_id=admin_id,
        )

        return {
            "message": "Admin account deactivated successfully.",
            "user_id": str(admin.id),
            "email": admin.email,
            "role": admin.role.value,
            "is_active": admin.is_active,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/admins/{admin_id}/reactivate",
)
def reactivate_admin_account(
    admin_id: UUID,
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    try:
        admin = reactivate_admin(
            db=db,
            admin_id=admin_id,
        )

        return {
            "message": "Admin account reactivated successfully.",
            "user_id": str(admin.id),
            "email": admin.email,
            "role": admin.role.value,
            "is_active": admin.is_active,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/admins/{admin_id}",
)
def delete_admin_account(
    admin_id: UUID,
    current_user: User = Depends(require_owner),
    db=Depends(get_db),
):
    try:
        admin = delete_admin(
            db=db,
            admin_id=admin_id,
        )

        return {
            "message": "Admin account deleted successfully.",
            "user_id": str(admin.id),
            "email": admin.email,
            "role": admin.role.value,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
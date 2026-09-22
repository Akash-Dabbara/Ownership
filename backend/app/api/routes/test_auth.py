from fastapi import APIRouter, Depends

from app.core.auth import (
    require_admin_or_owner,
    require_any_authenticated_user,
    require_owner,
)
from app.models.user import User


router = APIRouter(
    prefix="/test-auth",
    tags=["Authentication Test"],
)


@router.get("/authenticated")
def authenticated_test(
    current_user: User = Depends(require_any_authenticated_user),
):
    return {
        "message": "Authentication successful.",
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role.value,
    }


@router.get("/owner")
def owner_test(
    current_user: User = Depends(require_owner),
):
    return {
        "message": "Owner authorization successful.",
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role.value,
    }


@router.get("/admin-or-owner")
def admin_or_owner_test(
    current_user: User = Depends(require_admin_or_owner),
):
    return {
        "message": "Admin/Owner authorization successful.",
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role.value,
    }
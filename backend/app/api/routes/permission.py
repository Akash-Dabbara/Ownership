from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.owner_setup import get_db
from app.core.auth import require_admin_or_owner
from app.models.permission import Permission
from app.models.user import User
from app.services.access_control import (
    can_manage_workspace,
    get_managed_workspace_ids,
)
from app.services.file_group_service import get_file_group_by_id
from app.services.permission_service import (
    create_permission,
    delete_permission,
    get_file_group_permissions,
    get_user_permissions,
    get_workspace_permissions,
)
from app.services.workspace_service import get_workspace_by_id


router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"],
)


def serialize_permission(
    permission: Permission,
) -> dict:
    return {
        "id": str(permission.id),
        "user_id": str(permission.user_id),
        "workspace_id": str(permission.workspace_id),
        "file_group_id": str(permission.file_group_id),
        "file_id": (
            str(permission.file_id)
            if permission.file_id
            else None
        ),
        "granted_by": str(permission.granted_by),
        "created_at": (
            permission.created_at.isoformat()
            if permission.created_at
            else None
        ),
        "updated_at": (
            permission.updated_at.isoformat()
            if permission.updated_at
            else None
        ),
    }


def _require_workspace_manager(
    db: Session,
    user: User,
    workspace_id: UUID,
) -> None:
    """Owner: any workspace. Admin: only workspaces they created."""

    workspace = get_workspace_by_id(
        db=db,
        workspace_id=workspace_id,
    )

    if workspace is None or not can_manage_workspace(
        user,
        workspace,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace was not found.",
        )


# ============================================================
# GRANT PERMISSION
# ============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def grant_permission(
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    """
    Grant a User access to a File Group (or one File in it).

    An Admin can only grant access inside Workspaces they created.
    """

    try:
        permission = create_permission(
            db=db,
            user_id=user_id,
            workspace_id=workspace_id,
            file_group_id=file_group_id,
            file_id=file_id,
            granted_by=current_user,
        )

        return {
            "message": "Permission granted successfully.",
            "permission": serialize_permission(permission),
        }

    except ValueError as exc:
        error_message = str(exc)

        if error_message.startswith("PERMISSION_EXISTS:"):
            existing_permission_id = error_message.split(":", 1)[1]

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PERMISSION_EXISTS",
                    "message": (
                        "This User already has access "
                        "to this File Group."
                    ),
                    "existing_permission_id": existing_permission_id,
                },
            ) from exc

        not_found_errors = {
            "User was not found.",
            "Workspace was not found.",
            "File Group was not found.",
            "File was not found.",
        }

        if error_message in not_found_errors:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            ) from exc

        forbidden_errors = {
            "User account is inactive.",
            "Permissions can only be granted to normal Users.",
            "You can only grant access to Workspaces you created.",
        }

        if error_message in forbidden_errors:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        ) from exc


# ============================================================
# LIST USER PERMISSIONS
# ============================================================

@router.get("/users/{user_id}")
def list_user_permissions(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    permissions = get_user_permissions(
        db=db,
        user_id=user_id,
    )

    # Admins only see permissions inside their own workspaces.
    managed_ids = get_managed_workspace_ids(db, current_user)

    if managed_ids is not None:
        permissions = [
            p for p in permissions if p.workspace_id in managed_ids
        ]

    return {
        "user_id": str(user_id),
        "permissions": [
            serialize_permission(p) for p in permissions
        ],
    }


# ============================================================
# LIST WORKSPACE PERMISSIONS
# ============================================================

@router.get("/workspaces/{workspace_id}")
def list_workspace_permissions(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    _require_workspace_manager(db, current_user, workspace_id)

    permissions = get_workspace_permissions(
        db=db,
        workspace_id=workspace_id,
    )

    return {
        "workspace_id": str(workspace_id),
        "permissions": [
            serialize_permission(p) for p in permissions
        ],
    }


# ============================================================
# LIST FILE GROUP PERMISSIONS
# ============================================================

@router.get("/file-groups/{file_group_id}")
def list_file_group_permissions(
    file_group_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File Group was not found.",
        )

    _require_workspace_manager(
        db,
        current_user,
        file_group.workspace_id,
    )

    permissions = get_file_group_permissions(
        db=db,
        file_group_id=file_group_id,
    )

    return {
        "file_group_id": str(file_group_id),
        "permissions": [
            serialize_permission(p) for p in permissions
        ],
    }


# ============================================================
# REVOKE PERMISSION
# ============================================================

@router.delete("/{permission_id}")
def revoke_permission(
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_owner),
):
    existing = db.get(Permission, permission_id)

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission was not found.",
        )

    _require_workspace_manager(
        db,
        current_user,
        existing.workspace_id,
    )

    try:
        permission = delete_permission(
            db=db,
            permission_id=permission_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {
        "message": "Permission revoked successfully.",
        "permission": serialize_permission(permission),
    }
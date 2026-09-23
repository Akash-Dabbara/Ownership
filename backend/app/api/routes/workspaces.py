from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import (
    BaseModel,
    Field,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.owner_setup import get_db
from app.core.auth import (
    require_admin_or_owner,
    require_any_authenticated_user,
)
from app.models.user import User, UserRole
from app.models.workspace import (
    Workspace,
    WorkspaceSourceType,
)
from app.services.access_control import get_permitted_workspace_ids


router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class WorkspaceCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    source_type: WorkspaceSourceType
    destination_path: str = Field(
        ...,
        min_length=1,
    )
    description: str | None = None
    data_source_credential_id: UUID | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    source_type: WorkspaceSourceType | None = None
    destination_path: str | None = Field(
        default=None,
        min_length=1,
    )
    description: str | None = None
    data_source_credential_id: UUID | None = None


# ============================================================
# RESPONSE HELPER
# ============================================================

def workspace_response(
    workspace: Workspace,
    creator_email: str | None = None,
):
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "source_type": (
            workspace.source_type.value
            if hasattr(workspace.source_type, "value")
            else workspace.source_type
        ),
        "destination_path": workspace.destination_path,
        "description": workspace.description,
        "data_source_credential_id": (
            str(workspace.data_source_credential_id)
            if workspace.data_source_credential_id
            else None
        ),
        "created_by": str(workspace.created_by),
        "created_by_email": creator_email,
        "created_at": (
            workspace.created_at.isoformat()
            if workspace.created_at
            else None
        ),
        "updated_at": (
            workspace.updated_at.isoformat()
            if workspace.updated_at
            else None
        ),
    }


# ============================================================
# GET ALL WORKSPACES (Role-aware)
# ============================================================

@router.get("")
def get_workspaces(
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.OWNER:
        workspaces = (
            db.query(Workspace)
            .order_by(Workspace.created_at.asc())
            .all()
        )
    elif current_user.role == UserRole.ADMIN:
        workspaces = (
            db.query(Workspace)
            .filter(Workspace.created_by == current_user.id)
            .order_by(Workspace.created_at.asc())
            .all()
        )
    else:
        # Standard User: fetch only workspaces granted via permissions table
        permitted_ids = get_permitted_workspace_ids(db=db, user_id=current_user.id)
        if not permitted_ids:
            workspaces = []
        else:
            workspaces = (
                db.query(Workspace)
                .filter(Workspace.id.in_(permitted_ids))
                .order_by(Workspace.created_at.asc())
                .all()
            )

    creator_ids = {w.created_by for w in workspaces}
    creator_emails = {}
    if creator_ids:
        creators = (
            db.query(User)
            .filter(User.id.in_(creator_ids))
            .all()
        )
        creator_emails = {u.id: u.email for u in creators}

    return {
        "workspaces": [
            workspace_response(
                workspace,
                creator_emails.get(workspace.created_by),
            )
            for workspace in workspaces
        ]
    }


# ============================================================
# GET ONE WORKSPACE
# ============================================================

@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(require_any_authenticated_user),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    # If role is USER, verify they have permission to view this workspace
    if current_user.role == UserRole.USER:
        permitted_ids = get_permitted_workspace_ids(db=db, user_id=current_user.id)
        if workspace.id not in permitted_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

    creator = (
        db.query(User)
        .filter(User.id == workspace.created_by)
        .first()
    )

    return {
        "workspace": workspace_response(
            workspace,
            creator.email if creator else None,
        )
    }


# ============================================================
# CREATE WORKSPACE
# ============================================================

@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    normalized_name = payload.name.strip()
    normalized_destination = payload.destination_path.strip()

    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace name cannot be empty.",
        )

    if not normalized_destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination path cannot be empty.",
        )

    existing_workspace = (
        db.query(Workspace)
        .filter(func.lower(Workspace.name) == normalized_name.lower())
        .first()
    )

    if existing_workspace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A workspace with this name already exists.",
        )

    try:
        workspace = Workspace(
            name=normalized_name,
            source_type=payload.source_type,
            destination_path=normalized_destination,
            description=(
                payload.description.strip()
                if payload.description and payload.description.strip()
                else None
            ),
            data_source_credential_id=payload.data_source_credential_id,
            created_by=current_user.id,
        )

        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        return {
            "message": "Workspace created successfully.",
            "workspace": workspace_response(
                workspace,
                current_user.email,
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to create workspace: {str(exc)}",
        ) from exc


# ============================================================
# UPDATE WORKSPACE
# ============================================================

@router.put("/{workspace_id}")
def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    if current_user.role == UserRole.ADMIN and workspace.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Admin who created this Workspace, or the Owner, can edit it.",
        )

    try:
        if payload.name is not None:
            normalized_name = payload.name.strip()
            if not normalized_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Workspace name cannot be empty.",
                )

            existing_workspace = (
                db.query(Workspace)
                .filter(
                    func.lower(Workspace.name) == normalized_name.lower(),
                    Workspace.id != workspace.id,
                )
                .first()
            )

            if existing_workspace:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A workspace with this name already exists.",
                )

            workspace.name = normalized_name

        if payload.source_type is not None:
            workspace.source_type = payload.source_type

        if payload.destination_path is not None:
            normalized_destination = payload.destination_path.strip()
            if not normalized_destination:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Destination path cannot be empty.",
                )
            workspace.destination_path = normalized_destination

        if payload.description is not None:
            workspace.description = (
                payload.description.strip()
                if payload.description.strip()
                else None
            )

        if payload.data_source_credential_id is not None:
            workspace.data_source_credential_id = payload.data_source_credential_id

        db.commit()
        db.refresh(workspace)

        creator = (
            db.query(User)
            .filter(User.id == workspace.created_by)
            .first()
        )

        return {
            "message": "Workspace updated successfully.",
            "workspace": workspace_response(
                workspace,
                creator.email if creator else None,
            ),
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to update workspace: {str(exc)}",
        ) from exc


# ============================================================
# DELETE WORKSPACE
# ============================================================

@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(require_admin_or_owner),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    if current_user.role == UserRole.ADMIN and workspace.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Admin who created this Workspace, or the Owner, can delete it.",
        )

    try:
        db.delete(workspace)
        db.commit()

        return {
            "message": "Workspace deleted successfully.",
            "workspace_id": str(workspace_id),
        }

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete workspace: {str(exc)}",
        ) from exc
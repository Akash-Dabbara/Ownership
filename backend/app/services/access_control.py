"""
Central "who may touch what" rules for DataEase.

    Owner  -> everything
    Admin  -> only Workspaces they created, and only data source
              credentials the Owner assigned to them
    User   -> only what a Permission row grants them
              (a whole File Group, or one specific File)

Every route that reads or changes Workspaces, File Groups, Files or
data source credentials should go through these helpers so the rules
live in one place.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source_credential import DataSourceCredential
from app.models.permission import Permission
from app.models.user import User, UserRole
from app.models.workspace import Workspace


# ============================================================
# WORKSPACES
# ============================================================

def can_manage_workspace(
    user: User,
    workspace: Workspace,
) -> bool:
    """Owner: any Workspace. Admin: only Workspaces they created."""

    if user.role == UserRole.OWNER:
        return True

    if user.role == UserRole.ADMIN:
        return workspace.created_by == user.id

    return False


def get_managed_workspace_ids(
    db: Session,
    user: User,
) -> set[UUID] | None:
    """
    Workspace IDs the user can manage.

    Returns None for the Owner, meaning "all of them".
    """

    if user.role == UserRole.OWNER:
        return None

    if user.role == UserRole.ADMIN:
        rows = db.execute(
            select(Workspace.id).where(
                Workspace.created_by == user.id
            )
        ).scalars().all()

        return set(rows)

    return set()


# ============================================================
# DATA SOURCE CREDENTIALS
# ============================================================

def can_use_credential(
    user: User,
    credential: DataSourceCredential,
) -> bool:
    """
    Owner: any credential.
    Admin: only credentials assigned to them.
    User:  never (Users read data through a File Group instead).
    """

    if user.role == UserRole.OWNER:
        return True

    if user.role == UserRole.ADMIN:
        return credential.assigned_admin_id == user.id

    return False


# ============================================================
# USER (role USER) PERMISSIONS
# ============================================================

def get_permitted_workspace_ids(
    db: Session,
    user_id: UUID,
) -> set[UUID]:
    rows = db.execute(
        select(Permission.workspace_id).where(
            Permission.user_id == user_id
        )
    ).scalars().all()

    return set(rows)


def get_permitted_file_group_ids(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
) -> set[UUID]:
    rows = db.execute(
        select(Permission.file_group_id).where(
            Permission.user_id == user_id,
            Permission.workspace_id == workspace_id,
        )
    ).scalars().all()

    return set(rows)


def get_permitted_file_scope(
    db: Session,
    user_id: UUID,
    file_group_id: UUID,
) -> tuple[bool, set[UUID]]:
    """
    Returns (has_whole_group_access, specific_file_ids).

    A Permission with file_id = NULL grants the whole File Group.
    Otherwise each Permission grants one specific File.
    """

    rows = db.execute(
        select(Permission.file_id).where(
            Permission.user_id == user_id,
            Permission.file_group_id == file_group_id,
        )
    ).scalars().all()

    whole_group = any(file_id is None for file_id in rows)

    file_ids = {
        file_id for file_id in rows if file_id is not None
    }

    return whole_group, file_ids


def user_has_any_workspace_access(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
) -> bool:
    found = db.execute(
        select(Permission.id)
        .where(
            Permission.user_id == user_id,
            Permission.workspace_id == workspace_id,
        )
        .limit(1)
    ).scalar_one_or_none()

    return found is not None


def user_has_any_file_group_access(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
) -> bool:
    found = db.execute(
        select(Permission.id)
        .where(
            Permission.user_id == user_id,
            Permission.workspace_id == workspace_id,
            Permission.file_group_id == file_group_id,
        )
        .limit(1)
    ).scalar_one_or_none()

    return found is not None
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.file_group import FileGroup
from app.models.permission import Permission
from app.models.user import User, UserRole
from app.models.workspace import Workspace


# ============================================================
# GET EXISTING PERMISSION
# ============================================================

def get_permission(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID | None = None,
) -> Permission | None:
    """
    Return the existing permission for a specific
    User + Workspace + File Group (+ optional File) combination.
    """

    statement = (
        select(Permission)
        .where(
            Permission.user_id == user_id,
            Permission.workspace_id == workspace_id,
            Permission.file_group_id == file_group_id,
            Permission.file_id == file_id,
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


# ============================================================
# CREATE PERMISSION
# ============================================================

def create_permission(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
    granted_by: User,
    file_id: UUID | None = None,
    commit: bool = True,
) -> Permission:
    """
    Grant a normal User access to a File Group, or to one
    specific File within it if file_id is given.

    Validation performed:

    1. Target User exists.
    2. Target User is active.
    3. Target User has USER role.
    4. Workspace exists.
    5. Granter is the Owner, or the Admin who created this Workspace.
    6. File Group exists.
    7. File Group belongs to Workspace.
    8. If file_id given: File exists and belongs to the File Group.
    9. Permission does not already exist for this exact scope.

    Transaction behavior:

    commit=True:
        Permission is committed immediately.

        Used for direct Admin/Owner permission grants.

    commit=False:
        Permission is added to the current database
        transaction but is not committed.

        Used when Permission creation must be combined
        with another database operation, such as
        approving an Access Request.
    """

    # --------------------------------------------------------
    # VALIDATE TARGET USER
    # --------------------------------------------------------

    user_statement = (
        select(User)
        .where(
            User.id == user_id
        )
        .limit(1)
    )

    target_user = db.execute(
        user_statement
    ).scalar_one_or_none()

    if target_user is None:
        raise ValueError(
            "User was not found."
        )

    if not target_user.is_active:
        raise ValueError(
            "User account is inactive."
        )

    if target_user.role != UserRole.USER:
        raise ValueError(
            "Permissions can only be granted to normal Users."
        )

    # --------------------------------------------------------
    # VALIDATE WORKSPACE
    # --------------------------------------------------------

    workspace_statement = (
        select(Workspace)
        .where(
            Workspace.id == workspace_id
        )
        .limit(1)
    )

    workspace = db.execute(
        workspace_statement
    ).scalar_one_or_none()

    if workspace is None:
        raise ValueError(
            "Workspace was not found."
        )

    # --------------------------------------------------------
    # AN ADMIN MAY ONLY GRANT ACCESS INSIDE WORKSPACES THEY
    # CREATED. THE OWNER MAY GRANT ACCESS ANYWHERE.
    # --------------------------------------------------------

    if (
        granted_by.role == UserRole.ADMIN
        and workspace.created_by != granted_by.id
    ):
        raise ValueError(
            "You can only grant access to Workspaces you created."
        )

    # --------------------------------------------------------
    # VALIDATE FILE GROUP
    # --------------------------------------------------------

    file_group_statement = (
        select(FileGroup)
        .where(
            FileGroup.id == file_group_id
        )
        .limit(1)
    )

    file_group = db.execute(
        file_group_statement
    ).scalar_one_or_none()

    if file_group is None:
        raise ValueError(
            "File Group was not found."
        )

    # --------------------------------------------------------
    # VALIDATE WORKSPACE <-> FILE GROUP RELATIONSHIP
    # --------------------------------------------------------

    if file_group.workspace_id != workspace_id:
        raise ValueError(
            "The File Group does not belong to "
            "the specified Workspace."
        )

    # --------------------------------------------------------
    # VALIDATE FILE, IF SCOPING TO A SPECIFIC FILE
    # --------------------------------------------------------

    if file_id is not None:
        file_statement = (
            select(File)
            .where(File.id == file_id)
            .limit(1)
        )

        file_record = db.execute(
            file_statement
        ).scalar_one_or_none()

        if file_record is None:
            raise ValueError(
                "File was not found."
            )

        if file_record.file_group_id != file_group_id:
            raise ValueError(
                "The File does not belong to "
                "the specified File Group."
            )

    # --------------------------------------------------------
    # CHECK EXISTING PERMISSION
    # --------------------------------------------------------

    existing_permission = get_permission(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
        file_id=file_id,
    )

    if existing_permission is not None:
        raise ValueError(
            f"PERMISSION_EXISTS:{existing_permission.id}"
        )

    # --------------------------------------------------------
    # CREATE PERMISSION
    # --------------------------------------------------------

    permission = Permission(
        user_id=user_id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
        file_id=file_id,
        granted_by=granted_by.id,
    )

    db.add(permission)

    # --------------------------------------------------------
    # COMMIT WHEN REQUIRED
    # --------------------------------------------------------

    if commit:
        try:
            db.commit()
            db.refresh(permission)

        except Exception:
            db.rollback()
            raise

    return permission


# ============================================================
# GET USER PERMISSIONS
# ============================================================

def get_user_permissions(
    db: Session,
    user_id: UUID,
) -> list[Permission]:
    """
    Return all permissions granted to a specific User.
    """

    statement = (
        select(Permission)
        .where(
            Permission.user_id == user_id
        )
        .order_by(
            Permission.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        )
        .scalars()
        .all()
    )


# ============================================================
# GET WORKSPACE PERMISSIONS
# ============================================================

def get_workspace_permissions(
    db: Session,
    workspace_id: UUID,
) -> list[Permission]:
    """
    Return all permissions belonging to a Workspace.
    """

    statement = (
        select(Permission)
        .where(
            Permission.workspace_id == workspace_id
        )
        .order_by(
            Permission.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        )
        .scalars()
        .all()
    )


# ============================================================
# GET FILE GROUP PERMISSIONS
# ============================================================

def get_file_group_permissions(
    db: Session,
    file_group_id: UUID,
) -> list[Permission]:
    """
    Return all permissions for a specific File Group.
    """

    statement = (
        select(Permission)
        .where(
            Permission.file_group_id == file_group_id
        )
        .order_by(
            Permission.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        )
        .scalars()
        .all()
    )


# ============================================================
# CHECK FILE GROUP ACCESS
# ============================================================

def user_has_file_group_access(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
) -> bool:
    """
    Return True if the User has whole-File-Group permission
    (i.e. a Permission row with file_id = NULL for this scope).

    Note: this intentionally does NOT return True for a
    file-scoped permission — use user_has_file_access for that.
    """

    permission = get_permission(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
        file_id=None,
    )

    return permission is not None


# ============================================================
# CHECK SPECIFIC FILE ACCESS
# ============================================================

def user_has_file_access(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID,
) -> bool:
    """
    Return True if the User can access this specific File —
    either because they have whole-File-Group access, or because
    they have a Permission scoped to this exact File.
    """

    if user_has_file_group_access(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
    ):
        return True

    file_level_permission = get_permission(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
        file_id=file_id,
    )

    return file_level_permission is not None


# ============================================================
# DELETE PERMISSION
# ============================================================

def delete_permission(
    db: Session,
    permission_id: UUID,
) -> Permission:
    """
    Delete an existing Permission.
    """

    statement = (
        select(Permission)
        .where(
            Permission.id == permission_id
        )
        .limit(1)
    )

    permission = db.execute(
        statement
    ).scalar_one_or_none()

    if permission is None:
        raise ValueError(
            "Permission was not found."
        )

    try:
        db.delete(permission)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return permission
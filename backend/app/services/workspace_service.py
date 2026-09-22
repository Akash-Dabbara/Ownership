from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace


def find_workspace_by_name(
    db: Session,
    name: str,
) -> Workspace | None:
    """
    Find a Workspace using a case-insensitive
    name comparison.
    """

    normalized_name = name.strip()

    if not normalized_name:
        return None

    statement = (
        select(Workspace)
        .where(
            func.lower(Workspace.name)
            == normalized_name.lower()
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


# ============================================================
# CREATE WORKSPACE
# ============================================================

def create_workspace(
    db: Session,
    name: str,
    description: str | None,
    created_by: User,
) -> Workspace:
    """
    Create a new Workspace.

    Data source information is intentionally not
    handled at the Workspace level.

    Data sources are selected later when configuring
    File Groups.
    """

    normalized_name = name.strip()

    if not normalized_name:
        raise ValueError(
            "Workspace name cannot be empty."
        )

    existing_workspace = find_workspace_by_name(
        db=db,
        name=normalized_name,
    )

    if existing_workspace is not None:
        raise ValueError(
            f"WORKSPACE_NAME_EXISTS:{existing_workspace.id}"
        )

    workspace = Workspace(
        name=normalized_name,
        description=(
            description.strip()
            if description
            else None
        ),
        created_by=created_by.id,
    )

    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    return workspace


# ============================================================
# GET ALL WORKSPACES
# ============================================================

def get_all_workspaces(
    db: Session,
) -> list[Workspace]:
    """
    Return all Workspaces ordered by creation time.
    """

    statement = (
        select(Workspace)
        .order_by(
            Workspace.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        ).scalars().all()
    )


# ============================================================
# GET WORKSPACE BY ID
# ============================================================

def get_workspace_by_id(
    db: Session,
    workspace_id: UUID,
) -> Workspace | None:
    """
    Return a Workspace by its unique ID.
    """

    statement = (
        select(Workspace)
        .where(
            Workspace.id == workspace_id
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


# ============================================================
# UPDATE WORKSPACE
# ============================================================

def update_workspace(
    db: Session,
    workspace_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> Workspace:
    """
    Update Workspace metadata.

    Only supplied fields are changed.
    """

    workspace = get_workspace_by_id(
        db=db,
        workspace_id=workspace_id,
    )

    if workspace is None:
        raise ValueError(
            "Workspace was not found."
        )

    # --------------------------------------------------------
    # UPDATE NAME
    # --------------------------------------------------------

    if name is not None:
        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "Workspace name cannot be empty."
            )

        existing_workspace = find_workspace_by_name(
            db=db,
            name=normalized_name,
        )

        if (
            existing_workspace is not None
            and existing_workspace.id != workspace.id
        ):
            raise ValueError(
                "A workspace with this name already exists."
            )

        workspace.name = normalized_name

    # --------------------------------------------------------
    # UPDATE DESCRIPTION
    # --------------------------------------------------------

    if description is not None:
        workspace.description = (
            description.strip()
            if description.strip()
            else None
        )

    db.commit()
    db.refresh(workspace)

    return workspace


# ============================================================
# DELETE WORKSPACE
# ============================================================

def delete_workspace(
    db: Session,
    workspace_id: UUID,
) -> Workspace:
    """
    Delete a Workspace by ID.

    Related File Groups and permissions will be handled
    according to the database relationship configuration.
    """

    workspace = get_workspace_by_id(
        db=db,
        workspace_id=workspace_id,
    )

    if workspace is None:
        raise ValueError(
            "Workspace was not found."
        )

    db.delete(workspace)
    db.commit()

    return workspace
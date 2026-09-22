from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access_request import (
    AccessRequest,
    AccessRequestStatus,
)
from app.models.file import File
from app.models.user import User, UserRole
from app.services.file_group_service import (
    get_file_group_by_id,
)
from app.services.permission_service import (
    create_permission,
    user_has_file_access,
    user_has_file_group_access,
)
from app.services.workspace_service import (
    get_workspace_by_id,
)


def get_access_request_by_id(
    db: Session,
    request_id: UUID,
) -> AccessRequest | None:
    statement = (
        select(AccessRequest)
        .where(
            AccessRequest.id == request_id
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


def get_pending_access_request(
    db: Session,
    user_id: UUID,
    workspace_id: UUID,
    file_group_id: UUID,
    file_id: UUID | None = None,
) -> AccessRequest | None:
    statement = (
        select(AccessRequest)
        .where(
            AccessRequest.user_id == user_id,
            AccessRequest.workspace_id
            == workspace_id,
            AccessRequest.file_group_id
            == file_group_id,
            AccessRequest.file_id == file_id,
            AccessRequest.status
            == AccessRequestStatus.PENDING,
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


def create_access_request(
    db: Session,
    user: User,
    workspace_id: UUID,
    file_group_id: UUID,
    admin_id: UUID,
    file_id: UUID | None = None,
    reason: str | None = None,
) -> AccessRequest:

    workspace = get_workspace_by_id(
        db=db,
        workspace_id=workspace_id,
    )

    if workspace is None:
        raise ValueError(
            "Workspace was not found."
        )

    file_group = get_file_group_by_id(
        db=db,
        file_group_id=file_group_id,
    )

    if file_group is None:
        raise ValueError(
            "File Group was not found."
        )

    if file_group.workspace_id != workspace_id:
        raise ValueError(
            "The File Group does not belong to "
            "the specified Workspace."
        )

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

    admin_statement = (
        select(User)
        .where(
            User.id == admin_id,
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
        .limit(1)
    )

    admin = db.execute(
        admin_statement
    ).scalar_one_or_none()

    if admin is None:
        raise ValueError(
            "The selected Admin was not found "
            "or is not active."
        )

    already_has_access = (
        user_has_file_access(
            db=db,
            user_id=user.id,
            workspace_id=workspace_id,
            file_group_id=file_group_id,
            file_id=file_id,
        )
        if file_id is not None
        else user_has_file_group_access(
            db=db,
            user_id=user.id,
            workspace_id=workspace_id,
            file_group_id=file_group_id,
        )
    )

    if already_has_access:
        raise ValueError(
            "You already have permission to "
            "access this File Group."
        )

    existing_request = get_pending_access_request(
        db=db,
        user_id=user.id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
        file_id=file_id,
    )

    if existing_request is not None:
        raise ValueError(
            f"ACCESS_REQUEST_EXISTS:"
            f"{existing_request.id}"
        )

    cleaned_reason = None

    if reason is not None:
        cleaned_reason = reason.strip() or None

    access_request = AccessRequest(
        user_id=user.id,
        workspace_id=workspace_id,
        file_group_id=file_group_id,
        file_id=file_id,
        admin_id=admin.id,
        status=AccessRequestStatus.PENDING,
        reason=cleaned_reason,
    )

    db.add(access_request)
    db.commit()
    db.refresh(access_request)

    return access_request


def get_user_access_requests(
    db: Session,
    user_id: UUID,
) -> list[AccessRequest]:

    statement = (
        select(AccessRequest)
        .where(
            AccessRequest.user_id == user_id
        )
        .order_by(
            AccessRequest.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        ).scalars().all()
    )


def get_admin_access_requests(
    db: Session,
    admin_id: UUID,
) -> list[AccessRequest]:

    statement = (
        select(AccessRequest)
        .where(
            AccessRequest.admin_id == admin_id
        )
        .order_by(
            AccessRequest.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        ).scalars().all()
    )


def get_all_access_requests(
    db: Session,
) -> list[AccessRequest]:

    statement = (
        select(AccessRequest)
        .order_by(
            AccessRequest.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        ).scalars().all()
    )


def approve_access_request(
    db: Session,
    request_id: UUID,
    reviewer: User,
) -> AccessRequest:
    """
    Approve an Access Request.

    Permission creation and request approval happen
    in the same database transaction.
    """

    access_request = get_access_request_by_id(
        db=db,
        request_id=request_id,
    )

    if access_request is None:
        raise ValueError(
            "Access Request was not found."
        )

    if (
        access_request.status
        != AccessRequestStatus.PENDING
    ):
        raise ValueError(
            "Only a pending Access Request "
            "can be approved."
        )

    if reviewer.role == UserRole.ADMIN:

        if access_request.admin_id != reviewer.id:
            raise ValueError(
                "You are not authorized to approve "
                "this Access Request."
            )

    elif reviewer.role != UserRole.OWNER:
        raise ValueError(
            "You are not authorized to approve "
            "Access Requests."
        )

    already_has_access = (
        user_has_file_access(
            db=db,
            user_id=access_request.user_id,
            workspace_id=access_request.workspace_id,
            file_group_id=access_request.file_group_id,
            file_id=access_request.file_id,
        )
        if access_request.file_id is not None
        else user_has_file_group_access(
            db=db,
            user_id=access_request.user_id,
            workspace_id=access_request.workspace_id,
            file_group_id=access_request.file_group_id,
        )
    )

    try:

        if not already_has_access:

            create_permission(
                db=db,
                user_id=access_request.user_id,
                workspace_id=access_request.workspace_id,
                file_group_id=access_request.file_group_id,
                file_id=access_request.file_id,
                granted_by=reviewer,
                commit=False,
            )

        access_request.status = (
            AccessRequestStatus.APPROVED
        )

        access_request.reviewed_at = (
            datetime.now(timezone.utc)
        )

        access_request.reviewed_by = reviewer.id

        db.commit()
        db.refresh(access_request)

        return access_request

    except Exception:
        db.rollback()
        raise


def reject_access_request(
    db: Session,
    request_id: UUID,
    reviewer: User,
) -> AccessRequest:

    access_request = get_access_request_by_id(
        db=db,
        request_id=request_id,
    )

    if access_request is None:
        raise ValueError(
            "Access Request was not found."
        )

    if (
        access_request.status
        != AccessRequestStatus.PENDING
    ):
        raise ValueError(
            "Only a pending Access Request "
            "can be rejected."
        )

    if reviewer.role == UserRole.ADMIN:

        if access_request.admin_id != reviewer.id:
            raise ValueError(
                "You are not authorized to reject "
                "this Access Request."
            )

    elif reviewer.role != UserRole.OWNER:
        raise ValueError(
            "You are not authorized to reject "
            "Access Requests."
        )

    access_request.status = (
        AccessRequestStatus.REJECTED
    )

    access_request.reviewed_at = (
        datetime.now(timezone.utc)
    )

    access_request.reviewed_by = reviewer.id

    db.commit()
    db.refresh(access_request)

    return access_request


def cancel_access_request(
    db: Session,
    request_id: UUID,
    user: User,
) -> AccessRequest:

    access_request = get_access_request_by_id(
        db=db,
        request_id=request_id,
    )

    if access_request is None:
        raise ValueError(
            "Access Request was not found."
        )

    if access_request.user_id != user.id:
        raise ValueError(
            "You are not authorized to cancel "
            "this Access Request."
        )

    if (
        access_request.status
        != AccessRequestStatus.PENDING
    ):
        raise ValueError(
            "Only a pending Access Request "
            "can be cancelled."
        )

    access_request.status = (
        AccessRequestStatus.CANCELLED
    )

    access_request.reviewed_at = (
        datetime.now(timezone.utc)
    )

    access_request.reviewed_by = user.id

    db.commit()
    db.refresh(access_request)

    return access_request
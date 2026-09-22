from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.admin_setup_request import (
    AdminSetupRequest,
    AdminSetupRequestStatus,
)
from app.models.user import User, UserRole


def create_admin_setup_request(
    db: Session,
    email: str,
    password: str,
) -> AdminSetupRequest:
    normalized_email = email.strip().lower()

    existing_user = db.execute(
        select(User.id)
        .where(User.email == normalized_email)
        .limit(1)
    ).scalar_one_or_none()

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    existing_request = db.execute(
        select(AdminSetupRequest.id)
        .where(
            AdminSetupRequest.email == normalized_email,
            AdminSetupRequest.status
            == AdminSetupRequestStatus.PENDING,
        )
        .limit(1)
    ).scalar_one_or_none()

    if existing_request is not None:
        raise ValueError(
            "An Admin setup request for this email is already pending."
        )

    admin_request = AdminSetupRequest(
        email=normalized_email,
        password_hash=hash_password(password),
        status=AdminSetupRequestStatus.PENDING,
    )

    db.add(admin_request)
    db.commit()
    db.refresh(admin_request)

    return admin_request


def get_pending_admin_requests(
    db: Session,
) -> list[AdminSetupRequest]:
    statement = (
        select(AdminSetupRequest)
        .where(
            AdminSetupRequest.status
            == AdminSetupRequestStatus.PENDING
        )
        .order_by(AdminSetupRequest.created_at.asc())
    )

    return list(db.execute(statement).scalars().all())


def approve_admin_setup_request(
    db: Session,
    request_id: UUID,
) -> User:
    statement = (
        select(AdminSetupRequest)
        .where(AdminSetupRequest.id == request_id)
        .with_for_update()
    )

    admin_request = db.execute(statement).scalar_one_or_none()

    if admin_request is None:
        raise ValueError(
            "Admin setup request was not found."
        )

    if admin_request.status != AdminSetupRequestStatus.PENDING:
        raise ValueError(
            "Only a PENDING Admin setup request can be approved."
        )

    existing_user = db.execute(
        select(User.id)
        .where(User.email == admin_request.email)
        .limit(1)
    ).scalar_one_or_none()

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    admin = User(
        email=admin_request.email,
        password_hash=admin_request.password_hash,
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=True,
    )

    admin_request.status = AdminSetupRequestStatus.APPROVED
    admin_request.reviewed_at = datetime.now(timezone.utc)

    db.add(admin)
    db.commit()
    db.refresh(admin)

    return admin


def reject_admin_setup_request(
    db: Session,
    request_id: UUID,
    rejection_reason: str | None = None,
) -> AdminSetupRequest:
    statement = (
        select(AdminSetupRequest)
        .where(AdminSetupRequest.id == request_id)
        .with_for_update()
    )

    admin_request = db.execute(statement).scalar_one_or_none()

    if admin_request is None:
        raise ValueError(
            "Admin setup request was not found."
        )

    if admin_request.status != AdminSetupRequestStatus.PENDING:
        raise ValueError(
            "Only a PENDING Admin setup request can be rejected."
        )

    admin_request.status = AdminSetupRequestStatus.REJECTED
    admin_request.rejection_reason = (
        rejection_reason.strip()
        if rejection_reason
        else None
    )
    admin_request.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(admin_request)

    return admin_request
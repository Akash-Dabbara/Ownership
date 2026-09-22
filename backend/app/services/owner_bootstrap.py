from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.owner_setup_request import (
    OwnerSetupRequest,
    OwnerSetupRequestStatus,
)
from app.models.user import User, UserRole


def owner_exists(db: Session) -> bool:
    """
    Check whether DataEase already has an active Owner.

    Returns:
        True  -> an active Owner exists
        False -> no active Owner exists
    """

    statement = (
        select(User.id)
        .where(
            User.role == UserRole.OWNER,
            User.is_active.is_(True),
        )
        .limit(1)
    )

    owner_id = db.execute(statement).scalar_one_or_none()

    return owner_id is not None


def create_owner_setup_request(
    db: Session,
    email: str,
    password: str,
) -> OwnerSetupRequest:
    """
    Create the initial Owner Setup Request.

    An Owner Setup Request can only be created when
    there is no active Owner in the system.

    The plaintext password is never stored.
    It is securely hashed before being saved.
    """

    if owner_exists(db):
        raise ValueError(
            "An active Owner already exists. "
            "Initial Owner setup is no longer available."
        )

    normalized_email = email.strip().lower()

    owner_request = OwnerSetupRequest(
        email=normalized_email,
        password_hash=hash_password(password),
        status=OwnerSetupRequestStatus.PENDING,
    )

    db.add(owner_request)
    db.commit()
    db.refresh(owner_request)

    return owner_request


def approve_owner_setup_request(
    db: Session,
    request_id: UUID,
) -> User:
    """
    Approve a pending Owner Setup Request and create
    the first active OWNER user.

    The Owner Setup Request password is already hashed,
    so its password_hash is copied directly to the User.
    """

    # Lock the setup request while processing it.
    statement = (
        select(OwnerSetupRequest)
        .where(OwnerSetupRequest.id == request_id)
        .with_for_update()
    )

    owner_request = db.execute(statement).scalar_one_or_none()

    if owner_request is None:
        raise ValueError("Owner setup request was not found.")

    if owner_request.status != OwnerSetupRequestStatus.PENDING:
        raise ValueError(
            "Only a PENDING Owner setup request can be approved."
        )

    # Final check before creating the active Owner.
    if owner_exists(db):
        raise ValueError(
            "An active Owner already exists. "
            "This Owner setup request cannot be approved."
        )

    # Prevent duplicate email addresses.
    existing_user = db.execute(
        select(User.id)
        .where(User.email == owner_request.email)
        .limit(1)
    ).scalar_one_or_none()

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    # Create the actual active Owner.
    owner = User(
        email=owner_request.email,
        password_hash=owner_request.password_hash,
        role=UserRole.OWNER,
        is_active=True,
        must_change_password=False,
    )

    # Update the setup request.
    owner_request.status = OwnerSetupRequestStatus.APPROVED
    owner_request.reviewed_at = datetime.now(timezone.utc)

    db.add(owner)

    # Save both changes in the same transaction.
    db.commit()

    db.refresh(owner)

    return owner
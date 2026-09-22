from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.access_request import AccessRequest
from app.models.permission import Permission
from app.models.user import User, UserRole


def create_user(
    db: Session,
    email: str,
    temporary_password: str,
) -> User:
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

    user = User(
        email=normalized_email,
        password_hash=hash_password(
            temporary_password
        ),
        role=UserRole.USER,
        is_active=True,
        must_change_password=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_all_users(
    db: Session,
) -> list[User]:
    statement = (
        select(User)
        .where(User.role == UserRole.USER)
        .order_by(User.created_at.asc())
    )

    return list(
        db.execute(statement).scalars().all()
    )


def deactivate_user(
    db: Session,
    user_id,
) -> User:
    statement = (
        select(User)
        .where(
            User.id == user_id,
            User.role == UserRole.USER,
        )
        .with_for_update()
    )

    user = db.execute(
        statement
    ).scalar_one_or_none()

    if user is None:
        raise ValueError(
            "User was not found."
        )

    if not user.is_active:
        raise ValueError(
            "User account is already inactive."
        )

    user.is_active = False

    db.commit()
    db.refresh(user)

    return user


def reactivate_user(
    db: Session,
    user_id,
) -> User:
    statement = (
        select(User)
        .where(
            User.id == user_id,
            User.role == UserRole.USER,
        )
        .with_for_update()
    )

    user = db.execute(
        statement
    ).scalar_one_or_none()

    if user is None:
        raise ValueError(
            "User was not found."
        )

    if user.is_active:
        raise ValueError(
            "User account is already active."
        )

    user.is_active = True

    db.commit()
    db.refresh(user)

    return user


def delete_user(
    db: Session,
    user_id,
) -> User:
    statement = (
        select(User)
        .where(
            User.id == user_id,
            User.role == UserRole.USER,
        )
        .with_for_update()
    )

    user = db.execute(
        statement
    ).scalar_one_or_none()

    if user is None:
        raise ValueError(
            "User was not found."
        )

    try:
        # permissions.user_id and access_requests.user_id have no
        # ON DELETE CASCADE, so deleting a User who has any access
        # would fail with a foreign-key error (HTTP 500). A User's own
        # access rows are removed together with the account.
        db.execute(
            delete(Permission).where(
                Permission.user_id == user.id
            )
        )
        db.execute(
            delete(AccessRequest).where(
                AccessRequest.user_id == user.id
            )
        )

        db.delete(user)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise ValueError(
            "This account is referenced by other records and "
            "cannot be deleted. Deactivate it instead."
        ) from exc

    return user
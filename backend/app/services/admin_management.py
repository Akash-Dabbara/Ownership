from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def get_all_admins(
    db: Session,
) -> list[User]:
    statement = (
        select(User)
        .where(User.role == UserRole.ADMIN)
        .order_by(User.created_at.asc())
    )

    return list(
        db.execute(statement).scalars().all()
    )


def deactivate_admin(
    db: Session,
    admin_id,
) -> User:
    statement = (
        select(User)
        .where(
            User.id == admin_id,
            User.role == UserRole.ADMIN,
        )
        .with_for_update()
    )

    admin = db.execute(
        statement
    ).scalar_one_or_none()

    if admin is None:
        raise ValueError(
            "Admin user was not found."
        )

    if not admin.is_active:
        raise ValueError(
            "Admin account is already inactive."
        )

    admin.is_active = False

    db.commit()
    db.refresh(admin)

    return admin


def reactivate_admin(
    db: Session,
    admin_id,
) -> User:
    statement = (
        select(User)
        .where(
            User.id == admin_id,
            User.role == UserRole.ADMIN,
        )
        .with_for_update()
    )

    admin = db.execute(
        statement
    ).scalar_one_or_none()

    if admin is None:
        raise ValueError(
            "Admin user was not found."
        )

    if admin.is_active:
        raise ValueError(
            "Admin account is already active."
        )

    admin.is_active = True

    db.commit()
    db.refresh(admin)

    return admin


def delete_admin(
    db: Session,
    admin_id,
) -> User:
    statement = (
        select(User)
        .where(
            User.id == admin_id,
            User.role == UserRole.ADMIN,
        )
        .with_for_update()
    )

    admin = db.execute(
        statement
    ).scalar_one_or_none()

    if admin is None:
        raise ValueError(
            "Admin user was not found."
        )

    try:
        db.delete(admin)
        db.commit()

    except IntegrityError as exc:
        # An Admin who has granted permissions, received access
        # requests or created workspaces is still referenced by
        # those rows. Deleting them silently would destroy other
        # people's access, so refuse and point to deactivation.
        db.rollback()

        raise ValueError(
            "This Admin has granted permissions or owns other "
            "records and cannot be deleted. Deactivate the "
            "account instead."
        ) from exc

    return admin
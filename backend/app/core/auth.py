from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.owner_setup import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole


security = HTTPBearer()


def _get_authenticated_user(
    credentials: HTTPAuthorizationCredentials,
    db: Session,
) -> User:
    """
    Validate the JWT and return the authenticated active user.

    This internal function does not enforce the
    must_change_password requirement so that the
    password-change endpoint remains accessible.
    """

    token = credentials.credentials

    try:
        payload = decode_access_token(token)

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
            )

        try:
            user_uuid = UUID(user_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
            ) from exc

    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
        ) from exc

    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    user = db.execute(
        select(User)
        .where(User.id == user_uuid)
        .limit(1)
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Return the currently authenticated user.

    Users who must change their password are blocked
    from normal protected APIs.
    """

    user = _get_authenticated_user(
        credentials=credentials,
        db=db,
    )

    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before accessing this resource.",
        )

    return user


def get_current_user_for_password_change(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Return the authenticated user for the password-change
    endpoint.

    This intentionally allows users whose
    must_change_password flag is True.
    """

    return _get_authenticated_user(
        credentials=credentials,
        db=db,
    )


def require_owner(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Allow access only to an active Owner
    who has completed any required password change.
    """

    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required.",
        )

    return current_user


def require_admin_or_owner(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Allow access to Owners and Admins who have
    completed any required password change.
    """

    if current_user.role not in {
        UserRole.OWNER,
        UserRole.ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Owner access required.",
        )

    return current_user


def require_any_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Allow access to any active authenticated user
    who has completed any required password change.
    """

    return current_user
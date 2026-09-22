from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.auth import get_current_user_for_password_change
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate a user and return a JWT access token.
    """

    normalized_email = login_data.email.strip().lower()

    user = db.execute(
        select(User)
        .where(User.email == normalized_email)
        .limit(1)
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(
        login_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        must_change_password=user.must_change_password,
    )


@router.post(
    "/change-password",
)
def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(
        get_current_user_for_password_change
    ),
    db: Session = Depends(get_db),
):
    """
    Change the password of the currently authenticated user.

    This endpoint remains accessible even when
    must_change_password is True.
    """

    user = db.execute(
        select(User)
        .where(User.id == current_user.id)
        .limit(1)
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if not verify_password(
        password_data.current_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "New password must be different "
                "from the current password."
            ),
        )

    if len(password_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "New password must contain "
                "at least 8 characters."
            ),
        )

    user.password_hash = hash_password(
        password_data.new_password
    )

    user.must_change_password = False

    db.commit()
    db.refresh(user)

    return {
        "message": "Password changed successfully.",
        "must_change_password": user.must_change_password,
    }
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.db.session import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Hash a plaintext password securely.

    The returned value is safe to store in the database.
    """
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against its stored hash.
    """
    return password_hash.verify(password, hashed_password)


def create_access_token(
    user_id: str,
    role: str,
    expires_minutes: int = 60,
) -> str:
    """
    Create a JWT access token for an authenticated user.
    """

    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Raises jwt.InvalidTokenError when the token
    is invalid or expired.
    """

    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=["HS256"],
    )
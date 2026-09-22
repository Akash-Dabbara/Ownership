from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.owner_bootstrap import (
    approve_owner_setup_request,
    create_owner_setup_request,
    owner_exists,
)


router = APIRouter(
    prefix="/owner-setup",
    tags=["Owner Setup"],
)


def get_db():
    """
    Provide a database session for the API request.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


class OwnerSetupCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


# ============================================================
# CHECK WHETHER AN OWNER ALREADY EXISTS (public)
#
# Used by the frontend on first load to decide whether to show
# the Owner Setup screen or the normal Role Select screen.
# ============================================================

@router.get("/status")
def get_owner_setup_status(
    db: Session = Depends(get_db),
):
    return {
        "owner_exists": owner_exists(db),
    }


@router.post(
    "/request",
    status_code=status.HTTP_201_CREATED,
)
def request_owner_setup(
    payload: OwnerSetupCreate,
    db: Session = Depends(get_db),
):
    """
    Submit the initial Owner Setup request and activate it
    immediately.

    This is only ever reachable when no active Owner exists yet
    (enforced by create_owner_setup_request). Since nobody inside
    the app could exist to review this request at that point,
    submitting it IS the approval — this is the one and only
    Owner setup that is auto-approved rather than requiring a
    separate reviewer.
    """

    try:
        owner_request = create_owner_setup_request(
            db=db,
            email=payload.email,
            password=payload.password,
        )

        owner = approve_owner_setup_request(
            db=db,
            request_id=owner_request.id,
        )

        return {
            "message": (
                "Owner account created successfully. "
                "You can now log in."
            ),
            "request_id": str(owner_request.id),
            "status": "APPROVED",
            "owner_email": owner.email,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
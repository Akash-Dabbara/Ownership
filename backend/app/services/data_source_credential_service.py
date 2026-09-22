from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import (
    EncryptionError,
    decrypt_json,
    encrypt_json,
)
from app.models.data_source_credential import (
    DataSourceCredential,
    DataSourceType,
)
from app.models.user import User, UserRole


# Sentinel: "the caller did not pass this argument".
# Needed because None is a real value for assigned_admin_id
# (it means "make this Owner-only").
UNSET = object()


def get_credential_by_id(
    db: Session,
    credential_id: UUID,
) -> DataSourceCredential | None:
    statement = (
        select(DataSourceCredential)
        .where(DataSourceCredential.id == credential_id)
        .limit(1)
    )

    return db.execute(statement).scalar_one_or_none()


def get_credential_by_name(
    db: Session,
    name: str,
    assigned_admin_id: UUID | None = None,
) -> DataSourceCredential | None:
    """
    Find a credential by exact, case-insensitive name within one
    "owner scope": the given Admin's credentials, or the Owner-only
    credentials when assigned_admin_id is None.

    (The old version used ILIKE, where "_" and "%" act as wildcards,
    so a name like "prod_db" also matched "prodXdb".)
    """

    normalized_name = name.strip().lower()

    statement = select(DataSourceCredential).where(
        func.lower(DataSourceCredential.name)
        == normalized_name
    )

    if assigned_admin_id is None:
        statement = statement.where(
            DataSourceCredential.assigned_admin_id.is_(None)
        )
    else:
        statement = statement.where(
            DataSourceCredential.assigned_admin_id
            == assigned_admin_id
        )

    return db.execute(
        statement.limit(1)
    ).scalar_one_or_none()


def list_credentials(
    db: Session,
    include_inactive: bool = False,
    viewer: User | None = None,
) -> list[DataSourceCredential]:
    """
    Owner (or viewer=None): every credential.
    Admin: only credentials assigned to them, and only active ones.
    Anyone else: nothing.
    """

    statement = select(DataSourceCredential)

    if viewer is not None and viewer.role == UserRole.ADMIN:
        statement = statement.where(
            DataSourceCredential.assigned_admin_id == viewer.id
        )
        include_inactive = False

    elif viewer is not None and viewer.role != UserRole.OWNER:
        return []

    if not include_inactive:
        statement = statement.where(
            DataSourceCredential.is_active.is_(True)
        )

    statement = statement.order_by(
        DataSourceCredential.name.asc()
    )

    return list(
        db.execute(statement).scalars().all()
    )


def _ensure_admin_exists(
    db: Session,
    admin_id: UUID,
) -> None:
    admin = db.execute(
        select(User.id)
        .where(
            User.id == admin_id,
            User.role == UserRole.ADMIN,
        )
        .limit(1)
    ).scalar_one_or_none()

    if admin is None:
        raise ValueError(
            "Assigned Admin was not found."
        )


def create_credential(
    db: Session,
    name: str,
    source_type: DataSourceType,
    config: dict,
    created_by: User,
    assigned_admin_id: UUID | None = None,
) -> DataSourceCredential:
    normalized_name = name.strip()

    if not normalized_name:
        raise ValueError(
            "Credential name cannot be empty."
        )

    if len(normalized_name) > 255:
        raise ValueError(
            "Credential name cannot exceed 255 characters."
        )

    if not isinstance(source_type, DataSourceType):
        raise ValueError(
            "Invalid data source type."
        )

    if not isinstance(config, dict) or not config:
        raise ValueError(
            "Credential configuration cannot be empty."
        )

    if assigned_admin_id is not None:
        _ensure_admin_exists(db, assigned_admin_id)

    existing_credential = get_credential_by_name(
        db=db,
        name=normalized_name,
        assigned_admin_id=assigned_admin_id,
    )

    if existing_credential is not None:
        raise ValueError(
            f"CREDENTIAL_EXISTS:{existing_credential.id}"
        )

    try:
        encrypted_config = encrypt_json(config)
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError(
            "Failed to encrypt credential configuration."
        ) from exc

    credential = DataSourceCredential(
        name=normalized_name,
        source_type=source_type,
        encrypted_config=encrypted_config,
        is_active=True,
        created_by=created_by.id,
        assigned_admin_id=assigned_admin_id,
    )

    db.add(credential)

    try:
        db.commit()
        db.refresh(credential)
    except Exception:
        db.rollback()
        raise

    return credential


def get_decrypted_config(
    db: Session,
    credential_id: UUID,
) -> dict:
    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None:
        raise ValueError(
            "Credential was not found."
        )

    if not credential.is_active:
        raise ValueError(
            "Credential is inactive."
        )

    try:
        return decrypt_json(
            credential.encrypted_config
        )
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError(
            "Failed to decrypt credential configuration."
        ) from exc


def update_credential(
    db: Session,
    credential_id: UUID,
    name: str | None = None,
    source_type: DataSourceType | None = None,
    config: dict | None = None,
    assigned_admin_id=UNSET,
) -> DataSourceCredential:
    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None:
        raise ValueError(
            "Credential was not found."
        )

    new_name = credential.name
    new_admin_id = credential.assigned_admin_id
    identity_changed = False

    if name is not None:
        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "Credential name cannot be empty."
            )

        if len(normalized_name) > 255:
            raise ValueError(
                "Credential name cannot exceed 255 characters."
            )

        new_name = normalized_name
        identity_changed = True

    if assigned_admin_id is not UNSET:
        if assigned_admin_id is not None:
            _ensure_admin_exists(db, assigned_admin_id)

        new_admin_id = assigned_admin_id
        identity_changed = True

    if identity_changed:
        existing_credential = get_credential_by_name(
            db=db,
            name=new_name,
            assigned_admin_id=new_admin_id,
        )

        if (
            existing_credential is not None
            and existing_credential.id != credential.id
        ):
            raise ValueError(
                f"CREDENTIAL_EXISTS:{existing_credential.id}"
            )

        credential.name = new_name
        credential.assigned_admin_id = new_admin_id

    if source_type is not None:
        if not isinstance(source_type, DataSourceType):
            raise ValueError(
                "Invalid data source type."
            )

        credential.source_type = source_type

    if config is not None:
        if not isinstance(config, dict) or not config:
            raise ValueError(
                "Credential configuration cannot be empty."
            )

        credential.encrypted_config = encrypt_json(
            config
        )

    try:
        db.commit()
        db.refresh(credential)
    except Exception:
        db.rollback()
        raise

    return credential


def set_credential_active_status(
    db: Session,
    credential_id: UUID,
    is_active: bool,
) -> DataSourceCredential:
    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None:
        raise ValueError(
            "Credential was not found."
        )

    credential.is_active = is_active

    try:
        db.commit()
        db.refresh(credential)
    except Exception:
        db.rollback()
        raise

    return credential


def delete_credential(
    db: Session,
    credential_id: UUID,
) -> None:
    credential = get_credential_by_id(
        db=db,
        credential_id=credential_id,
    )

    if credential is None:
        raise ValueError(
            "Credential was not found."
        )

    try:
        db.delete(credential)
        db.commit()
    except Exception:
        db.rollback()
        raise
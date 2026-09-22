import json

from cryptography.fernet import Fernet, InvalidToken

from app.db.session import settings


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


def _get_encryption_key() -> bytes:
    key = getattr(settings, "dataease_encryption_key", None)

    if not key:
        raise EncryptionError(
            "DATAEASE_ENCRYPTION_KEY is not configured."
        )

    try:
        key_bytes = key.encode("utf-8")
        Fernet(key_bytes)
        return key_bytes
    except Exception as exc:
        raise EncryptionError(
            "DATAEASE_ENCRYPTION_KEY is invalid. "
            "It must be a valid Fernet key."
        ) from exc


def encrypt_value(value: str) -> str:
    if not isinstance(value, str):
        raise EncryptionError(
            "Only string values can be encrypted."
        )

    if not value:
        raise EncryptionError(
            "Cannot encrypt an empty value."
        )

    try:
        fernet = Fernet(_get_encryption_key())
        encrypted = fernet.encrypt(
            value.encode("utf-8")
        )
        return encrypted.decode("utf-8")
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError(
            "Failed to encrypt value."
        ) from exc


def decrypt_value(encrypted_value: str) -> str:
    if not isinstance(encrypted_value, str):
        raise EncryptionError(
            "Encrypted value must be a string."
        )

    if not encrypted_value:
        raise EncryptionError(
            "Cannot decrypt an empty value."
        )

    try:
        fernet = Fernet(_get_encryption_key())
        decrypted = fernet.decrypt(
            encrypted_value.encode("utf-8")
        )
        return decrypted.decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError(
            "Unable to decrypt value. "
            "The encryption key or encrypted data is invalid."
        ) from exc
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError(
            "Failed to decrypt value."
        ) from exc


def encrypt_json(data: dict) -> str:
    try:
        serialized_data = json.dumps(
            data,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise EncryptionError(
            "Credential configuration could not be serialized."
        ) from exc

    return encrypt_value(serialized_data)


def decrypt_json(encrypted_data: str) -> dict:
    decrypted_data = decrypt_value(encrypted_data)

    try:
        data = json.loads(decrypted_data)
    except (TypeError, ValueError) as exc:
        raise EncryptionError(
            "Decrypted credential configuration is invalid."
        ) from exc

    if not isinstance(data, dict):
        raise EncryptionError(
            "Decrypted credential configuration must be a JSON object."
        )

    return data
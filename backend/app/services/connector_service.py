from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.base import (
    BaseConnector,
    ConnectorValidationError,
)
from app.connectors.registry import ConnectorRegistry
from app.core.encryption import EncryptionError
from app.models.data_source_credential import (
    DataSourceCredential,
)
from app.services.data_source_credential_service import (
    get_credential_by_id,
    get_decrypted_config,
)


# ============================================================
# EXCEPTIONS
# ============================================================

class ConnectorServiceError(Exception):
    """Base exception for connector service errors."""


class ConnectorCredentialNotFoundError(
    ConnectorServiceError
):
    """Raised when the requested credential does not exist."""


class ConnectorCredentialInactiveError(
    ConnectorServiceError
):
    """Raised when the requested credential is inactive."""


# ============================================================
# CONNECTOR SERVICE
# ============================================================

class ConnectorService:

    # ========================================================
    # GET CREDENTIAL
    # ========================================================

    @staticmethod
    def get_credential(
        db: Session,
        credential_id: UUID,
    ) -> DataSourceCredential:

        credential = get_credential_by_id(
            db=db,
            credential_id=credential_id,
        )

        if credential is None:
            raise ConnectorCredentialNotFoundError(
                "Data source credential was not found."
            )

        if not credential.is_active:
            raise ConnectorCredentialInactiveError(
                "Data source credential is inactive."
            )

        return credential


    # ========================================================
    # CREATE CONNECTOR
    # ========================================================

    @staticmethod
    def create_connector(
        db: Session,
        credential_id: UUID,
        database_name: str | None = None,
    ) -> BaseConnector:

        credential = ConnectorService.get_credential(
            db=db,
            credential_id=credential_id,
        )

        try:

            config = get_decrypted_config(
                db=db,
                credential_id=credential.id,
            )

        except EncryptionError as exc:

            raise ConnectorServiceError(
                "Unable to decrypt the data source credential."
            ) from exc

        except ValueError as exc:

            raise ConnectorServiceError(
                str(exc)
            ) from exc


        # ----------------------------------------------------
        # OVERRIDE DATABASE IF REQUESTED
        # ----------------------------------------------------

        if database_name is not None:

            if not isinstance(
                database_name,
                str,
            ):
                raise ConnectorServiceError(
                    "Database name must be a string."
                )

            normalized_database = (
                database_name.strip()
            )

            if not normalized_database:
                raise ConnectorServiceError(
                    "Database name cannot be empty."
                )

            config["database"] = (
                normalized_database
            )


        # ----------------------------------------------------
        # GET SOURCE TYPE
        # ----------------------------------------------------

        source_type = (
            credential.source_type.value
            if hasattr(
                credential.source_type,
                "value",
            )
            else str(
                credential.source_type
            )
        )


        # ----------------------------------------------------
        # CREATE CONNECTOR FROM REGISTRY
        # ----------------------------------------------------

        try:

            connector = (
                ConnectorRegistry.get_connector(
                    source_type=source_type,
                    config=config,
                )
            )

        except ConnectorValidationError as exc:

            raise ConnectorServiceError(
                "Unable to create connector for "
                f"data source type '{source_type}'."
            ) from exc

        except Exception as exc:

            raise ConnectorServiceError(
                "Unexpected error while creating "
                f"connector: {str(exc)}"
            ) from exc

        return connector


    # ========================================================
    # TEST CONNECTION
    # ========================================================

    @staticmethod
    def test_connection(
        db: Session,
        credential_id: UUID,
    ) -> bool:

        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
            )
        )

        try:

            return bool(
                connector.test_connection()
            )

        except Exception as exc:

            raise ConnectorServiceError(
                f"Connection test failed: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # LIST ROOT PATHS
    # ========================================================

    @staticmethod
    def list_root_paths(
        db: Session,
        credential_id: UUID,
    ) -> list[str]:

        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
            )
        )

        try:

            paths = (
                connector.list_root_paths()
            )

            return list(paths or [])

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to list root paths: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # SEARCH CHILD PATHS
    # ========================================================

    @staticmethod
    def search_child_paths(
        db: Session,
        credential_id: UUID,
        parent_path: str,
        search_text: str | None = None,
        database_name: str | None = None,
    ) -> list[str]:

        if not isinstance(
            parent_path,
            str,
        ):
            raise ConnectorServiceError(
                "Parent path must be a string."
            )

        normalized_parent_path = (
            parent_path.strip()
        )

        if not normalized_parent_path:
            raise ConnectorServiceError(
                "Parent path cannot be empty."
            )


        # ----------------------------------------------------
        # DATABASE SELECTION
        # ----------------------------------------------------

        selected_database = (
            database_name.strip()
            if database_name
            else normalized_parent_path
        )


        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
                database_name=selected_database,
            )
        )

        try:

            paths = (
                connector.search_child_paths(
                    parent_path=normalized_parent_path,
                    search_text=(
                        search_text.strip()
                        if search_text
                        else None
                    ),
                )
            )

            return list(paths or [])

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to search child paths: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # LIST TABLES
    # ========================================================

    @staticmethod
    def list_tables(
        db: Session,
        credential_id: UUID,
        database_name: str,
        schema_name: str,
        search_text: str | None = None,
    ) -> list[str]:

        if not isinstance(
            database_name,
            str,
        ):
            raise ConnectorServiceError(
                "Database name must be a string."
            )

        if not isinstance(
            schema_name,
            str,
        ):
            raise ConnectorServiceError(
                "Schema name must be a string."
            )


        normalized_database = (
            database_name.strip()
        )

        normalized_schema = (
            schema_name.strip()
        )


        if not normalized_database:
            raise ConnectorServiceError(
                "Database name cannot be empty."
            )

        if not normalized_schema:
            raise ConnectorServiceError(
                "Schema name cannot be empty."
            )


        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
                database_name=normalized_database,
            )
        )

        try:

            list_tables_method = getattr(
                connector,
                "list_tables",
                None,
            )

            if not callable(
                list_tables_method
            ):
                raise ConnectorServiceError(
                    "The selected connector does not "
                    "support table browsing."
                )


            tables = (
                list_tables_method(
                    schema_name=normalized_schema,
                    search_text=(
                        search_text.strip()
                        if search_text
                        else None
                    ),
                    database_name=normalized_database,
                )
            )

            return list(tables or [])

        except ConnectorServiceError:
            raise

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to list tables: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # GET TABLE COLUMNS
    # ========================================================

    @staticmethod
    def get_table_columns(
        db: Session,
        credential_id: UUID,
        database_name: str,
        schema_name: str,
        table_name: str,
    ) -> list[dict]:

        if not isinstance(
            database_name,
            str,
        ):
            raise ConnectorServiceError(
                "Database name must be a string."
            )

        if not isinstance(
            schema_name,
            str,
        ):
            raise ConnectorServiceError(
                "Schema name must be a string."
            )

        if not isinstance(
            table_name,
            str,
        ):
            raise ConnectorServiceError(
                "Table name must be a string."
            )


        normalized_database = (
            database_name.strip()
        )

        normalized_schema = (
            schema_name.strip()
        )

        normalized_table = (
            table_name.strip()
        )


        if not normalized_database:
            raise ConnectorServiceError(
                "Database name cannot be empty."
            )

        if not normalized_schema:
            raise ConnectorServiceError(
                "Schema name cannot be empty."
            )

        if not normalized_table:
            raise ConnectorServiceError(
                "Table name cannot be empty."
            )


        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
                database_name=normalized_database,
            )
        )

        try:

            get_columns_method = getattr(
                connector,
                "get_table_columns",
                None,
            )

            if not callable(
                get_columns_method
            ):
                raise ConnectorServiceError(
                    "The selected connector does not "
                    "support column browsing."
                )


            columns = (
                get_columns_method(
                    schema_name=normalized_schema,
                    table_name=normalized_table,
                    database_name=normalized_database,
                )
            )

            return list(columns or [])

        except ConnectorServiceError:
            raise

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to retrieve table columns: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # VALIDATE DESTINATION PATH
    # ========================================================

    @staticmethod
    def validate_destination_path(
        db: Session,
        credential_id: UUID,
        path: str,
        database_name: str | None = None,
    ) -> bool:

        if not isinstance(
            path,
            str,
        ):
            raise ConnectorServiceError(
                "Destination path must be a string."
            )

        normalized_path = (
            path.strip()
        )

        if not normalized_path:
            raise ConnectorServiceError(
                "Destination path cannot be empty."
            )


        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
                database_name=database_name,
            )
        )

        try:

            validate_method = getattr(
                connector,
                "validate_destination_path",
                None,
            )

            if not callable(
                validate_method
            ):
                # The connector does not implement
                # explicit path validation.
                # Returning True prevents unnecessarily
                # blocking valid destination selections.
                return True


            return bool(
                validate_method(
                    path=normalized_path,
                )
            )

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to validate destination path: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # PREVIEW DATA
    # ========================================================

    @staticmethod
    def preview_data(
        db: Session,
        credential_id: UUID,
        limit: int = 100,
        database_name: str | None = None,
        schema_name: str | None = None,
        table_name: str | None = None,
        source_path: str | None = None,
    ) -> dict:

        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
                database_name=database_name,
            )
        )

        try:

            if table_name:
                return connector.preview_table_data(
                    schema_name=schema_name,
                    table_name=table_name,
                    database_name=database_name,
                    limit=limit,
                )

            if source_path:
                return connector.preview_path_data(
                    path=source_path,
                    limit=limit,
                )

            raise ConnectorServiceError(
                "Either a table or a source path must be provided "
                "to preview data."
            )

        except NotImplementedError as exc:

            raise ConnectorServiceError(
                str(exc)
            ) from exc

        except ConnectorServiceError:
            raise

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to preview data: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


    # ========================================================
    # WRITE DATA (EXPORT)
    # ========================================================

    @staticmethod
    def write_data(
        db: Session,
        credential_id: UUID,
        columns: list[str],
        rows: list[list],
        database_name: str | None = None,
        schema_name: str | None = None,
        table_name: str | None = None,
        destination_path: str | None = None,
    ) -> dict:

        connector = (
            ConnectorService.create_connector(
                db=db,
                credential_id=credential_id,
                database_name=database_name,
            )
        )

        try:

            if table_name:
                return connector.write_table_data(
                    schema_name=schema_name,
                    table_name=table_name,
                    columns=columns,
                    rows=rows,
                    database_name=database_name,
                )

            if destination_path:
                return connector.write_path_data(
                    path=destination_path,
                    columns=columns,
                    rows=rows,
                )

            raise ConnectorServiceError(
                "Either a table or a destination path must be "
                "provided to write data."
            )

        except NotImplementedError as exc:

            raise ConnectorServiceError(
                str(exc)
            ) from exc

        except ConnectorServiceError:
            raise

        except Exception as exc:

            raise ConnectorServiceError(
                f"Unable to write export data: {str(exc)}"
            ) from exc

        finally:

            try:
                connector.close()
            except Exception:
                pass


# ============================================================
# PUBLIC WRAPPER FUNCTIONS
#
# These functions are used by other backend services.
# ============================================================


def create_connector_from_credential(
    db: Session,
    credential_id: UUID,
    database_name: str | None = None,
) -> BaseConnector:

    return ConnectorService.create_connector(
        db=db,
        credential_id=credential_id,
        database_name=database_name,
    )


def test_connector_connection(
    db: Session,
    credential_id: UUID,
) -> bool:

    return ConnectorService.test_connection(
        db=db,
        credential_id=credential_id,
    )


def list_connector_root_paths(
    db: Session,
    credential_id: UUID,
) -> list[str]:

    return ConnectorService.list_root_paths(
        db=db,
        credential_id=credential_id,
    )


def search_connector_child_paths(
    db: Session,
    credential_id: UUID,
    parent_path: str,
    search_text: str | None = None,
    database_name: str | None = None,
) -> list[str]:

    return ConnectorService.search_child_paths(
        db=db,
        credential_id=credential_id,
        parent_path=parent_path,
        search_text=search_text,
        database_name=database_name,
    )


def list_connector_tables(
    db: Session,
    credential_id: UUID,
    database_name: str,
    schema_name: str,
    search_text: str | None = None,
) -> list[str]:

    return ConnectorService.list_tables(
        db=db,
        credential_id=credential_id,
        database_name=database_name,
        schema_name=schema_name,
        search_text=search_text,
    )



# ============================================================
# IMPORTANT: THIS FUNCTION NAME IS REQUIRED BY
# file_group_service.py
# ============================================================

def list_connector_table_columns(
    db: Session,
    credential_id: UUID,
    database_name: str,
    schema_name: str,
    table_name: str,
) -> list[dict]:

    return ConnectorService.get_table_columns(
        db=db,
        credential_id=credential_id,
        database_name=database_name,
        schema_name=schema_name,
        table_name=table_name,
    )


def validate_connector_destination_path(
    db: Session,
    credential_id: UUID,
    path: str,
    database_name: str | None = None,
) -> bool:

    return ConnectorService.validate_destination_path(
        db=db,
        credential_id=credential_id,
        path=path,
        database_name=database_name,
    )


def preview_connector_data(
    db: Session,
    credential_id: UUID,
    limit: int = 100,
    database_name: str | None = None,
    schema_name: str | None = None,
    table_name: str | None = None,
    source_path: str | None = None,
) -> dict:

    return ConnectorService.preview_data(
        db=db,
        credential_id=credential_id,
        limit=limit,
        database_name=database_name,
        schema_name=schema_name,
        table_name=table_name,
        source_path=source_path,
    )


def write_connector_data(
    db: Session,
    credential_id: UUID,
    columns: list[str],
    rows: list[list],
    database_name: str | None = None,
    schema_name: str | None = None,
    table_name: str | None = None,
    destination_path: str | None = None,
) -> dict:

    return ConnectorService.write_data(
        db=db,
        credential_id=credential_id,
        columns=columns,
        rows=rows,
        database_name=database_name,
        schema_name=schema_name,
        table_name=table_name,
        destination_path=destination_path,
    )
from abc import ABC, abstractmethod
from typing import Any


class ConnectorError(Exception):
    """Base exception for connector-related errors."""


class ConnectorValidationError(ConnectorError):
    """Raised when connector configuration is invalid."""


class ConnectorOperationError(ConnectorError):
    """Raised when a connector operation fails."""


class BaseConnector(ABC):
    """
    Common interface for all DataEase connectors.

    Every connector must implement the same core operations so
    the rest of DataEase does not need to know which specific
    data source is being used.
    """

    source_type: str

    def __init__(self, config: dict[str, Any]):
        if not isinstance(config, dict):
            raise ConnectorValidationError(
                "Connector configuration must be a dictionary."
            )

        if not config:
            raise ConnectorValidationError(
                "Connector configuration cannot be empty."
            )

        self.config = config

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test whether the configured data source can be reached.
        """

        raise NotImplementedError

    @abstractmethod
    def list_root_paths(self) -> list[str]:
        """
        Return the available root-level paths/resources.

        Examples:
        - Database connector: databases
        - S3: buckets
        - Azure Blob: containers
        """

        raise NotImplementedError

    @abstractmethod
    def search_child_paths(
        self,
        parent_path: str,
        search_text: str | None = None,
    ) -> list[str]:
        """
        Search immediate child paths/resources below a parent path.
        """

        raise NotImplementedError

    @abstractmethod
    def validate_destination_path(
        self,
        path: str,
    ) -> bool:
        """
        Validate whether a destination path is usable.
        """

        raise NotImplementedError

    def preview_table_data(
        self,
        schema_name: str,
        table_name: str,
        database_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Return a small preview of a database table's rows, as
        {"columns": [...], "rows": [[...], [...]]}.

        Optional — only implemented by database-type connectors
        (PostgreSQL, MySQL, Snowflake). Not abstract, so connectors
        that don't support this (e.g. S3) don't break.
        """

        raise NotImplementedError(
            f"{self.source_type} does not support table data preview."
        )

    def preview_path_data(
        self,
        path: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Return a small preview of a path-based file's rows, as
        {"columns": [...], "rows": [[...], [...]]}.

        Optional — only implemented by path-based connectors
        (AWS S3, Local File, URL). Not abstract, so connectors
        that don't support this (e.g. database connectors) don't
        break.
        """

        raise NotImplementedError(
            f"{self.source_type} does not support path data preview."
        )

    def write_table_data(
        self,
        schema_name: str,
        table_name: str,
        columns: list[str],
        rows: list[list],
        database_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Write rows to a new (or existing) database table at the
        given schema/table. Used for exporting anonymized data.

        Optional — only implemented by database-type connectors.
        """

        raise NotImplementedError(
            f"{self.source_type} does not support writing table data."
        )

    def write_path_data(
        self,
        path: str,
        columns: list[str],
        rows: list[list],
    ) -> dict[str, Any]:
        """
        Write rows to a path-based destination (e.g. a CSV file
        in an S3 bucket/prefix). Used for exporting anonymized
        data.

        Optional — only implemented by path-based connectors.
        """

        raise NotImplementedError(
            f"{self.source_type} does not support writing path data."
        )

    def close(self) -> None:
        """
        Release connector resources.

        Connectors that maintain persistent connections should
        override this method.
        """

        return None

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        self.close()
        return False
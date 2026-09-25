import csv
import io
import json
from typing import Any

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from app.connectors.base import (
    BaseConnector,
    ConnectorOperationError,
    ConnectorValidationError,
)


class AzureBlobConnector(BaseConnector):
    """
    Azure Blob Storage connector for DataEase.

    Credential configuration:

    {
        "connection_string": "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
    }

    DataEase treats each Azure "container" the way it treats a
    PostgreSQL database, and each blob inside a container the way
    it treats a file inside a folder — this mirrors how the S3
    connector treats buckets/objects, since Azure Blob has the same
    "container -> virtual folder -> file" shape as S3.

    Paths used throughout this connector are always the FULL path
    starting with the container name, e.g.:

        "my-container"                     -> the container itself
        "my-container/reports"             -> a virtual folder
        "my-container/reports/sales.csv"   -> a specific blob

    This matches how the frontend builds up a path by joining each
    level the user clicks through, starting from the container list
    returned by list_root_paths().

    NOTE ON FILE PARSING: preview_path_data() below parses .csv
    files with Python's built-in csv module and .json files (a
    JSON array of objects) with the json module. If the rest of
    this app's path-based connectors (S3, local/URL files) use a
    different parsing library or support additional formats,
    align this method with that convention once s3.py / local_data.py
    are available for reference — right now this is a safe,
    dependency-light default rather than a confirmed match to the
    existing convention.
    """

    source_type = "AZURE_BLOB"

    REQUIRED_CONFIG_FIELDS = {"connection_string"}

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)

        self._validate_config()

        self._client: BlobServiceClient | None = None

    # ========================================================
    # CONFIGURATION VALIDATION
    # ========================================================

    def _validate_config(self) -> None:
        missing_fields = sorted(
            field
            for field in self.REQUIRED_CONFIG_FIELDS
            if field not in self.config
            or self.config[field] is None
            or self.config[field] == ""
        )

        if missing_fields:
            raise ConnectorValidationError(
                "Azure Blob Storage configuration is missing "
                f"required fields: {', '.join(missing_fields)}."
            )

        if not isinstance(self.config["connection_string"], str):
            raise ConnectorValidationError(
                "Azure Blob Storage connection string must be a string."
            )

        if not self.config["connection_string"].strip():
            raise ConnectorValidationError(
                "Azure Blob Storage connection string cannot be empty."
            )

    # ========================================================
    # CLIENT (lazy, cached — the SDK client itself doesn't open
    # a network connection until a call is actually made, so
    # there's no separate "connect" step the way there is for a
    # database driver)
    # ========================================================

    def _get_client(self) -> BlobServiceClient:
        if self._client is not None:
            return self._client

        try:
            self._client = BlobServiceClient.from_connection_string(
                self.config["connection_string"]
            )
        except (ValueError, AzureError) as exc:
            raise ConnectorValidationError(
                "The Azure Blob Storage connection string is invalid."
            ) from exc

        return self._client

    @staticmethod
    def _split_path(path: str) -> tuple[str, str]:
        """
        Split a "container/optional/blob/path" string into
        (container_name, remainder). remainder is "" when path is
        just the container name.
        """

        normalized = path.strip().strip("/")

        if not normalized:
            raise ConnectorValidationError("Path cannot be empty.")

        parts = normalized.split("/", 1)
        container_name = parts[0]
        remainder = parts[1] if len(parts) > 1 else ""

        return container_name, remainder

    # ========================================================
    # TEST CONNECTION
    # ========================================================

    def test_connection(self) -> bool:
        client = self._get_client()

        try:
            # list_containers() is lazily paginated by the SDK, so
            # nothing is actually sent to Azure until it's iterated.
            # Fetching just the first page is enough to prove the
            # connection string authenticates.
            containers = client.list_containers(results_per_page=1)
            next(iter(containers.by_page()), None)
            return True

        except AzureError as exc:
            raise ConnectorOperationError(
                "Unable to connect to Azure Blob Storage."
            ) from exc

    # ========================================================
    # ROOT PATHS — every container in the account
    # ========================================================

    def list_root_paths(self) -> list[str]:
        client = self._get_client()

        try:
            containers = [c.name for c in client.list_containers()]
            return sorted(containers)

        except AzureError as exc:
            raise ConnectorOperationError(
                "Unable to list Azure Blob Storage containers."
            ) from exc

    # ========================================================
    # CHILD PATHS — one level of virtual folders/blobs under a
    # given container or folder path
    # ========================================================

    def search_child_paths(
        self,
        parent_path: str,
        search_text: str | None = None,
    ) -> list[str]:
        if not isinstance(parent_path, str):
            raise ConnectorValidationError(
                "Azure Blob Storage parent path must be a string."
            )

        container_name, remainder = self._split_path(parent_path)

        prefix = f"{remainder}/" if remainder else ""

        client = self._get_client()

        try:
            container_client = client.get_container_client(container_name)

            child_names: list[str] = []

            # walk_blobs with a "/" delimiter returns one level of
            # virtual folders (as BlobPrefix items) and blobs (as
            # BlobProperties items) at a time, the same way S3's
            # ListObjectsV2 with a delimiter emulates folders.
            for item in container_client.walk_blobs(
                name_starts_with=prefix,
                delimiter="/",
            ):
                full_name = item.name.rstrip("/")
                child_name = full_name.rsplit("/", 1)[-1]
                child_names.append(child_name)

            if search_text:
                normalized_search = search_text.strip().lower()
                child_names = [
                    name
                    for name in child_names
                    if normalized_search in name.lower()
                ]

            return sorted(child_names)

        except ResourceNotFoundError as exc:
            raise ConnectorValidationError(
                f"Container '{container_name}' was not found."
            ) from exc

        except AzureError as exc:
            raise ConnectorOperationError(
                "Unable to browse Azure Blob Storage."
            ) from exc

    # ========================================================
    # DESTINATION VALIDATION
    # ========================================================

    def validate_destination_path(self, path: str) -> bool:
        if not isinstance(path, str):
            raise ConnectorValidationError(
                "Azure Blob Storage destination path must be a string."
            )

        try:
            container_name, _ = self._split_path(path)
        except ConnectorValidationError:
            return False

        client = self._get_client()

        try:
            container_client = client.get_container_client(container_name)
            return container_client.exists()

        except AzureError as exc:
            raise ConnectorOperationError(
                "Unable to validate the Azure Blob Storage destination."
            ) from exc

    # ========================================================
    # PREVIEW DATA
    # ========================================================

    def preview_path_data(
        self,
        path: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        container_name, blob_name = self._split_path(path)

        if not blob_name:
            raise ConnectorValidationError(
                "A specific blob (file) must be selected to preview data, "
                "not just a container."
            )

        safe_limit = max(1, min(int(limit), 1_000_000))

        client = self._get_client()

        try:
            container_client = client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            raw_bytes = blob_client.download_blob().readall()

        except ResourceNotFoundError as exc:
            raise ConnectorValidationError(
                f"Blob '{blob_name}' was not found in container "
                f"'{container_name}'."
            ) from exc

        except AzureError as exc:
            raise ConnectorOperationError(
                "Unable to read the selected file from Azure Blob Storage."
            ) from exc

        lower_name = blob_name.lower()

        if lower_name.endswith(".json"):
            return self._parse_json(raw_bytes, safe_limit)

        # Default to CSV for .csv and any other/unknown extension —
        # matches this app's other path-based sources treating CSV
        # as the default tabular format.
        return self._parse_csv(raw_bytes, safe_limit)

    @staticmethod
    def _parse_csv(raw_bytes: bytes, limit: int) -> dict[str, Any]:
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ConnectorOperationError(
                "The selected file is not readable as UTF-8 text."
            ) from exc

        reader = csv.reader(io.StringIO(text))

        try:
            columns = next(reader)
        except StopIteration:
            return {"columns": [], "rows": []}

        rows = []
        for row in reader:
            if len(rows) >= limit:
                break
            rows.append(row)

        return {"columns": columns, "rows": rows}

    @staticmethod
    def _parse_json(raw_bytes: bytes, limit: int) -> dict[str, Any]:
        try:
            data = json.loads(raw_bytes.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorOperationError(
                "The selected file is not valid JSON."
            ) from exc

        if not isinstance(data, list):
            raise ConnectorOperationError(
                "Only a JSON file containing an array of objects "
                "is supported for preview."
            )

        limited = data[:limit]

        columns: list[str] = []
        for record in limited:
            if isinstance(record, dict):
                for key in record.keys():
                    if key not in columns:
                        columns.append(key)

        rows = [
            [record.get(col) if isinstance(record, dict) else None for col in columns]
            for record in limited
        ]

        return {"columns": columns, "rows": rows}

    # ========================================================
    # WRITE DATA (EXPORT)
    # ========================================================

    def write_path_data(
        self,
        path: str,
        columns: list[str],
        rows: list[list],
    ) -> dict[str, Any]:
        container_name, blob_name = self._split_path(path)

        if not blob_name:
            raise ConnectorValidationError(
                "A destination file path (not just a container) is "
                "required to export data."
            )

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(
                "" if value is None else value for value in row
            )

        client = self._get_client()

        try:
            container_client = client.get_container_client(container_name)

            if not container_client.exists():
                container_client.create_container()

            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                buffer.getvalue().encode("utf-8"),
                overwrite=True,
            )

        except AzureError as exc:
            raise ConnectorOperationError(
                "Unable to write the export file to Azure Blob Storage."
            ) from exc

        return {"rows_written": len(rows)}

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        # The SDK's BlobServiceClient makes stateless REST calls
        # rather than holding a persistent connection the way a
        # database driver does, so there's nothing to explicitly
        # close — this just drops the cached client.
        self._client = None
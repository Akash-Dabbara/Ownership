import io
import os
from typing import Any

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

from app.connectors.base import (
    BaseConnector,
    ConnectorOperationError,
    ConnectorValidationError,
)

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}

# The ZIP file signature every .xlsx file starts with — used as a
# safety net when the object key's extension is missing or wrong.
ZIP_MAGIC_BYTES = b"PK\x03\x04"


class AWS3Connector(BaseConnector):
    """
    Real AWS S3 connector using boto3.

    Browsing model:
      - list_root_paths() -> the account's buckets
      - search_child_paths(parent_path) -> folders/objects one
        level below the given prefix, using S3's '/' delimiter
        convention

    NOTE: this returns plain path segment names for both folders
    and files. The frontend currently cannot distinguish a folder
    from a leaf file from this list alone — that requires a small
    response-shape change (e.g. returning {"name": ..., "is_leaf":
    ...} instead of bare strings) across the connector interface,
    the routes, and the frontend browser. That change is scoped
    separately and not included in this pass.
    """

    source_type = "AWS_S3"

    REQUIRED_CONFIG_FIELDS = {
        "access_key",
        "secret_key",
    }

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._validate_config()

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
                "AWS S3 configuration is missing required "
                f"fields: {', '.join(missing_fields)}."
            )

    def _client(self):
        try:
            return boto3.client(
                "s3",
                aws_access_key_id=self.config["access_key"],
                aws_secret_access_key=self.config["secret_key"],
                region_name=self.config.get("region", "us-east-1"),
            )
        except (BotoCoreError, ClientError) as exc:
            raise ConnectorOperationError(
                "Unable to create an AWS S3 client."
            ) from exc

    def test_connection(self) -> bool:
        try:
            client = self._client()
            client.list_buckets()
            return True
        except ConnectorOperationError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise ConnectorOperationError(
                "AWS S3 connection test failed."
            ) from exc

    def list_root_paths(self) -> list[str]:
        try:
            client = self._client()
            response = client.list_buckets()
            return [b["Name"] for b in response.get("Buckets", [])]
        except ConnectorOperationError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise ConnectorOperationError(
                "Unable to list S3 buckets."
            ) from exc

    def search_child_paths(
        self,
        parent_path: str,
        search_text: str | None = None,
    ) -> list[str]:
        """
        parent_path is either just a bucket name, or
        "bucket/prefix/subprefix" for deeper levels.
        """

        if not isinstance(parent_path, str) or not parent_path.strip():
            raise ConnectorValidationError(
                "S3 parent path cannot be empty."
            )

        segments = [s for s in parent_path.strip().split("/") if s]
        bucket_name = segments[0]
        prefix = "/".join(segments[1:])

        if prefix:
            prefix = prefix.rstrip("/") + "/"

        try:
            client = self._client()
            response = client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                Delimiter="/",
            )

            folder_names = [
                cp["Prefix"].rstrip("/").split("/")[-1]
                for cp in response.get("CommonPrefixes", [])
            ]

            file_names = [
                obj["Key"].split("/")[-1]
                for obj in response.get("Contents", [])
                if obj["Key"] != prefix and obj["Key"].split("/")[-1]
            ]

            results = folder_names + file_names

            if search_text:
                normalized = search_text.strip().lower()
                results = [r for r in results if normalized in r.lower()]

            return results
        except (BotoCoreError, ClientError) as exc:
            raise ConnectorOperationError(
                "Unable to browse the S3 bucket."
            ) from exc

    def validate_destination_path(self, path: str) -> bool:
        """
        Checks that the bucket (and prefix, if given) is reachable.
        A prefix that doesn't exist yet as an object is still a
        valid destination to write new anonymized output to.
        """

        if not isinstance(path, str) or not path.strip():
            return False

        segments = [s for s in path.strip().split("/") if s]
        bucket_name = segments[0]

        try:
            client = self._client()
            client.head_bucket(Bucket=bucket_name)
            return True
        except (BotoCoreError, ClientError):
            return False

    @staticmethod
    def _read_csv_bytes_with_fallback(body: bytes, nrows: int):
        """
        Tries a sequence of (encoding, delimiter) combinations —
        explicit delimiters in priority order rather than pandas'
        automatic sniffer, since the sniffer can misfire on files
        with commas/semicolons embedded inside text fields.

        As a last resort, malformed rows are skipped rather than
        failing the whole read.
        """

        encodings_to_try = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        delimiters_to_try = [",", ";", "\t", "|"]
        last_error = None

        for encoding in encodings_to_try:
            for delimiter in delimiters_to_try:
                try:
                    df = pd.read_csv(
                        io.BytesIO(body),
                        nrows=nrows,
                        encoding=encoding,
                        sep=delimiter,
                    )
                    if df.shape[1] > 1 or delimiter == delimiters_to_try[-1]:
                        return df
                except Exception as exc:
                    last_error = exc

        try:
            return pd.read_csv(
                io.BytesIO(body),
                nrows=nrows,
                encoding="latin-1",
                encoding_errors="replace",
                sep=",",
                engine="python",
                on_bad_lines="skip",
            )
        except Exception:
            raise last_error

    def preview_path_data(
        self,
        path: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Reads a CSV file from S3 and returns up to `limit` rows.
        Currently supports CSV only — other formats (Parquet,
        JSON) can be added the same way as this need arises.
        """

        if not isinstance(path, str) or not path.strip():
            raise ConnectorValidationError("S3 file path cannot be empty.")

        segments = [s for s in path.strip().split("/") if s]
        if len(segments) < 2:
            raise ConnectorValidationError(
                "S3 path must include a bucket and an object key."
            )

        bucket_name = segments[0]
        object_key = "/".join(segments[1:])
        safe_limit = max(1, min(int(limit), 1_000_000))

        try:
            client = self._client()
            response = client.get_object(Bucket=bucket_name, Key=object_key)
            body = response["Body"].read()

            extension = os.path.splitext(object_key)[1].lower()
            is_excel = extension in EXCEL_EXTENSIONS or body[:4] == ZIP_MAGIC_BYTES

            if is_excel:
                df = pd.read_excel(io.BytesIO(body), nrows=safe_limit, engine="openpyxl")
            else:
                df = self._read_csv_bytes_with_fallback(body, safe_limit)

            df = df.astype(object).where(pd.notnull(df), None)

            rows = [
                [
                    value.item() if hasattr(value, "item") else value
                    for value in row
                ]
                for row in df.values.tolist()
            ]

            return {
                "columns": [str(c) for c in df.columns],
                "rows": rows,
            }
        except (BotoCoreError, ClientError) as exc:
            raise ConnectorOperationError(
                "Unable to read the file from S3."
            ) from exc
        except Exception as exc:
            raise ConnectorOperationError(
                f"Unable to parse the file as CSV: {str(exc)}"
            ) from exc

    def write_path_data(
        self,
        path: str,
        columns: list[str],
        rows: list[list],
    ) -> dict[str, Any]:
        """
        Writes rows as a CSV file to the given S3 bucket/prefix.
        `path` is treated as "bucket/prefix..." — the CSV is
        written directly at that key.
        """

        if not isinstance(path, str) or not path.strip():
            raise ConnectorValidationError("S3 destination path cannot be empty.")

        segments = [s for s in path.strip().split("/") if s]
        if not segments:
            raise ConnectorValidationError(
                "S3 destination path must include at least a bucket."
            )

        bucket_name = segments[0]
        object_key = "/".join(segments[1:]) if len(segments) > 1 else "export.csv"

        try:
            df = pd.DataFrame(rows, columns=columns)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)

            client = self._client()
            client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=csv_buffer.getvalue().encode("utf-8"),
            )

            return {"rows_written": len(rows)}
        except (BotoCoreError, ClientError) as exc:
            raise ConnectorOperationError(
                "Unable to write the export file to S3."
            ) from exc

    def close(self) -> None:
        return None
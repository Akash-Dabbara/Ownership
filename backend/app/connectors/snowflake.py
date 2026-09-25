from typing import Any

import snowflake.connector

from app.connectors.base import (
    BaseConnector,
    ConnectorOperationError,
    ConnectorValidationError,
)
from app.core.jsonable import to_jsonable


def _rows_with_column(cursor, column_name: str) -> list[str]:
    """
    Snowflake SHOW/DESC commands return dynamic result sets.
    This pulls out a named column by looking it up in the
    cursor description rather than assuming a fixed index.
    """

    columns = [desc[0].lower() for desc in cursor.description]

    try:
        index = columns.index(column_name.lower())
    except ValueError as exc:
        raise ConnectorOperationError(
            f"Unexpected Snowflake response: missing '{column_name}' column."
        ) from exc

    return [row[index] for row in cursor.fetchall()]


class SnowflakeConnector(BaseConnector):
    """
    Real Snowflake connector using snowflake-connector-python.

    Metadata browsing (SHOW DATABASES / SHOW SCHEMAS / DESC TABLE)
    does not require an active warehouse, so none is required in
    the credential configuration.
    """

    source_type = "SNOWFLAKE"

    REQUIRED_CONFIG_FIELDS = {
        "account_identifier",
        "username",
        "password",
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
                "Snowflake configuration is missing required "
                f"fields: {', '.join(missing_fields)}."
            )

    def _connect(self):
        try:
            connect_kwargs = {
                "account": self.config["account_identifier"],
                "user": self.config["username"],
                "password": self.config["password"],
                "login_timeout": 10,
            }

            if self.config.get("warehouse"):
                connect_kwargs["warehouse"] = self.config["warehouse"]

            if self.config.get("role"):
                connect_kwargs["role"] = self.config["role"]

            return snowflake.connector.connect(**connect_kwargs)
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to connect to the Snowflake data source."
            ) from exc

    def test_connection(self) -> bool:
        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            return result == (1,)
        except ConnectorOperationError:
            raise
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Snowflake connection test failed."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def list_root_paths(self) -> list[str]:
        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES")
            return _rows_with_column(cursor, "name")
        except ConnectorOperationError:
            raise
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to list Snowflake databases."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def search_child_paths(
        self,
        parent_path: str,
        search_text: str | None = None,
    ) -> list[str]:
        if not isinstance(parent_path, str) or not parent_path.strip():
            raise ConnectorValidationError(
                "Snowflake parent path (database) cannot be empty."
            )

        database_name = parent_path.strip()

        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute(f'SHOW SCHEMAS IN DATABASE "{database_name}"')
            schemas = _rows_with_column(cursor, "name")

            if search_text:
                normalized = search_text.strip().lower()
                schemas = [s for s in schemas if normalized in s.lower()]

            return schemas
        except ConnectorOperationError:
            raise
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to list Snowflake schemas."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def list_tables(
        self,
        schema_name: str,
        search_text: str | None = None,
        database_name: str | None = None,
    ) -> list[str]:
        if not database_name or not schema_name:
            raise ConnectorValidationError(
                "A Snowflake database and schema must be selected "
                "before listing tables."
            )

        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute(
                f'SHOW TABLES IN SCHEMA "{database_name}"."{schema_name}"'
            )
            tables = _rows_with_column(cursor, "name")

            if search_text:
                normalized = search_text.strip().lower()
                tables = [t for t in tables if normalized in t.lower()]

            return tables
        except ConnectorOperationError:
            raise
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to list Snowflake tables."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def get_table_columns(
        self,
        schema_name: str,
        table_name: str,
        database_name: str | None = None,
    ) -> list[dict[str, Any]]:
        if not database_name or not schema_name or not table_name:
            raise ConnectorValidationError(
                "Snowflake database, schema, and table are all required."
            )

        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute(
                f'DESC TABLE "{database_name}"."{schema_name}"."{table_name}"'
            )
            columns = [desc[0].lower() for desc in cursor.description]
            name_idx = columns.index("name")
            type_idx = columns.index("type")
            null_idx = columns.index("null?")

            rows = cursor.fetchall()

            return [
                {
                    "column_name": row[name_idx],
                    "data_type": row[type_idx],
                    "is_nullable": str(row[null_idx]).upper() == "Y",
                    "ordinal_position": position + 1,
                }
                for position, row in enumerate(rows)
            ]
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to read Snowflake table metadata."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def validate_destination_path(self, path: str) -> bool:
        if not isinstance(path, str) or not path.strip():
            return False

        parts = [p.strip() for p in path.strip().split("/") if p.strip()]
        if len(parts) > 2:
            return False

        database_name = self.config.get("database")
        if not database_name:
            raise ConnectorValidationError(
                "A Snowflake database must be selected before "
                "destination validation."
            )

        try:
            if len(parts) == 1:
                schemas = self.search_child_paths(database_name)
                return parts[0] in schemas
            else:
                tables = self.list_tables(
                    schema_name=parts[0],
                    database_name=database_name,
                )
                return parts[1] in tables
        except ConnectorOperationError:
            raise

    def preview_table_data(
        self,
        schema_name: str,
        table_name: str,
        database_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if not database_name or not schema_name or not table_name:
            raise ConnectorValidationError(
                "Snowflake database, schema, and table are all required."
            )

        safe_limit = max(1, min(int(limit), 1_000_000))

        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute(
                f'SELECT * FROM "{database_name}"."{schema_name}"."{table_name}" '
                f"LIMIT {safe_limit}"
            )
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            return {
                "columns": columns,
                "rows": [
                    [to_jsonable(value) for value in row]
                    for row in rows
                ],
            }
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to preview Snowflake table data."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def write_table_data(
        self,
        schema_name: str,
        table_name: str,
        columns: list[str],
        rows: list[list],
        database_name: str | None = None,
    ) -> dict[str, Any]:
        if not database_name or not schema_name or not table_name:
            raise ConnectorValidationError(
                "Snowflake database, schema, and table are all required."
            )

        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()

            create_columns_sql = ", ".join(
                f'"{col}" STRING' for col in columns
            )
            cursor.execute(
                f'CREATE TABLE IF NOT EXISTS "{database_name}"."{schema_name}"."{table_name}" '
                f"({create_columns_sql})"
            )

            # Clear any existing rows so re-exporting to the same
            # table name replaces its contents instead of appending
            # underneath what's already there.
            cursor.execute(
                f'TRUNCATE TABLE "{database_name}"."{schema_name}"."{table_name}"'
            )

            if rows:
                insert_columns_sql = ", ".join(f'"{col}"' for col in columns)
                placeholders_sql = ", ".join(["%s"] * len(columns))

                string_rows = [
                    [
                        None if value is None else str(value)
                        for value in row
                    ]
                    for row in rows
                ]

                cursor.executemany(
                    f'INSERT INTO "{database_name}"."{schema_name}"."{table_name}" '
                    f"({insert_columns_sql}) VALUES ({placeholders_sql})",
                    string_rows,
                )

            connection.commit()
            return {"rows_written": len(rows)}
        except snowflake.connector.errors.Error as exc:
            raise ConnectorOperationError(
                "Unable to write Snowflake export data."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def close(self) -> None:
        return None
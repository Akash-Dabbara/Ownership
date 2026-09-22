from typing import Any

import pymysql

from app.connectors.base import (
    BaseConnector,
    ConnectorOperationError,
    ConnectorValidationError,
)
from app.core.jsonable import to_jsonable

SYSTEM_DATABASES = {
    "information_schema",
    "performance_schema",
    "mysql",
    "sys",
}


class MySQLConnector(BaseConnector):
    """
    Real MySQL connector using pymysql.

    MySQL does not have a separate "schema" concept distinct
    from "database" — a MySQL schema IS a database. To keep
    the same database -> schema -> table browsing flow used
    by every other connector, the "schema" level here simply
    passes through as the same database name.
    """

    source_type = "MYSQL"

    REQUIRED_CONFIG_FIELDS = {
        "host",
        "port",
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
                "MySQL configuration is missing required "
                f"fields: {', '.join(missing_fields)}."
            )

        try:
            self.config["port"] = int(self.config["port"])
        except (TypeError, ValueError) as exc:
            raise ConnectorValidationError(
                "MySQL port must be a valid integer."
            ) from exc

    def _connect(self, database_name: str | None = None):
        try:
            return pymysql.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["username"],
                password=self.config["password"],
                database=database_name,
                connect_timeout=10,
                cursorclass=pymysql.cursors.Cursor,
            )
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to connect to the MySQL data source."
            ) from exc

    def test_connection(self) -> bool:
        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            return result == (1,)
        except ConnectorOperationError:
            raise
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "MySQL connection test failed."
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
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    ORDER BY schema_name
                    """
                )
                rows = cursor.fetchall()

            return [
                row[0]
                for row in rows
                if row[0].lower() not in SYSTEM_DATABASES
            ]
        except ConnectorOperationError:
            raise
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to list MySQL databases."
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
        """
        MySQL schema == database, so this confirms the
        database exists and returns it as its own single
        "schema" entry.
        """

        if not isinstance(parent_path, str) or not parent_path.strip():
            raise ConnectorValidationError(
                "MySQL parent path cannot be empty."
            )

        database_name = parent_path.strip()

        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name = %s
                    """,
                    (database_name,),
                )
                row = cursor.fetchone()

            return [row[0]] if row else []
        except ConnectorOperationError:
            raise
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to verify MySQL database."
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
        target_database = (database_name or schema_name or "").strip()

        if not target_database:
            raise ConnectorValidationError(
                "A MySQL database must be selected before listing tables."
            )

        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                if search_text:
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                          AND table_type = 'BASE TABLE'
                          AND table_name LIKE %s
                        ORDER BY table_name
                        """,
                        (target_database, f"%{search_text.strip()}%"),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                          AND table_type = 'BASE TABLE'
                        ORDER BY table_name
                        """,
                        (target_database,),
                    )
                rows = cursor.fetchall()

            return [row[0] for row in rows]
        except ConnectorOperationError:
            raise
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to list MySQL tables."
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
        target_database = (database_name or schema_name or "").strip()

        if not target_database or not table_name:
            raise ConnectorValidationError(
                "MySQL database and table name cannot be empty."
            )

        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        ordinal_position
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (target_database, table_name.strip()),
                )
                rows = cursor.fetchall()

            return [
                {
                    "column_name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2] == "YES",
                    "ordinal_position": row[3],
                }
                for row in rows
            ]
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to read MySQL table metadata."
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
                "A MySQL database must be selected before destination validation."
            )

        connection = None
        try:
            connection = self._connect()
            with connection.cursor() as cursor:
                if len(parts) == 1:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.schemata
                            WHERE schema_name = %s
                        )
                        """,
                        (parts[0],),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = %s AND table_name = %s
                        )
                        """,
                        (parts[0], parts[1]),
                    )
                result = cursor.fetchone()
            return bool(result and result[0])
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to validate MySQL destination path."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def preview_table_data(
        self,
        schema_name: str,
        table_name: str,
        database_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        target_database = (database_name or schema_name or "").strip()

        if not target_database or not table_name:
            raise ConnectorValidationError(
                "MySQL database and table name cannot be empty."
            )

        safe_limit = max(1, min(int(limit), 1_000_000))

        connection = None
        try:
            connection = self._connect(database_name=target_database)
            with connection.cursor() as cursor:
                # Backtick-quote identifiers; database/table names
                # were already validated against information_schema
                # before being saved, so this is safe.
                query = (
                    f"SELECT * FROM `{target_database}`.`{table_name}` "
                    f"LIMIT %s"
                )
                cursor.execute(query, (safe_limit,))
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

            return {
                "columns": columns,
                "rows": [
                    [to_jsonable(value) for value in row]
                    for row in rows
                ],
            }
        except ConnectorOperationError:
            raise
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to preview MySQL table data."
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
        target_database = (database_name or schema_name or "").strip()

        if not target_database or not table_name:
            raise ConnectorValidationError(
                "MySQL database and table name cannot be empty."
            )

        connection = None
        try:
            connection = self._connect(database_name=target_database)
            with connection.cursor() as cursor:
                create_columns_sql = ", ".join(
                    f"`{col}` TEXT" for col in columns
                )
                cursor.execute(
                    f"CREATE TABLE IF NOT EXISTS `{target_database}`.`{table_name}` "
                    f"({create_columns_sql})"
                )

                if rows:
                    insert_columns_sql = ", ".join(f"`{col}`" for col in columns)
                    placeholders_sql = ", ".join(["%s"] * len(columns))

                    string_rows = [
                        [
                            None if value is None else str(value)
                            for value in row
                        ]
                        for row in rows
                    ]

                    cursor.executemany(
                        f"INSERT INTO `{target_database}`.`{table_name}` "
                        f"({insert_columns_sql}) VALUES ({placeholders_sql})",
                        string_rows,
                    )

            connection.commit()
            return {"rows_written": len(rows)}
        except ConnectorOperationError:
            raise
        except pymysql.MySQLError as exc:
            raise ConnectorOperationError(
                "Unable to write MySQL export data."
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def close(self) -> None:
        return None
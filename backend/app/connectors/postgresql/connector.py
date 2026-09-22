from typing import Any

import psycopg
from psycopg import sql

from app.connectors.base import (
    BaseConnector,
    ConnectorOperationError,
    ConnectorValidationError,
)
from app.core.jsonable import to_jsonable


class PostgreSQLConnector(BaseConnector):
    """
    PostgreSQL connector for DataEase.

    The credential configuration contains the PostgreSQL
    server connection information.

    Database selection is optional because DataEase selects
    the database later during the File Group Look-Forward flow.

    Credential configuration:

    {
        "host": "localhost",
        "port": 5432,
        "username": "username",
        "password": "password"
    }

    Optional configuration:

    {
        "database": "database_name",
        "sslmode": "prefer",
        "connect_timeout": 10,
        "application_name": "DataEase"
    }

    The database value may be supplied dynamically when a
    File Group selects a database.

    Passwords and other secrets are never logged or returned.
    """

    source_type = "POSTGRESQL"

    REQUIRED_CONFIG_FIELDS = {
        "host",
        "port",
        "username",
        "password",
    }

    DEFAULT_TEST_DATABASE = "postgres"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)

        self._validate_config()

        self._connection = None

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
                "PostgreSQL configuration is missing required "
                f"fields: {', '.join(missing_fields)}."
            )

        try:
            port = int(self.config["port"])
        except (TypeError, ValueError) as exc:
            raise ConnectorValidationError(
                "PostgreSQL port must be a valid integer."
            ) from exc

        if not 1 <= port <= 65535:
            raise ConnectorValidationError(
                "PostgreSQL port must be between 1 and 65535."
            )

        self.config["port"] = port

        if not isinstance(self.config["host"], str):
            raise ConnectorValidationError(
                "PostgreSQL host must be a string."
            )

        if not isinstance(self.config["username"], str):
            raise ConnectorValidationError(
                "PostgreSQL username must be a string."
            )

        if not isinstance(self.config["password"], str):
            raise ConnectorValidationError(
                "PostgreSQL password must be a string."
            )

        if not self.config["host"].strip():
            raise ConnectorValidationError(
                "PostgreSQL host cannot be empty."
            )

        if not self.config["username"].strip():
            raise ConnectorValidationError(
                "PostgreSQL username cannot be empty."
            )

        if "database" in self.config:
            database = self.config["database"]

            if database is not None:
                if not isinstance(database, str):
                    raise ConnectorValidationError(
                        "PostgreSQL database must be a string."
                    )

                if not database.strip():
                    raise ConnectorValidationError(
                        "PostgreSQL database cannot be empty."
                    )

        if "sslmode" in self.config:
            sslmode = self.config["sslmode"]

            if sslmode is not None and not isinstance(
                sslmode,
                str,
            ):
                raise ConnectorValidationError(
                    "PostgreSQL sslmode must be a string."
                )

        if "connect_timeout" in self.config:
            connect_timeout = self.config[
                "connect_timeout"
            ]

            if connect_timeout is not None:
                try:
                    connect_timeout = int(
                        connect_timeout
                    )
                except (TypeError, ValueError) as exc:
                    raise ConnectorValidationError(
                        "PostgreSQL connect_timeout must "
                        "be a valid integer."
                    ) from exc

                if connect_timeout <= 0:
                    raise ConnectorValidationError(
                        "PostgreSQL connect_timeout must "
                        "be greater than zero."
                    )

                self.config[
                    "connect_timeout"
                ] = connect_timeout

    # ========================================================
    # CONNECTION
    # ========================================================

    def _build_connection_kwargs(
        self,
        database_name: str | None = None,
    ) -> dict[str, Any]:
        connection_kwargs = {
            "host": self.config["host"],
            "port": self.config["port"],
            "user": self.config["username"],
            "password": self.config["password"],
        }

        selected_database = database_name

        if selected_database is None:
            selected_database = self.config.get(
                "database"
            )

        if selected_database is not None:
            if not isinstance(
                selected_database,
                str,
            ):
                raise ConnectorValidationError(
                    "PostgreSQL database must be a string."
                )

            selected_database = selected_database.strip()

            if not selected_database:
                raise ConnectorValidationError(
                    "PostgreSQL database cannot be empty."
                )

            connection_kwargs["dbname"] = (
                selected_database
            )

        optional_fields = (
            "sslmode",
            "connect_timeout",
            "application_name",
        )

        for field in optional_fields:
            value = self.config.get(field)

            if value is not None:
                connection_kwargs[field] = value

        return connection_kwargs

    def _connect(
        self,
        database_name: str | None = None,
    ):
        try:
            return psycopg.connect(
                **self._build_connection_kwargs(
                    database_name=database_name,
                )
            )
        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to connect to the PostgreSQL "
                "data source."
            ) from exc

    # ========================================================
    # TEST CONNECTION
    # ========================================================

    def test_connection(self) -> bool:
        connection = None

        try:
            database_name = self.config.get(
                "database"
            )

            if not database_name:
                database_name = (
                    self.DEFAULT_TEST_DATABASE
                )

            connection = self._connect(
                database_name=database_name,
            )

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            return result == (1,)

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "PostgreSQL connection test failed."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # ROOT PATHS
    # ========================================================

    def list_root_paths(self) -> list[str]:
        """
        Return PostgreSQL databases visible to the
        configured PostgreSQL user.
        """

        connection = None

        try:
            connection = self._connect(
                database_name=self.config.get(
                    "database"
                )
                or self.DEFAULT_TEST_DATABASE
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT datname
                    FROM pg_database
                    WHERE datallowconn = TRUE
                      AND datistemplate = FALSE
                    ORDER BY datname
                    """
                )

                rows = cursor.fetchall()

            return [
                row[0]
                for row in rows
            ]

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to list PostgreSQL databases."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # CHILD PATHS
    # ========================================================

    def search_child_paths(
        self,
        parent_path: str,
        search_text: str | None = None,
    ) -> list[str]:
        """
        Return schemas belonging to the selected database.

        parent_path represents the database selected from
        the Look-Forward root.
        """

        if not isinstance(parent_path, str):
            raise ConnectorValidationError(
                "PostgreSQL parent path must be a string."
            )

        database_name = parent_path.strip()

        if not database_name:
            raise ConnectorValidationError(
                "PostgreSQL parent path cannot be empty."
            )

        connection = None

        try:
            connection = self._connect(
                database_name=database_name,
            )

            with connection.cursor() as cursor:
                if search_text:
                    normalized_search = (
                        search_text.strip()
                    )

                    cursor.execute(
                        """
                        SELECT schema_name
                        FROM information_schema.schemata
                        WHERE schema_name ILIKE %s
                        ORDER BY schema_name
                        """,
                        (
                            f"%{normalized_search}%",
                        ),
                    )

                else:
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
            ]

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to search PostgreSQL schemas."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # DESTINATION VALIDATION
    # ========================================================

    def validate_destination_path(
        self,
        path: str,
    ) -> bool:
        """
        Validate a PostgreSQL destination path.

        Supported formats:

            schema

        or:

            schema/table

        The database is supplied by the connector configuration.
        """

        if not isinstance(path, str):
            raise ConnectorValidationError(
                "PostgreSQL destination path must be a string."
            )

        normalized_path = path.strip()

        if not normalized_path:
            return False

        parts = [
            part.strip()
            for part in normalized_path.split("/")
            if part.strip()
        ]

        if len(parts) > 2:
            return False

        database_name = self.config.get(
            "database"
        )

        if not database_name:
            raise ConnectorValidationError(
                "A PostgreSQL database must be selected "
                "before destination validation."
            )

        connection = None

        try:
            connection = self._connect(
                database_name=database_name,
            )

            with connection.cursor() as cursor:
                if len(parts) == 1:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.schemata
                            WHERE schema_name = %s
                        )
                        """,
                        (
                            parts[0],
                        ),
                    )

                else:
                    schema_name = parts[0]
                    table_name = parts[1]

                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = %s
                              AND table_name = %s
                        )
                        """,
                        (
                            schema_name,
                            table_name,
                        ),
                    )

                result = cursor.fetchone()

            return bool(
                result
                and result[0]
            )

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to validate PostgreSQL "
                "destination path."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # SCHEMA LISTING
    # ========================================================

    def list_schemas(
        self,
        database_name: str | None = None,
        search_text: str | None = None,
    ) -> list[str]:
        """
        List schemas from the selected PostgreSQL database.
        """

        selected_database = database_name

        if not selected_database:
            selected_database = self.config.get(
                "database"
            )

        if not selected_database:
            raise ConnectorValidationError(
                "A PostgreSQL database must be selected "
                "before listing schemas."
            )

        selected_database = selected_database.strip()

        if not selected_database:
            raise ConnectorValidationError(
                "PostgreSQL database cannot be empty."
            )

        connection = None

        try:
            connection = self._connect(
                database_name=selected_database,
            )

            with connection.cursor() as cursor:
                if search_text:
                    normalized_search = (
                        search_text.strip()
                    )

                    cursor.execute(
                        """
                        SELECT schema_name
                        FROM information_schema.schemata
                        WHERE schema_name ILIKE %s
                        ORDER BY schema_name
                        """,
                        (
                            f"%{normalized_search}%",
                        ),
                    )

                else:
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
            ]

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to list PostgreSQL schemas."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # TABLE LISTING
    # ========================================================

    def list_tables(
        self,
        schema_name: str,
        search_text: str | None = None,
        database_name: str | None = None,
    ) -> list[str]:
        """
        List tables from a selected PostgreSQL schema.

        database_name must identify the database selected
        through Look-Forward.
        """

        if not isinstance(schema_name, str):
            raise ConnectorValidationError(
                "PostgreSQL schema name must be a string."
            )

        schema_name = schema_name.strip()

        if not schema_name:
            raise ConnectorValidationError(
                "PostgreSQL schema name cannot be empty."
            )

        selected_database = database_name

        if not selected_database:
            selected_database = self.config.get(
                "database"
            )

        if not selected_database:
            raise ConnectorValidationError(
                "A PostgreSQL database must be selected "
                "before listing tables."
            )

        selected_database = selected_database.strip()

        if not selected_database:
            raise ConnectorValidationError(
                "PostgreSQL database cannot be empty."
            )

        connection = None

        try:
            connection = self._connect(
                database_name=selected_database,
            )

            with connection.cursor() as cursor:
                if search_text:
                    normalized_search = (
                        search_text.strip()
                    )

                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                          AND table_type = 'BASE TABLE'
                          AND table_name ILIKE %s
                        ORDER BY table_name
                        """,
                        (
                            schema_name,
                            f"%{normalized_search}%",
                        ),
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
                        (
                            schema_name,
                        ),
                    )

                rows = cursor.fetchall()

            return [
                row[0]
                for row in rows
            ]

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to list PostgreSQL tables."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # TABLE COLUMN METADATA
    # ========================================================

    def get_table_columns(
        self,
        schema_name: str,
        table_name: str,
        database_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return column metadata for a selected table.
        """

        if not isinstance(schema_name, str):
            raise ConnectorValidationError(
                "PostgreSQL schema name must be a string."
            )

        if not isinstance(table_name, str):
            raise ConnectorValidationError(
                "PostgreSQL table name must be a string."
            )

        schema_name = schema_name.strip()
        table_name = table_name.strip()

        if not schema_name or not table_name:
            raise ConnectorValidationError(
                "PostgreSQL schema and table names "
                "cannot be empty."
            )

        selected_database = database_name

        if not selected_database:
            selected_database = self.config.get(
                "database"
            )

        if not selected_database:
            raise ConnectorValidationError(
                "A PostgreSQL database must be selected "
                "before reading table metadata."
            )

        selected_database = selected_database.strip()

        if not selected_database:
            raise ConnectorValidationError(
                "PostgreSQL database cannot be empty."
            )

        connection = None

        try:
            connection = self._connect(
                database_name=selected_database,
            )

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
                    (
                        schema_name,
                        table_name,
                    ),
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

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to read PostgreSQL "
                "table metadata."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # PREVIEW DATA
    # ========================================================

    def preview_table_data(
        self,
        schema_name: str,
        table_name: str,
        database_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Return up to `limit` rows from the given table, as
        {"columns": [...], "rows": [[...], [...]]}.
        """

        selected_database = database_name or self.config.get("database")

        if not selected_database:
            raise ConnectorValidationError(
                "A PostgreSQL database must be selected before "
                "previewing data."
            )

        if not schema_name or not table_name:
            raise ConnectorValidationError(
                "PostgreSQL schema and table names cannot be empty."
            )

        safe_limit = max(1, min(int(limit), 1_000_000))

        connection = None

        try:
            connection = self._connect(database_name=selected_database)

            with connection.cursor() as cursor:
                # sql.Identifier safely quotes/escapes identifiers,
                # preventing SQL injection via schema/table names.
                query = sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name),
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

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to preview PostgreSQL table data."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # WRITE DATA (EXPORT)
    # ========================================================

    def write_table_data(
        self,
        schema_name: str,
        table_name: str,
        columns: list[str],
        rows: list[list],
        database_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Creates the destination table if it doesn't already
        exist (all columns as TEXT — a deliberate simplification
        so exported anonymized values of any original type can
        be written without a type-inference step) and inserts
        the given rows.
        """

        selected_database = database_name or self.config.get("database")

        if not selected_database:
            raise ConnectorValidationError(
                "A PostgreSQL database must be selected before "
                "exporting data."
            )

        if not schema_name or not table_name:
            raise ConnectorValidationError(
                "PostgreSQL schema and table names cannot be empty."
            )

        connection = None

        try:
            connection = self._connect(database_name=selected_database)

            with connection.cursor() as cursor:
                create_columns_sql = sql.SQL(", ").join(
                    sql.SQL("{} TEXT").format(sql.Identifier(col))
                    for col in columns
                )

                create_statement = sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {}.{} ({})"
                ).format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name),
                    create_columns_sql,
                )

                cursor.execute(create_statement)

                if rows:
                    insert_columns_sql = sql.SQL(", ").join(
                        sql.Identifier(col) for col in columns
                    )
                    placeholders_sql = sql.SQL(", ").join(
                        sql.Placeholder() for _ in columns
                    )

                    insert_statement = sql.SQL(
                        "INSERT INTO {}.{} ({}) VALUES ({})"
                    ).format(
                        sql.Identifier(schema_name),
                        sql.Identifier(table_name),
                        insert_columns_sql,
                        placeholders_sql,
                    )

                    string_rows = [
                        [
                            None if value is None else str(value)
                            for value in row
                        ]
                        for row in rows
                    ]

                    cursor.executemany(insert_statement, string_rows)

            connection.commit()

            return {"rows_written": len(rows)}

        except ConnectorOperationError:
            raise

        except psycopg.Error as exc:
            raise ConnectorOperationError(
                "Unable to write PostgreSQL export data."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                pass

            self._connection = None
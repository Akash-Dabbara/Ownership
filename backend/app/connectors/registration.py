from app.connectors.postgresql import PostgreSQLConnector
from app.connectors.mysql import MySQLConnector
from app.connectors.snowflake import SnowflakeConnector
from app.connectors.s3 import AWS3Connector
from app.connectors.registry import ConnectorRegistry


def register_all_connectors() -> None:
    if not ConnectorRegistry.is_registered("POSTGRESQL"):
        ConnectorRegistry.register("POSTGRESQL", PostgreSQLConnector)

    if not ConnectorRegistry.is_registered("MYSQL"):
        ConnectorRegistry.register("MYSQL", MySQLConnector)

    if not ConnectorRegistry.is_registered("SNOWFLAKE"):
        ConnectorRegistry.register("SNOWFLAKE", SnowflakeConnector)

    if not ConnectorRegistry.is_registered("AWS_S3"):
        ConnectorRegistry.register("AWS_S3", AWS3Connector)
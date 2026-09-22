from collections.abc import Callable
from typing import Any

from app.connectors.base import (
    BaseConnector,
    ConnectorValidationError,
)


ConnectorFactory = Callable[
    [dict[str, Any]],
    BaseConnector,
]


class ConnectorRegistry:
    """
    Central registry for DataEase connectors.

    A connector implementation registers itself against a
    DataSourceType value. The registry can then create the
    correct connector dynamically.
    """

    _connectors: dict[str, ConnectorFactory] = {}

    @classmethod
    def register(
        cls,
        source_type: str,
        connector_factory: ConnectorFactory,
    ) -> None:
        if not isinstance(source_type, str):
            raise ConnectorValidationError(
                "Connector source type must be a string."
            )

        normalized_source_type = source_type.strip().upper()

        if not normalized_source_type:
            raise ConnectorValidationError(
                "Connector source type cannot be empty."
            )

        if not callable(connector_factory):
            raise ConnectorValidationError(
                "Connector factory must be callable."
            )

        if normalized_source_type in cls._connectors:
            raise ConnectorValidationError(
                f"Connector already registered for "
                f"source type '{normalized_source_type}'."
            )

        cls._connectors[
            normalized_source_type
        ] = connector_factory

    @classmethod
    def unregister(
        cls,
        source_type: str,
    ) -> None:
        normalized_source_type = source_type.strip().upper()

        cls._connectors.pop(
            normalized_source_type,
            None,
        )

    @classmethod
    def is_registered(
        cls,
        source_type: str,
    ) -> bool:
        normalized_source_type = source_type.strip().upper()

        return normalized_source_type in cls._connectors

    @classmethod
    def get_connector(
        cls,
        source_type: str,
        config: dict[str, Any],
    ) -> BaseConnector:
        normalized_source_type = source_type.strip().upper()

        connector_factory = cls._connectors.get(
            normalized_source_type
        )

        if connector_factory is None:
            raise ConnectorValidationError(
                f"No connector registered for "
                f"source type '{normalized_source_type}'."
            )

        try:
            connector = connector_factory(config)
        except ConnectorValidationError:
            raise
        except Exception as exc:
            raise ConnectorValidationError(
                f"Unable to create connector for "
                f"source type '{normalized_source_type}'."
            ) from exc

        if not isinstance(connector, BaseConnector):
            raise ConnectorValidationError(
                f"Connector factory for "
                f"'{normalized_source_type}' did not return "
                f"a valid BaseConnector."
            )

        return connector

    @classmethod
    def list_registered_types(cls) -> list[str]:
        return sorted(cls._connectors.keys())

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registrations.

        Intended primarily for testing.
        """

        cls._connectors.clear()
"""
Connectors package initializer.

This module exposes the public connector API for the application:
- ConnectorBase: base class for connector implementations
- register_connector: decorator to register a connector implementation
- get_connector: factory to instantiate a connector by name
- available_connectors: mapping of registered connector names to classes

Connector implementations should live in this package (e.g. 1xbet_connector.py,
parimatch_connector.py, mock_connector.py) and use the @register_connector
decorator to make themselves available to the connector manager.
"""

from typing import Dict, Type, Optional
import importlib
import pkgutil
import logging

logger = logging.getLogger(__name__)

# Public registry
available_connectors: Dict[str, Type["ConnectorBase"]] = {}

def register_connector(name: str):
    """
    Decorator to register a connector class under the given name.

    Usage:
        @register_connector("1xBet")
        class OneXBetConnector(ConnectorBase):
            ...
    """
    def _decorator(cls: Type["ConnectorBase"]):
        key = name.strip()
        if key in available_connectors:
            logger.warning("Overwriting existing connector registration: %s", key)
        available_connectors[key] = cls
        logger.debug("Registered connector %s -> %s", key, cls.__name__)
        return cls
    return _decorator

class ConnectorBase:
    """
    Minimal connector interface.

    Concrete connectors should subclass this and implement:
      - async def start(self): start background fetching/publishing
      - async def stop(self): stop cleanly
      - def status(self) -> dict: return current status (mode, last_seen, enabled)
    The constructor should accept a config dict and a publish callback:
      def __init__(self, name: str, config: dict, publish: Callable[[dict], None])
    """
    def __init__(self, name: str, config: dict, publish):
        self.name = name
        self.config = config or {}
        self.publish = publish
        self._enabled = True

    async def start(self):
        raise NotImplementedError

    async def stop(self):
        raise NotImplementedError

    def status(self) -> dict:
        return {
            "name": self.name,
            "enabled": self._enabled,
            "mode": self.config.get("mode", "unknown"),
            "last_seen": None
        }

def _discover_submodules():
    """
    Import all submodules in the connectors package so they can register themselves.
    This allows connector modules to use @register_connector at import time.
    """
    package = __name__
    for finder, name, ispkg in pkgutil.iter_modules(__path__):
        full = f"{package}.{name}"
        try:
            importlib.import_module(full)
            logger.debug("Imported connector module: %s", full)
        except Exception as e:
            logger.debug("Skipping import of %s: %s", full, e)

# Discover connector modules on import so registrations run automatically.
_discover_submodules()

def get_connector(name: str, config: dict, publish) -> Optional[ConnectorBase]:
    """
    Factory: instantiate a registered connector by name.

    - name: the connector key as registered (case-sensitive by design).
    - config: connector-specific configuration dict.
    - publish: callable used by connector to publish normalized events.

    Returns an instance of ConnectorBase or None if the name is unknown.
    """
    cls = available_connectors.get(name)
    if cls is None:
        logger.warning("Requested unknown connector: %s", name)
        return None
    return cls(name=name, config=config, publish=publish)

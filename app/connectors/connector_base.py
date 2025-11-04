import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class ConnectorBase:
    """
    Minimal async connector base.
    Subclasses must implement _run_loop (async) and can override start/stop/status.
    """
    def __init__(self, name: str, config: dict, publish: Callable[[dict], None]):
        self.name = name
        self.config = config or {}
        self.publish = publish
        self._task: Optional[asyncio.Task] = None
        self._stopping = False
        self._last_seen = None
        self._mode = self.config.get("mode", "mock")

    async def start(self):
        if self._task and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Connector %s started in %s mode", self.name, self._mode)

    async def stop(self):
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
        logger.info("Connector %s stopped", self.name)

    async def _run_loop(self):
        raise NotImplementedError

    def status(self):
        return {
            "name": self.name,
            "mode": self._mode,
            "enabled": not self._stopping,
            "last_seen": self._last_seen,
      }

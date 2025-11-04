import asyncio
import logging
import os
import random
import time

from app.connectors import register_connector
from app.connectors.connector_base import ConnectorBase
from app.connectors.mock_connector import generate_mock_event

logger = logging.getLogger(__name__)

@register_connector("Stake")
class StakeConnector(ConnectorBase):
    def __init__(self, name, config, publish):
        super().__init__(name, config, publish)
        self.api_key_env = config.get("env_key", "BOOKIE_STAKE_KEY")
        self._mode = "live" if os.getenv(self.api_key_env) else "mock"

    async def _run_loop(self):
        while not self._stopping:
            if self._mode == "live":
                try:
                    await asyncio.sleep(1)
                    event = {
                        "bookmaker": "Stake",
                        "market": "1X2",
                        "home": round(random.uniform(1.5, 3.1), 2),
                        "draw": round(random.uniform(2.9, 4.8), 2),
                        "away": round(random.uniform(1.7, 3.2), 2),
                        "timestamp": time.time(),
                    }
                    self._last_seen = event["timestamp"]
                    self.publish(event)
                except Exception:
                    logger.exception("Stake live fetch failed")
                    await asyncio.sleep(5)
            else:
                event = generate_mock_event("Stake")
                self._last_seen = event["timestamp"]
                self.publish(event)
                await asyncio.sleep(self.config.get("interval", 4))

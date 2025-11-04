import asyncio
import logging
import os
import random
import time

from app.connectors import register_connector
from app.connectors.connector_base import ConnectorBase
from app.connectors.mock_connector import generate_mock_event

logger = logging.getLogger(__name__)

@register_connector("1xBet")
class OneXBetConnector(ConnectorBase):
    def __init__(self, name, config, publish):
        super().__init__(name, config, publish)
        # env key name override allowed in config
        self.api_key_env = config.get("env_key", "BOOKIE_1XBET_KEY")
        if os.getenv(self.api_key_env):
            self._mode = "live"
        else:
            self._mode = "mock"

    async def _run_loop(self):
        while not self._stopping:
            if self._mode == "live":
                # placeholder: replace with real API call logic
                try:
                    # simulate request latency
                    await asyncio.sleep(1)
                    event = {
                        "bookmaker": "1xBet",
                        "market": "1X2",
                        "home": round(random.uniform(1.4, 3.2), 2),
                        "draw": round(random.uniform(2.8, 4.8), 2),
                        "away": round(random.uniform(1.6, 4.0), 2),
                        "timestamp": time.time(),
                    }
                    self._last_seen = event["timestamp"]
                    self.publish(event)
                except Exception:
                    logger.exception("1xBet live fetch failed")
                    await asyncio.sleep(5)
            else:
                event = generate_mock_event("1xBet")
                self._last_seen = event["timestamp"]
                self.publish(event)
                await asyncio.sleep(self.config.get("interval", 4))

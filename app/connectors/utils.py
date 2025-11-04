import logging
import time
import random

logger = logging.getLogger(__name__)

def pretty_event(ev: dict) -> str:
    ts = ev.get("timestamp", time.time())
    return f"{ev.get('bookmaker')} | {ev.get('market')} | H:{ev.get('home')} D:{ev.get('draw')} A:{ev.get('away')} @ {ts}"

# helper used by connectors when they want to generate a simple mock
def gen_simple_odds():
    return {
        "home": round(random.uniform(1.4, 3.0), 2),
        "draw": round(random.uniform(2.6, 4.8), 2),
        "away": round(random.uniform(1.5, 4.0), 2),
        "timestamp": time.time()
    }

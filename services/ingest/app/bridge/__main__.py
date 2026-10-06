"""Run the stream bridge:  python -m app.bridge"""

import logging
import signal
import threading

from ..config import get_settings
from .consumer import Bridge
from .state import BridgeState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    settings = get_settings()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())     # docker stop -> close the consumer cleanly
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    bridge = Bridge(settings.KAFKA_BOOTSTRAP, settings.MARKET_STREAM_URL, BridgeState(settings.BRIDGE_MIN_DTE))
    bridge.run(stop)


if __name__ == "__main__":
    main()

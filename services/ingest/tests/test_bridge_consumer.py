from datetime import date, datetime, timedelta, timezone

from app.bridge.consumer import Bridge, should_post, start_offset
from app.bridge.state import BridgeState
from tests.test_bridge_state import QUOTED, chain_env

T0 = QUOTED + timedelta(minutes=1)


def test_start_offset_seeks_back_but_not_past_retention():
    assert start_offset(low=0, high=500, back=60) == 440
    assert start_offset(low=0, high=20, back=60) == 0
    assert start_offset(low=480, high=500, back=60) == 480      # older messages already deleted by retention


def test_throttle_and_resend():
    assert not should_post(T0, None, changed=False)              # nothing to say yet
    assert should_post(T0, None, changed=True)
    assert not should_post(T0 + timedelta(seconds=3), T0, changed=True)      # at most every 5s
    assert should_post(T0 + timedelta(seconds=5), T0, changed=True)
    assert not should_post(T0 + timedelta(seconds=59), T0, changed=False)
    assert should_post(T0 + timedelta(seconds=60), T0, changed=False)        # resend keeps market-stream filled


def test_handle_then_post_and_skip_bad_messages():
    posted = []
    bridge = Bridge("unused", "http://market-stream", BridgeState(min_dte=1), post=posted.append)
    bridge.handle(b"not json")
    bridge.handle(b'{"schema": "bars.v9", "payload": {}}')
    assert not bridge.changed
    bridge.handle(chain_env(date(2026, 10, 9)).to_bytes())
    assert bridge.maybe_post(T0) and len(posted) == 1 and not bridge.changed
    assert not bridge.maybe_post(T0 + timedelta(seconds=10))     # unchanged, not yet time to resend


def test_no_post_until_replay_reaches_the_startup_end():
    posted = []
    bridge = Bridge("unused", "http://market-stream", BridgeState(min_dte=1), post=posted.append)
    bridge.catching_up = {("options.chain.quotes", 0): 10, ("options.chain.quotes", 1): 4}
    bridge.handle(chain_env(date(2026, 10, 9)).to_bytes())
    bridge.track_replay("options.chain.quotes", 0, 9)            # partition 0 done (offset 9 is its last)
    assert not bridge.maybe_post(T0)                              # partition 1 still replaying
    bridge.track_replay("options.chain.quotes", 1, 3)
    assert bridge.maybe_post(T0) and len(posted) == 1


def test_failed_post_is_retried():
    calls = []

    def flaky(quote):
        calls.append(quote)
        if len(calls) == 1:
            raise ConnectionError("market-stream restarting")

    bridge = Bridge("unused", "http://market-stream", BridgeState(min_dte=1), post=flaky)
    bridge.handle(chain_env(date(2026, 10, 9)).to_bytes())
    assert not bridge.maybe_post(T0) and bridge.changed
    assert bridge.maybe_post(T0 + timedelta(seconds=5)) and len(calls) == 2

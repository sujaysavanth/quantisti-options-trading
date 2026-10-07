"""Data sources. `chain_source(name)` picks the option-chain provider (CHAIN_SOURCE setting)."""

from .base import ChainSource


def chain_source(name: str) -> ChainSource:
    if name == "cboe":
        from .cboe import CboeDelayedSource
        return CboeDelayedSource()
    if name == "yahoo":
        from .yahoo import YahooDelayedSource
        return YahooDelayedSource()
    raise ValueError(f"Unknown chain source {name!r}; expected 'cboe' or 'yahoo'")

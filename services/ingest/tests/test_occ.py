from datetime import date

import pytest

from app.sources.occ import OccSymbol, parse_occ


@pytest.mark.parametrize("symbol, expected", [
    ("SPXW261016C07650000", OccSymbol("SPXW", date(2026, 10, 16), "C", 7650.0)),
    ("SPX261016P00200000", OccSymbol("SPX", date(2026, 10, 16), "P", 200.0)),
    ("SPXW261002P07587500", OccSymbol("SPXW", date(2026, 10, 2), "P", 7587.5)),   # half-point strike
    ("SPX   261016C07650000", OccSymbol("SPX", date(2026, 10, 16), "C", 7650.0)),  # space-padded root
])
def test_parse_occ(symbol, expected):
    assert parse_occ(symbol) == expected


@pytest.mark.parametrize("bad", ["", "SPX", "SPXW261016X07650000", "SPXW261316C07650000", "SPXW2610C07650000"])
def test_parse_occ_rejects_bad_symbols(bad):
    with pytest.raises(ValueError):
        parse_occ(bad)

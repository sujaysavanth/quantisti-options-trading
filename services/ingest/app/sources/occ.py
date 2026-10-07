"""OCC option symbols, e.g. SPXW261016C07650000 = SPXW, 2026-10-16, Call, strike 7650."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# root (letters) + YYMMDD + C/P + strike x 1000 as 8 digits. The official format pads
# the root with spaces to 6 characters ("SPX   261016C07650000"); feeds often strip them.
_OCC = re.compile(r"^([A-Z]{1,6})\s*(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")


@dataclass(frozen=True)
class OccSymbol:
    root: str          # 'SPX' (monthly, AM-settled) or 'SPXW' (weeklies/dailies, PM-settled)
    expiry: date
    option_type: str   # 'C' or 'P'
    strike: float


def parse_occ(symbol: str) -> OccSymbol:
    match = _OCC.match(symbol.strip().upper())
    if not match:
        raise ValueError(f"Not an OCC option symbol: {symbol!r}")
    root, yy, mm, dd, option_type, strike = match.groups()
    return OccSymbol(root, date(2000 + int(yy), int(mm), int(dd)), option_type, int(strike) / 1000)

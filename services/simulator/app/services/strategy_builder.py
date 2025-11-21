"""Build simple weekly option strategies from live market-stream quote."""

from __future__ import annotations

from typing import Dict, List, Optional

from ..models.strategy_live import StrategyInstance, StrategyLeg


def _pick_price(leg: Dict) -> float:
    for key in ("last", "bid", "ask"):
        val = leg.get(key)
        if val not in (None, 0):
            return float(val)
    return 0.0


def _nearest_leg(legs: List[Dict], option_type: str, target: float, prefer: str = "closest") -> Optional[Dict]:
    same_type = [l for l in legs if l.get("option_type") == option_type]
    if not same_type:
        return None
    if prefer == "above":
        same_type = [l for l in same_type if l.get("strike", 0) >= target]
    elif prefer == "below":
        same_type = [l for l in same_type if l.get("strike", 0) <= target]
    if not same_type:
        return None
    return min(same_type, key=lambda l: abs(l.get("strike", 0) - target))


def _leg_model(raw: Dict, side: str, qty: int = 1) -> StrategyLeg:
    return StrategyLeg(
        identifier=raw.get("identifier"),
        strike=float(raw.get("strike")),
        option_type=raw.get("option_type"),
        expiry=raw.get("expiry"),
        quantity=qty,
        side=side,
        price=_pick_price(raw)
    )


def build_strategies_from_quote(quote: Dict) -> List[StrategyInstance]:
    legs_raw = quote.get("legs") or []
    if not legs_raw:
        return []

    price = float(quote.get("last_price", 0))

    atm_leg_call = _nearest_leg(legs_raw, "CALL", price, "closest")
    atm_leg_put = _nearest_leg(legs_raw, "PUT", price, "closest")
    one_step_up_call = _nearest_leg(legs_raw, "CALL", price + 50, "above")
    two_step_up_call = _nearest_leg(legs_raw, "CALL", price + 100, "above")
    three_step_up_call = _nearest_leg(legs_raw, "CALL", price + 150, "above")
    one_step_down_put = _nearest_leg(legs_raw, "PUT", price - 50, "below")
    two_step_down_put = _nearest_leg(legs_raw, "PUT", price - 100, "below")
    three_step_down_put = _nearest_leg(legs_raw, "PUT", price - 150, "below")

    # Fallback selections so we still emit ideas even if the chain is sparse
    up_for_strangle = one_step_up_call or two_step_up_call or three_step_up_call or atm_leg_call
    down_for_strangle = one_step_down_put or two_step_down_put or three_step_down_put or atm_leg_put

    strategies: List[StrategyInstance] = []

    # Long Call
    if atm_leg_call:
        strategies.append(
            StrategyInstance(
                name="Long Call",
                category="Directional",
                description="Buy ATM call expecting upside",
                net_premium=_pick_price(atm_leg_call),
                max_profit=None,
                max_loss=_pick_price(atm_leg_call),
                breakevens=[atm_leg_call["strike"] + _pick_price(atm_leg_call)],
                legs=[_leg_model(atm_leg_call, "BUY")]
            )
        )

    # Long Put
    if atm_leg_put:
        premium = _pick_price(atm_leg_put)
        strategies.append(
            StrategyInstance(
                name="Long Put",
                category="Directional",
                description="Buy ATM put expecting downside",
                net_premium=premium,
                max_profit=None,
                max_loss=premium,
                breakevens=[atm_leg_put["strike"] - premium],
                legs=[_leg_model(atm_leg_put, "BUY")]
            )
        )

    # Bull Call Spread
    if atm_leg_call and one_step_up_call:
        debit = _pick_price(atm_leg_call) - _pick_price(one_step_up_call)
        width = one_step_up_call["strike"] - atm_leg_call["strike"]
        strategies.append(
            StrategyInstance(
                name="Bull Call Spread",
                category="Spread",
                description="Buy ATM call, sell higher call",
                net_premium=debit,
                max_profit=max(width - debit, 0),
                max_loss=max(debit, 0),
                breakevens=[atm_leg_call["strike"] + debit],
                legs=[
                    _leg_model(atm_leg_call, "BUY"),
                    _leg_model(one_step_up_call, "SELL")
                ]
            )
        )

    # Bear Put Spread
    if atm_leg_put and one_step_down_put:
        debit = _pick_price(atm_leg_put) - _pick_price(one_step_down_put)
        width = atm_leg_put["strike"] - one_step_down_put["strike"]
        strategies.append(
            StrategyInstance(
                name="Bear Put Spread",
                category="Spread",
                description="Buy ATM put, sell lower put",
                net_premium=debit,
                max_profit=max(width - debit, 0),
                max_loss=max(debit, 0),
                breakevens=[atm_leg_put["strike"] - debit],
                legs=[
                    _leg_model(atm_leg_put, "BUY"),
                    _leg_model(one_step_down_put, "SELL")
                ]
            )
        )

    # Bull Put Credit Spread
    if atm_leg_put and one_step_down_put:
        credit = _pick_price(atm_leg_put) - _pick_price(one_step_down_put)
        width = atm_leg_put["strike"] - one_step_down_put["strike"]
        strategies.append(
            StrategyInstance(
                name="Bull Put Spread",
                category="Credit Spread",
                description="Sell higher put, buy lower put",
                net_premium=credit,
                max_profit=credit,
                max_loss=max(width - credit, 0),
                breakevens=[atm_leg_put["strike"] - credit],
                legs=[
                    _leg_model(atm_leg_put, "SELL"),
                    _leg_model(one_step_down_put, "BUY")
                ]
            )
        )

    # Bear Call Credit Spread
    if atm_leg_call and one_step_up_call:
        credit = _pick_price(atm_leg_call) - _pick_price(one_step_up_call)
        width = one_step_up_call["strike"] - atm_leg_call["strike"]
        strategies.append(
            StrategyInstance(
                name="Bear Call Spread",
                category="Credit Spread",
                description="Sell lower call, buy higher call",
                net_premium=credit,
                max_profit=credit,
                max_loss=max(width - credit, 0),
                breakevens=[atm_leg_call["strike"] + credit],
                legs=[
                    _leg_model(atm_leg_call, "SELL"),
                    _leg_model(one_step_up_call, "BUY")
                ]
            )
        )

    # Long Straddle
    if atm_leg_call and atm_leg_put:
        total_debit = _pick_price(atm_leg_call) + _pick_price(atm_leg_put)
        strategies.append(
            StrategyInstance(
                name="Long Straddle",
                category="Volatility",
                description="Buy ATM call and put",
                net_premium=total_debit,
                max_profit=None,
                max_loss=total_debit,
                breakevens=[
                    atm_leg_call["strike"] + total_debit,
                    atm_leg_put["strike"] - total_debit
                ],
                legs=[
                    _leg_model(atm_leg_call, "BUY"),
                    _leg_model(atm_leg_put, "BUY")
                ]
            )
        )

    # Long Strangle
    if up_for_strangle and down_for_strangle and up_for_strangle is not down_for_strangle:
        total_debit = _pick_price(up_for_strangle) + _pick_price(down_for_strangle)
        strategies.append(
            StrategyInstance(
                name="Long Strangle",
                category="Volatility",
                description="Buy OTM call and put",
                net_premium=total_debit,
                max_profit=None,
                max_loss=total_debit,
                breakevens=[
                    up_for_strangle["strike"] + total_debit,
                    down_for_strangle["strike"] - total_debit
                ],
                legs=[
                    _leg_model(up_for_strangle, "BUY"),
                    _leg_model(down_for_strangle, "BUY")
                ]
            )
        )

    # Short Straddle
    if atm_leg_call and atm_leg_put:
        total_credit = _pick_price(atm_leg_call) + _pick_price(atm_leg_put)
        strategies.append(
            StrategyInstance(
                name="Short Straddle",
                category="Income",
                description="Sell ATM call and put",
                net_premium=total_credit,
                max_profit=total_credit,
                max_loss=None,
                breakevens=[
                    atm_leg_call["strike"] + total_credit,
                    atm_leg_put["strike"] - total_credit
                ],
                legs=[
                    _leg_model(atm_leg_call, "SELL"),
                    _leg_model(atm_leg_put, "SELL")
                ]
            )
        )

    # Short Strangle
    if up_for_strangle and down_for_strangle and up_for_strangle is not down_for_strangle:
        total_credit = _pick_price(up_for_strangle) + _pick_price(down_for_strangle)
        strategies.append(
            StrategyInstance(
                name="Short Strangle",
                category="Income",
                description="Sell OTM call and put",
                net_premium=total_credit,
                max_profit=total_credit,
                max_loss=None,
                breakevens=[
                    up_for_strangle["strike"] + total_credit,
                    down_for_strangle["strike"] - total_credit
                ],
                legs=[
                    _leg_model(up_for_strangle, "SELL"),
                    _leg_model(down_for_strangle, "SELL")
                ]
            )
        )

    # Iron Condor
    if one_step_up_call and two_step_up_call and one_step_down_put and two_step_down_put:
        credit = (
            _pick_price(one_step_up_call)
            + _pick_price(one_step_down_put)
            - _pick_price(two_step_up_call)
            - _pick_price(two_step_down_put)
        )
        width_call = two_step_up_call["strike"] - one_step_up_call["strike"] if two_step_up_call else 0
        width_put = one_step_down_put["strike"] - two_step_down_put["strike"] if two_step_down_put else 0
        width = min(width_call, width_put)
        strategies.append(
          StrategyInstance(
              name="Iron Condor",
              category="Volatility",
              description="Sell OTM call/put spreads",
              net_premium=credit,
              max_profit=credit,
              max_loss=max(width - credit, 0) if width else None,
              breakevens=[
                  one_step_down_put["strike"] - credit,
                  one_step_up_call["strike"] + credit
              ],
              legs=[
                  _leg_model(one_step_up_call, "SELL"),
                  _leg_model(two_step_up_call, "BUY"),
                  _leg_model(one_step_down_put, "SELL"),
                  _leg_model(two_step_down_put, "BUY"),
              ]
          )
        )

    # Iron Butterfly (sell straddle, buy wings)
    if atm_leg_call and atm_leg_put and two_step_up_call and two_step_down_put:
        credit = (
            _pick_price(atm_leg_call)
            + _pick_price(atm_leg_put)
            - _pick_price(two_step_up_call)
            - _pick_price(two_step_down_put)
        )
        wing_width = min(
            abs(two_step_up_call["strike"] - atm_leg_call["strike"]),
            abs(atm_leg_put["strike"] - two_step_down_put["strike"]),
        )
        strategies.append(
            StrategyInstance(
                name="Iron Butterfly",
                category="Volatility",
                description="Sell ATM straddle, buy OTM wings",
                net_premium=credit,
                max_profit=credit,
                max_loss=max(wing_width - credit, 0) if wing_width else None,
                breakevens=[
                    atm_leg_put["strike"] - credit,
                    atm_leg_call["strike"] + credit,
                ],
                legs=[
                    _leg_model(atm_leg_call, "SELL"),
                    _leg_model(atm_leg_put, "SELL"),
                    _leg_model(two_step_up_call, "BUY"),
                    _leg_model(two_step_down_put, "BUY"),
                ],
            )
        )

    # Call Butterfly (long)
    if one_step_down_put and atm_leg_call and one_step_up_call:
        # Re-purpose nearest strikes as evenly spaced as possible
        lower = _nearest_leg(legs_raw, "CALL", price - 50, "below") or atm_leg_call
        mid = atm_leg_call
        upper = one_step_up_call
        if lower and mid and upper:
            debit = _pick_price(lower) - 2 * _pick_price(mid) + _pick_price(upper)
            width = upper["strike"] - mid["strike"]
            strategies.append(
                StrategyInstance(
                    name="Long Call Butterfly",
                    category="Range",
                    description="Buy lower, sell 2x ATM, buy higher call",
                    net_premium=debit,
                    max_profit=max(width - debit, 0),
                    max_loss=max(debit, 0),
                    breakevens=[
                        lower["strike"] + debit,
                        upper["strike"] - debit,
                    ],
                    legs=[
                        _leg_model(lower, "BUY"),
                        _leg_model(mid, "SELL", qty=2),
                        _leg_model(upper, "BUY"),
                    ],
                )
            )

    # Ratio Call Spread (1x long ATM, 2x short OTM)
    if atm_leg_call and one_step_up_call and two_step_up_call:
        credit = (
            -_pick_price(atm_leg_call)
            + 2 * _pick_price(one_step_up_call)
        )
        width = one_step_up_call["strike"] - atm_leg_call["strike"]
        strategies.append(
            StrategyInstance(
                name="Call Ratio Spread",
                category="Directional",
                description="Buy 1 ATM call, sell 2 OTM calls",
                net_premium=credit,
                max_profit=None,
                max_loss=max(width - credit, 0),
                breakevens=[
                    atm_leg_call["strike"] + credit,
                    one_step_up_call["strike"] + (credit + width),
                ],
                legs=[
                    _leg_model(atm_leg_call, "BUY"),
                    _leg_model(one_step_up_call, "SELL", qty=2),
                ],
            )
        )

    # Put Ratio Spread (1x long ATM, 2x short OTM)
    if atm_leg_put and one_step_down_put and two_step_down_put:
        credit = (
            -_pick_price(atm_leg_put)
            + 2 * _pick_price(one_step_down_put)
        )
        width = atm_leg_put["strike"] - one_step_down_put["strike"]
        strategies.append(
            StrategyInstance(
                name="Put Ratio Spread",
                category="Directional",
                description="Buy 1 ATM put, sell 2 OTM puts",
                net_premium=credit,
                max_profit=None,
                max_loss=max(width - credit, 0),
                breakevens=[
                    atm_leg_put["strike"] - credit,
                    one_step_down_put["strike"] - (credit + width),
                ],
                legs=[
                    _leg_model(atm_leg_put, "BUY"),
                    _leg_model(one_step_down_put, "SELL", qty=2),
                ],
            )
        )

    # Long Put Butterfly
    if one_step_up_call and atm_leg_put and one_step_down_put: # Using Call for upper bound check is weird, but let's stick to puts
        # We need ITM Put (higher strike), ATM Put, OTM Put (lower strike)
        # one_step_up_call is roughly price + 50. Let's find one_step_up_put if possible, or use nearest
        one_step_up_put = _nearest_leg(legs_raw, "PUT", price + 50, "above")
        
        upper = one_step_up_put
        mid = atm_leg_put
        lower = one_step_down_put
        
        if upper and mid and lower:
            debit = _pick_price(upper) - 2 * _pick_price(mid) + _pick_price(lower)
            width = upper["strike"] - mid["strike"]
            strategies.append(
                StrategyInstance(
                    name="Long Put Butterfly",
                    category="Range",
                    description="Buy ITM, sell 2x ATM, buy OTM put",
                    net_premium=debit,
                    max_profit=max(width - debit, 0),
                    max_loss=max(debit, 0),
                    breakevens=[
                        upper["strike"] - debit,
                        lower["strike"] + debit,
                    ],
                    legs=[
                        _leg_model(upper, "BUY"),
                        _leg_model(mid, "SELL", qty=2),
                        _leg_model(lower, "BUY"),
                    ],
                )
            )

    # Jade Lizard (Sell OTM Put, Sell OTM Call Spread)
    if one_step_down_put and one_step_up_call and two_step_up_call:
        credit = (
            _pick_price(one_step_down_put)
            + _pick_price(one_step_up_call)
            - _pick_price(two_step_up_call)
        )
        strategies.append(
            StrategyInstance(
                name="Jade Lizard",
                category="Income",
                description="Sell OTM put, sell OTM call spread",
                net_premium=credit,
                max_profit=credit,
                max_loss=None, # Technically unlimited downside on put, but capped upside
                breakevens=[one_step_down_put["strike"] - credit],
                legs=[
                    _leg_model(one_step_down_put, "SELL"),
                    _leg_model(one_step_up_call, "SELL"),
                    _leg_model(two_step_up_call, "BUY"),
                ],
            )
        )

    # Reverse Jade Lizard (Sell OTM Call, Sell OTM Put Spread)
    if one_step_up_call and one_step_down_put and two_step_down_put:
        credit = (
            _pick_price(one_step_up_call)
            + _pick_price(one_step_down_put)
            - _pick_price(two_step_down_put)
        )
        strategies.append(
            StrategyInstance(
                name="Reverse Jade Lizard",
                category="Income",
                description="Sell OTM call, sell OTM put spread",
                net_premium=credit,
                max_profit=credit,
                max_loss=None, # Unlimited upside on call
                breakevens=[one_step_up_call["strike"] + credit],
                legs=[
                    _leg_model(one_step_up_call, "SELL"),
                    _leg_model(one_step_down_put, "SELL"),
                    _leg_model(two_step_down_put, "BUY"),
                ],
            )
        )

    # Call Ratio Backspread (Sell 1 ATM, Buy 2 OTM)
    if atm_leg_call and one_step_up_call:
        debit_or_credit = _pick_price(atm_leg_call) - 2 * _pick_price(one_step_up_call)
        # If positive, it's a credit (we sold expensive, bought cheap x2). If negative, debit.
        # Usually backspreads are done for a credit or small debit.
        strategies.append(
            StrategyInstance(
                name="Call Ratio Backspread",
                category="Volatility",
                description="Sell 1 ATM call, buy 2 OTM calls",
                net_premium=debit_or_credit,
                max_profit=None, # Unlimited
                max_loss=None, # Risk is if market stays at long strike
                breakevens=[], # Complex
                legs=[
                    _leg_model(atm_leg_call, "SELL"),
                    _leg_model(one_step_up_call, "BUY", qty=2),
                ],
            )
        )

    # Put Ratio Backspread (Sell 1 ATM, Buy 2 OTM)
    if atm_leg_put and one_step_down_put:
        debit_or_credit = _pick_price(atm_leg_put) - 2 * _pick_price(one_step_down_put)
        strategies.append(
            StrategyInstance(
                name="Put Ratio Backspread",
                category="Volatility",
                description="Sell 1 ATM put, buy 2 OTM puts",
                net_premium=debit_or_credit,
                max_profit=None,
                max_loss=None,
                breakevens=[],
                legs=[
                    _leg_model(atm_leg_put, "SELL"),
                    _leg_model(one_step_down_put, "BUY", qty=2),
                ],
            )
        )

    # Broken Wing Butterfly (Call)
    # Buy ATM, Sell 2x OTM (+100), Buy Far OTM (+250) -> approximated as +150 here (three_step_up)
    if atm_leg_call and two_step_up_call and three_step_up_call:
        # Using two_step (+100) as the short strikes, and three_step (+150) as the broken wing
        # Standard fly would be +200. Here we buy +150 (tighter) or +250 (wider).
        # Let's assume "Broken Wing" means we skip a strike for the far wing to make it cheaper/credit.
        # So Buy ATM, Sell 2x (+100), Buy (+250).
        # We don't have +250 easily in our variables, let's use three_step (+150) as the "wing" but maybe that's too close?
        # Actually, BWB usually implies the far wing is FURTHER out to create a credit.
        # If standard is 0, 100, 200. BWB is 0, 100, 250.
        # We only have variables for up to +150.
        # Let's try to fetch +200 or +250 dynamically.
        far_wing = _nearest_leg(legs_raw, "CALL", price + 200, "above")
        
        if far_wing:
            debit = _pick_price(atm_leg_call) - 2 * _pick_price(two_step_up_call) + _pick_price(far_wing)
            strategies.append(
                StrategyInstance(
                    name="Broken Wing Butterfly",
                    category="Directional",
                    description="Buy ATM, Sell 2x OTM, Buy Far OTM",
                    net_premium=debit,
                    max_profit=None,
                    max_loss=None,
                    breakevens=[],
                    legs=[
                        _leg_model(atm_leg_call, "BUY"),
                        _leg_model(two_step_up_call, "SELL", qty=2),
                        _leg_model(far_wing, "BUY"),
                    ],
                )
            )

    return strategies

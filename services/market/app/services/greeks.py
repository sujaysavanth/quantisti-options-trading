"""Options Greeks calculator."""

import math
from typing import Dict

from scipy.stats import norm

from ..models.options import Greeks


class GreeksCalculator:
    """Calculate option Greeks using Black-Scholes model."""

    @staticmethod
    def calculate_greeks(
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: str,
        dividend_yield: float = 0.0
    ) -> Greeks:
        """Calculate all Greeks for an option.

        Args:
            spot_price: Current price of underlying
            strike: Strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate (annual)
            volatility: Implied volatility (annual)
            option_type: 'CE' for call, 'PE' for put
            dividend_yield: Dividend yield (annual)

        Returns:
            Greeks object with all calculated values
        """
        if time_to_expiry <= 0:
            # At expiration, Greeks are undefined or zero
            return Greeks(delta=0, gamma=0, theta=0, vega=0, rho=0)

        # Calculate d1 and d2
        d1 = (
            math.log(spot_price / strike)
            + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        # Calculate Delta
        if option_type == "CE":
            delta = math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
        else:  # PUT
            delta = -math.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)

        # Calculate Gamma (same for calls and puts)
        gamma = (
            math.exp(-dividend_yield * time_to_expiry)
            * norm.pdf(d1)
            / (spot_price * volatility * math.sqrt(time_to_expiry))
        )

        # Calculate Vega (same for calls and puts)
        # Vega is typically expressed per 1% change in volatility
        vega = (
            spot_price
            * math.exp(-dividend_yield * time_to_expiry)
            * norm.pdf(d1)
            * math.sqrt(time_to_expiry)
            / 100  # Per 1% volatility change
        )

        # Calculate Theta
        if option_type == "CE":
            theta = (
                -spot_price * norm.pdf(d1) * volatility * math.exp(-dividend_yield * time_to_expiry)
                / (2 * math.sqrt(time_to_expiry))
                - risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
                + dividend_yield * spot_price * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
            ) / 365  # Per day
        else:  # PUT
            theta = (
                -spot_price * norm.pdf(d1) * volatility * math.exp(-dividend_yield * time_to_expiry)
                / (2 * math.sqrt(time_to_expiry))
                + risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
                - dividend_yield * spot_price * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)
            ) / 365  # Per day

        # Calculate Rho
        # Rho is typically expressed per 1% change in interest rate
        if option_type == "CE":
            rho = (
                strike
                * time_to_expiry
                * math.exp(-risk_free_rate * time_to_expiry)
                * norm.cdf(d2)
                / 100  # Per 1% rate change
            )
        else:  # PUT
            rho = (
                -strike
                * time_to_expiry
                * math.exp(-risk_free_rate * time_to_expiry)
                * norm.cdf(-d2)
                / 100  # Per 1% rate change
            )

        return Greeks(
            delta=round(delta, 6),
            gamma=round(gamma, 8),
            theta=round(theta, 6),
            vega=round(vega, 6),
            rho=round(rho, 6)
        )

    @staticmethod
    def calculate_delta(
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: str,
        dividend_yield: float = 0.0
    ) -> float:
        """Calculate Delta only (optimized for single Greek calculation).

        Args:
            spot_price: Current price of underlying
            strike: Strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate (annual)
            volatility: Implied volatility (annual)
            option_type: 'CE' for call, 'PE' for put
            dividend_yield: Dividend yield (annual)

        Returns:
            Delta value
        """
        if time_to_expiry <= 0:
            return 0

        d1 = (
            math.log(spot_price / strike)
            + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        if option_type == "CE":
            return math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
        else:
            return -math.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)

"""Black-Scholes option pricing model implementation."""

import math
from datetime import date
from typing import Tuple

from scipy.stats import norm


class BlackScholesCalculator:
    """Black-Scholes option pricing calculator.

    Implements the Black-Scholes-Merton model for European options.
    """

    @staticmethod
    def calculate_d1_d2(
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> Tuple[float, float]:
        """Calculate d1 and d2 parameters.

        Args:
            spot_price: Current price of underlying
            strike: Strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate (annual)
            volatility: Implied volatility (annual)
            dividend_yield: Dividend yield (annual)

        Returns:
            Tuple of (d1, d2)
        """
        if time_to_expiry <= 0:
            raise ValueError("time_to_expiry must be positive")

        if volatility <= 0:
            raise ValueError("volatility must be positive")

        d1 = (
            math.log(spot_price / strike)
            + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        return d1, d2

    @classmethod
    def call_price(
        cls,
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """Calculate European call option price.

        Args:
            spot_price: Current price of underlying
            strike: Strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate (annual)
            volatility: Implied volatility (annual)
            dividend_yield: Dividend yield (annual)

        Returns:
            Call option price
        """
        if time_to_expiry <= 0:
            # At expiration
            return max(spot_price - strike, 0)

        d1, d2 = cls.calculate_d1_d2(
            spot_price, strike, time_to_expiry, risk_free_rate, volatility, dividend_yield
        )

        call_value = (
            spot_price * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
            - strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        )

        return max(call_value, 0)  # Price cannot be negative

    @classmethod
    def put_price(
        cls,
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """Calculate European put option price.

        Args:
            spot_price: Current price of underlying
            strike: Strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate (annual)
            volatility: Implied volatility (annual)
            dividend_yield: Dividend yield (annual)

        Returns:
            Put option price
        """
        if time_to_expiry <= 0:
            # At expiration
            return max(strike - spot_price, 0)

        d1, d2 = cls.calculate_d1_d2(
            spot_price, strike, time_to_expiry, risk_free_rate, volatility, dividend_yield
        )

        put_value = (
            strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
            - spot_price * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)
        )

        return max(put_value, 0)  # Price cannot be negative

    @staticmethod
    def calculate_time_to_expiry(current_date: date, expiry_date: date) -> float:
        """Calculate time to expiry in years.

        Args:
            current_date: Current date
            expiry_date: Option expiry date

        Returns:
            Time to expiry in years (365-day convention)
        """
        days = (expiry_date - current_date).days
        if days < 0:
            return 0.0
        return days / 365.0

    @staticmethod
    def intrinsic_value(spot_price: float, strike: float, option_type: str) -> float:
        """Calculate intrinsic value of option.

        Args:
            spot_price: Current spot price
            strike: Strike price
            option_type: 'CE' for call, 'PE' for put

        Returns:
            Intrinsic value (non-negative)
        """
        if option_type == "CE":
            return max(spot_price - strike, 0)
        elif option_type == "PE":
            return max(strike - spot_price, 0)
        else:
            raise ValueError(f"Invalid option_type: {option_type}")

    @classmethod
    def time_value(
        cls,
        option_price: float,
        spot_price: float,
        strike: float,
        option_type: str
    ) -> float:
        """Calculate time value of option.

        Args:
            option_price: Option premium
            spot_price: Current spot price
            strike: Strike price
            option_type: 'CE' for call, 'PE' for put

        Returns:
            Time value (non-negative)
        """
        intrinsic = cls.intrinsic_value(spot_price, strike, option_type)
        return max(option_price - intrinsic, 0)

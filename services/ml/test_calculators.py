"""Test script to verify feature calculators work correctly."""

import pandas as pd
import sys
sys.path.insert(0, 'app')

from app.calculators.price_calculator import PriceFeatureCalculator
from app.calculators.technical_calculator import TechnicalIndicatorCalculator
from app.calculators.volatility_calculator import VolatilityCalculator


def create_sample_data():
    """Create sample OHLC data for testing."""
    return pd.DataFrame({
        'close': [19500, 19600, 19550, 19700, 19800, 19750, 19900, 20000,
                  19950, 20100, 20050, 20200, 20150, 20300, 20250, 20400,
                  20350, 20500, 20450, 20600, 20550, 20700, 20650, 20800,
                  20750, 20900, 20850, 21000, 20950, 21100],
        'high': [19600, 19700, 19650, 19800, 19900, 19850, 20000, 20100,
                 20050, 20200, 20150, 20300, 20250, 20400, 20350, 20500,
                 20450, 20600, 20550, 20700, 20650, 20800, 20750, 20900,
                 20850, 21000, 20950, 21100, 21050, 21200],
        'low': [19400, 19500, 19450, 19600, 19700, 19650, 19800, 19900,
                19850, 20000, 19950, 20100, 20050, 20200, 20150, 20300,
                20250, 20400, 20350, 20500, 20450, 20600, 20550, 20700,
                20650, 20800, 20750, 20900, 20850, 21000],
        'volume': [1000000, 1200000, 1100000, 1300000, 1250000, 1150000,
                   1400000, 1350000, 1250000, 1450000, 1400000, 1300000,
                   1500000, 1450000, 1350000, 1550000, 1500000, 1400000,
                   1600000, 1550000, 1450000, 1650000, 1600000, 1500000,
                   1700000, 1650000, 1550000, 1750000, 1700000, 1600000]
    })


def test_price_features():
    """Test price feature calculator."""
    print("\n" + "="*60)
    print("Testing Price Feature Calculator")
    print("="*60)

    calc = PriceFeatureCalculator()
    data = create_sample_data()

    features = calc.calculate_all(data)

    print("\n✅ Price Features:")
    print(f"  Weekly Change %:     {features['weekly_change_pct']}")
    print(f"  Weekly H-L Range %:  {features['weekly_high_low_range_pct']}")
    print(f"  Volume Ratio:        {features['volume_ratio']}")


def test_technical_indicators():
    """Test technical indicator calculator."""
    print("\n" + "="*60)
    print("Testing Technical Indicator Calculator")
    print("="*60)

    calc = TechnicalIndicatorCalculator()
    data = create_sample_data()

    features = calc.calculate_all(data)

    print("\n✅ Technical Indicators:")
    print(f"  RSI (14):           {features['rsi_14']}")
    print(f"  MACD:               {features['macd']}")
    print(f"  MACD Signal:        {features['macd_signal']}")
    print(f"  Bollinger Band %:   {features['bb_width']}")


def test_volatility_features():
    """Test volatility calculator."""
    print("\n" + "="*60)
    print("Testing Volatility Calculator")
    print("="*60)

    calc = VolatilityCalculator()
    data = create_sample_data()

    features = calc.calculate_all(data)

    print("\n✅ Volatility Features:")
    print(f"  Historical Vol 10d: {features['historical_vol_10d']}%")
    print(f"  Historical Vol 20d: {features['historical_vol_20d']}%")
    print(f"  ATR (14):           {features['atr_14']}")


if __name__ == "__main__":
    print("\n🧪 Feature Calculator Test Suite")
    print("Testing with sample NIFTY-like data (30 days)")

    try:
        test_price_features()
        test_technical_indicators()
        test_volatility_features()

        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("1. Deploy the service: docker compose up ml")
        print("2. Run database migration")
        print("3. Integrate with market service")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

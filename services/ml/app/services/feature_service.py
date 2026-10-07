"""Weekly features: build them from Postgres and read them back (see app/dataset/)."""

import logging
from contextlib import contextmanager
from datetime import date
from typing import Optional

from ..dataset import store
from ..dataset.features import FEATURE_VERSION, MODEL_FEATURES
from ..db.connection import get_db_connection, return_db_connection
from ..models.features import PriceFeatures, TechnicalIndicators, VolatilityFeatures, WeeklyFeatures

logger = logging.getLogger(__name__)

SUPPORTED_SYMBOLS = ("SPX",)


@contextmanager
def _connection():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_db_connection(conn)


class FeatureService:
    """Builds every week in one pass (about a second for 2010 to today) and serves stored weeks."""

    def rebuild(self, symbol: str = "SPX") -> dict:
        with _connection() as conn:
            features, labels = store.build(conn, symbol)
            n_features, n_labels = store.save(conn, features, labels, symbol)
        complete = features.dropna(subset=list(MODEL_FEATURES))
        summary = {
            "symbol": symbol,
            "weeks": n_features,
            "weeks_with_all_features": len(complete),
            "labelled_weeks": n_labels,
            "first_anchor": features["anchor_date"].min() if n_features else None,
            "last_anchor": features["anchor_date"].max() if n_features else None,
            "feature_version": FEATURE_VERSION,
        }
        logger.info("rebuilt weekly dataset: %s", summary)
        return summary

    def get_features(self, symbol: str, day: date) -> Optional[WeeklyFeatures]:
        with _connection() as conn:
            row = store.read_week(conn, symbol, day)
        return self.to_model(row) if row else None

    def get_latest_features(self, symbol: str) -> Optional[WeeklyFeatures]:
        with _connection() as conn:
            row = store.read_latest(conn, symbol)
        return self.to_model(row) if row else None

    @staticmethod
    def to_model(row: dict) -> WeeklyFeatures:
        def pick(*names):
            return {n: row.get(n) for n in names}

        return WeeklyFeatures(
            week_start_date=row["week_start_date"],
            anchor_date=row.get("anchor_date"),
            symbol=row["symbol"],
            price_features=PriceFeatures(**pick("weekly_change_pct", "weekly_high_low_range_pct", "volume_ratio")),
            technical_indicators=TechnicalIndicators(**pick("rsi_14", "macd", "macd_signal", "bb_width")),
            volatility_features=VolatilityFeatures(**pick("historical_vol_10d", "historical_vol_20d", "atr_14",
                                                          "vix_close", "vix_change_1w", "vix_hv_spread")),
            model_features=pick(*MODEL_FEATURES),
            feature_version=row.get("feature_version"),
            created_at=row.get("created_at"),
        )

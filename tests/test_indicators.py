"""
tests/test_indicators.py — Unit tests for indicator calculations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import sys
import os

# Ensure project root is on the path when running tests from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from indicators import add_ema, add_macd, add_rsi, add_volume_ma, add_all_indicators


# ── fixtures ───────────────────────────────────────────────────────────────────

def make_df(close: list[float], volume: list[float] | None = None) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame."""
    n = len(close)
    if volume is None:
        volume = [1_000_000.0] * n
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    return pd.DataFrame(
        {
            "Open": close,
            "High": [c * 1.02 for c in close],
            "Low": [c * 0.98 for c in close],
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )


# ── EMA tests ─────────────────────────────────────────────────────────────────

class TestAddEma:
    def test_columns_added(self):
        df = make_df([100.0] * 30)
        result = add_ema(df)
        assert "EMA9" in result.columns
        assert "EMA21" in result.columns

    def test_original_not_mutated(self):
        df = make_df([100.0] * 30)
        _ = add_ema(df)
        assert "EMA9" not in df.columns

    def test_flat_price_ema_equals_price(self):
        """For a constant price series EMA must equal the price itself."""
        price = 150.0
        df = make_df([price] * 50)
        result = add_ema(df)
        assert result["EMA9"].iloc[-1] == pytest.approx(price, rel=1e-6)
        assert result["EMA21"].iloc[-1] == pytest.approx(price, rel=1e-6)

    def test_ema9_faster_than_ema21_on_rising_series(self):
        """On a steadily rising series EMA9 should be above EMA21."""
        prices = list(range(1, 60))
        df = make_df(prices)
        result = add_ema(df)
        # After enough bars the fast EMA should be above the slow EMA.
        assert result["EMA9"].iloc[-1] > result["EMA21"].iloc[-1]

    def test_custom_windows(self):
        df = make_df([100.0] * 40)
        result = add_ema(df, fast=5, slow=15)
        assert "EMA5" in result.columns
        assert "EMA15" in result.columns


# ── MACD tests ────────────────────────────────────────────────────────────────

class TestAddMacd:
    def test_columns_added(self):
        df = make_df([100.0] * 50)
        result = add_macd(df)
        assert "MACD_line" in result.columns
        assert "MACD_signal" in result.columns
        assert "MACD_hist" in result.columns

    def test_histogram_equals_line_minus_signal(self):
        df = make_df(list(range(100, 160)))
        result = add_macd(df)
        diff = result["MACD_line"] - result["MACD_signal"] - result["MACD_hist"]
        assert diff.abs().max() < 1e-10

    def test_flat_series_macd_near_zero(self):
        df = make_df([200.0] * 60)
        result = add_macd(df)
        assert result["MACD_line"].iloc[-1] == pytest.approx(0.0, abs=1e-8)
        assert result["MACD_hist"].iloc[-1] == pytest.approx(0.0, abs=1e-8)


# ── RSI tests ─────────────────────────────────────────────────────────────────

class TestAddRsi:
    def test_column_added(self):
        df = make_df([100.0] * 30)
        result = add_rsi(df)
        assert "RSI" in result.columns

    def test_rsi_bounds(self):
        """RSI must always be in [0, 100]."""
        prices = [100 + 10 * np.sin(i * 0.3) for i in range(100)]
        df = make_df(prices)
        result = add_rsi(df)
        valid = result["RSI"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_high_for_rising_series(self):
        """Strongly rising series (with minor pullbacks) → RSI well above 50."""
        # Use a mostly rising series with small alternating dips so avg_loss > 0.
        base = [50.0 + i * 2 for i in range(60)]
        prices = [v + (5 if i % 3 != 0 else -2) for i, v in enumerate(base)]
        df = make_df(prices)
        result = add_rsi(df)
        valid = result["RSI"].dropna()
        assert len(valid) > 0
        assert valid.iloc[-1] > 50.0

    def test_rsi_low_for_falling_series(self):
        """Strongly falling series → RSI closer to 0 than 50."""
        prices = [float(i) for i in range(110, 50, -1)]
        df = make_df(prices)
        result = add_rsi(df)
        assert result["RSI"].iloc[-1] < 50.0


# ── Volume MA tests ───────────────────────────────────────────────────────────

class TestAddVolumeMA:
    def test_column_added(self):
        df = make_df([100.0] * 30)
        result = add_volume_ma(df)
        assert "Volume_MA" in result.columns

    def test_volume_ma_value(self):
        """For constant volume, the MA should equal the volume."""
        vol = 5_000_000.0
        df = make_df([100.0] * 30, volume=[vol] * 30)
        result = add_volume_ma(df, period=20)
        assert result["Volume_MA"].iloc[-1] == pytest.approx(vol, rel=1e-9)

    def test_first_bar_has_value(self):
        """min_periods=1 means the first bar always has a defined MA."""
        df = make_df([100.0] * 5)
        result = add_volume_ma(df, period=20)
        assert not np.isnan(result["Volume_MA"].iloc[0])


# ── add_all_indicators ────────────────────────────────────────────────────────

class TestAddAllIndicators:
    def test_all_columns_present(self):
        df = make_df(list(range(50, 110)))
        result = add_all_indicators(df)
        expected = {"EMA9", "EMA21", "MACD_line", "MACD_signal", "MACD_hist", "RSI", "Volume_MA"}
        assert expected.issubset(set(result.columns))

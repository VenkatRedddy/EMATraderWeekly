"""
tests/test_screener.py — Unit tests for the TradingView-style screener filters.

These tests mock external network calls so they run offline without hitting
Yahoo Finance.
"""

from __future__ import annotations

import math
import sys
import os
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from indicators import add_adr
from screener import _screen_ticker, run_screener


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_daily_df(
    n: int = 80,
    base_price: float = 50.0,
    step: float = 1.0,
    volume: float = 1_000_000.0,
    high_mult: float = 1.03,
    low_mult: float = 0.97,
) -> pd.DataFrame:
    """Build a synthetic daily OHLCV DataFrame.

    *step* is the price increment per bar.  Use ``step=1.0`` (default) to
    produce a ~0.78 % daily gain — comfortably above the 0.5 % screener
    threshold.  Use ``step=0.0`` to produce a flat (0 % change) series.
    """
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    close = [base_price + i * step for i in range(n)]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [c * high_mult for c in close],
            "Low": [c * low_mult for c in close],
            "Close": close,
            "Volume": [volume] * n,
        },
        index=dates,
    )


def _make_weekly_df(n: int = 40, base_price: float = 50.0) -> pd.DataFrame:
    """Build a synthetic weekly OHLCV DataFrame."""
    dates = pd.date_range("2022-01-03", periods=n, freq="W-MON")
    close = [base_price + i * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [c * 1.02 for c in close],
            "Low":  [c * 0.98 for c in close],
            "Close": close,
            "Volume": [2_000_000.0] * n,
        },
        index=dates,
    )


_GOOD_FUNDAMENTALS = {
    "market_cap": 500_000_000.0,   # 500 M — passes ≥300 M
    "analyst_rating": "buy",
    "previous_close": 49.5,
}

_LOW_MKTCAP_FUNDAMENTALS = {
    "market_cap": 100_000_000.0,   # 100 M — fails ≥300 M
    "analyst_rating": "buy",
    "previous_close": 49.5,
}

_SELL_RATING_FUNDAMENTALS = {
    "market_cap": 500_000_000.0,
    "analyst_rating": "sell",     # not in allowed list
    "previous_close": 49.5,
}

_MISSING_RATING_FUNDAMENTALS = {
    "market_cap": 500_000_000.0,
    "analyst_rating": None,        # missing data
    "previous_close": 49.5,
}


# ── ADR indicator tests ───────────────────────────────────────────────────────

class TestAddAdr:
    def test_column_added(self):
        df = _make_daily_df()
        result = add_adr(df, period=14)
        assert "ADR_pct" in result.columns

    def test_original_not_mutated(self):
        df = _make_daily_df()
        _ = add_adr(df, period=14)
        assert "ADR_pct" not in df.columns

    def test_adr_value_positive(self):
        df = _make_daily_df(high_mult=1.03, low_mult=0.97)
        result = add_adr(df, period=14)
        assert (result["ADR_pct"].dropna() > 0).all()

    def test_flat_high_low_gives_zero_adr(self):
        df = _make_daily_df()
        df["High"] = df["Close"]
        df["Low"] = df["Close"]
        result = add_adr(df, period=14)
        assert result["ADR_pct"].iloc[-1] == pytest.approx(0.0, abs=1e-6)

    def test_adr_calculation(self):
        """Manual verification: for a single bar with H=110, L=90, C=100 → range%=20."""
        dates = pd.date_range("2024-01-01", periods=1, freq="B")
        df = pd.DataFrame(
            {"Open": [100.0], "High": [110.0], "Low": [90.0], "Close": [100.0], "Volume": [1e6]},
            index=dates,
        )
        result = add_adr(df, period=1)
        assert result["ADR_pct"].iloc[0] == pytest.approx(20.0, rel=1e-6)


# ── _screen_ticker tests ──────────────────────────────────────────────────────

class TestScreenTicker:
    """Tests for the per-ticker screener function using mocked data fetchers."""

    def _run(self, daily_df, fundamentals, weekly_df=None):
        """Helper: patch data fetchers and run _screen_ticker for 'TEST'."""
        if weekly_df is None:
            weekly_df = _make_weekly_df()
        with (
            patch("screener.fetch_daily_data", return_value=daily_df),
            patch("screener.fetch_fundamentals", return_value=fundamentals),
            patch("screener.fetch_weekly_data", return_value=weekly_df),
        ):
            return _screen_ticker("TEST")

    # -- passing case --

    def test_all_filters_pass(self):
        """A stock meeting every criterion should pass the screener."""
        # ADR ≈6% (High=1.03×Close, Low=0.97×Close), volume=1M (>500K),
        # price≈57.9 (>3), rising so change%>0, EMA21/50 < price (rising series).
        daily = _make_daily_df(n=80, base_price=50.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is True

    def test_weekly_signal_populated_for_passing_stock(self):
        daily = _make_daily_df(n=80, base_price=50.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["weekly_signal"] in {"GOLDEN_CROSS", "DEATH_CROSS", "HOLD"}

    # -- price filter --

    def test_fails_low_price(self):
        """Close price below SCREENER_MIN_PRICE should fail."""
        # Constant price of $1.50 — always below the $3 threshold.
        daily = _make_daily_df(n=80, base_price=1.5, step=0.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_price"] is False

    # -- price change filter --

    def test_fails_flat_price_change(self):
        """A flat series has 0% change, which should fail >0.5% filter."""
        daily = _make_daily_df(n=80, base_price=50.0, step=0.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_change"] is False

    # -- market cap filter --

    def test_fails_low_market_cap(self):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        row = self._run(daily, _LOW_MKTCAP_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_market_cap"] is False

    # -- analyst rating filter --

    def test_fails_sell_rating(self):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        row = self._run(daily, _SELL_RATING_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_analyst"] is False

    def test_passes_with_missing_analyst_data(self):
        """Missing analyst data → filter skipped (not a hard fail)."""
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        row = self._run(daily, _MISSING_RATING_FUNDAMENTALS)
        # Should still pass (analyst filter is soft when data is absent)
        assert row["f_analyst"] is None
        assert row["pass_screener"] is True

    # -- EMA filters --

    def test_fails_when_ema50_above_price(self):
        """A falling price series causes EMA50 > price → should fail."""
        # Descending series: EMA50 will be above the latest (falling) close.
        n = 80
        dates = pd.date_range("2024-01-02", periods=n, freq="B")
        close = [100.0 - i * 0.5 for i in range(n)]
        daily = pd.DataFrame(
            {
                "Open": close,
                "High": [c * 1.03 for c in close],
                "Low": [c * 0.97 for c in close],
                "Close": close,
                "Volume": [1_000_000.0] * n,
            },
            index=dates,
        )
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        # EMA50 should be above price on a falling series.
        assert row["f_ema50"] is False or row["f_ema21"] is False

    # -- volume filter --

    def test_fails_low_volume(self):
        """10-day avg volume below 500K should fail."""
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=100_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_volume"] is False

    # -- ADR filter --

    def test_fails_low_adr(self):
        """ADR of ~0.2% (High/Low very close to Close) should fail ≥2% threshold."""
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        daily["High"] = daily["Close"] * 1.001
        daily["Low"] = daily["Close"] * 0.999
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_adr"] is False

    # -- empty data --

    def test_empty_daily_data_returns_no_pass(self):
        with (
            patch("screener.fetch_daily_data", return_value=pd.DataFrame()),
            patch("screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
        ):
            row = _screen_ticker("TEST")
        assert row["pass_screener"] is False


# ── run_screener integration test ─────────────────────────────────────────────

class TestRunScreener:
    """Smoke-test run_screener with mocked fetchers."""

    def test_returns_dataframe(self, tmp_path):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        weekly = _make_weekly_df()
        out_csv = str(tmp_path / "results.csv")
        with (
            patch("screener.fetch_daily_data", return_value=daily),
            patch("screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
            patch("screener.fetch_weekly_data", return_value=weekly),
        ):
            result = run_screener(tickers=["FAKE1", "FAKE2"], output_csv=out_csv)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_csv_written(self, tmp_path):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        weekly = _make_weekly_df()
        out_csv = str(tmp_path / "results.csv")
        with (
            patch("screener.fetch_daily_data", return_value=daily),
            patch("screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
            patch("screener.fetch_weekly_data", return_value=weekly),
        ):
            run_screener(tickers=["FAKE1"], output_csv=out_csv)
        assert os.path.exists(out_csv)
        df = pd.read_csv(out_csv)
        assert len(df) == 1
        assert "ticker" in df.columns
        assert "weekly_signal" in df.columns

    def test_sorted_by_volume_desc(self, tmp_path):
        """Passing tickers should be sorted highest volume first."""
        daily_hi = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=5_000_000.0)
        daily_lo = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        weekly = _make_weekly_df()
        out_csv = str(tmp_path / "results.csv")

        tickers_order = ["HI_VOL", "LO_VOL"]

        def _mock_daily(ticker, **kwargs):
            return daily_hi if ticker == "HI_VOL" else daily_lo

        with (
            patch("screener.fetch_daily_data", side_effect=_mock_daily),
            patch("screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
            patch("screener.fetch_weekly_data", return_value=weekly),
        ):
            result = run_screener(tickers=tickers_order, output_csv=out_csv)

        passing = result[result["pass_screener"]]
        if len(passing) >= 2:
            vols = passing["avg_volume_10d"].tolist()
            assert vols == sorted(vols, reverse=True)

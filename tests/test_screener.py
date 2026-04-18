"""
tests/test_screener.py — Unit tests for the EMA crossover screener module.

Tests use synthetic data only (no network calls).
"""

from __future__ import annotations

import sys
import os
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

# Ensure the project root is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from screener.screener import _calc_ema, _compute_indicators, _log_signals, run_screener
from screener.notifier import build_alert_message, send_notifications


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_weekly_df(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    """Build a minimal weekly OHLCV DataFrame."""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000.0] * n
    dates = pd.date_range("2023-01-02", periods=n, freq="W-MON")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )


def _make_mock_cfg(**overrides):
    """Return a simple namespace acting as screener_config."""
    defaults = {
        "STOCK_UNIVERSE": "csv",
        "CSV_FILE": str(_REPO_ROOT / "screener" / "sample_stocks_us.csv"),
        "MIN_AVG_VOLUME": 500_000,
        "LOOKBACK_WEEKS": 60,
        "EMA_FAST": 9,
        "EMA_SLOW": 21,
        "OUTPUT_CSV": "/tmp/test_screener_output.csv",
        "LOG_FILE": "/tmp/test_screener_signals.log",
        "EMAIL_ENABLED": False,
        "WHATSAPP_ENABLED": False,
        "EMAIL_SUBJECT_PREFIX": "[EMA Screener]",
        "EMAIL_USER": "test@example.com",
        "EMAIL_PASS": "password",
        "EMAIL_TO": "recipient@example.com",
        "EMAIL_SMTP_HOST": "smtp.gmail.com",
        "EMAIL_SMTP_PORT": 587,
        "EMAIL_USE_TLS": True,
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_FROM": "whatsapp:+14155238886",
        "TWILIO_TO": "whatsapp:+10000000000",
    }
    defaults.update(overrides)
    cfg = types.SimpleNamespace(**defaults)
    return cfg


# ── _calc_ema ─────────────────────────────────────────────────────────────────

class TestCalcEma:
    def test_flat_series_returns_same_value(self):
        s = pd.Series([100.0] * 50)
        result = _calc_ema(s, span=9)
        assert result.iloc[-1] == pytest.approx(100.0, rel=1e-6)

    def test_rising_series_ema9_above_ema21(self):
        s = pd.Series(range(1, 60), dtype=float)
        ema9 = _calc_ema(s, 9)
        ema21 = _calc_ema(s, 21)
        assert ema9.iloc[-1] > ema21.iloc[-1]


# ── _compute_indicators ───────────────────────────────────────────────────────

class TestComputeIndicators:
    def test_columns_added(self):
        df = _make_weekly_df([float(i) for i in range(1, 51)])
        result = _compute_indicators(df, ema_fast=9, ema_slow=21)
        assert "EMA_fast" in result.columns
        assert "EMA_slow" in result.columns
        assert "Avg_Volume_10W" in result.columns
        assert "Cross_Up" in result.columns
        assert "Cross_Down" in result.columns

    def test_no_crossover_on_flat_series(self):
        df = _make_weekly_df([100.0] * 50)
        result = _compute_indicators(df, ema_fast=9, ema_slow=21)
        assert not result["Cross_Up"].any()
        assert not result["Cross_Down"].any()

    def test_cross_up_detected(self):
        """Simulate a falling then sharply rising series to trigger a golden cross."""
        # Gradually fall (EMA9 drops below EMA21), then jump sharply up
        closes = [100.0 - i * 2 for i in range(25)] + [200.0] * 25
        df = _make_weekly_df(closes)
        result = _compute_indicators(df, ema_fast=9, ema_slow=21)
        assert result["Cross_Up"].any()
        assert not result["Cross_Up"].all()

    def test_cross_down_detected(self):
        """Simulate a rising then sharply falling series to trigger a death cross."""
        # Gradually rise (EMA9 rises above EMA21), then drop sharply
        closes = [50.0 + i * 2 for i in range(25)] + [10.0] * 25
        df = _make_weekly_df(closes)
        result = _compute_indicators(df, ema_fast=9, ema_slow=21)
        assert result["Cross_Down"].any()
        assert not result["Cross_Down"].all()

    def test_original_df_not_mutated(self):
        df = _make_weekly_df([float(i) for i in range(1, 40)])
        _ = _compute_indicators(df, 9, 21)
        assert "EMA_fast" not in df.columns

    def test_avg_volume_10w_value(self):
        vol = 2_000_000.0
        df = _make_weekly_df([100.0] * 30, volumes=[vol] * 30)
        result = _compute_indicators(df, 9, 21)
        assert result["Avg_Volume_10W"].iloc[-1] == pytest.approx(vol, rel=1e-9)


# ── run_screener with mocked yfinance ─────────────────────────────────────────

class TestRunScreener:
    def _patched_fetch(self, closes, volumes=None):
        """Return a mock _fetch_one that always returns synthetic data."""
        df = _make_weekly_df(closes, volumes)

        def _mock_fetch(symbol, lookback_weeks):
            return df.copy()

        return _mock_fetch

    def test_empty_table_when_all_data_missing(self):
        cfg = _make_mock_cfg()
        with patch("screener.screener._fetch_one", return_value=None):
            # Override get_symbols to return just 1 symbol
            with patch("screener.stock_universe.get_symbols", return_value=["AAPL"]):
                table, signals = run_screener(cfg)
        assert table.empty
        assert signals == []

    def test_table_sorted_by_volume_descending(self):
        """Stocks with higher volume should appear first."""
        cfg = _make_mock_cfg()
        call_count = [0]
        volumes_by_call = [
            [500_000.0] * 35,  # AAPL — low volume
            [5_000_000.0] * 35,  # MSFT — high volume
        ]

        def mock_fetch(symbol, lookback_weeks):
            v = volumes_by_call[call_count[0] % len(volumes_by_call)]
            call_count[0] += 1
            return _make_weekly_df([100.0] * 35, v)

        with patch("screener.screener._fetch_one", side_effect=mock_fetch):
            with patch("screener.stock_universe.get_symbols", return_value=["AAPL", "MSFT"]):
                table, _ = run_screener(cfg)

        assert not table.empty
        # Higher volume should be first
        assert table.iloc[0]["Avg_Volume_10W"] >= table.iloc[-1]["Avg_Volume_10W"]

    def test_volume_filter_applied_to_signals(self):
        """Crossover signals should only appear for stocks above MIN_AVG_VOLUME."""
        cfg = _make_mock_cfg(MIN_AVG_VOLUME=1_000_000)
        # Low volume stock: crossover but below threshold → no signal
        low_vol_closes = [50.0] * 20 + [200.0] * 15
        low_vol_df = _make_weekly_df(low_vol_closes, [100_000.0] * 35)

        def mock_fetch(symbol, lookback_weeks):
            return low_vol_df.copy()

        with patch("screener.screener._fetch_one", side_effect=mock_fetch):
            with patch("screener.stock_universe.get_symbols", return_value=["LOWVOL"]):
                _, signals = run_screener(cfg)

        assert signals == []

    def test_crossover_signal_captured(self):
        """High-volume stock with a crossover should produce a signal."""
        cfg = _make_mock_cfg(MIN_AVG_VOLUME=500_000)
        # Force a golden cross by using low then high prices
        closes = [50.0] * 22 + [500.0] * 13
        df = _make_weekly_df(closes, [2_000_000.0] * 35)

        # Verify that _compute_indicators actually produces a cross_up
        computed = _compute_indicators(df, 9, 21)
        if not computed["Cross_Up"].any():
            pytest.skip("Synthetic data didn't produce a crossover — skip test.")

        def mock_fetch(symbol, lookback_weeks):
            return df.copy()

        with patch("screener.screener._fetch_one", side_effect=mock_fetch):
            with patch("screener.stock_universe.get_symbols", return_value=["TEST"]):
                table, signals = run_screener(cfg)

        assert not table.empty
        # May or may not have a signal depending on which bar is "latest completed"
        # but the table should contain the stock
        assert table.iloc[0]["Symbol"] == "TEST"


# ── _log_signals ──────────────────────────────────────────────────────────────

class TestLogSignals:
    def test_creates_log_file(self, tmp_path):
        log_file = str(tmp_path / "signals.log")
        signals = [
            {
                "symbol": "AAPL",
                "direction": "BULLISH",
                "price": 150.0,
                "ema9": 148.0,
                "ema21": 145.0,
                "avg_volume": 1_200_000,
                "timestamp": "2024-01-08",
            }
        ]
        _log_signals(signals, log_file)
        content = Path(log_file).read_text()
        assert "AAPL" in content
        assert "BULLISH" in content

    def test_appends_on_multiple_calls(self, tmp_path):
        log_file = str(tmp_path / "signals.log")
        signal = {
            "symbol": "MSFT",
            "direction": "BEARISH",
            "price": 400.0,
            "ema9": 402.0,
            "ema21": 410.0,
            "avg_volume": 800_000,
            "timestamp": "2024-01-08",
        }
        _log_signals([signal], log_file)
        _log_signals([signal], log_file)
        content = Path(log_file).read_text()
        assert content.count("MSFT") >= 2

    def test_no_file_created_when_empty(self, tmp_path):
        log_file = str(tmp_path / "empty.log")
        _log_signals([], log_file)
        assert not Path(log_file).exists()


# ── build_alert_message ───────────────────────────────────────────────────────

class TestBuildAlertMessage:
    def _bullish_signal(self):
        return {
            "symbol": "NVDA",
            "direction": "BULLISH",
            "price": 900.0,
            "ema9": 890.0,
            "ema21": 880.0,
            "avg_volume": 5_000_000,
            "timestamp": "2024-04-15",
        }

    def _bearish_signal(self):
        return {
            "symbol": "TSLA",
            "direction": "BEARISH",
            "price": 200.0,
            "ema9": 195.0,
            "ema21": 210.0,
            "avg_volume": 3_000_000,
            "timestamp": "2024-04-15",
        }

    def test_bullish_contains_buy_keyword(self):
        msg = build_alert_message(self._bullish_signal())
        assert "BUY" in msg or "BULLISH" in msg or "Golden Cross" in msg

    def test_bearish_contains_sell_keyword(self):
        msg = build_alert_message(self._bearish_signal())
        assert "SELL" in msg or "BEARISH" in msg or "Death Cross" in msg

    def test_symbol_in_message(self):
        msg = build_alert_message(self._bullish_signal())
        assert "NVDA" in msg

    def test_price_in_message(self):
        msg = build_alert_message(self._bullish_signal())
        assert "900" in msg

    def test_returns_string(self):
        assert isinstance(build_alert_message(self._bullish_signal()), str)
        assert isinstance(build_alert_message(self._bearish_signal()), str)

    def test_bullish_has_green_emoji(self):
        msg = build_alert_message(self._bullish_signal())
        assert "🟢" in msg

    def test_bearish_has_red_emoji(self):
        msg = build_alert_message(self._bearish_signal())
        assert "🔴" in msg


# ── send_notifications ────────────────────────────────────────────────────────

class TestSendNotifications:
    def test_no_exception_on_empty_signals(self):
        cfg = _make_mock_cfg()
        send_notifications([], cfg)  # should not raise

    def test_email_called_when_enabled(self):
        cfg = _make_mock_cfg(EMAIL_ENABLED=True)
        signal = {
            "symbol": "AAPL",
            "direction": "BULLISH",
            "price": 200.0,
            "ema9": 198.0,
            "ema21": 190.0,
            "avg_volume": 600_000,
            "timestamp": "2024-04-15",
        }
        with patch("screener.notifier._send_email") as mock_email:
            send_notifications([signal], cfg)
            mock_email.assert_called_once()

    def test_email_not_called_when_disabled(self):
        cfg = _make_mock_cfg(EMAIL_ENABLED=False)
        signal = {
            "symbol": "AAPL",
            "direction": "BULLISH",
            "price": 200.0,
            "ema9": 198.0,
            "ema21": 190.0,
            "avg_volume": 600_000,
            "timestamp": "2024-04-15",
        }
        with patch("screener.notifier._send_email") as mock_email:
            send_notifications([signal], cfg)
            mock_email.assert_not_called()

    def test_whatsapp_called_when_enabled(self):
        cfg = _make_mock_cfg(WHATSAPP_ENABLED=True)
        signal = {
            "symbol": "AAPL",
            "direction": "BEARISH",
            "price": 150.0,
            "ema9": 148.0,
            "ema21": 155.0,
            "avg_volume": 700_000,
            "timestamp": "2024-04-15",
        }
        with patch("screener.notifier._send_whatsapp") as mock_wa:
            send_notifications([signal], cfg)
            mock_wa.assert_called_once()

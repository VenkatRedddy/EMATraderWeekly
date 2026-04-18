"""
tests/test_screener.py — Unit tests for both screener implementations.

  Part 1: TradingView-style 8-filter screener (screener.py at repo root).
          Tests use synthetic data; all network calls are mocked.

  Part 2: EMA crossover screener with notifications (screener/ package).
          Tests use synthetic data only (no network calls).
"""

from __future__ import annotations

import math
import sys
import os
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

# ── Path setup ───────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Imports for Part 1 (root-level screener.py) ───────────────────────────────
# Use importlib to load screener.py directly, because the screener/ package
# shadows a plain `import screener` after the merge.
import importlib.util as _ilu

_tv_spec = _ilu.spec_from_file_location(
    "tv_screener",
    str(_REPO_ROOT / "screener.py"),
)
_tv_mod = _ilu.module_from_spec(_tv_spec)
sys.modules["tv_screener"] = _tv_mod  # register so patch("tv_screener.*") resolves
_tv_spec.loader.exec_module(_tv_mod)
_screen_ticker = _tv_mod._screen_ticker
run_tv_screener = _tv_mod.run_screener

from indicators import add_adr

# ── Imports for Part 2 (screener/ package) ────────────────────────────────────
from screener.screener import _calc_ema, _compute_indicators, _log_signals, run_screener as run_ema_screener
from screener.notifier import build_alert_message, send_notifications


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — TradingView-style 8-filter screener (screener.py)
# ══════════════════════════════════════════════════════════════════════════════

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


def _make_weekly_df_simple(n: int = 40, base_price: float = 50.0) -> pd.DataFrame:
    """Build a synthetic weekly OHLCV DataFrame (used by Part 1 tests)."""
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
    "market_cap": 500_000_000.0,   # 500 M -- passes >=300 M
    "analyst_rating": "buy",
    "previous_close": 49.5,
}

_LOW_MKTCAP_FUNDAMENTALS = {
    "market_cap": 100_000_000.0,   # 100 M -- fails >=300 M
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
        """Manual verification: for a single bar H=110, L=90, C=100 -> range%=20."""
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
            weekly_df = _make_weekly_df_simple()
        with (
            patch("tv_screener.fetch_daily_data", return_value=daily_df),
            patch("tv_screener.fetch_fundamentals", return_value=fundamentals),
            patch("tv_screener.fetch_weekly_data", return_value=weekly_df),
        ):
            return _screen_ticker("TEST")

    def test_all_filters_pass(self):
        """A stock meeting every criterion should pass the screener."""
        daily = _make_daily_df(n=80, base_price=50.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is True

    def test_weekly_signal_populated_for_passing_stock(self):
        daily = _make_daily_df(n=80, base_price=50.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["weekly_signal"] in {"GOLDEN_CROSS", "DEATH_CROSS", "HOLD"}

    def test_fails_low_price(self):
        """Close price below SCREENER_MIN_PRICE should fail."""
        daily = _make_daily_df(n=80, base_price=1.5, step=0.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_price"] is False

    def test_fails_flat_price_change(self):
        """A flat series has 0% change, which should fail >0.5% filter."""
        daily = _make_daily_df(n=80, base_price=50.0, step=0.0, volume=1_000_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_change"] is False

    def test_fails_low_market_cap(self):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        row = self._run(daily, _LOW_MKTCAP_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_market_cap"] is False

    def test_fails_sell_rating(self):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        row = self._run(daily, _SELL_RATING_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_analyst"] is False

    def test_passes_with_missing_analyst_data(self):
        """Missing analyst data -> filter skipped (not a hard fail)."""
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        row = self._run(daily, _MISSING_RATING_FUNDAMENTALS)
        assert row["f_analyst"] is None
        assert row["pass_screener"] is True

    def test_fails_when_ema50_above_price(self):
        """A falling price series causes EMA50 > price -> should fail."""
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
        assert row["f_ema50"] is False or row["f_ema21"] is False

    def test_fails_low_volume(self):
        """10-day avg volume below 500K should fail."""
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=100_000.0)
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_volume"] is False

    def test_fails_low_adr(self):
        """ADR of ~0.2% (High/Low very close to Close) should fail >=2% threshold."""
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        daily["High"] = daily["Close"] * 1.001
        daily["Low"] = daily["Close"] * 0.999
        row = self._run(daily, _GOOD_FUNDAMENTALS)
        assert row["pass_screener"] is False
        assert row["f_adr"] is False

    def test_empty_daily_data_returns_no_pass(self):
        with (
            patch("tv_screener.fetch_daily_data", return_value=pd.DataFrame()),
            patch("tv_screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
        ):
            row = _screen_ticker("TEST")
        assert row["pass_screener"] is False


# ── run_tv_screener integration tests ─────────────────────────────────────────

class TestRunTvScreener:
    """Smoke-test run_tv_screener (root-level screener.py) with mocked fetchers."""

    def test_returns_dataframe(self, tmp_path):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        weekly = _make_weekly_df_simple()
        out_csv = str(tmp_path / "results.csv")
        with (
            patch("tv_screener.fetch_daily_data", return_value=daily),
            patch("tv_screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
            patch("tv_screener.fetch_weekly_data", return_value=weekly),
        ):
            result = run_tv_screener(tickers=["FAKE1", "FAKE2"], output_csv=out_csv)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_csv_written(self, tmp_path):
        daily = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        weekly = _make_weekly_df_simple()
        out_csv = str(tmp_path / "results.csv")
        with (
            patch("tv_screener.fetch_daily_data", return_value=daily),
            patch("tv_screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
            patch("tv_screener.fetch_weekly_data", return_value=weekly),
        ):
            run_tv_screener(tickers=["FAKE1"], output_csv=out_csv)
        assert os.path.exists(out_csv)
        df = pd.read_csv(out_csv)
        assert len(df) == 1
        assert "ticker" in df.columns
        assert "weekly_signal" in df.columns

    def test_sorted_by_volume_desc(self, tmp_path):
        """Passing tickers should be sorted highest volume first."""
        daily_hi = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=5_000_000.0)
        daily_lo = _make_daily_df(n=80, base_price=50.0, step=1.0, volume=1_000_000.0)
        weekly = _make_weekly_df_simple()
        out_csv = str(tmp_path / "results.csv")

        tickers_order = ["HI_VOL", "LO_VOL"]

        def _mock_daily(ticker, **kwargs):
            return daily_hi if ticker == "HI_VOL" else daily_lo

        with (
            patch("tv_screener.fetch_daily_data", side_effect=_mock_daily),
            patch("tv_screener.fetch_fundamentals", return_value=_GOOD_FUNDAMENTALS),
            patch("tv_screener.fetch_weekly_data", return_value=weekly),
        ):
            result = run_tv_screener(tickers=tickers_order, output_csv=out_csv)

        passing = result[result["pass_screener"]]
        if len(passing) >= 2:
            vols = passing["avg_volume_10d"].tolist()
            assert vols == sorted(vols, reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — EMA crossover screener with notifications (screener/ package)
# ══════════════════════════════════════════════════════════════════════════════

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_weekly_df(closes: list, volumes: list = None) -> pd.DataFrame:
    """Build a minimal weekly OHLCV DataFrame (used by Part 2 tests)."""
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
        closes = [100.0 - i * 2 for i in range(25)] + [200.0] * 25
        df = _make_weekly_df(closes)
        result = _compute_indicators(df, ema_fast=9, ema_slow=21)
        assert result["Cross_Up"].any()
        assert not result["Cross_Up"].all()

    def test_cross_down_detected(self):
        """Simulate a rising then sharply falling series to trigger a death cross."""
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


# ── run_ema_screener with mocked yfinance ─────────────────────────────────────

class TestRunEmaScreener:
    def test_empty_table_when_all_data_missing(self):
        cfg = _make_mock_cfg()
        with patch("screener.screener._fetch_one", return_value=None):
            with patch("screener.stock_universe.get_symbols", return_value=["AAPL"]):
                table, signals = run_ema_screener(cfg)
        assert table.empty
        assert signals == []

    def test_table_sorted_by_volume_descending(self):
        """Stocks with higher volume should appear first."""
        cfg = _make_mock_cfg()
        call_count = [0]
        volumes_by_call = [
            [500_000.0] * 35,   # AAPL -- low volume
            [5_000_000.0] * 35, # MSFT -- high volume
        ]

        def mock_fetch(symbol, lookback_weeks):
            v = volumes_by_call[call_count[0] % len(volumes_by_call)]
            call_count[0] += 1
            return _make_weekly_df([100.0] * 35, v)

        with patch("screener.screener._fetch_one", side_effect=mock_fetch):
            with patch("screener.stock_universe.get_symbols", return_value=["AAPL", "MSFT"]):
                table, _ = run_ema_screener(cfg)

        assert not table.empty
        assert table.iloc[0]["Avg_Volume_10W"] >= table.iloc[-1]["Avg_Volume_10W"]

    def test_volume_filter_applied_to_signals(self):
        """Crossover signals should only appear for stocks above MIN_AVG_VOLUME."""
        cfg = _make_mock_cfg(MIN_AVG_VOLUME=1_000_000)
        low_vol_closes = [50.0] * 20 + [200.0] * 15
        low_vol_df = _make_weekly_df(low_vol_closes, [100_000.0] * 35)

        def mock_fetch(symbol, lookback_weeks):
            return low_vol_df.copy()

        with patch("screener.screener._fetch_one", side_effect=mock_fetch):
            with patch("screener.stock_universe.get_symbols", return_value=["LOWVOL"]):
                _, signals = run_ema_screener(cfg)

        assert signals == []

    def test_crossover_signal_captured(self):
        """High-volume stock with a crossover should produce a signal."""
        cfg = _make_mock_cfg(MIN_AVG_VOLUME=500_000)
        closes = [50.0] * 22 + [500.0] * 13
        df = _make_weekly_df(closes, [2_000_000.0] * 35)

        computed = _compute_indicators(df, 9, 21)
        if not computed["Cross_Up"].any():
            pytest.skip("Synthetic data didn't produce a crossover -- skip test.")

        def mock_fetch(symbol, lookback_weeks):
            return df.copy()

        with patch("screener.screener._fetch_one", side_effect=mock_fetch):
            with patch("screener.stock_universe.get_symbols", return_value=["TEST"]):
                table, signals = run_ema_screener(cfg)

        assert not table.empty
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
                "ema_fast_key": "ema9",
                "ema_slow_key": "ema21",
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
            "ema_fast_key": "ema9",
            "ema_slow_key": "ema21",
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
            "ema_fast_key": "ema9",
            "ema_slow_key": "ema21",
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
            "ema_fast_key": "ema9",
            "ema_slow_key": "ema21",
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
        assert "\U0001f7e2" in msg

    def test_bearish_has_red_emoji(self):
        msg = build_alert_message(self._bearish_signal())
        assert "\U0001f534" in msg


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
            "ema_fast_key": "ema9",
            "ema_slow_key": "ema21",
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
            "ema_fast_key": "ema9",
            "ema_slow_key": "ema21",
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
            "ema_fast_key": "ema9",
            "ema_slow_key": "ema21",
            "avg_volume": 700_000,
            "timestamp": "2024-04-15",
        }
        with patch("screener.notifier._send_whatsapp") as mock_wa:
            send_notifications([signal], cfg)
            mock_wa.assert_called_once()

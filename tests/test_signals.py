"""
tests/test_signals.py — Unit tests for signal generation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from indicators import add_all_indicators
from signals import generate_signals


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_base_df(n: int = 60) -> pd.DataFrame:
    """Return a minimal DataFrame with all indicator columns pre-filled."""
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    close = [float(100 + i) for i in range(n)]
    df = pd.DataFrame(
        {
            "Open": close,
            "High": [c * 1.02 for c in close],
            "Low":  [c * 0.98 for c in close],
            "Close": close,
            "Volume": [2_000_000.0] * n,
        },
        index=dates,
    )
    return add_all_indicators(df)


def _inject_golden_cross(df: pd.DataFrame, idx: int) -> pd.DataFrame:
    """
    Manually inject a golden-cross condition at *idx* by ensuring:
      - EMA9[idx-1] <= EMA21[idx-1]
      - EMA9[idx]   >  EMA21[idx]
    """
    out = df.copy()
    slow_val = out["EMA21"].iloc[idx]
    out.iloc[idx - 1, out.columns.get_loc("EMA9")] = slow_val - 1.0  # fast < slow yesterday
    out.iloc[idx,     out.columns.get_loc("EMA9")] = slow_val + 1.0  # fast > slow today
    return out


def _inject_death_cross(df: pd.DataFrame, idx: int) -> pd.DataFrame:
    out = df.copy()
    slow_val = out["EMA21"].iloc[idx]
    out.iloc[idx - 1, out.columns.get_loc("EMA9")] = slow_val + 1.0
    out.iloc[idx,     out.columns.get_loc("EMA9")] = slow_val - 1.0
    return out


# ── test: signal column presence ─────────────────────────────────────────────

class TestSignalColumns:
    def test_columns_added(self):
        df = _make_base_df()
        result = generate_signals(df)
        assert "Signal" in result.columns
        assert "Signal_Type" in result.columns
        assert "Signal_Reason" in result.columns

    def test_signal_values_valid(self):
        df = _make_base_df()
        result = generate_signals(df)
        assert set(result["Signal"].unique()).issubset({-1, 0, 1})

    def test_original_not_mutated(self):
        df = _make_base_df()
        _ = generate_signals(df)
        assert "Signal" not in df.columns


# ── test: BUY conditions ──────────────────────────────────────────────────────

class TestBuySignal:
    def test_buy_requires_golden_cross(self):
        """Without a golden cross there should be no BUY signal."""
        df = _make_base_df()
        # Ensure EMA9 is always BELOW EMA21 (no cross possible).
        df["EMA9"] = df["EMA21"] - 2.0
        result = generate_signals(df)
        assert (result["Signal"] != 1).all()

    def test_buy_blocked_when_macd_negative(self):
        df = _make_base_df()
        idx = 40
        df = _inject_golden_cross(df, idx)
        # Force MACD histogram negative at the crossover bar.
        df.iloc[idx, df.columns.get_loc("MACD_hist")] = -0.5
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] != 1

    def test_buy_blocked_when_rsi_overbought(self):
        df = _make_base_df()
        idx = 40
        df = _inject_golden_cross(df, idx)
        df["MACD_hist"] = 1.0   # ensure MACD is positive
        df["RSI"] = 75.0        # overbought → BUY should be blocked
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] != 1

    def test_buy_blocked_when_low_volume(self):
        df = _make_base_df()
        idx = 40
        df = _inject_golden_cross(df, idx)
        df["MACD_hist"] = 1.0
        df["RSI"] = 50.0
        # Set volume below Volume_MA at the signal bar.
        df.iloc[idx, df.columns.get_loc("Volume")] = 500_000.0
        df.iloc[idx, df.columns.get_loc("Volume_MA")] = 2_000_000.0
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] != 1

    def test_valid_buy_signal_fires(self):
        """All conditions met → Signal == 1."""
        df = _make_base_df()
        idx = 40
        df = _inject_golden_cross(df, idx)
        df["MACD_hist"] = 1.0
        df["RSI"] = 50.0
        df["Volume"] = 3_000_000.0    # above MA
        df["Volume_MA"] = 2_000_000.0
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] == 1

    def test_strong_buy_label_when_rsi_oversold(self):
        df = _make_base_df()
        idx = 40
        df = _inject_golden_cross(df, idx)
        df["MACD_hist"] = 1.0
        df["RSI"] = 25.0              # oversold
        df["Volume"] = 3_000_000.0
        df["Volume_MA"] = 2_000_000.0
        result = generate_signals(df)
        assert result["Signal_Type"].iloc[idx] == "STRONG_BUY"

    def test_buy_reason_populated(self):
        df = _make_base_df()
        idx = 40
        df = _inject_golden_cross(df, idx)
        df["MACD_hist"] = 1.0
        df["RSI"] = 50.0
        df["Volume"] = 3_000_000.0
        df["Volume_MA"] = 2_000_000.0
        result = generate_signals(df)
        reason = result["Signal_Reason"].iloc[idx]
        assert len(reason) > 0
        assert "EMA" in reason


# ── test: SELL conditions ─────────────────────────────────────────────────────

class TestSellSignal:
    def test_sell_requires_death_cross(self):
        df = _make_base_df()
        # Ensure EMA9 is always ABOVE EMA21 (no death cross).
        df["EMA9"] = df["EMA21"] + 2.0
        result = generate_signals(df)
        assert (result["Signal"] != -1).all()

    def test_sell_blocked_when_macd_positive(self):
        df = _make_base_df()
        idx = 40
        df = _inject_death_cross(df, idx)
        df.iloc[idx, df.columns.get_loc("MACD_hist")] = 0.5  # positive → block SELL
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] != -1

    def test_sell_blocked_when_rsi_oversold(self):
        df = _make_base_df()
        idx = 40
        df = _inject_death_cross(df, idx)
        df["MACD_hist"] = -1.0
        df["RSI"] = 20.0   # oversold → SELL should be blocked
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] != -1

    def test_valid_sell_signal_fires(self):
        df = _make_base_df()
        idx = 40
        df = _inject_death_cross(df, idx)
        df["MACD_hist"] = -1.0
        df["RSI"] = 50.0
        df["Volume"] = 3_000_000.0
        df["Volume_MA"] = 2_000_000.0
        result = generate_signals(df)
        assert result["Signal"].iloc[idx] == -1

    def test_strong_sell_label_when_rsi_overbought(self):
        df = _make_base_df()
        idx = 40
        df = _inject_death_cross(df, idx)
        df["MACD_hist"] = -1.0
        df["RSI"] = 75.0   # overbought
        df["Volume"] = 3_000_000.0
        df["Volume_MA"] = 2_000_000.0
        result = generate_signals(df)
        assert result["Signal_Type"].iloc[idx] == "STRONG_SELL"


# ── test: no simultaneous buy and sell ───────────────────────────────────────

class TestNoSimultaneousSignals:
    def test_signal_column_never_both_buy_and_sell(self):
        df = _make_base_df()
        result = generate_signals(df)
        # Each row is exactly one of {-1, 0, 1}; never multiple.
        for val in result["Signal"]:
            assert val in {-1, 0, 1}

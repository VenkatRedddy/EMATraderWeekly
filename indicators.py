"""
indicators.py — Compute EMA9, EMA21, MACD, RSI, and Volume MA.

All functions accept a ``pd.DataFrame`` with at minimum a ``Close``
(and ``Volume``) column and return a new DataFrame with the additional
indicator columns appended.  The input is never mutated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    EMA_FAST,
    EMA_SLOW,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    RSI_PERIOD,
    VOLUME_MA_PERIOD,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average with *span* periods (adjust=False)."""
    return series.ewm(span=span, adjust=False).mean()


# ── public API ────────────────────────────────────────────────────────────────

def add_ema(df: pd.DataFrame, fast: int = EMA_FAST, slow: int = EMA_SLOW) -> pd.DataFrame:
    """Add EMA9 and EMA21 columns (or whatever ``fast``/``slow`` are set to).

    Parameters
    ----------
    df:
        DataFrame with a ``Close`` column.
    fast, slow:
        EMA window sizes.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with ``EMA_fast`` and ``EMA_slow`` columns added.
    """
    out = df.copy()
    out[f"EMA{fast}"] = _ema(out["Close"], fast)
    out[f"EMA{slow}"] = _ema(out["Close"], slow)
    return out


def add_macd(
    df: pd.DataFrame,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> pd.DataFrame:
    """Add MACD line, signal line, and histogram columns.

    Columns added: ``MACD_line``, ``MACD_signal``, ``MACD_hist``.
    """
    out = df.copy()
    ema_fast = _ema(out["Close"], fast)
    ema_slow = _ema(out["Close"], slow)
    out["MACD_line"] = ema_fast - ema_slow
    out["MACD_signal"] = _ema(out["MACD_line"], signal)
    out["MACD_hist"] = out["MACD_line"] - out["MACD_signal"]
    return out


def add_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.DataFrame:
    """Add a Wilder-smoothed RSI column (``RSI``).

    Uses exponential smoothing (Wilder's method) on gains and losses.
    """
    out = df.copy()
    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder smoothing = EWM with alpha = 1/period
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI"] = 100.0 - (100.0 / (1.0 + rs))
    return out


def add_volume_ma(df: pd.DataFrame, period: int = VOLUME_MA_PERIOD) -> pd.DataFrame:
    """Add a simple moving average of Volume (``Volume_MA``)."""
    out = df.copy()
    out["Volume_MA"] = out["Volume"].rolling(window=period, min_periods=1).mean()
    return out


def add_adr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add Average Daily Range percentage column (``ADR_pct``).

    ADR% = rolling mean of ``(High − Low) / Close * 100`` over *period* bars.
    A period of 14 trading days is commonly used.

    Parameters
    ----------
    df:
        DataFrame that must contain ``High``, ``Low``, and ``Close`` columns.
    period:
        Rolling window (bars) used to average the daily range.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with an extra ``ADR_pct`` column.
    """
    out = df.copy()
    daily_range_pct = (out["High"] - out["Low"]) / out["Close"] * 100.0
    out["ADR_pct"] = daily_range_pct.rolling(window=period, min_periods=1).mean()
    return out


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience wrapper: apply all four indicator functions in order."""
    df = add_ema(df)
    df = add_macd(df)
    df = add_rsi(df)
    df = add_volume_ma(df)
    return df

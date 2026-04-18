"""
indicators.py — Technical indicator calculations.

All indicators are computed purely with pandas / numpy so there is no
hard dependency on the `ta` library at runtime; but if `ta` is installed
it can be used as an optional cross-check.

Public API
----------
add_indicators(df) -> pd.DataFrame
    Adds EMA9, EMA21, MACD_Line, MACD_Signal, MACD_Hist, RSI, Volume_MA
    columns to a copy of the input DataFrame.
"""

import numpy as np
import pandas as pd

from . import config


# ── helpers ───────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average with pandas ewm (adjust=False matches most
    charting platforms and the `ta` library convention)."""
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = config.RSI_PERIOD) -> pd.Series:
    """Wilder-smoothed RSI (matches TradingView / most platforms)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Use Wilder's smoothing (equivalent to EMA with alpha = 1/period).
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ── public API ────────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute and attach all technical indicators used by the strategy.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain at least a ``Close`` and ``Volume`` column.

    Returns
    -------
    pd.DataFrame — a copy of *df* with extra indicator columns:

    =========  ============================================================
    Column     Description
    =========  ============================================================
    EMA9       9-period EMA of Close
    EMA21      21-period EMA of Close
    MACD_Line  EMA12(Close) − EMA26(Close)
    MACD_Signal EMA9 of MACD_Line
    MACD_Hist  MACD_Line − MACD_Signal
    RSI        14-period Wilder RSI of Close
    Volume_MA  20-period simple moving average of Volume
    =========  ============================================================
    """
    df = df.copy()
    close = df["Close"]

    # ── EMA crossover lines ──────────────────────────────────────────────────
    df["EMA9"] = _ema(close, config.EMA_FAST)
    df["EMA21"] = _ema(close, config.EMA_SLOW)

    # ── MACD ────────────────────────────────────────────────────────────────
    ema_fast = _ema(close, config.MACD_FAST)
    ema_slow = _ema(close, config.MACD_SLOW)
    df["MACD_Line"] = ema_fast - ema_slow
    df["MACD_Signal"] = _ema(df["MACD_Line"], config.MACD_SIGNAL)
    df["MACD_Hist"] = df["MACD_Line"] - df["MACD_Signal"]

    # ── RSI ─────────────────────────────────────────────────────────────────
    df["RSI"] = _rsi(close, config.RSI_PERIOD)

    # ── Volume MA ────────────────────────────────────────────────────────────
    df["Volume_MA"] = (
        df["Volume"].rolling(window=config.VOLUME_MA_PERIOD, min_periods=1).mean()
    )

    return df

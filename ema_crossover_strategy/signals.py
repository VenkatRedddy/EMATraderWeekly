"""
signals.py — Buy / Sell signal generation.

Rules (ALL conditions must be satisfied simultaneously):

BUY
  1. EMA9 crosses ABOVE EMA21  (Golden Cross)
  2. MACD Histogram > 0  OR  MACD Line crosses above Signal Line
  3. RSI < RSI_OVERBOUGHT (70)
  4. Volume > 20-week Volume MA

SELL
  1. EMA9 crosses BELOW EMA21  (Death Cross)
  2. MACD Histogram < 0  OR  MACD Line crosses below Signal Line
  3. RSI > RSI_OVERSOLD (30)
  4. Volume > 20-week Volume MA

Crossover detection uses the *previous* and *current* week bars.

Public API
----------
generate_signals(df) -> pd.DataFrame
    Adds Signal column (1 = BUY, -1 = SELL, 0 = HOLD) to a copy of df.
"""

import pandas as pd

from . import config


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute buy/sell signals for every bar in *df*.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain the columns produced by :func:`indicators.add_indicators`.

    Returns
    -------
    pd.DataFrame — copy of *df* with extra boolean helper columns and a
    final ``Signal`` column (``1`` = BUY, ``-1`` = SELL, ``0`` = no signal).
    """
    df = df.copy()

    # ── EMA crossover flags ──────────────────────────────────────────────────
    # Previous week's EMA relationship
    prev_ema9 = df["EMA9"].shift(1)
    prev_ema21 = df["EMA21"].shift(1)

    # Golden Cross: EMA9 was BELOW EMA21 last week, now ABOVE
    df["Golden_Cross"] = (prev_ema9 < prev_ema21) & (df["EMA9"] > df["EMA21"])
    # Death Cross: EMA9 was ABOVE EMA21 last week, now BELOW
    df["Death_Cross"] = (prev_ema9 > prev_ema21) & (df["EMA9"] < df["EMA21"])

    # ── MACD confirmation ────────────────────────────────────────────────────
    prev_macd_line = df["MACD_Line"].shift(1)
    prev_macd_signal = df["MACD_Signal"].shift(1)

    # Bullish: histogram positive OR line crosses above signal
    df["MACD_Bullish"] = (df["MACD_Hist"] > 0) | (
        (prev_macd_line < prev_macd_signal)
        & (df["MACD_Line"] > df["MACD_Signal"])
    )
    # Bearish: histogram negative OR line crosses below signal
    df["MACD_Bearish"] = (df["MACD_Hist"] < 0) | (
        (prev_macd_line > prev_macd_signal)
        & (df["MACD_Line"] < df["MACD_Signal"])
    )

    # ── RSI filter ───────────────────────────────────────────────────────────
    df["RSI_Not_Overbought"] = df["RSI"] < config.RSI_OVERBOUGHT
    df["RSI_Not_Oversold"] = df["RSI"] > config.RSI_OVERSOLD

    # Bonus flags (for informational output)
    df["RSI_Strong_Buy"] = df["RSI"] < config.RSI_OVERSOLD    # oversold bounce
    df["RSI_Strong_Sell"] = df["RSI"] > config.RSI_OVERBOUGHT  # overbought reversal

    # ── Volume confirmation ──────────────────────────────────────────────────
    df["High_Volume"] = df["Volume"] > df["Volume_MA"]

    # ── Final signals ────────────────────────────────────────────────────────
    buy_cond = (
        df["Golden_Cross"]
        & df["MACD_Bullish"]
        & df["RSI_Not_Overbought"]
        & df["High_Volume"]
    )

    sell_cond = (
        df["Death_Cross"]
        & df["MACD_Bearish"]
        & df["RSI_Not_Oversold"]
        & df["High_Volume"]
    )

    df["Signal"] = 0
    df.loc[buy_cond, "Signal"] = 1
    df.loc[sell_cond, "Signal"] = -1

    return df

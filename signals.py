"""
signals.py — Generate BUY / SELL signals from indicator columns.

Signal logic (ALL conditions must be true):

BUY:
  1. EMA9 crosses above EMA21 (golden cross)
  2. MACD histogram > 0
  3. RSI < 70  (RSI < 30 → strong buy)
  4. Volume > 20-week average volume

SELL:
  1. EMA9 crosses below EMA21 (death cross)
  2. MACD histogram < 0
  3. RSI > 30  (RSI > 70 → strong sell)
  4. Volume > 20-week average volume
"""

from __future__ import annotations

import pandas as pd

from config import EMA_FAST, EMA_SLOW, RSI_OVERBOUGHT, RSI_OVERSOLD

_FAST = f"EMA{EMA_FAST}"
_SLOW = f"EMA{EMA_SLOW}"


def _ema_crossover(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return two boolean Series: (golden_cross, death_cross).

    A *golden cross* occurs when EMA_fast crosses above EMA_slow.
    A *death cross* occurs when EMA_fast crosses below EMA_slow.
    """
    ema_fast = df[_FAST]
    ema_slow = df[_SLOW]

    # Current bar: fast > slow
    curr_above = ema_fast > ema_slow
    # Previous bar: fast <= slow
    prev_not_above = (ema_fast.shift(1) <= ema_slow.shift(1))

    golden = curr_above & prev_not_above

    # Current bar: fast < slow; previous bar: fast >= slow
    curr_below = ema_fast < ema_slow
    prev_not_below = ema_fast.shift(1) >= ema_slow.shift(1)
    death = curr_below & prev_not_below

    return golden.fillna(False), death.fillna(False)


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Attach ``Signal``, ``Signal_Type``, and ``Signal_Reason`` columns.

    Parameters
    ----------
    df:
        DataFrame that already contains all indicator columns
        (``EMA9``, ``EMA21``, ``MACD_hist``, ``RSI``, ``Volume``, ``Volume_MA``).

    Returns
    -------
    pd.DataFrame
        Copy of *df* with three new columns:

        * ``Signal``      : 1 = buy, -1 = sell, 0 = hold
        * ``Signal_Type`` : ``"BUY"`` / ``"STRONG_BUY"`` / ``"SELL"`` /
                            ``"STRONG_SELL"`` / ``""``
        * ``Signal_Reason``: human-readable string
    """
    out = df.copy()

    golden_cross, death_cross = _ema_crossover(out)

    macd_bull = out["MACD_hist"] > 0
    macd_bear = out["MACD_hist"] < 0

    rsi_buy_ok = out["RSI"] < RSI_OVERBOUGHT          # not overbought
    rsi_sell_ok = out["RSI"] > RSI_OVERSOLD            # not oversold
    rsi_strong_buy = out["RSI"] < RSI_OVERSOLD         # oversold
    rsi_strong_sell = out["RSI"] > RSI_OVERBOUGHT      # overbought

    vol_confirm = out["Volume"] > out["Volume_MA"]

    buy_mask = golden_cross & macd_bull & rsi_buy_ok & vol_confirm
    sell_mask = death_cross & macd_bear & rsi_sell_ok & vol_confirm

    signal = pd.Series(0, index=out.index, name="Signal")
    signal_type = pd.Series("", index=out.index, name="Signal_Type")
    signal_reason = pd.Series("", index=out.index, name="Signal_Reason")

    # BUY
    signal[buy_mask] = 1
    signal_type[buy_mask] = "BUY"
    signal_type[buy_mask & rsi_strong_buy] = "STRONG_BUY"

    # SELL
    signal[sell_mask] = -1
    signal_type[sell_mask] = "SELL"
    signal_type[sell_mask & rsi_strong_sell] = "STRONG_SELL"

    # Reasons
    for idx in out.index[buy_mask]:
        rsi_val = out.loc[idx, "RSI"]
        reason = "EMA golden cross; MACD hist > 0; RSI=%.1f (<70); volume above avg" % rsi_val
        if rsi_val < RSI_OVERSOLD:
            reason += " [OVERSOLD — strong buy]"
        signal_reason[idx] = reason

    for idx in out.index[sell_mask]:
        rsi_val = out.loc[idx, "RSI"]
        reason = "EMA death cross; MACD hist < 0; RSI=%.1f (>30); volume above avg" % rsi_val
        if rsi_val > RSI_OVERBOUGHT:
            reason += " [OVERBOUGHT — strong sell]"
        signal_reason[idx] = reason

    out["Signal"] = signal
    out["Signal_Type"] = signal_type
    out["Signal_Reason"] = signal_reason
    return out

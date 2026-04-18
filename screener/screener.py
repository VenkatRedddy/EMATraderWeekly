"""
screener.py — Core EMA9/EMA21 weekly crossover screener.

For each stock in the universe the screener:
  1. Downloads weekly OHLCV data (yfinance).
  2. Calculates EMA9, EMA21, and 10-week average volume.
  3. Detects whether EMA9 just crossed above (bullish) or below (bearish) EMA21.
  4. Collects every stock that had a crossover in the *latest completed week*.
  5. Sorts ALL stocks by average weekly volume (descending) and writes a CSV.
  6. Returns crossover signals for the notifier.

Public API
----------
run_screener(cfg) -> tuple[pd.DataFrame, list[dict]]
    Returns (full_screener_table, crossover_signals)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Number of bars to skip at the very end if the latest weekly bar is
# still "live" (incomplete week).  Set to 0 if you want to include
# the in-progress bar.
_COMPLETED_BARS_OFFSET = 1


def _calc_ema(series: pd.Series, span: int) -> pd.Series:
    """Return EMA of *series* using the standard pandas ewm formula."""
    return series.ewm(span=span, adjust=False).mean()


def _fetch_one(ticker: str, lookback_weeks: int) -> pd.DataFrame | None:
    """Download *lookback_weeks* of weekly data for *ticker*.

    Returns None on failure so the caller can skip the symbol gracefully.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(weeks=lookback_weeks + 4)  # small buffer
    try:
        raw = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1wk",
            auto_adjust=True,
            progress=False,
            actions=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("yfinance error for %s: %s", ticker, exc)
        return None

    if raw is None or raw.empty:
        return None

    # Flatten multi-level columns that yfinance may produce
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    required = ["Close", "Volume"]
    if not all(c in raw.columns for c in required):
        return None

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    df.dropna(subset=["Close"], inplace=True)
    df.ffill(inplace=True)
    return df


def _compute_indicators(df: pd.DataFrame, ema_fast: int, ema_slow: int) -> pd.DataFrame:
    """Add EMA9, EMA21, avg_volume, crossover columns to *df*."""
    df = df.copy()
    df["EMA_fast"] = _calc_ema(df["Close"], ema_fast)
    df["EMA_slow"] = _calc_ema(df["Close"], ema_slow)
    df["Avg_Volume_10W"] = df["Volume"].rolling(window=10, min_periods=1).mean()

    prev_fast = df["EMA_fast"].shift(1)
    prev_slow = df["EMA_slow"].shift(1)

    df["Cross_Up"] = (prev_fast < prev_slow) & (df["EMA_fast"] > df["EMA_slow"])
    df["Cross_Down"] = (prev_fast > prev_slow) & (df["EMA_fast"] < df["EMA_slow"])
    return df


def run_screener(cfg) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Run the weekly EMA screener over the configured stock universe.

    Parameters
    ----------
    cfg : module
        The screener_config module (or compatible object).

    Returns
    -------
    screener_table : pd.DataFrame
        All stocks with latest price, EMA values, avg volume, and crossover flag,
        sorted by avg volume descending.  Also written to *cfg.OUTPUT_CSV*.
    signals : list[dict]
        Crossover events; each dict has keys:
        symbol, direction, price, ema_fast, ema_slow, avg_volume, timestamp.
    """
    from screener.stock_universe import get_symbols  # local import to avoid circular

    symbols = get_symbols(cfg)
    logger.info("Screening %d symbols …", len(symbols))

    rows: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    for i, symbol in enumerate(symbols, 1):
        logger.debug("[%d/%d] Processing %s", i, len(symbols), symbol)
        df = _fetch_one(symbol, cfg.LOOKBACK_WEEKS)
        if df is None or len(df) < max(cfg.EMA_SLOW + 5, 15):
            logger.debug("Skipping %s — insufficient data.", symbol)
            continue

        df = _compute_indicators(df, cfg.EMA_FAST, cfg.EMA_SLOW)

        # Use the last *completed* weekly bar
        latest = df.iloc[-_COMPLETED_BARS_OFFSET]
        avg_vol = float(latest["Avg_Volume_10W"])

        # Apply minimum volume filter
        if avg_vol < cfg.MIN_AVG_VOLUME:
            logger.debug("Skipping %s — avg volume %.0f < %.0f", symbol, avg_vol, cfg.MIN_AVG_VOLUME)
            # Still include in screener table for completeness (with flag)
            pass

        row: dict[str, Any] = {
            "Symbol": symbol,
            "Close": round(float(latest["Close"]), 4),
            f"EMA{cfg.EMA_FAST}": round(float(latest["EMA_fast"]), 4),
            f"EMA{cfg.EMA_SLOW}": round(float(latest["EMA_slow"]), 4),
            "Avg_Volume_10W": int(avg_vol),
            "Cross_Up": bool(latest["Cross_Up"]),
            "Cross_Down": bool(latest["Cross_Down"]),
            "Above_Volume_Filter": avg_vol >= cfg.MIN_AVG_VOLUME,
            "Week": str(latest.name.date()) if hasattr(latest.name, "date") else str(latest.name),
        }
        rows.append(row)

        # Build signal if crossover detected AND passes volume filter
        if avg_vol >= cfg.MIN_AVG_VOLUME:
            if latest["Cross_Up"]:
                signals.append({
                    "symbol": symbol,
                    "direction": "BULLISH",
                    "price": row["Close"],
                    f"ema{cfg.EMA_FAST}": row[f"EMA{cfg.EMA_FAST}"],
                    f"ema{cfg.EMA_SLOW}": row[f"EMA{cfg.EMA_SLOW}"],
                    "avg_volume": int(avg_vol),
                    "timestamp": row["Week"],
                })
            elif latest["Cross_Down"]:
                signals.append({
                    "symbol": symbol,
                    "direction": "BEARISH",
                    "price": row["Close"],
                    f"ema{cfg.EMA_FAST}": row[f"EMA{cfg.EMA_FAST}"],
                    f"ema{cfg.EMA_SLOW}": row[f"EMA{cfg.EMA_SLOW}"],
                    "avg_volume": int(avg_vol),
                    "timestamp": row["Week"],
                })

    if not rows:
        logger.warning("No data collected — check your symbol list and network.")
        return pd.DataFrame(), signals

    screener_table = pd.DataFrame(rows)
    screener_table.sort_values("Avg_Volume_10W", ascending=False, inplace=True)
    screener_table.reset_index(drop=True, inplace=True)

    # Write CSV
    output_path = Path(cfg.OUTPUT_CSV)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    screener_table.to_csv(output_path, index=False)
    logger.info("Screener table saved to %s (%d rows).", output_path, len(screener_table))

    # Log signals
    _log_signals(signals, cfg.LOG_FILE)

    return screener_table, signals


def _log_signals(signals: list[dict], log_path: str) -> None:
    """Append crossover signals to the audit log file."""
    if not signals:
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        fh.write(f"\n{'─' * 60}\n")
        fh.write(f"Screener run: {run_ts}\n")
        for s in signals:
            direction_icon = "▲ BULLISH" if s["direction"] == "BULLISH" else "▼ BEARISH"
            fh.write(
                f"  {direction_icon:12}  {s['symbol']:<10}  "
                f"Price={s['price']:.4f}  "
                f"Avg Vol={s['avg_volume']:>12,}  "
                f"Week={s['timestamp']}\n"
            )
    logger.info("Appended %d signal(s) to %s.", len(signals), log_path)

"""
screener.py — TradingView-style stock screener with EMA9/EMA21 crossover detection.

Pre-filters (applied first, in order):
  1. Price         >= SCREENER_MIN_PRICE            (latest daily close)
  2. % Change      >  SCREENER_MIN_CHANGE_PCT        (close vs previous close)
  3. Market Cap    >= SCREENER_MIN_MARKET_CAP        (from Yahoo Finance)
  4. Analyst Rating in SCREENER_ANALYST_RATINGS     (Yahoo recommendationKey)
  5. EMA(50)       <  Price                         (daily EMA50 below close)
  6. EMA(21)       <  Price                         (daily EMA21 below close)
  7. Avg Volume 10D > SCREENER_MIN_AVG_VOLUME_10D   (10-day rolling avg daily vol)
  8. ADR%          >= SCREENER_MIN_ADR_PCT           (avg daily range as % of price)

EMA9/EMA21 weekly crossover signal (applied only to stocks that pass all filters):
  GOLDEN_CROSS  — EMA9 crossed above EMA21 in the most recent weekly bar
  DEATH_CROSS   — EMA9 crossed below EMA21 in the most recent weekly bar
  HOLD          — no crossover in the most recent bar

Public API
----------
run_screener(tickers, output_csv) -> pd.DataFrame
    Run screener on *tickers*, write results to *output_csv*, return the full
    results DataFrame (one row per ticker, regardless of pass/fail).
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

import config
from data_fetcher import fetch_daily_data, fetch_fundamentals, fetch_weekly_data
from indicators import add_adr, add_ema, add_volume_ma

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _latest_ema(series: pd.Series, span: int) -> float:
    """Return the last value of an EMA with *span* periods."""
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])


def _weekly_crossover_signal(ticker: str) -> str:
    """
    Fetch weekly OHLCV and return the EMA9/EMA21 crossover status for the
    most recent completed weekly bar.

    Returns
    -------
    ``'GOLDEN_CROSS'``, ``'DEATH_CROSS'``, ``'HOLD'``, or ``'N/A'`` if data
    cannot be fetched.
    """
    try:
        df = fetch_weekly_data(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Weekly data unavailable for %s: %s", ticker, exc)
        return "N/A"

    if len(df) < 2:
        return "N/A"

    df = add_ema(df, fast=config.EMA_FAST, slow=config.EMA_SLOW)
    ema_fast = df[f"EMA{config.EMA_FAST}"]
    ema_slow = df[f"EMA{config.EMA_SLOW}"]

    curr_above = ema_fast.iloc[-1] > ema_slow.iloc[-1]
    prev_above = ema_fast.iloc[-2] > ema_slow.iloc[-2]

    if curr_above and not prev_above:
        return "GOLDEN_CROSS"
    if not curr_above and prev_above:
        return "DEATH_CROSS"
    return "HOLD"


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Per-ticker screening
# ---------------------------------------------------------------------------

def _screen_ticker(ticker: str) -> dict[str, Any]:
    """
    Run all screener checks for a single *ticker*.

    Returns a flat dictionary with every filter value, a ``pass_screener``
    boolean, and (if it passes) a ``weekly_signal`` string.
    """
    row: dict[str, Any] = {
        "ticker": ticker,
        "close": float("nan"),
        "prev_close": float("nan"),
        "change_pct": float("nan"),
        "market_cap": float("nan"),
        "analyst_rating": None,
        "ema21_daily": float("nan"),
        "ema50_daily": float("nan"),
        "avg_volume_10d": float("nan"),
        "adr_pct": float("nan"),
        "pass_screener": False,
        "weekly_ema9": float("nan"),
        "weekly_ema21": float("nan"),
        "weekly_signal": "N/A",
        # individual filter results (True/False/None=data missing)
        "f_price": None,
        "f_change": None,
        "f_market_cap": None,
        "f_analyst": None,
        "f_ema50": None,
        "f_ema21": None,
        "f_volume": None,
        "f_adr": None,
    }

    # ── 1. Daily OHLCV data ──────────────────────────────────────────────────
    daily_df = fetch_daily_data(ticker)
    if daily_df.empty or len(daily_df) < 2:
        logger.warning("[%s] Skipped — insufficient daily data.", ticker)
        return row

    daily_df = add_ema(daily_df, fast=config.SCREENER_EMA21_PERIOD, slow=config.SCREENER_EMA50_PERIOD)
    daily_df = add_adr(daily_df, period=config.SCREENER_ADR_PERIOD)
    daily_df = add_volume_ma(daily_df, period=10)

    latest = daily_df.iloc[-1]
    prev = daily_df.iloc[-2]

    close = _safe_float(latest["Close"])
    prev_close = _safe_float(prev["Close"])
    change_pct = ((close - prev_close) / prev_close * 100.0) if (not pd.isna(prev_close) and prev_close != 0) else float("nan")
    ema21 = _safe_float(latest[f"EMA{config.SCREENER_EMA21_PERIOD}"])
    ema50 = _safe_float(latest[f"EMA{config.SCREENER_EMA50_PERIOD}"])
    avg_vol_10d = _safe_float(latest["Volume_MA"])
    adr = _safe_float(latest["ADR_pct"])

    row.update(
        close=close,
        prev_close=prev_close,
        change_pct=change_pct,
        ema21_daily=ema21,
        ema50_daily=ema50,
        avg_volume_10d=avg_vol_10d,
        adr_pct=adr,
    )

    # ── 2. Fundamental data (market cap + analyst rating) ────────────────────
    fundamentals = fetch_fundamentals(ticker)
    market_cap = _safe_float(fundamentals.get("market_cap"))
    analyst_raw = fundamentals.get("analyst_rating")
    # Normalise to lowercase; treat 'none' / empty as None
    analyst_rating = analyst_raw.lower().strip() if isinstance(analyst_raw, str) and analyst_raw.lower() != "none" else None
    row.update(market_cap=market_cap, analyst_rating=analyst_rating)

    # ── 3. Apply each pre-filter ─────────────────────────────────────────────
    # Filter 1 — Price
    f_price = (close >= config.SCREENER_MIN_PRICE) if not pd.isna(close) else None
    # Filter 2 — % Change
    f_change = (change_pct > config.SCREENER_MIN_CHANGE_PCT) if not pd.isna(change_pct) else None
    # Filter 3 — Market Cap
    f_mktcap = (market_cap >= config.SCREENER_MIN_MARKET_CAP) if not pd.isna(market_cap) else None
    # Filter 4 — Analyst Rating
    if analyst_rating is None:
        logger.warning("[%s] Analyst rating data unavailable — filter skipped.", ticker)
        f_analyst = None
    else:
        f_analyst = analyst_rating in config.SCREENER_ANALYST_RATINGS
    # Filter 5 — EMA50 < Price
    f_ema50 = (ema50 < close) if (not pd.isna(ema50) and not pd.isna(close)) else None
    # Filter 6 — EMA21 < Price
    f_ema21 = (ema21 < close) if (not pd.isna(ema21) and not pd.isna(close)) else None
    # Filter 7 — 10-day avg volume
    f_vol = (avg_vol_10d > config.SCREENER_MIN_AVG_VOLUME_10D) if not pd.isna(avg_vol_10d) else None
    # Filter 8 — ADR%
    f_adr = (adr >= config.SCREENER_MIN_ADR_PCT) if not pd.isna(adr) else None

    row.update(
        f_price=f_price,
        f_change=f_change,
        f_market_cap=f_mktcap,
        f_analyst=f_analyst,
        f_ema50=f_ema50,
        f_ema21=f_ema21,
        f_volume=f_vol,
        f_adr=f_adr,
    )

    # ── 4. Determine overall pass/fail ───────────────────────────────────────
    # A filter result of None (missing data) causes the stock to fail that filter
    # with a warning already logged above.
    hard_filters = [f_price, f_change, f_mktcap, f_ema50, f_ema21, f_vol, f_adr]
    # Analyst filter is optional when data is missing (skip rather than fail)
    passes = all(f is True for f in hard_filters) and (f_analyst is not False)

    row["pass_screener"] = passes

    if not passes:
        failing = []
        labels = {
            "Price": f_price, "Change%": f_change, "MarketCap": f_mktcap,
            "EMA50": f_ema50, "EMA21": f_ema21, "Volume": f_vol, "ADR": f_adr,
        }
        if f_analyst is False:
            labels["AnalystRating"] = f_analyst
        for name, val in labels.items():
            if val is not True:
                failing.append(f"{name}={'MISSING' if val is None else 'FAIL'}")
        logger.info("[%s] Did not pass screener: %s", ticker, ", ".join(failing))
        return row

    # ── 5. Weekly EMA9/EMA21 crossover ───────────────────────────────────────
    logger.info("[%s] Passed all pre-filters — checking weekly crossover.", ticker)
    signal = _weekly_crossover_signal(ticker)
    row["weekly_signal"] = signal

    # Also store current weekly EMA values for the CSV
    try:
        wdf = fetch_weekly_data(ticker)
        wdf = add_ema(wdf, fast=config.EMA_FAST, slow=config.EMA_SLOW)
        row["weekly_ema9"] = float(wdf[f"EMA{config.EMA_FAST}"].iloc[-1])
        row["weekly_ema21"] = float(wdf[f"EMA{config.EMA_SLOW}"].iloc[-1])
    except Exception:  # noqa: BLE001
        pass

    return row


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_screener(
    tickers: list[str] | None = None,
    output_csv: str | None = None,
) -> pd.DataFrame:
    """Run the full screener on *tickers* and write results to *output_csv*.

    Parameters
    ----------
    tickers:
        List of ticker symbols to scan.  Defaults to ``config.SCREENER_TICKERS``.
    output_csv:
        File path for the output CSV.  Defaults to ``config.SCREENER_OUTPUT_CSV``.

    Returns
    -------
    pd.DataFrame
        One row per ticker.  Columns include all filter values, individual
        filter pass/fail flags, and the ``weekly_signal`` for passing tickers.
        The DataFrame is sorted by ``avg_volume_10d`` descending (highest
        volume first, matching the TradingView "sort by volume" default).
    """
    if tickers is None:
        tickers = list(config.SCREENER_TICKERS)
    if output_csv is None:
        output_csv = config.SCREENER_OUTPUT_CSV

    logger.info("Starting screener scan for %d tickers …", len(tickers))

    rows = []
    for symbol in tickers:
        logger.info("Screening %s …", symbol)
        try:
            row = _screen_ticker(symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected error screening %s: %s", symbol, exc)
            row = {"ticker": symbol, "pass_screener": False, "weekly_signal": "N/A"}
        rows.append(row)

    df = pd.DataFrame(rows)

    # ── Sort: passing stocks by volume (desc), then failing stocks ───────────
    passing = df[df["pass_screener"]].copy()
    failing = df[~df["pass_screener"]].copy()

    if "avg_volume_10d" in passing.columns:
        passing = passing.sort_values("avg_volume_10d", ascending=False)

    df_out = pd.concat([passing, failing], ignore_index=True)

    # ── Write CSV ─────────────────────────────────────────────────────────────
    df_out.to_csv(output_csv, index=False)
    n_pass = int(df["pass_screener"].sum())
    logger.info(
        "Screener complete: %d / %d tickers passed.  Results saved to %s",
        n_pass, len(tickers), output_csv,
    )

    return df_out

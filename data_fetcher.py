"""
data_fetcher.py — Download OHLCV data and fundamental data from Yahoo Finance.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from config import DEFAULT_END, DEFAULT_START, DEFAULT_TICKER, INTERVAL, SCREENER_DAILY_PERIOD

logger = logging.getLogger(__name__)


def fetch_weekly_data(
    ticker: str = DEFAULT_TICKER,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    interval: str = INTERVAL,
) -> pd.DataFrame:
    """Download weekly OHLCV data for *ticker* from Yahoo Finance.

    Parameters
    ----------
    ticker:
        Equity/index symbol accepted by yfinance (e.g. ``"AAPL"``, ``"^NIFTY"``).
    start:
        ISO-8601 start date string (``"YYYY-MM-DD"``).
    end:
        ISO-8601 end date string (``"YYYY-MM-DD"``).
    interval:
        yfinance interval string.  Defaults to ``"1wk"`` (weekly).

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by ``Date`` with columns
        ``Open, High, Low, Close, Volume``.

    Raises
    ------
    ValueError
        If the downloaded DataFrame is empty or missing required columns.
    """
    logger.info("Fetching %s data from %s to %s (interval=%s)", ticker, start, end, interval)

    raw: pd.DataFrame = yf.download(
        ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            f"No data returned for ticker '{ticker}' "
            f"between {start} and {end} at interval '{interval}'."
        )

    # yfinance may return a MultiIndex if multiple tickers were requested;
    # flatten to a single-level index just in case.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Downloaded data is missing columns: {missing}")

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()

    # Ensure the index is a proper DatetimeIndex with a consistent name.
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    # Drop weeks where Close is NaN (can happen at start/end of series).
    df.dropna(subset=["Close"], inplace=True)

    logger.info("Downloaded %d weekly bars for %s.", len(df), ticker)
    return df


def fetch_daily_data(
    ticker: str,
    period: str = SCREENER_DAILY_PERIOD,
) -> pd.DataFrame:
    """Download daily OHLCV data for *ticker* from Yahoo Finance.

    Parameters
    ----------
    ticker:
        Equity symbol accepted by yfinance (e.g. ``"AAPL"``).
    period:
        yfinance period string (e.g. ``"6mo"``, ``"1y"``).  A period of at
        least 3 months is recommended so that EMA50 can warm up properly.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by ``Date`` with columns
        ``Open, High, Low, Close, Volume``.
        Returns an *empty* DataFrame on failure so the caller can skip the
        ticker gracefully.
    """
    logger.debug("Fetching daily data for %s (period=%s).", ticker, period)
    try:
        raw: pd.DataFrame = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not download daily data for %s: %s", ticker, exc)
        return pd.DataFrame()

    if raw.empty:
        logger.warning("No daily data returned for %s.", ticker)
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(raw.columns)):
        logger.warning("Daily data for %s is missing required columns.", ticker)
        return pd.DataFrame()

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    df.dropna(subset=["Close"], inplace=True)
    logger.debug("Downloaded %d daily bars for %s.", len(df), ticker)
    return df


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    """Fetch fundamental and analyst data for *ticker* from Yahoo Finance.

    Returns a dictionary with the following keys (all may be ``None`` if the
    data is unavailable):

    * ``market_cap``        — float, total market capitalisation in USD
    * ``analyst_rating``    — str, Yahoo Finance ``recommendationKey``
                              (``'buy'``, ``'strong_buy'``, ``'hold'``,
                              ``'sell'``, ``'strong_sell'``, or ``None``)
    * ``previous_close``    — float, previous trading-day close price
    """
    result: dict[str, Any] = {
        "market_cap": None,
        "analyst_rating": None,
        "previous_close": None,
    }
    try:
        info = yf.Ticker(ticker).info
        result["market_cap"] = info.get("marketCap")
        result["analyst_rating"] = info.get("recommendationKey")
        result["previous_close"] = info.get("previousClose")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch fundamentals for %s: %s", ticker, exc)
    return result

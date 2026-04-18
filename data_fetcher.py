"""
data_fetcher.py — Download weekly OHLCV data from Yahoo Finance.
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from config import DEFAULT_END, DEFAULT_START, DEFAULT_TICKER, INTERVAL

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

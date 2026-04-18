"""
data_fetcher.py — Download weekly OHLCV data from Yahoo Finance.

Public API
----------
fetch_weekly_data(ticker, start_date, end_date) -> pd.DataFrame
"""

import logging

import pandas as pd
import yfinance as yf

from . import config

logger = logging.getLogger(__name__)


def fetch_weekly_data(
    ticker: str = config.DEFAULT_TICKER,
    start_date: str = config.DEFAULT_START_DATE,
    end_date: str = config.DEFAULT_END_DATE,
) -> pd.DataFrame:
    """Download weekly OHLCV data for *ticker* from Yahoo Finance.

    Parameters
    ----------
    ticker:     Yahoo Finance ticker symbol, e.g. ``"AAPL"``.
    start_date: ISO date string ``"YYYY-MM-DD"``.
    end_date:   ISO date string ``"YYYY-MM-DD"``.

    Returns
    -------
    pd.DataFrame with columns [Open, High, Low, Close, Volume] indexed by Date.
    Raises ValueError when the download returns an empty result.
    """
    logger.info("Fetching %s weekly data from %s to %s …", ticker, start_date, end_date)

    raw = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        interval=config.DATA_INTERVAL,
        auto_adjust=True,
        progress=False,
    )

    if raw is None or raw.empty:
        raise ValueError(
            f"No data returned for ticker '{ticker}' "
            f"({start_date} → {end_date}).  "
            "Check the ticker symbol and date range."
        )

    # yfinance may return a MultiIndex when a single ticker is passed with
    # certain versions.  Flatten to simple column names.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Keep only the standard OHLCV columns that we care about.
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Downloaded data is missing columns: {missing}")

    df = raw[required].copy()

    # Ensure the index is a proper DatetimeIndex named "Date".
    df.index.name = "Date"
    df.index = pd.to_datetime(df.index)

    # Drop rows where Close is NaN (occasionally happens at week boundaries).
    initial_len = len(df)
    df.dropna(subset=["Close"], inplace=True)
    dropped = initial_len - len(df)
    if dropped:
        logger.warning("Dropped %d rows with NaN Close.", dropped)

    # Forward-fill remaining NaNs (e.g. sporadic missing Open/High/Low).
    df.ffill(inplace=True)

    logger.info("Downloaded %d weekly bars for %s.", len(df), ticker)
    return df

"""
stock_universe.py — Fetch / build the list of stock symbols to screen.

Supported universe modes (controlled by screener_config.STOCK_UNIVERSE):
    "csv"           — read a user-supplied CSV file (column "Symbol")
    "nse_top"       — top NSE stocks (from bundled sample_stocks_nse.csv)
    "bse_top"       — top BSE stocks (from bundled sample_stocks_bse.csv)
    "us_sp500"      — S&P 500 constituents from Wikipedia
    "us_nasdaq100"  — Nasdaq-100 constituents from Wikipedia

Public API
----------
get_symbols(config) -> list[str]
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import types

logger = logging.getLogger(__name__)

# Directory that contains the bundled sample CSV files.
_HERE = Path(__file__).parent


def get_symbols(cfg) -> list[str]:
    """Return a deduplicated list of ticker symbols for the chosen universe.

    Parameters
    ----------
    cfg : module
        The screener_config module (or any object with the same attributes).

    Returns
    -------
    list[str]  — ticker symbols ready to pass to yfinance.
    """
    mode = getattr(cfg, "STOCK_UNIVERSE", "csv").lower()

    if mode == "csv":
        return _from_csv(cfg.CSV_FILE)
    elif mode == "nse_top":
        return _from_csv(str(_HERE / "sample_stocks_nse.csv"))
    elif mode == "bse_top":
        return _from_csv(str(_HERE / "sample_stocks_bse.csv"))
    elif mode == "us_sp500":
        return _sp500_from_wikipedia()
    elif mode == "us_nasdaq100":
        return _nasdaq100_from_wikipedia()
    else:
        raise ValueError(
            f"Unknown STOCK_UNIVERSE '{mode}'. "
            "Valid options: csv, nse_top, bse_top, us_sp500, us_nasdaq100."
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _from_csv(path: str) -> list[str]:
    """Load symbols from a CSV that must contain a 'Symbol' column."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Symbol CSV not found: {path}. "
            "Update CSV_FILE in screener_config.py."
        )
    df = pd.read_csv(p)
    if "Symbol" not in df.columns:
        raise ValueError(f"CSV '{path}' must contain a column named 'Symbol'.")
    symbols = df["Symbol"].dropna().str.strip().str.upper().unique().tolist()
    logger.info("Loaded %d symbols from %s.", len(symbols), path)
    return symbols


def _sp500_from_wikipedia() -> list[str]:
    """Fetch S&P 500 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    logger.info("Fetching S&P 500 constituents from Wikipedia …")
    try:
        tables = pd.read_html(url)
        symbols = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        logger.info("Fetched %d S&P 500 symbols.", len(symbols))
        return symbols
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch S&P 500 from Wikipedia: %s", exc)
        logger.warning("Falling back to bundled US sample list.")
        return _from_csv(str(_HERE / "sample_stocks_us.csv"))


def _nasdaq100_from_wikipedia() -> list[str]:
    """Fetch Nasdaq-100 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    logger.info("Fetching Nasdaq-100 constituents from Wikipedia …")
    try:
        tables = pd.read_html(url)
        # The constituents table is usually the one with a 'Ticker' column.
        for tbl in tables:
            if "Ticker" in tbl.columns:
                symbols = tbl["Ticker"].dropna().str.strip().tolist()
                logger.info("Fetched %d Nasdaq-100 symbols.", len(symbols))
                return symbols
        raise ValueError("Could not find 'Ticker' column in any Wikipedia table.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch Nasdaq-100 from Wikipedia: %s", exc)
        logger.warning("Falling back to bundled US sample list.")
        return _from_csv(str(_HERE / "sample_stocks_us.csv"))

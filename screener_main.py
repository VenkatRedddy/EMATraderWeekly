"""
screener_main.py — CLI entry point for the TradingView-style stock screener.

Usage
-----
    # Scan the default watchlist from config.py
    python screener_main.py

    # Scan specific tickers
    python screener_main.py --tickers AAPL MSFT NVDA GOOGL

    # Write results to a custom CSV
    python screener_main.py --output my_scan.csv

    # Show only stocks that passed all filters
    python screener_main.py --passing-only
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

import config
from screener import run_screener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TradingView-style stock screener with EMA9/EMA21 weekly crossover alerts"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        metavar="TICKER",
        help="Space-separated list of ticker symbols to scan (default: config.SCREENER_TICKERS)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help=f"Output CSV file path (default: {config.SCREENER_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--passing-only",
        action="store_true",
        help="Print only tickers that passed all pre-filters",
    )
    return parser.parse_args()


def _print_results(df: pd.DataFrame, passing_only: bool) -> None:
    display_cols = [
        "ticker", "close", "change_pct", "market_cap",
        "analyst_rating", "ema21_daily", "ema50_daily",
        "avg_volume_10d", "adr_pct", "pass_screener", "weekly_signal",
    ]
    # Keep only columns that actually exist (future-proof)
    display_cols = [c for c in display_cols if c in df.columns]

    subset = df[df["pass_screener"]] if passing_only else df

    if subset.empty:
        print("\n  No tickers matched the screener criteria.")
        return

    pd.set_option("display.max_colwidth", 18)
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:.2f}".format)
    print(subset[display_cols].to_string(index=False))


def main() -> None:
    args = parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else None
    output_csv = args.output or config.SCREENER_OUTPUT_CSV

    print(f"\n{'═' * 60}")
    print("  EMATraderWeekly — Stock Screener")
    print(f"  Filters: Price≥${config.SCREENER_MIN_PRICE}  "
          f"Change>{config.SCREENER_MIN_CHANGE_PCT}%  "
          f"MktCap≥${config.SCREENER_MIN_MARKET_CAP/1e6:.0f}M")
    print(f"  EMA50<Price  EMA21<Price  "
          f"AvgVol10D>{config.SCREENER_MIN_AVG_VOLUME_10D/1e3:.0f}K  "
          f"ADR≥{config.SCREENER_MIN_ADR_PCT}%")
    print(f"  Analyst: {', '.join(config.SCREENER_ANALYST_RATINGS)}")
    print(f"{'═' * 60}\n")

    try:
        results = run_screener(tickers=tickers, output_csv=output_csv)
    except Exception as exc:
        logger.error("Screener failed: %s", exc)
        sys.exit(1)

    _print_results(results, args.passing_only)

    n_pass = int(results["pass_screener"].sum()) if "pass_screener" in results.columns else 0
    print(f"\n  {n_pass} / {len(results)} tickers passed all filters.")
    print(f"  Full results saved to: {output_csv}\n")


if __name__ == "__main__":
    main()

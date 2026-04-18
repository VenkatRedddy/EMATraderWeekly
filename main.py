"""
main.py — Entry point for the EMA9/EMA21 weekly crossover strategy.

Usage
-----
    python main.py [TICKER] [START_DATE] [END_DATE]

Examples
--------
    python main.py                          # uses defaults from config.py
    python main.py MSFT 2018-01-01 2026-01-01
    python main.py ^NIFTY 2015-01-01 2026-01-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from backtest import run_backtest, trades_to_dataframe
from config import DEFAULT_END, DEFAULT_START, DEFAULT_TICKER, INITIAL_CAPITAL
from data_fetcher import fetch_weekly_data
from indicators import add_all_indicators
from performance import compute_metrics, print_metrics
from signals import generate_signals
from visualize import plot_strategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EMA9/EMA21 Weekly Moving Average Crossover Strategy"
    )
    parser.add_argument("ticker", nargs="?", default=DEFAULT_TICKER, help="Ticker symbol")
    parser.add_argument("start", nargs="?", default=DEFAULT_START, help="Start date YYYY-MM-DD")
    parser.add_argument("end", nargs="?", default=DEFAULT_END, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--no-chart", action="store_true", help="Skip the visualisation chart"
    )
    parser.add_argument(
        "--save-chart", type=str, default=None,
        metavar="PATH", help="Save chart to file instead of displaying it"
    )
    parser.add_argument(
        "--save-trades", type=str, default=None,
        metavar="PATH", help="Save trade log CSV to file"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ticker: str = args.ticker.upper()
    start: str = args.start
    end: str = args.end

    print(f"\n{'═' * 55}")
    print(f"  EMA9/EMA21 Weekly Crossover Strategy")
    print(f"  Ticker : {ticker}")
    print(f"  Period : {start}  →  {end}")
    print(f"{'═' * 55}\n")

    # ── 1. Fetch data ─────────────────────────────────────────────────────────
    logger.info("Step 1/5 — Fetching weekly data …")
    df = fetch_weekly_data(ticker, start, end)
    logger.info("  %d weekly bars loaded.", len(df))

    # ── 2. Compute indicators ─────────────────────────────────────────────────
    logger.info("Step 2/5 — Computing indicators …")
    df = add_all_indicators(df)

    # ── 3. Generate signals ───────────────────────────────────────────────────
    logger.info("Step 3/5 — Generating signals …")
    df = generate_signals(df)
    n_buy = int((df["Signal"] == 1).sum())
    n_sell = int((df["Signal"] == -1).sum())
    logger.info("  BUY signals: %d  |  SELL signals: %d", n_buy, n_sell)

    # ── 4. Run backtest ───────────────────────────────────────────────────────
    logger.info("Step 4/5 — Running backtest …")
    result = run_backtest(df)

    # ── 5. Compute and print metrics ──────────────────────────────────────────
    logger.info("Step 5/5 — Computing performance metrics …")
    metrics = compute_metrics(
        result.equity_curve,
        result.trades,
        INITIAL_CAPITAL,
        df["Close"],
    )
    print_metrics(metrics)

    # ── Trade log ─────────────────────────────────────────────────────────────
    trade_df = trades_to_dataframe(result.trades)
    if not trade_df.empty:
        print("\n  TRADE LOG")
        print("─" * 45)
        pd.set_option("display.max_colwidth", 60)
        pd.set_option("display.width", 160)
        print(trade_df.to_string(index=False))
        print()

    if args.save_trades:
        save_path = Path(args.save_trades)
        trade_df.to_csv(save_path, index=False)
        logger.info("Trade log saved to: %s", save_path)

    # ── Visualisation ─────────────────────────────────────────────────────────
    if not args.no_chart:
        chart_path = args.save_chart
        plot_strategy(df, result.equity_curve, result.trades, metrics, ticker, save_path=chart_path)


if __name__ == "__main__":
    main()

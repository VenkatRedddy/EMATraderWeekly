"""
main.py — Entry point / orchestrator for the EMA9/EMA21 trading strategy.

Usage
-----
    # Run on a single ticker with defaults
    python -m ema_crossover_strategy

    # Run on a custom ticker / date range
    python -m ema_crossover_strategy --ticker MSFT --start 2018-01-01 --end 2026-01-01

    # Run a multi-ticker batch
    python -m ema_crossover_strategy --tickers AAPL MSFT GOOGL AMZN TSLA

    # Suppress charts and only print metrics
    python -m ema_crossover_strategy --no-show --no-save
"""

import argparse
import logging
import os
import sys

import pandas as pd

from . import config
from .data_fetcher import fetch_weekly_data
from .indicators import add_indicators
from .signals import generate_signals
from .backtest import run_backtest
from .performance import compute_metrics, buy_and_hold_return, print_metrics
from .visualize import plot_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_single(
    ticker: str,
    start_date: str,
    end_date: str,
    show: bool = True,
    save: bool = True,
    output_dir: str = config.PLOT_OUTPUT_DIR,
    initial_capital: float = config.INITIAL_CAPITAL,
) -> dict:
    """End-to-end pipeline for a single *ticker*.

    Returns the performance metrics dict.
    """
    print(f"\n{'═' * 55}")
    print(f"  Ticker : {ticker}")
    print(f"  Period : {start_date}  →  {end_date}")
    print(f"{'═' * 55}")

    # 1. Fetch data
    df = fetch_weekly_data(ticker, start_date, end_date)

    # 2. Add indicators
    df = add_indicators(df)

    # 3. Generate signals
    df = generate_signals(df)

    # 4. Backtest
    trades_df, equity_df = run_backtest(df, initial_capital=initial_capital)

    # 5. Performance
    metrics = compute_metrics(trades_df, equity_df, initial_capital=initial_capital)
    bnh = buy_and_hold_return(df, initial_capital=initial_capital)
    print_metrics(metrics, bnh_return=bnh)

    # 6. Trade log
    if not trades_df.empty:
        print("\n  TRADE LOG")
        print(trades_df.to_string(index=False))

    # 7. Visualize
    plot_all(
        df,
        equity_df,
        ticker=ticker,
        output_dir=output_dir,
        show=show,
        save=save,
        initial_capital=initial_capital,
    )

    # 8. Save trade log CSV
    if save:
        os.makedirs(output_dir, exist_ok=True)
        trades_path = os.path.join(output_dir, f"{ticker}_trades.csv")
        trades_df.to_csv(trades_path, index=False)
        print(f"Trade log saved → {trades_path}")

    return metrics


def run_batch(
    tickers: list[str],
    start_date: str,
    end_date: str,
    show: bool = False,
    save: bool = True,
    output_dir: str = config.PLOT_OUTPUT_DIR,
    initial_capital: float = config.INITIAL_CAPITAL,
) -> pd.DataFrame:
    """Run the pipeline for multiple tickers and return a summary DataFrame."""
    summary_rows = []
    for ticker in tickers:
        try:
            metrics = run_single(
                ticker,
                start_date,
                end_date,
                show=show,
                save=save,
                output_dir=output_dir,
                initial_capital=initial_capital,
            )
            metrics["Ticker"] = ticker
            summary_rows.append(metrics)
        except Exception as exc:
            logger.error("Failed for %s: %s", ticker, exc)

    summary = pd.DataFrame(summary_rows).set_index("Ticker") if summary_rows else pd.DataFrame()

    if save and not summary.empty:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "batch_summary.csv")
        summary.to_csv(path)
        print(f"\nBatch summary saved → {path}")

    return summary


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="ema_crossover_strategy",
        description="EMA9/EMA21 Weekly Crossover Trading Strategy",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ticker", default=config.DEFAULT_TICKER, help="Single ticker symbol")
    group.add_argument(
        "--tickers",
        nargs="+",
        help="Multiple ticker symbols for batch run",
    )
    parser.add_argument("--start", default=config.DEFAULT_START_DATE, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=config.DEFAULT_END_DATE, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL, help="Initial capital")
    parser.add_argument("--no-show", dest="show", action="store_false", help="Suppress interactive chart")
    parser.add_argument("--no-save", dest="save", action="store_false", help="Do not save charts/CSVs")
    parser.add_argument("--output-dir", default=config.PLOT_OUTPUT_DIR, help="Output directory")
    parser.set_defaults(show=True, save=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    if args.tickers:
        run_batch(
            tickers=args.tickers,
            start_date=args.start,
            end_date=args.end,
            show=args.show,
            save=args.save,
            output_dir=args.output_dir,
            initial_capital=args.capital,
        )
    else:
        run_single(
            ticker=args.ticker,
            start_date=args.start,
            end_date=args.end,
            show=args.show,
            save=args.save,
            output_dir=args.output_dir,
            initial_capital=args.capital,
        )


if __name__ == "__main__":
    main()

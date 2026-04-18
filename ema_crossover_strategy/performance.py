"""
performance.py — Strategy performance metrics.

Public API
----------
compute_metrics(trades_df, equity_df, initial_capital) -> dict
print_metrics(metrics)
buy_and_hold_return(df, initial_capital) -> float
"""

import math
from typing import Optional

import numpy as np
import pandas as pd

from . import config


def compute_metrics(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    initial_capital: float = config.INITIAL_CAPITAL,
) -> dict:
    """Compute comprehensive performance metrics for the backtest.

    Parameters
    ----------
    trades_df : pd.DataFrame  — output of backtest.run_backtest
    equity_df : pd.DataFrame  — output of backtest.run_backtest
    initial_capital : float

    Returns
    -------
    dict with keys matching the metrics described in the project spec.
    """
    metrics: dict = {}

    if equity_df.empty:
        return metrics

    final_value = float(equity_df["Portfolio_Value"].iloc[-1])
    total_return_pct = (final_value / initial_capital - 1) * 100
    metrics["Total_Return_%"] = round(total_return_pct, 2)
    metrics["Final_Portfolio_Value"] = round(final_value, 2)

    # ── Annualised Return (CAGR) ─────────────────────────────────────────────
    start_date = equity_df.index[0]
    end_date = equity_df.index[-1]
    years = (end_date - start_date).days / 365.25
    if years > 0:
        cagr = ((final_value / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0
    metrics["CAGR_%"] = round(cagr, 2)

    # ── Weekly returns for Sharpe / drawdown ─────────────────────────────────
    pv = equity_df["Portfolio_Value"]
    weekly_returns = pv.pct_change().dropna()

    # ── Sharpe Ratio (annualised, risk-free rate assumed 0) ──────────────────
    if weekly_returns.std() > 0:
        sharpe = (weekly_returns.mean() / weekly_returns.std()) * math.sqrt(52)
    else:
        sharpe = 0.0
    metrics["Sharpe_Ratio"] = round(sharpe, 4)

    # ── Maximum Drawdown ─────────────────────────────────────────────────────
    rolling_max = pv.cummax()
    drawdown = (pv - rolling_max) / rolling_max
    max_drawdown_pct = drawdown.min() * 100
    metrics["Max_Drawdown_%"] = round(max_drawdown_pct, 2)

    # ── Trade-level statistics ───────────────────────────────────────────────
    metrics["Total_Trades"] = len(trades_df)

    if len(trades_df) > 0:
        winning = trades_df[trades_df["PnL"] > 0]
        losing = trades_df[trades_df["PnL"] <= 0]

        win_rate = len(winning) / len(trades_df) * 100
        metrics["Win_Rate_%"] = round(win_rate, 2)

        gross_profit = winning["PnL"].sum()
        gross_loss = abs(losing["PnL"].sum())
        metrics["Gross_Profit"] = round(gross_profit, 2)
        metrics["Gross_Loss"] = round(gross_loss, 2)
        metrics["Profit_Factor"] = (
            round(gross_profit / gross_loss, 4) if gross_loss > 0 else float("inf")
        )

        metrics["Avg_Trade_PnL"] = round(trades_df["PnL"].mean(), 2)
        metrics["Avg_Trade_PnL_%"] = round(trades_df["PnL_%"].mean(), 2)
        metrics["Avg_Duration_Weeks"] = round(trades_df["Duration_Weeks"].mean(), 1)
        metrics["Best_Trade_%"] = round(trades_df["PnL_%"].max(), 2)
        metrics["Worst_Trade_%"] = round(trades_df["PnL_%"].min(), 2)
    else:
        metrics.update(
            {
                "Win_Rate_%": 0.0,
                "Gross_Profit": 0.0,
                "Gross_Loss": 0.0,
                "Profit_Factor": 0.0,
                "Avg_Trade_PnL": 0.0,
                "Avg_Trade_PnL_%": 0.0,
                "Avg_Duration_Weeks": 0.0,
                "Best_Trade_%": 0.0,
                "Worst_Trade_%": 0.0,
            }
        )

    return metrics


def buy_and_hold_return(
    df: pd.DataFrame,
    initial_capital: float = config.INITIAL_CAPITAL,
) -> float:
    """Compute the simple buy-and-hold return (%) for the same period."""
    first_close = float(df["Close"].iloc[0])
    last_close = float(df["Close"].iloc[-1])
    return round((last_close / first_close - 1) * 100, 2)


def print_metrics(metrics: dict, bnh_return: Optional[float] = None) -> None:
    """Pretty-print the metrics dictionary to stdout."""
    separator = "─" * 45
    print(f"\n{separator}")
    print("  STRATEGY PERFORMANCE REPORT")
    print(separator)

    labels = {
        "Total_Return_%": "Total Return",
        "Final_Portfolio_Value": "Final Portfolio Value ($)",
        "CAGR_%": "Annualised Return (CAGR)",
        "Sharpe_Ratio": "Sharpe Ratio",
        "Max_Drawdown_%": "Max Drawdown",
        "Total_Trades": "Total Trades",
        "Win_Rate_%": "Win Rate",
        "Profit_Factor": "Profit Factor",
        "Gross_Profit": "Gross Profit ($)",
        "Gross_Loss": "Gross Loss ($)",
        "Avg_Trade_PnL": "Avg Trade PnL ($)",
        "Avg_Trade_PnL_%": "Avg Trade Return (%)",
        "Avg_Duration_Weeks": "Avg Trade Duration (weeks)",
        "Best_Trade_%": "Best Trade (%)",
        "Worst_Trade_%": "Worst Trade (%)",
    }

    for key, label in labels.items():
        value = metrics.get(key, "N/A")
        if isinstance(value, float):
            suffix = ""
            if key.endswith("_%"):
                suffix = " %"
            print(f"  {label:<33} {value:>8.2f}{suffix}")
        else:
            print(f"  {label:<33} {value!s:>8}")

    if bnh_return is not None:
        print(separator)
        print(f"  {'Buy & Hold Return':<33} {bnh_return:>8.2f} %")

    print(separator)

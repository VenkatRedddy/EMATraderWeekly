"""
performance.py — Compute strategy performance metrics.

Metrics calculated
------------------
* Total return %
* Annualized (CAGR) return %
* Sharpe ratio (annualised, 52-week basis)
* Max drawdown %
* Win rate %
* Profit factor
* Number of trades
* Average trade duration (weeks)
* Buy-and-hold return % (benchmark)
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from backtest import Trade
from config import RISK_FREE_RATE


def compute_metrics(
    equity_curve: pd.Series,
    trades: List[Trade],
    initial_capital: float,
    price_series: pd.Series,
) -> Dict[str, float | str]:
    """Return a dict of performance statistics.

    Parameters
    ----------
    equity_curve:
        Portfolio value at each weekly bar.
    trades:
        List of completed :class:`~backtest.Trade` objects.
    initial_capital:
        Starting capital used in the backtest.
    price_series:
        Raw Close prices for the buy-and-hold benchmark calculation.
    """
    metrics: Dict[str, float | str] = {}

    final_value = float(equity_curve.iloc[-1])
    metrics["initial_capital"] = round(initial_capital, 2)
    metrics["final_capital"] = round(final_value, 2)

    # ── Total return ──────────────────────────────────────────────────────────
    total_return = (final_value - initial_capital) / initial_capital * 100.0
    metrics["total_return_pct"] = round(total_return, 2)

    # ── Annualised return (CAGR) ──────────────────────────────────────────────
    n_weeks = len(equity_curve)
    n_years = n_weeks / 52.0
    if n_years > 0 and initial_capital > 0:
        cagr = ((final_value / initial_capital) ** (1.0 / n_years) - 1.0) * 100.0
    else:
        cagr = 0.0
    metrics["annualized_return_pct"] = round(cagr, 2)

    # ── Sharpe ratio ──────────────────────────────────────────────────────────
    weekly_returns = equity_curve.pct_change().dropna()
    rf_weekly = RISK_FREE_RATE / 52.0
    excess = weekly_returns - rf_weekly
    if excess.std() > 0:
        sharpe = (excess.mean() / excess.std()) * np.sqrt(52)
    else:
        sharpe = 0.0
    metrics["sharpe_ratio"] = round(float(sharpe), 4)

    # ── Max drawdown ──────────────────────────────────────────────────────────
    roll_max = equity_curve.cummax()
    drawdown = (equity_curve - roll_max) / roll_max
    max_dd = float(drawdown.min()) * 100.0
    metrics["max_drawdown_pct"] = round(max_dd, 2)

    # ── Trade statistics ──────────────────────────────────────────────────────
    metrics["total_trades"] = len(trades)

    if trades:
        profits = [t.profit for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]

        metrics["win_rate_pct"] = round(len(wins) / len(trades) * 100.0, 2)
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        metrics["profit_factor"] = (
            round(gross_profit / gross_loss, 4) if gross_loss > 0 else float("inf")
        )
        metrics["avg_profit_per_trade"] = round(np.mean(profits), 2)

        durations = []
        for t in trades:
            if t.entry_date and t.exit_date:
                weeks = (t.exit_date - t.entry_date).days / 7.0
                durations.append(weeks)
        metrics["avg_trade_duration_weeks"] = round(float(np.mean(durations)), 1) if durations else 0.0
    else:
        metrics["win_rate_pct"] = 0.0
        metrics["profit_factor"] = 0.0
        metrics["avg_profit_per_trade"] = 0.0
        metrics["avg_trade_duration_weeks"] = 0.0

    # ── Buy-and-hold benchmark ────────────────────────────────────────────────
    bah_return = (
        (float(price_series.iloc[-1]) - float(price_series.iloc[0]))
        / float(price_series.iloc[0])
        * 100.0
    )
    metrics["buy_and_hold_return_pct"] = round(bah_return, 2)

    return metrics


def print_metrics(metrics: Dict[str, float | str]) -> None:
    """Pretty-print the metrics dict."""
    separator = "─" * 45
    print(separator)
    print("  PERFORMANCE METRICS")
    print(separator)
    labels = {
        "initial_capital": "Initial Capital ($)",
        "final_capital": "Final Capital ($)",
        "total_return_pct": "Total Return (%)",
        "annualized_return_pct": "Annualised Return / CAGR (%)",
        "sharpe_ratio": "Sharpe Ratio",
        "max_drawdown_pct": "Max Drawdown (%)",
        "total_trades": "Total Trades",
        "win_rate_pct": "Win Rate (%)",
        "profit_factor": "Profit Factor",
        "avg_profit_per_trade": "Avg Profit per Trade ($)",
        "avg_trade_duration_weeks": "Avg Trade Duration (weeks)",
        "buy_and_hold_return_pct": "Buy-and-Hold Return (%)",
    }
    for key, label in labels.items():
        val = metrics.get(key, "N/A")
        print(f"  {label:<34} {val}")
    print(separator)

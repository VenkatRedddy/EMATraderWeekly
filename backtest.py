"""
backtest.py — Event-driven backtesting engine.

Assumptions
-----------
* One position at a time (long only).
* Enter at the *Close* of the signal bar (next-bar execution is optional but
  would require minimal changes).
* Commission is charged on both entry and exit as a fraction of trade value.
* A 5 % trailing stop is maintained during a trade; if the Close of any week
  falls below the trailing stop level, the position is closed.
* Full capital is deployed on each trade (position sizing = 100 %).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from config import COMMISSION_RATE, INITIAL_CAPITAL, TRAILING_STOP_PCT


@dataclass
class Trade:
    """Record for a completed round-trip trade."""

    entry_date: pd.Timestamp
    entry_price: float
    entry_reason: str
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    shares: float = 0.0
    profit: float = 0.0
    return_pct: float = 0.0


@dataclass
class BacktestResult:
    """Container returned by :func:`run_backtest`."""

    equity_curve: pd.Series                   # portfolio value over time
    trades: List[Trade] = field(default_factory=list)
    final_capital: float = 0.0


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = INITIAL_CAPITAL,
    commission_rate: float = COMMISSION_RATE,
    trailing_stop_pct: float = TRAILING_STOP_PCT,
) -> BacktestResult:
    """Run the EMA9/EMA21 crossover backtest on *df*.

    Parameters
    ----------
    df:
        DataFrame with columns ``Close``, ``Signal``, ``Signal_Type``,
        ``Signal_Reason`` (i.e. output of :func:`signals.generate_signals`).
    initial_capital:
        Starting portfolio value in USD.
    commission_rate:
        Fractional commission charged per trade leg (e.g. 0.001 = 0.1 %).
    trailing_stop_pct:
        Maximum allowed drawdown from the intra-trade peak before the
        position is stopped out (e.g. 0.05 = 5 %).

    Returns
    -------
    BacktestResult
    """
    capital = initial_capital
    position: Optional[dict] = None   # dict when in a trade, else None
    trades: List[Trade] = []
    equity_values: list = []

    for date, row in df.iterrows():
        close = float(row["Close"])
        signal = int(row.get("Signal", 0))
        reason = str(row.get("Signal_Reason", ""))

        # ── Update trailing stop if in a position ─────────────────────────────
        if position is not None:
            # Raise the high-water mark if price moved higher.
            if close > position["peak"]:
                position["peak"] = close
            stop_level = position["peak"] * (1.0 - trailing_stop_pct)

            # Check trailing stop.
            if close <= stop_level:
                trade = _close_position(position, date, close, "Trailing stop hit", commission_rate)
                trades.append(trade)
                capital = position["capital_at_entry"] + trade.profit
                position = None

        # ── Process signals ────────────────────────────────────────────────────
        if position is None and signal == 1:
            # Open long position.
            cost = close * (1.0 + commission_rate)
            shares = capital / cost
            position = {
                "entry_date": date,
                "entry_price": close,
                "entry_reason": reason,
                "shares": shares,
                "peak": close,
                "capital_at_entry": capital,
            }

        elif position is not None and signal == -1:
            # Close long position on sell signal.
            trade = _close_position(position, date, close, reason, commission_rate)
            trades.append(trade)
            capital = position["capital_at_entry"] + trade.profit
            position = None

        # ── Record equity ──────────────────────────────────────────────────────
        if position is not None:
            equity = position["shares"] * close * (1.0 - commission_rate)
        else:
            equity = capital
        equity_values.append(equity)

    # Close any open position at the last bar.
    if position is not None:
        last_date = df.index[-1]
        last_close = float(df["Close"].iloc[-1])
        trade = _close_position(position, last_date, last_close, "End of data", commission_rate)
        trades.append(trade)
        capital = position["capital_at_entry"] + trade.profit
        equity_values[-1] = capital

    equity_curve = pd.Series(equity_values, index=df.index, name="Equity")
    return BacktestResult(equity_curve=equity_curve, trades=trades, final_capital=capital)


# ── internal helpers ──────────────────────────────────────────────────────────

def _close_position(
    position: dict,
    date: pd.Timestamp,
    price: float,
    reason: str,
    commission_rate: float,
) -> Trade:
    shares = position["shares"]
    entry_price = position["entry_price"]
    entry_cost = shares * entry_price * (1.0 + commission_rate)
    exit_proceeds = shares * price * (1.0 - commission_rate)
    profit = exit_proceeds - entry_cost
    return_pct = profit / entry_cost * 100.0

    return Trade(
        entry_date=position["entry_date"],
        entry_price=entry_price,
        entry_reason=position["entry_reason"],
        exit_date=date,
        exit_price=price,
        exit_reason=reason,
        shares=shares,
        profit=profit,
        return_pct=return_pct,
    )


def trades_to_dataframe(trades: List[Trade]) -> pd.DataFrame:
    """Convert a list of :class:`Trade` objects to a tidy DataFrame."""
    if not trades:
        return pd.DataFrame(
            columns=[
                "entry_date", "entry_price", "entry_reason",
                "exit_date", "exit_price", "exit_reason",
                "shares", "profit", "return_pct",
            ]
        )
    rows = [
        {
            "entry_date": t.entry_date,
            "entry_price": round(t.entry_price, 4),
            "entry_reason": t.entry_reason,
            "exit_date": t.exit_date,
            "exit_price": round(t.exit_price, 4) if t.exit_price else None,
            "exit_reason": t.exit_reason,
            "shares": round(t.shares, 4),
            "profit": round(t.profit, 2),
            "return_pct": round(t.return_pct, 4),
        }
        for t in trades
    ]
    return pd.DataFrame(rows)

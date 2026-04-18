"""
backtest.py — Weekly backtesting engine.

Parameters (from config.py)
---------------------------
INITIAL_CAPITAL : float  — starting portfolio value
COMMISSION      : float  — fraction charged on each fill (entry + exit)
SLIPPAGE        : float  — one-way slippage fraction
STOP_LOSS_PCT   : float  — trailing stop-loss as fraction of price
POSITION_SIZE_PCT: float — fraction of available capital to deploy

Public API
----------
run_backtest(df) -> (trades_df, equity_df)
    df must contain Signal, Close, Open, High, Low columns plus all
    indicator columns.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from . import config

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    signal_reason: str
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    duration_weeks: int = 0


def _fill_price(bar_close: float, direction: int) -> float:
    """Apply slippage to the execution price.

    direction: +1 for a buy (pays more), -1 for a sell (receives less).
    """
    return bar_close * (1 + direction * config.SLIPPAGE)


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = config.INITIAL_CAPITAL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate the EMA9/EMA21 strategy on *df*.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: Date (index), Open, High, Low, Close, Volume,
        EMA9, EMA21, RSI, MACD_Line, MACD_Signal, MACD_Hist, Volume_MA,
        Signal, Golden_Cross, Death_Cross, RSI_Strong_Buy, RSI_Strong_Sell.
    initial_capital : float
        Starting cash.

    Returns
    -------
    trades_df : pd.DataFrame  — one row per completed round-trip trade.
    equity_df : pd.DataFrame  — portfolio equity at every weekly bar.
    """
    cash = initial_capital
    position_shares = 0.0
    entry_price = 0.0
    trailing_stop = 0.0
    open_trade: Optional[Trade] = None
    completed_trades: List[Trade] = []
    equity_series: List[dict] = []

    for i, (date, row) in enumerate(df.iterrows()):
        close = float(row["Close"])
        signal = int(row.get("Signal", 0))

        # ── Update trailing stop while in a position ──────────────────────
        if position_shares > 0:
            new_stop = close * (1 - config.STOP_LOSS_PCT)
            if new_stop > trailing_stop:
                trailing_stop = new_stop

        # ── Check stop-loss trigger ───────────────────────────────────────
        stop_hit = position_shares > 0 and close <= trailing_stop

        if stop_hit:
            exit_p = _fill_price(close, -1)
            gross = position_shares * exit_p
            commission = gross * config.COMMISSION
            cash += gross - commission
            pnl = (exit_p - open_trade.entry_price) * position_shares - commission
            pnl -= open_trade.entry_price * position_shares * config.COMMISSION

            open_trade.exit_date = date
            open_trade.exit_price = exit_p
            open_trade.exit_reason = "Stop-Loss"
            open_trade.pnl = pnl
            open_trade.pnl_pct = (exit_p / open_trade.entry_price - 1) * 100
            open_trade.duration_weeks = i - df.index.get_loc(open_trade.entry_date)
            completed_trades.append(open_trade)
            logger.debug("Stop-loss exit at %s, price %.4f", date, exit_p)

            position_shares = 0.0
            trailing_stop = 0.0
            open_trade = None

        # ── Execute SELL signal ───────────────────────────────────────────
        elif signal == -1 and position_shares > 0:
            exit_p = _fill_price(close, -1)
            gross = position_shares * exit_p
            commission = gross * config.COMMISSION
            cash += gross - commission

            reason_prefix = "Strong-Sell" if row.get("RSI_Strong_Sell") else "Sell"
            pnl = (exit_p - open_trade.entry_price) * position_shares - commission
            pnl -= open_trade.entry_price * position_shares * config.COMMISSION

            open_trade.exit_date = date
            open_trade.exit_price = exit_p
            open_trade.exit_reason = reason_prefix
            open_trade.pnl = pnl
            open_trade.pnl_pct = (exit_p / open_trade.entry_price - 1) * 100
            open_trade.duration_weeks = i - df.index.get_loc(open_trade.entry_date)
            completed_trades.append(open_trade)
            logger.debug("Sell signal at %s, price %.4f", date, exit_p)

            position_shares = 0.0
            trailing_stop = 0.0
            open_trade = None

        # ── Execute BUY signal ────────────────────────────────────────────
        if signal == 1 and position_shares == 0:
            entry_p = _fill_price(close, +1)
            invest_cash = cash * config.POSITION_SIZE_PCT
            commission = invest_cash * config.COMMISSION
            net_invest = invest_cash - commission
            position_shares = net_invest / entry_p
            cash -= invest_cash
            trailing_stop = entry_p * (1 - config.STOP_LOSS_PCT)
            entry_price = entry_p

            reason_label = "Strong-Buy" if row.get("RSI_Strong_Buy") else "Buy"
            open_trade = Trade(
                entry_date=date,
                entry_price=entry_p,
                shares=position_shares,
                signal_reason=reason_label,
            )
            logger.debug("Buy signal at %s, price %.4f", date, entry_p)

        # ── Portfolio value snapshot ──────────────────────────────────────
        portfolio_value = cash + position_shares * close
        equity_series.append(
            {
                "Date": date,
                "Portfolio_Value": portfolio_value,
                "Cash": cash,
                "Shares": position_shares,
                "Close": close,
                "Signal": signal,
            }
        )

    # Close any open position at the last bar
    if position_shares > 0 and open_trade is not None:
        last_date = df.index[-1]
        last_close = float(df["Close"].iloc[-1])
        exit_p = _fill_price(last_close, -1)
        gross = position_shares * exit_p
        commission = gross * config.COMMISSION
        cash += gross - commission
        pnl = (exit_p - open_trade.entry_price) * position_shares - commission
        pnl -= open_trade.entry_price * open_trade.shares * config.COMMISSION

        open_trade.exit_date = last_date
        open_trade.exit_price = exit_p
        open_trade.exit_reason = "End-Of-Data"
        open_trade.pnl = pnl
        open_trade.pnl_pct = (exit_p / open_trade.entry_price - 1) * 100
        open_trade.duration_weeks = len(df) - 1 - df.index.get_loc(open_trade.entry_date)
        completed_trades.append(open_trade)

    trades_df = pd.DataFrame(
        [
            {
                "Entry_Date": t.entry_date,
                "Entry_Price": round(t.entry_price, 4),
                "Exit_Date": t.exit_date,
                "Exit_Price": round(t.exit_price, 4) if t.exit_price else None,
                "Shares": round(t.shares, 4),
                "PnL": round(t.pnl, 2),
                "PnL_%": round(t.pnl_pct, 2),
                "Duration_Weeks": t.duration_weeks,
                "Entry_Reason": t.signal_reason,
                "Exit_Reason": t.exit_reason,
            }
            for t in completed_trades
        ]
    )

    equity_df = pd.DataFrame(equity_series).set_index("Date")

    return trades_df, equity_df

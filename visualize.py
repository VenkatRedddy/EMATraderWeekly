"""
visualize.py — Produce a multi-panel strategy dashboard.

Layout (top-to-bottom)
----------------------
1. Price chart with EMA9, EMA21, buy (▲) and sell (▼) markers
2. MACD panel (line, signal, histogram)
3. RSI panel with 30 / 70 reference lines
4. Volume panel with 20-week MA overlay
5. Equity curve vs buy-and-hold benchmark
"""

from __future__ import annotations

from typing import Dict, List, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from backtest import Trade
from config import EMA_FAST, EMA_SLOW, RSI_OVERBOUGHT, RSI_OVERSOLD

_FAST_COL = f"EMA{EMA_FAST}"
_SLOW_COL = f"EMA{EMA_SLOW}"


def plot_strategy(
    df: pd.DataFrame,
    equity_curve: pd.Series,
    trades: List[Trade],
    metrics: Dict,
    ticker: str = "",
    save_path: Optional[str] = None,
) -> None:
    """Render and optionally save the full strategy dashboard.

    Parameters
    ----------
    df:
        DataFrame with all indicator + signal columns.
    equity_curve:
        Portfolio value series from the backtest.
    trades:
        List of :class:`~backtest.Trade` objects.
    metrics:
        Performance metrics dict from :func:`performance.compute_metrics`.
    ticker:
        Symbol used as chart title prefix.
    save_path:
        If provided, save the figure to this path instead of displaying it.
    """
    fig, axes = plt.subplots(
        5, 1,
        figsize=(16, 22),
        gridspec_kw={"height_ratios": [3, 1.5, 1.5, 1.2, 1.8]},
        sharex=True,
    )
    fig.subplots_adjust(hspace=0.08)

    dates = df.index

    # ── 1. Price + EMA ────────────────────────────────────────────────────────
    ax1 = axes[0]
    ax1.plot(dates, df["Close"], color="#2196F3", linewidth=1.2, label="Close", zorder=2)
    ax1.plot(dates, df[_FAST_COL], color="#FF9800", linewidth=1.2, label=f"EMA{EMA_FAST}", zorder=3)
    ax1.plot(dates, df[_SLOW_COL], color="#9C27B0", linewidth=1.2, label=f"EMA{EMA_SLOW}", zorder=3)

    buy_dates = df.index[df["Signal"] == 1]
    sell_dates = df.index[df["Signal"] == -1]
    ax1.scatter(
        buy_dates, df.loc[buy_dates, "Close"] * 0.98,
        marker="^", color="#4CAF50", s=120, zorder=5, label="BUY",
    )
    ax1.scatter(
        sell_dates, df.loc[sell_dates, "Close"] * 1.02,
        marker="v", color="#F44336", s=120, zorder=5, label="SELL",
    )
    title = f"EMA{EMA_FAST}/{EMA_SLOW} Weekly Crossover Strategy"
    if ticker:
        title = f"{ticker} — {title}"
    ax1.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax1.set_ylabel("Price (USD)", fontsize=10)
    ax1.legend(loc="upper left", fontsize=9, framealpha=0.7)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.grid(True, alpha=0.3)

    # Shade trade regions.
    for trade in trades:
        if trade.exit_date:
            ax1.axvspan(trade.entry_date, trade.exit_date, alpha=0.06, color="green")

    # ── 2. MACD ───────────────────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.plot(dates, df["MACD_line"], color="#2196F3", linewidth=1, label="MACD")
    ax2.plot(dates, df["MACD_signal"], color="#FF9800", linewidth=1, label="Signal")
    hist_colors = ["#4CAF50" if v >= 0 else "#F44336" for v in df["MACD_hist"].fillna(0)]
    ax2.bar(dates, df["MACD_hist"], color=hist_colors, alpha=0.6, label="Histogram")
    ax2.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax2.set_ylabel("MACD", fontsize=10)
    ax2.legend(loc="upper left", fontsize=8, framealpha=0.7)
    ax2.grid(True, alpha=0.3)

    # ── 3. RSI ────────────────────────────────────────────────────────────────
    ax3 = axes[2]
    ax3.plot(dates, df["RSI"], color="#9C27B0", linewidth=1, label="RSI(14)")
    ax3.axhline(RSI_OVERBOUGHT, color="#F44336", linewidth=0.9, linestyle="--", label="Overbought (70)")
    ax3.axhline(RSI_OVERSOLD, color="#4CAF50", linewidth=0.9, linestyle="--", label="Oversold (30)")
    ax3.fill_between(dates, RSI_OVERBOUGHT, df["RSI"].clip(lower=RSI_OVERBOUGHT), alpha=0.15, color="#F44336")
    ax3.fill_between(dates, df["RSI"].clip(upper=RSI_OVERSOLD), RSI_OVERSOLD, alpha=0.15, color="#4CAF50")
    ax3.set_ylim(0, 100)
    ax3.set_ylabel("RSI", fontsize=10)
    ax3.legend(loc="upper left", fontsize=8, framealpha=0.7)
    ax3.grid(True, alpha=0.3)

    # ── 4. Volume ─────────────────────────────────────────────────────────────
    ax4 = axes[3]
    vol_colors = [
        "#4CAF50" if v > ma else "#90A4AE"
        for v, ma in zip(df["Volume"].fillna(0), df["Volume_MA"].fillna(0))
    ]
    ax4.bar(dates, df["Volume"], color=vol_colors, alpha=0.7, label="Volume")
    ax4.plot(dates, df["Volume_MA"], color="#FF9800", linewidth=1.2, label="20-wk MA")
    ax4.set_ylabel("Volume", fontsize=10)
    ax4.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.0f}M"))
    ax4.legend(loc="upper left", fontsize=8, framealpha=0.7)
    ax4.grid(True, alpha=0.3)

    # ── 5. Equity curve ───────────────────────────────────────────────────────
    ax5 = axes[4]
    # Buy-and-hold normalised to same initial capital.
    close_norm = (df["Close"] / float(df["Close"].iloc[0])) * float(equity_curve.iloc[0])
    ax5.plot(dates, equity_curve, color="#2196F3", linewidth=1.4, label="Strategy")
    ax5.plot(dates, close_norm, color="#9E9E9E", linewidth=1, linestyle="--", label="Buy & Hold")
    ax5.set_ylabel("Portfolio ($)", fontsize=10)
    ax5.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax5.legend(loc="upper left", fontsize=9, framealpha=0.7)
    ax5.grid(True, alpha=0.3)

    # Annotate final returns on equity curve.
    total_ret = metrics.get("total_return_pct", 0)
    bah_ret = metrics.get("buy_and_hold_return_pct", 0)
    ax5.annotate(
        f"Strategy: {total_ret:+.1f}%  |  B&H: {bah_ret:+.1f}%",
        xy=(0.01, 0.92), xycoords="axes fraction",
        fontsize=9, color="black",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7),
    )

    # Shared x-axis formatting.
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].xaxis.set_major_locator(mdates.YearLocator())
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=30, ha="right")

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved to: {save_path}")
    else:
        plt.show()
    plt.close(fig)

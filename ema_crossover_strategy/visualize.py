"""
visualize.py — Charts and plots for the EMA crossover strategy.

Five charts are produced:
  1. Price with EMA9/EMA21 + buy/sell markers
  2. MACD panel
  3. RSI panel with oversold/overbought zones
  4. Volume panel with 20-week MA and above-average highlighting
  5. Equity curve vs Buy & Hold benchmark

Public API
----------
plot_all(df, equity_df, ticker, output_dir, show, save)
"""

import os

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from . import config


_PANEL_RATIOS = [3, 1.2, 1.2, 1.2, 1.5]   # relative heights of the 5 panels
_FIGSIZE = (18, 22)


def _setup_axes(ticker: str):
    fig, axes = plt.subplots(
        5,
        1,
        figsize=_FIGSIZE,
        gridspec_kw={"height_ratios": _PANEL_RATIOS},
        sharex=True,
    )
    fig.suptitle(
        f"{ticker} — EMA9/EMA21 Weekly Strategy",
        fontsize=16,
        fontweight="bold",
        y=0.99,
    )
    fig.subplots_adjust(hspace=0.05)
    return fig, axes


def _format_date_axis(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")


# ── Panel 1: Price + EMA crossover ───────────────────────────────────────────

def _plot_price(ax, df: pd.DataFrame):
    ax.plot(df.index, df["Close"], color="steelblue", linewidth=1.2, label="Close")
    ax.plot(df.index, df["EMA9"], color="orange", linewidth=1.2, label="EMA9")
    ax.plot(df.index, df["EMA21"], color="purple", linewidth=1.2, label="EMA21")

    buys = df[df["Signal"] == 1]
    sells = df[df["Signal"] == -1]

    ax.scatter(
        buys.index,
        buys["Close"],
        marker="^",
        color="lime",
        s=100,
        zorder=5,
        label="BUY",
    )
    ax.scatter(
        sells.index,
        sells["Close"],
        marker="v",
        color="red",
        s=100,
        zorder=5,
        label="SELL",
    )

    ax.set_ylabel("Price", fontsize=11)
    ax.legend(loc="upper left", fontsize=9, ncol=3)
    ax.grid(alpha=0.3)


# ── Panel 2: MACD ────────────────────────────────────────────────────────────

def _plot_macd(ax, df: pd.DataFrame):
    ax.plot(df.index, df["MACD_Line"], color="blue", linewidth=1.0, label="MACD")
    ax.plot(df.index, df["MACD_Signal"], color="red", linewidth=1.0, label="Signal")

    hist = df["MACD_Hist"]
    colors = np.where(hist >= 0, "forestgreen", "tomato")
    ax.bar(df.index, hist, color=colors, alpha=0.6, width=5, label="Histogram")

    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax.set_ylabel("MACD", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)


# ── Panel 3: RSI ─────────────────────────────────────────────────────────────

def _plot_rsi(ax, df: pd.DataFrame):
    ax.plot(df.index, df["RSI"], color="darkorange", linewidth=1.0, label="RSI(14)")
    ax.axhline(config.RSI_OVERBOUGHT, color="red", linewidth=0.8, linestyle="--")
    ax.axhline(config.RSI_OVERSOLD, color="green", linewidth=0.8, linestyle="--")

    # Shaded zones
    ax.fill_between(
        df.index,
        config.RSI_OVERBOUGHT,
        100,
        alpha=0.1,
        color="red",
        label="Overbought",
    )
    ax.fill_between(
        df.index,
        0,
        config.RSI_OVERSOLD,
        alpha=0.1,
        color="green",
        label="Oversold",
    )

    ax.set_ylim(0, 100)
    ax.set_ylabel("RSI", fontsize=11)
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    ax.grid(alpha=0.3)


# ── Panel 4: Volume ──────────────────────────────────────────────────────────

def _plot_volume(ax, df: pd.DataFrame):
    above_avg = df["Volume"] > df["Volume_MA"]
    vol_colors = np.where(above_avg, "steelblue", "lightgrey")
    ax.bar(df.index, df["Volume"], color=vol_colors, alpha=0.7, width=5, label="Volume")
    ax.plot(
        df.index,
        df["Volume_MA"],
        color="orange",
        linewidth=1.2,
        label=f"Vol MA({config.VOLUME_MA_PERIOD})",
    )
    ax.set_ylabel("Volume", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)

    # Format y-axis in millions
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x / 1e6:.0f}M")
    )


# ── Panel 5: Equity curve ────────────────────────────────────────────────────

def _plot_equity(ax, equity_df: pd.DataFrame, df: pd.DataFrame, initial_capital: float):
    ax.plot(
        equity_df.index,
        equity_df["Portfolio_Value"],
        color="steelblue",
        linewidth=1.4,
        label="Strategy",
    )

    # Buy & Hold benchmark
    bnh = (df["Close"] / df["Close"].iloc[0]) * initial_capital
    bnh = bnh.reindex(equity_df.index, method="ffill")
    ax.plot(bnh.index, bnh, color="grey", linewidth=1.0, linestyle="--", label="Buy & Hold")

    ax.axhline(initial_capital, color="black", linewidth=0.6, linestyle=":")
    ax.set_ylabel("Portfolio Value ($)", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)


# ── Public entry point ────────────────────────────────────────────────────────

def plot_all(
    df: pd.DataFrame,
    equity_df: pd.DataFrame,
    ticker: str = config.DEFAULT_TICKER,
    output_dir: str = config.PLOT_OUTPUT_DIR,
    show: bool = config.PLOT_SHOW,
    save: bool = config.PLOT_SAVE,
    initial_capital: float = config.INITIAL_CAPITAL,
) -> None:
    """Render all five strategy panels.

    Parameters
    ----------
    df          : DataFrame with price, indicators and signals.
    equity_df   : DataFrame from backtest.run_backtest.
    ticker      : Ticker symbol for chart title / filename.
    output_dir  : Directory to save PNG files.
    show        : Display the chart interactively.
    save        : Save the chart as a PNG file.
    initial_capital : Starting capital (for Buy & Hold normalisation).
    """
    fig, (ax1, ax2, ax3, ax4, ax5) = _setup_axes(ticker)

    _plot_price(ax1, df)
    _plot_macd(ax2, df)
    _plot_rsi(ax3, df)
    _plot_volume(ax4, df)
    _plot_equity(ax5, equity_df, df, initial_capital)

    _format_date_axis(ax5)

    plt.tight_layout()

    if save:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{ticker}_strategy.png")
        fig.savefig(path, dpi=120, bbox_inches="tight")
        print(f"Chart saved → {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)

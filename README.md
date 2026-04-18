# EMATraderWeekly

A Python-based trading strategy that uses **EMA9/EMA21 crossovers on weekly
timeframes**, confirmed by MACD, RSI, and Volume, with full backtesting via
Yahoo Finance (`yfinance`).

---

## 🏗️ Project Structure

```
ema_crossover_strategy/
├── __init__.py        # Package marker
├── config.py          # Parameters & thresholds
├── data_fetcher.py    # Yahoo Finance data download
├── indicators.py      # EMA, MACD, RSI, Volume calculations
├── signals.py         # Buy/Sell signal generation logic
├── backtest.py        # Backtesting engine
├── performance.py     # Metrics (Sharpe, drawdown, win rate)
├── visualize.py       # Charts and plots
└── main.py            # Entry point / orchestrator
requirements.txt       # Python dependencies
```

---

## 📦 Installation

```bash
pip install -r requirements.txt
```

---

## 🚀 Quick Start

```bash
# Run on AAPL (default ticker, 2015–2026)
python -m ema_crossover_strategy

# Custom ticker and date range
python -m ema_crossover_strategy --ticker MSFT --start 2018-01-01 --end 2026-01-01

# Batch: multiple tickers (charts saved, not displayed)
python -m ema_crossover_strategy --tickers AAPL MSFT GOOGL AMZN TSLA --no-show

# Suppress all output files
python -m ema_crossover_strategy --ticker SPY --no-show --no-save
```

All output (PNG charts and CSV trade logs) is written to the `output/`
directory by default.

---

## 🎯 Strategy Rules

### BUY Signal (all conditions must be true)
| # | Condition | Details |
|---|-----------|---------|
| 1 | EMA9 crosses **above** EMA21 | Golden Cross |
| 2 | MACD Histogram > 0 **or** MACD Line crosses above Signal | Bullish momentum |
| 3 | RSI **< 70** (not overbought) | Bonus: RSI < 30 → Strong Buy |
| 4 | Volume **> 20-week Volume MA** | Conviction confirmation |

### SELL Signal (all conditions must be true)
| # | Condition | Details |
|---|-----------|---------|
| 1 | EMA9 crosses **below** EMA21 | Death Cross |
| 2 | MACD Histogram < 0 **or** MACD Line crosses below Signal | Bearish momentum |
| 3 | RSI **> 30** (not oversold) | Bonus: RSI > 70 → Strong Sell |
| 4 | Volume **> 20-week Volume MA** | Conviction confirmation |

---

## 📊 Indicators

| Indicator | Window | Purpose |
|-----------|--------|---------|
| EMA9 | 9 weeks | Fast signal line |
| EMA21 | 21 weeks | Slow trend line |
| MACD Line | EMA12 − EMA26 | Momentum |
| MACD Signal | EMA9 of MACD | Smoothed momentum |
| MACD Histogram | MACD − Signal | Momentum direction |
| RSI | 14 periods (Wilder) | Overbought / oversold |
| Volume MA | 20-week SMA | Volume confirmation |

---

## 🔁 Backtest Parameters

| Parameter | Default |
|-----------|---------|
| Initial Capital | $100,000 |
| Position Sizing | 100% of capital |
| Commission | 0.1% per trade |
| Slippage | 0.05% per trade |
| Trailing Stop-Loss | 5% |

---

## 📈 Performance Metrics

Total Return, CAGR, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor,
Total Trades, Avg Trade Duration, Best/Worst Trade, Buy & Hold comparison.

---

## 📉 Charts

Five panels are generated for every ticker:

1. **Price** with EMA9/EMA21 overlay and buy (▲) / sell (▼) markers
2. **MACD** — line, signal line, histogram
3. **RSI** — with oversold (< 30) and overbought (> 70) shaded zones
4. **Volume** — bars with 20-week MA; above-average bars highlighted
5. **Equity Curve** — strategy portfolio value vs Buy & Hold benchmark

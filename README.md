# EMATraderWeekly

**Python EMA9/EMA21 Weekly Moving Average Crossover Trading Strategy**

A fully self-contained backtesting system that uses Yahoo Finance weekly OHLCV data to implement, test, and visualise an EMA crossover strategy confirmed by MACD, RSI, and Volume.

---

## Table of Contents

1. [Strategy Logic](#strategy-logic)
2. [Project Structure](#project-structure)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [Understanding the Outputs](#understanding-the-outputs)
7. [Running Tests](#running-tests)
8. [Risk Disclaimer](#risk-disclaimer)

---

## Strategy Logic

### Indicators

| Indicator | Settings | Purpose |
|-----------|----------|---------|
| **EMA9** | 9-week EWM | Fast signal line |
| **EMA21** | 21-week EWM | Slow trend line |
| **MACD** | 12 / 26 / 9 | Momentum confirmation |
| **RSI** | 14-period Wilder | Overbought / oversold filter |
| **Volume MA** | 20-week SMA | Volume confirmation |

### BUY Signal (all conditions must be true)

```
1. EMA9 crosses ABOVE EMA21   → golden cross
2. MACD histogram > 0         → bullish momentum
3. RSI < 70                   → not overbought
   RSI < 30 → labelled STRONG_BUY (oversold bounce)
4. Volume > 20-week average   → conviction confirmation
```

### SELL Signal (all conditions must be true)

```
1. EMA9 crosses BELOW EMA21   → death cross
2. MACD histogram < 0         → bearish momentum
3. RSI > 30                   → not oversold
   RSI > 70 → labelled STRONG_SELL (overbought reversal)
4. Volume > 20-week average   → conviction confirmation
```

### Backtest Parameters

| Parameter | Default |
|-----------|---------|
| Initial capital | $100,000 |
| Commission | 0.1 % per leg |
| Trailing stop | 5 % |
| Position sizing | 100 % of capital |

---

## Project Structure

```
EMATraderWeekly/
├── config.py          # All tunable parameters
├── data_fetcher.py    # Yahoo Finance weekly OHLCV download
├── indicators.py      # EMA, MACD, RSI, Volume MA calculations
├── signals.py         # BUY / SELL signal generation
├── backtest.py        # Backtesting engine
├── performance.py     # Metrics (Sharpe, drawdown, win rate …)
├── visualize.py       # Multi-panel strategy chart
├── main.py            # CLI entry point
├── requirements.txt   # Python dependencies
├── tests/
│   ├── test_indicators.py
│   └── test_signals.py
└── README.md
```

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/VenkatRedddy/EMATraderWeekly.git
cd EMATraderWeekly

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Quick Start

### Run with defaults (AAPL, 2015–2026)

```bash
python main.py
```

### Run with a custom ticker and date range

```bash
python main.py MSFT 2018-01-01 2026-01-01
```

### Save the chart to a file (no interactive window)

```bash
python main.py TSLA 2018-01-01 2026-01-01 --save-chart tsla_strategy.png
```

### Save the trade log to CSV

```bash
python main.py AAPL --save-trades aapl_trades.csv
```

### Skip the visualisation entirely

```bash
python main.py --no-chart
```

---

## Configuration

Edit **`config.py`** to change any strategy parameter without touching the logic files:

```python
DEFAULT_TICKER   = "AAPL"
DEFAULT_START    = "2015-01-01"
DEFAULT_END      = "2026-01-01"

EMA_FAST         = 9           # fast EMA window
EMA_SLOW         = 21          # slow EMA window

MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9

RSI_PERIOD       = 14
RSI_OVERSOLD     = 30.0
RSI_OVERBOUGHT   = 70.0

VOLUME_MA_PERIOD = 20

INITIAL_CAPITAL  = 100_000.0
COMMISSION_RATE  = 0.001       # 0.1 % per trade leg
TRAILING_STOP_PCT = 0.05       # 5 % trailing stop

RISK_FREE_RATE   = 0.04        # annualised, for Sharpe ratio
```

---

## Understanding the Outputs

### Console metrics

```
─────────────────────────────────────────────
  PERFORMANCE METRICS
─────────────────────────────────────────────
  Initial Capital ($)               100000.0
  Final Capital ($)                 184321.45
  Total Return (%)                  84.32
  Annualised Return / CAGR (%)      7.23
  Sharpe Ratio                      0.8541
  Max Drawdown (%)                  -18.45
  Total Trades                      12
  Win Rate (%)                      58.33
  Profit Factor                     1.78
  Avg Profit per Trade ($)          7026.79
  Avg Trade Duration (weeks)        14.2
  Buy-and-Hold Return (%)           312.5
─────────────────────────────────────────────
```

| Metric | Interpretation |
|--------|---------------|
| **Total Return** | Cumulative P&L over the backtest period |
| **CAGR** | Compound annual growth rate — comparable across different time spans |
| **Sharpe Ratio** | Risk-adjusted return; >1.0 is considered good |
| **Max Drawdown** | Worst peak-to-trough portfolio decline |
| **Win Rate** | Percentage of trades that were profitable |
| **Profit Factor** | Gross profit ÷ gross loss; >1.0 means net profitable |
| **Buy-and-Hold** | Passive benchmark — hold throughout the entire period |

### Chart panels (top to bottom)

1. **Price + EMA** — Closing price with EMA9 (orange) and EMA21 (purple); green triangles = BUY, red triangles = SELL; green shading = active trade periods.
2. **MACD** — MACD line (blue), signal line (orange), histogram (green/red bars).
3. **RSI** — RSI(14) with 30 (green) and 70 (red) reference lines; shaded zones.
4. **Volume** — Weekly volume bars (green = above average); orange line = 20-week MA.
5. **Equity Curve** — Strategy portfolio value (blue) vs. buy-and-hold benchmark (grey dashed).

### Trade log columns

| Column | Description |
|--------|-------------|
| `entry_date` | Date the position was opened |
| `entry_price` | Close price at entry |
| `entry_reason` | Signal conditions met at entry |
| `exit_date` | Date the position was closed |
| `exit_price` | Close price at exit |
| `exit_reason` | Why position was closed (sell signal, trailing stop, or end of data) |
| `shares` | Number of shares held |
| `profit` | Net profit/loss in USD (after commission) |
| `return_pct` | Trade return as a percentage |

---

## Running Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run only indicator tests
pytest tests/test_indicators.py -v

# Run only signal tests
pytest tests/test_signals.py -v
```

---

## Risk Disclaimer

> ⚠️ **This software is for educational and research purposes only.**
>
> - EMA crossovers are **lagging indicators** — signals confirm trends *after* they begin; whipsaws are common in sideways markets.
> - Weekly timeframes produce fewer signals but allow larger drawdowns before an exit is triggered.
> - Past performance in backtests **does not guarantee future results**.
> - All indicators use only past data at each decision point (no look-ahead bias).
> - **Paper trade** and validate thoroughly before risking real capital.
> - This tool does not constitute financial or investment advice.
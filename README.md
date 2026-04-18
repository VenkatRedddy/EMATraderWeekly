# EMATraderWeekly

**Python EMA9/EMA21 Weekly Moving Average Crossover Trading Strategy + TradingView-style Stock Screener**

A fully self-contained backtesting system *and* automated weekly screener that uses Yahoo Finance weekly OHLCV data to implement, test, and visualise an EMA crossover strategy confirmed by MACD, RSI, and Volume — with TradingView-style pre-filters, email and WhatsApp alerts when a crossover fires.

---

## Table of Contents

1. [Strategy Logic](#strategy-logic)
2. [Stock Screener — TradingView-style Filters](#stock-screener--tradingview-style-filters)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Quick Start — Single Stock Backtest](#quick-start--single-stock-backtest)
6. [TradingView Screener Quick Start](#tradingview-screener-quick-start)
7. [Weekly EMA Crossover Screener](#weekly-ema-crossover-screener)
   - [How It Works](#how-it-works)
   - [Running the Screener](#running-the-screener)
   - [Screener Configuration](#screener-configuration)
   - [Sample Output Table](#sample-output-table)
   - [Email Notifications Setup](#email-notifications-setup)
   - [WhatsApp Notifications Setup](#whatsapp-notifications-setup)
   - [Scheduling (Cron)](#scheduling-cron)
8. [Configuration — Backtest](#configuration--backtest)
9. [Understanding the Outputs](#understanding-the-outputs)
10. [Running Tests](#running-tests)
11. [Risk Disclaimer](#risk-disclaimer)

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

## Stock Screener

The screener replicates a **TradingView-style breakout scanner**.  It applies 8 pre-filters on daily data, then — for stocks that pass — checks for a weekly **EMA9/EMA21 crossover** signal.  Results are written to a CSV file sorted by highest average volume.

### Pre-filters (applied in order)

| # | Filter | Default threshold | Data source |
|---|--------|-------------------|-------------|
| 1 | **Price** | ≥ $3.00 USD (latest close) | Yahoo daily OHLCV |
| 2 | **% Change** | > 0.5 % (close vs previous close) | Yahoo daily OHLCV |
| 3 | **Market Cap** | ≥ $300 M USD | `yfinance` `.info` |
| 4 | **Analyst Rating** | Buy, Strong Buy, or Neutral | `yfinance` `recommendationKey` |
| 5 | **EMA(50)** | < latest close (daily) | Calculated from daily OHLCV |
| 6 | **EMA(21)** | < latest close (daily) | Calculated from daily OHLCV |
| 7 | **Avg Volume 10D** | > 500,000 shares | 10-day rolling avg of daily volume |
| 8 | **ADR%** | ≥ 2.0 % (avg of (High−Low)/Close over 14 days) | Calculated from daily OHLCV |

> **Missing data handling:** If market cap or analyst data cannot be fetched from Yahoo Finance, the ticker is skipped or the analyst filter is soft-skipped with a warning logged to the console.

### Weekly crossover signal (for stocks passing all 8 filters)

| Signal | Meaning |
|--------|---------|
| `GOLDEN_CROSS` | EMA9 crossed **above** EMA21 in the most recent weekly bar |
| `DEATH_CROSS` | EMA9 crossed **below** EMA21 in the most recent weekly bar |
| `HOLD` | No crossover in the most recent weekly bar |

### Output CSV columns

| Column | Description |
|--------|-------------|
| `ticker` | Stock symbol |
| `close` | Latest daily close price (USD) |
| `change_pct` | % change vs previous close |
| `market_cap` | Market capitalisation (USD) |
| `analyst_rating` | Yahoo Finance `recommendationKey` |
| `ema21_daily` | Daily EMA(21) value |
| `ema50_daily` | Daily EMA(50) value |
| `avg_volume_10d` | 10-day rolling average daily volume |
| `adr_pct` | Average Daily Range % (14-day rolling) |
| `pass_screener` | `True` if all 8 filters passed |
| `weekly_ema9` | Latest weekly EMA9 (only for passing stocks) |
| `weekly_ema21` | Latest weekly EMA21 (only for passing stocks) |
| `weekly_signal` | `GOLDEN_CROSS` / `DEATH_CROSS` / `HOLD` / `N/A` |
| `f_price` … `f_adr` | Individual filter results (`True`/`False`/`None`) |

---

## Project Structure

```
EMATraderWeekly/
├── config.py           # All tunable parameters (strategy + screener filters)
├── data_fetcher.py     # Yahoo Finance OHLCV download + fundamentals fetch
├── indicators.py       # EMA, MACD, RSI, Volume MA, ADR calculations
├── signals.py          # BUY / SELL signal generation
├── screener.py         # TradingView-style 8-filter pre-screener logic
├── screener_main.py    # CLI entry point for the TradingView pre-screener
├── backtest.py         # Backtesting engine
├── performance.py      # Metrics (Sharpe, drawdown, win rate ...)
├── visualize.py        # Multi-panel strategy chart
├── main.py             # CLI entry point (single-stock backtest)
├── requirements.txt    # Python dependencies
│
├── screener/
│   ├── __init__.py
│   ├── screener_config.py  # Screener settings (universe, filters, notifications)
│   ├── stock_universe.py   # Symbol list fetcher (CSV / NSE / BSE / S&P500 / Nasdaq-100)
│   ├── screener.py         # Core EMA crossover screener logic
│   ├── notifier.py         # Email (SMTP) + WhatsApp (Twilio) alerts
│   ├── run_screener.py     # Headless CLI entry point
│   ├── sample_stocks_us.csv   # 50 large-cap US stocks
│   ├── sample_stocks_nse.csv  # 50 NSE (India) stocks
│   └── sample_stocks_bse.csv  # 50 BSE (India) stocks
│
├── tests/
│   ├── test_indicators.py
│   ├── test_signals.py
│   └── test_screener.py    # Screener unit tests (no network calls)
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

## Quick Start — Single Stock Backtest

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

---

## Weekly Screener

The screener replicates a TradingView-style breakout scanner with EMA9/EMA21 crossover detection,
minimum volume filter, and email + WhatsApp alerts.

### How It Works

1. Loads a configurable stock universe (CSV, NSE, BSE, S&P 500, or Nasdaq-100).
2. Downloads the last N weeks of weekly OHLCV data for every stock via Yahoo Finance.
3. Calculates **EMA9**, **EMA21**, and **10-week average volume** for each stock.
4. Detects whether EMA9 just crossed **above** (🟢 BULLISH / Golden Cross) or **below** (🔴 BEARISH / Death Cross) EMA21 in the latest completed week.
5. Applies the minimum average-volume filter (default: 500 K — matches the TradingView "Avg Volume 10D > 500K" filter).
6. Sorts all stocks by average weekly volume (descending) and writes `screener_results.csv`.
7. Sends email and/or WhatsApp alerts for every crossover stock that passes the volume filter.
8. Appends all signals to `screener_signals.log` for audit.

### Running the Screener

```bash
# Run with default settings (US sample list, volume ≥ 500K)
python screener/run_screener.py

# Use a different stock universe
python screener/run_screener.py --universe us_sp500
python screener/run_screener.py --universe nse_top
python screener/run_screener.py --universe us_nasdaq100

# Use a custom CSV of symbols
python screener/run_screener.py --csv my_watchlist.csv

# Raise the minimum volume filter to 1M
python screener/run_screener.py --min-volume 1000000

# Skip notifications even if enabled in config
python screener/run_screener.py --no-notify

# Verbose logging
python screener/run_screener.py --verbose
```

### Screener Configuration

Edit **`screener/screener_config.py`** (or copy it to `screener/screener_config_local.py` to keep credentials out of git):

```python
# ── Stock Universe ─────────────────────────────────────────────────────────
STOCK_UNIVERSE = "csv"            # csv | nse_top | bse_top | us_sp500 | us_nasdaq100
CSV_FILE       = "screener/sample_stocks_us.csv"

# ── Filters ────────────────────────────────────────────────────────────────
MIN_AVG_VOLUME = 500_000          # 10-week avg volume threshold
LOOKBACK_WEEKS = 60               # weeks of history to download

# ── EMA Settings ───────────────────────────────────────────────────────────
EMA_FAST = 9
EMA_SLOW = 21

# ── Output ─────────────────────────────────────────────────────────────────
OUTPUT_CSV = "screener_results.csv"
LOG_FILE   = "screener_signals.log"

# ── Email ──────────────────────────────────────────────────────────────────
EMAIL_ENABLED   = False
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_USE_TLS   = True
EMAIL_USER      = "your_email@gmail.com"   # or set SCREENER_EMAIL_USER env var
EMAIL_PASS      = "your_app_password"      # or set SCREENER_EMAIL_PASS env var
EMAIL_TO        = "recipient@example.com"  # or set SCREENER_EMAIL_TO env var

# ── WhatsApp (Twilio) ───────────────────────────────────────────────────────
WHATSAPP_ENABLED    = False
TWILIO_ACCOUNT_SID  = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN   = "your_twilio_auth_token"
TWILIO_FROM         = "whatsapp:+14155238886"   # Twilio sandbox number
TWILIO_TO           = "whatsapp:+1XXXXXXXXXX"   # your registered number
```

### Sample Output Table

```
══════════════════════════════════════════════════════════════════════════════════════════
  EMA Weekly Screener Results
══════════════════════════════════════════════════════════════════════════════════════════
 Symbol     Close    EMA9   EMA21  Avg_Volume_10W  Cross_Up  Cross_Down        Week
   NVDA   900.120  895.43  880.21      48,321,445      True       False  2024-04-15
   AAPL   174.610  173.80  171.55      62,140,832     False       False  2024-04-15
   MSFT   420.450  419.12  415.30      21,345,000     False       False  2024-04-15
   AMZN   184.300  183.10  180.45      38,220,100     False       False  2024-04-15
   TSLA   175.220  174.80  179.50     102,540,800     False        True  2024-04-15
    ...

  Total stocks screened: 50
  Full results saved  : screener_results.csv

══════════════════════════════════════════════════════════════════════════════════════════
  🚨 2 CROSSOVER SIGNAL(S) DETECTED
══════════════════════════════════════════════════════════════════════════════════════════

🟢 EMA Weekly Crossover Alert
────────────────────────────────────────
Stock     : NVDA
Signal    : BUY SIGNAL — EMA9 crossed ABOVE EMA21 (Golden Cross)
Price     : 900.1200
EMA9      : 895.4300
EMA21     : 880.2100
Avg Vol   : 48,321,445
Week      : 2024-04-15
────────────────────────────────────────

🔴 EMA Weekly Crossover Alert
────────────────────────────────────────
Stock     : TSLA
Signal    : SELL SIGNAL — EMA9 crossed BELOW EMA21 (Death Cross)
Price     : 175.2200
EMA9      : 174.8000
EMA21     : 179.5000
Avg Vol   : 102,540,800
Week      : 2024-04-15
────────────────────────────────────────
```

### Email Notifications Setup

1. Enable 2-Factor Authentication on your Gmail account.
2. Generate an **App Password** at <https://myaccount.google.com/apppasswords>.
3. Set credentials as environment variables (recommended):

```bash
export SCREENER_EMAIL_USER="your_email@gmail.com"
export SCREENER_EMAIL_PASS="your_16_char_app_password"
export SCREENER_EMAIL_TO="recipient@example.com"
```

4. Set `EMAIL_ENABLED = True` in `screener/screener_config.py`.

> **Other SMTP providers**: Change `EMAIL_SMTP_HOST` and `EMAIL_SMTP_PORT` accordingly
> (e.g., `smtp.office365.com:587` for Outlook).

### WhatsApp Notifications Setup

1. Sign up for a free account at <https://www.twilio.com/>.
2. In the Twilio Console, go to **Messaging → Try it out → Send a WhatsApp message**.
3. Follow the sandbox instructions: send the shown join code from your WhatsApp number to `+1 415 523 8886`.
4. Set credentials as environment variables:

```bash
export SCREENER_TWILIO_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export SCREENER_TWILIO_TOKEN="your_auth_token"
export SCREENER_TWILIO_FROM="whatsapp:+14155238886"
export SCREENER_TWILIO_TO="whatsapp:+91XXXXXXXXXX"   # your number
```

5. Set `WHATSAPP_ENABLED = True` in `screener/screener_config.py`.

### Scheduling (Cron)

Add to your crontab (`crontab -e`) to run every Monday at 8:00 AM:

```cron
0 8 * * 1  cd /path/to/EMATraderWeekly && /path/to/.venv/bin/python screener/run_screener.py >> /var/log/ema_screener.log 2>&1
```

---

## TradingView Screener Quick Start

### Scan the default watchlist

```bash
python screener_main.py
```

### Scan specific tickers

```bash
python screener_main.py --tickers AAPL MSFT NVDA GOOGL AMZN TSLA
```

### Write results to a custom CSV

```bash
python screener_main.py --output my_scan.csv
```

### Show only tickers that passed all filters

```bash
python screener_main.py --passing-only
```

---

## Configuration — Backtest & Screener Filters

Edit **`config.py`** to change any strategy or screener parameter without touching the logic files:

```python
# ── Strategy (backtest) ───────────────────────────────────────────────────────
DEFAULT_TICKER   = "AAPL"
DEFAULT_START    = "2015-01-01"
DEFAULT_END      = "2026-01-01"

EMA_FAST         = 9           # fast EMA window (weekly)
EMA_SLOW         = 21          # slow EMA window (weekly)

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

# ── Screener filters ──────────────────────────────────────────────────────────
SCREENER_TICKERS          = ["AAPL", "MSFT", ...]   # watchlist

SCREENER_MIN_PRICE        = 3.0          # Filter 1: close >= $3
SCREENER_MIN_CHANGE_PCT   = 0.5          # Filter 2: daily change > 0.5 %
SCREENER_MIN_MARKET_CAP   = 300_000_000  # Filter 3: market cap >= $300 M

# Filter 4: accepted analyst consensus values (Yahoo Finance format)
# 'buy'='Buy', 'strong_buy'='Strong Buy', 'hold'='Neutral' in TradingView
SCREENER_ANALYST_RATINGS  = ["buy", "strong_buy", "hold"]

SCREENER_EMA21_PERIOD     = 21           # Filter 6: daily EMA(21) < price
SCREENER_EMA50_PERIOD     = 50           # Filter 5: daily EMA(50) < price
SCREENER_MIN_AVG_VOLUME_10D = 500_000    # Filter 7: 10-day avg vol > 500 K
SCREENER_ADR_PERIOD       = 14           # ADR rolling window (trading days)
SCREENER_MIN_ADR_PCT      = 2.0          # Filter 8: ADR >= 2 %

SCREENER_DAILY_PERIOD     = "6mo"        # yfinance period for daily fetch
SCREENER_OUTPUT_CSV       = "screener_results.csv"
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

```bash
# Run only screener tests (no network calls)
pytest tests/test_screener.py -v
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


"""
config.py — Strategy parameters and thresholds.
All tunable settings live here so callers never have magic numbers.
"""

# ── Data ──────────────────────────────────────────────────────────────────────
DEFAULT_TICKER: str = "AAPL"
DEFAULT_START: str = "2015-01-01"
DEFAULT_END: str = "2026-01-01"
INTERVAL: str = "1wk"  # weekly bars from yfinance

# ── EMA windows ───────────────────────────────────────────────────────────────
EMA_FAST: int = 9
EMA_SLOW: int = 21

# ── MACD ──────────────────────────────────────────────────────────────────────
MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9

# ── RSI ───────────────────────────────────────────────────────────────────────
RSI_PERIOD: int = 14
RSI_OVERSOLD: float = 30.0
RSI_OVERBOUGHT: float = 70.0

# ── Volume ────────────────────────────────────────────────────────────────────
VOLUME_MA_PERIOD: int = 20

# ── Backtesting ───────────────────────────────────────────────────────────────
INITIAL_CAPITAL: float = 100_000.0
COMMISSION_RATE: float = 0.001   # 0.1 % per trade (one-way)
TRAILING_STOP_PCT: float = 0.05  # 5 % trailing stop loss

# ── Risk-free rate (annualised) for Sharpe calculation ────────────────────────
RISK_FREE_RATE: float = 0.04

# ── Screener filters (TradingView-style) ──────────────────────────────────────
# Default watchlist of tickers to scan.  Override as needed.
SCREENER_TICKERS: list = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "AVGO", "WMT", "AMD", "JPM", "V", "MA", "UNH", "XOM",
    "NFLX", "ADBE", "CRM", "INTC", "PYPL", "QCOM", "MU", "AMAT",
]

# 1. Minimum close price (USD)
SCREENER_MIN_PRICE: float = 3.0

# 2. Minimum % price change (day-over-day, using daily close vs previous close)
SCREENER_MIN_CHANGE_PCT: float = 0.5

# 3. Minimum market capitalisation (USD)
SCREENER_MIN_MARKET_CAP: float = 300_000_000.0  # 300 M

# 4. Allowed analyst consensus values from Yahoo Finance (recommendationKey).
#    Yahoo returns lowercase-with-underscores: 'buy', 'strong_buy', 'hold'.
#    'hold' corresponds to "Neutral" in TradingView.
SCREENER_ANALYST_RATINGS: list = ["buy", "strong_buy", "hold"]

# 5 & 6. Daily EMA periods that must be BELOW the latest close price
SCREENER_EMA21_PERIOD: int = 21
SCREENER_EMA50_PERIOD: int = 50

# 7. Minimum 10-day average daily volume (shares)
SCREENER_MIN_AVG_VOLUME_10D: float = 500_000.0

# 8. Average Daily Range: rolling period (trading days) and minimum threshold
SCREENER_ADR_PERIOD: int = 14
SCREENER_MIN_ADR_PCT: float = 2.0

# Fetch window for daily data (yfinance period string)
SCREENER_DAILY_PERIOD: str = "6mo"

# Output CSV path
SCREENER_OUTPUT_CSV: str = "screener_results.csv"

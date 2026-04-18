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

"""
config.py — Strategy parameters and thresholds.
All configurable values live here so they can be changed in one place.
"""

# ── Data ──────────────────────────────────────────────────────────────────────
DEFAULT_TICKER = "AAPL"
DEFAULT_START_DATE = "2015-01-01"
DEFAULT_END_DATE = "2026-01-01"
DATA_INTERVAL = "1wk"  # weekly bars

# ── EMA windows ───────────────────────────────────────────────────────────────
EMA_FAST = 9    # fast EMA period (weeks)
EMA_SLOW = 21   # slow EMA period (weeks)

# ── MACD parameters ───────────────────────────────────────────────────────────
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ── RSI parameters ────────────────────────────────────────────────────────────
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# ── Volume parameters ─────────────────────────────────────────────────────────
VOLUME_MA_PERIOD = 20  # 20-week volume moving average

# ── Backtest parameters ───────────────────────────────────────────────────────
INITIAL_CAPITAL = 100_000.0   # USD
COMMISSION = 0.001            # 0.1 % per trade (applied on entry AND exit)
SLIPPAGE = 0.0005             # 0.05 % per trade
STOP_LOSS_PCT = 0.05          # 5 % trailing stop-loss
POSITION_SIZE_PCT = 1.0       # 100 % of available capital per trade

# ── Output ────────────────────────────────────────────────────────────────────
PLOT_SHOW = True              # Set False to suppress interactive windows
PLOT_SAVE = True              # Save charts as PNG files
PLOT_OUTPUT_DIR = "output"    # Directory for saved charts / reports

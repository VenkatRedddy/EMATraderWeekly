"""
screener_config.py — All configurable settings for the EMA screener.

Copy this file to screener_config_local.py and edit that copy to keep your
credentials out of source control.  The run_screener.py entry point checks
for screener_config_local.py first and falls back to this file.

Environment variable overrides (highest priority):
    SCREENER_EMAIL_USER, SCREENER_EMAIL_PASS, SCREENER_EMAIL_TO
    SCREENER_TWILIO_SID, SCREENER_TWILIO_TOKEN
    SCREENER_TWILIO_FROM, SCREENER_TWILIO_TO
"""

import os

# ── Stock Universe ─────────────────────────────────────────────────────────────
# Choose ONE of: "csv", "nse_top", "bse_top", "us_sp500", "us_nasdaq100"
STOCK_UNIVERSE: str = "csv"

# Path to a CSV file with a column named "Symbol" (used when STOCK_UNIVERSE="csv")
# Bundled sample files: sample_stocks_nse.csv, sample_stocks_us.csv, sample_stocks_bse.csv
CSV_FILE: str = "screener/sample_stocks_us.csv"

# For "us_sp500" or "us_nasdaq100" these are fetched automatically via
# Wikipedia tables; no extra file needed.

# ── Screener Filters ───────────────────────────────────────────────────────────
# Minimum average 10-week volume (matches the TradingView "Avg Volume 10D > 500K" filter)
MIN_AVG_VOLUME: int = 500_000

# Number of weeks of history to download for indicator warm-up
LOOKBACK_WEEKS: int = 60

# ── EMA settings ──────────────────────────────────────────────────────────────
EMA_FAST: int = 9    # fast EMA period
EMA_SLOW: int = 21   # slow EMA period

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_CSV: str = "screener_results.csv"   # path for the sorted screener table
LOG_FILE: str = "screener_signals.log"     # append-only signal audit log

# ── Email Notifications ───────────────────────────────────────────────────────
EMAIL_ENABLED: bool = False          # set to True to activate
EMAIL_SMTP_HOST: str = "smtp.gmail.com"
EMAIL_SMTP_PORT: int = 587
EMAIL_USE_TLS: bool = True
# These should be set via environment variables in production:
EMAIL_USER: str = os.environ.get("SCREENER_EMAIL_USER", "your_email@gmail.com")
EMAIL_PASS: str = os.environ.get("SCREENER_EMAIL_PASS", "your_app_password")
EMAIL_TO: str = os.environ.get("SCREENER_EMAIL_TO", "recipient@example.com")
EMAIL_SUBJECT_PREFIX: str = "[EMA Screener]"

# ── WhatsApp / Twilio Notifications ───────────────────────────────────────────
WHATSAPP_ENABLED: bool = False        # set to True to activate
# Sign up at https://www.twilio.com/ and enable the WhatsApp Sandbox.
# Then fill in the values below (or set the corresponding env vars).
TWILIO_ACCOUNT_SID: str = os.environ.get("SCREENER_TWILIO_SID", "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
TWILIO_AUTH_TOKEN: str = os.environ.get("SCREENER_TWILIO_TOKEN", "your_twilio_auth_token")
# WhatsApp sandbox sender is always "whatsapp:+14155238886" for trial accounts.
TWILIO_FROM: str = os.environ.get("SCREENER_TWILIO_FROM", "whatsapp:+14155238886")
# Your WhatsApp-enabled number (must be verified in the Twilio sandbox).
TWILIO_TO: str = os.environ.get("SCREENER_TWILIO_TO", "whatsapp:+1XXXXXXXXXX")

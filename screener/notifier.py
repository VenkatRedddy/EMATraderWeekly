"""
notifier.py — Send EMA crossover alerts via email and/or WhatsApp (Twilio).

Public API
----------
send_notifications(signals, cfg)
    Sends email and/or WhatsApp messages for each crossover signal.

build_alert_message(signal) -> str
    Returns a human-readable alert string for a single crossover signal.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


def build_alert_message(signal: dict[str, Any]) -> str:
    """Build a human-readable alert for a single crossover signal.

    Parameters
    ----------
    signal : dict
        A crossover signal dict as produced by screener.run_screener().

    Returns
    -------
    str — multi-line alert text suitable for email body or WhatsApp message.
    """
    direction = signal["direction"]
    symbol = signal["symbol"]

    if direction == "BULLISH":
        emoji = "🟢"
        action = "BUY SIGNAL — EMA9 crossed ABOVE EMA21 (Golden Cross)"
    else:
        emoji = "🔴"
        action = "SELL SIGNAL — EMA9 crossed BELOW EMA21 (Death Cross)"

    # Build a key name like "ema9" regardless of fast/slow period
    ema_fast_key = next((k for k in signal if k.startswith("ema") and k != "ema21"), "ema9")
    ema_slow_key = next((k for k in signal if k.startswith("ema") and k != ema_fast_key), "ema21")

    lines = [
        f"{emoji} EMA Weekly Crossover Alert",
        "─" * 40,
        f"Stock     : {symbol}",
        f"Signal    : {action}",
        f"Price     : {signal['price']:.4f}",
        f"{ema_fast_key.upper():<10}: {signal[ema_fast_key]:.4f}",
        f"{ema_slow_key.upper():<10}: {signal[ema_slow_key]:.4f}",
        f"Avg Vol   : {signal['avg_volume']:,}",
        f"Week      : {signal['timestamp']}",
        "─" * 40,
    ]
    return "\n".join(lines)


def send_notifications(signals: list[dict[str, Any]], cfg) -> None:
    """Dispatch email and WhatsApp notifications for each crossover signal.

    Parameters
    ----------
    signals : list[dict]
        Crossover signals from screener.run_screener().
    cfg : module
        The screener_config module (or compatible object).
    """
    if not signals:
        logger.info("No crossover signals — no notifications to send.")
        return

    logger.info("Sending notifications for %d signal(s) …", len(signals))

    for signal in signals:
        message = build_alert_message(signal)
        subject = (
            f"{cfg.EMAIL_SUBJECT_PREFIX} "
            f"{'🟢 BULLISH' if signal['direction'] == 'BULLISH' else '🔴 BEARISH'} "
            f"— {signal['symbol']}"
        )

        if getattr(cfg, "EMAIL_ENABLED", False):
            _send_email(subject, message, cfg)

        if getattr(cfg, "WHATSAPP_ENABLED", False):
            _send_whatsapp(message, cfg)

    logger.info("Notification dispatch complete.")


# ── Email ──────────────────────────────────────────────────────────────────────

def _send_email(subject: str, body: str, cfg) -> None:
    """Send a plain-text email via SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.EMAIL_USER
        msg["To"] = cfg.EMAIL_TO
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(cfg.EMAIL_SMTP_HOST, cfg.EMAIL_SMTP_PORT) as server:
            if cfg.EMAIL_USE_TLS:
                server.starttls()
            server.login(cfg.EMAIL_USER, cfg.EMAIL_PASS)
            server.sendmail(cfg.EMAIL_USER, cfg.EMAIL_TO, msg.as_string())

        logger.info("Email sent to %s — %s", cfg.EMAIL_TO, subject)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send email: %s", exc)


# ── WhatsApp via Twilio ────────────────────────────────────────────────────────

def _send_whatsapp(body: str, cfg) -> None:
    """Send a WhatsApp message via the Twilio API.

    Setup instructions:
      1. Create a free Twilio account at https://www.twilio.com/
      2. Enable the Twilio Sandbox for WhatsApp in the Twilio console.
      3. Send "join <sandbox-keyword>" from your WhatsApp number to the
         sandbox number (+1 415 523 8886) to register your number.
      4. Fill in TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, and
         TWILIO_TO in screener_config.py (or via environment variables).
      5. Set WHATSAPP_ENABLED = True in screener_config.py.
    """
    try:
        from twilio.rest import Client  # type: ignore[import]
    except ImportError:
        logger.error(
            "twilio package not installed. "
            "Run: pip install twilio  to enable WhatsApp notifications."
        )
        return

    try:
        client = Client(cfg.TWILIO_ACCOUNT_SID, cfg.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=cfg.TWILIO_FROM,
            to=cfg.TWILIO_TO,
        )
        logger.info(
            "WhatsApp message sent to %s (SID: %s).", cfg.TWILIO_TO, message.sid
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send WhatsApp message: %s", exc)

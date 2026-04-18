#!/usr/bin/env python3
"""
run_screener.py — Headless entry point for the weekly EMA crossover screener.

Usage
-----
    # Use default config (screener/screener_config.py)
    python screener/run_screener.py

    # Override stock universe via CLI
    python screener/run_screener.py --universe us_sp500

    # Specify a custom CSV of symbols
    python screener/run_screener.py --csv my_symbols.csv

    # Increase minimum volume filter
    python screener/run_screener.py --min-volume 1000000

Cron example (runs every Monday at 8 AM):
    0 8 * * 1  cd /path/to/repo && python screener/run_screener.py >> /var/log/ema_screener.log 2>&1
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
import sys
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Make sure the repo root is importable ─────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_config():
    """Load screener config, preferring a local override file if present."""
    # Check for a local override first (not committed to git).
    local_cfg_path = _REPO_ROOT / "screener" / "screener_config_local.py"
    if local_cfg_path.exists():
        spec = importlib.util.spec_from_file_location("screener_config_local", local_cfg_path)
        cfg = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(cfg)  # type: ignore[union-attr]
        logger.info("Loaded local config from %s", local_cfg_path)
        return cfg
    from screener import screener_config as cfg  # type: ignore[attr-defined]
    return cfg


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Weekly EMA9/EMA21 crossover screener with email/WhatsApp alerts."
    )
    parser.add_argument(
        "--universe",
        choices=["csv", "nse_top", "bse_top", "us_sp500", "us_nasdaq100"],
        default=None,
        help="Override STOCK_UNIVERSE from config.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        metavar="FILE",
        help="Override CSV_FILE from config (path to symbol CSV).",
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=None,
        metavar="N",
        help="Override MIN_AVG_VOLUME from config.",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Override OUTPUT_CSV path.",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Skip email/WhatsApp notifications even if enabled in config.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = _load_config()

    # Apply CLI overrides
    if args.universe:
        cfg.STOCK_UNIVERSE = args.universe  # type: ignore[assignment]
    if args.csv:
        cfg.CSV_FILE = args.csv  # type: ignore[assignment]
    if args.min_volume is not None:
        cfg.MIN_AVG_VOLUME = args.min_volume  # type: ignore[assignment]
    if args.output:
        cfg.OUTPUT_CSV = args.output  # type: ignore[assignment]

    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║   EMA Weekly Crossover Screener              ║")
    logger.info("╚══════════════════════════════════════════════╝")
    logger.info("Universe    : %s", cfg.STOCK_UNIVERSE)
    logger.info("EMA periods : fast=%d  slow=%d", cfg.EMA_FAST, cfg.EMA_SLOW)
    logger.info("Min Avg Vol : %s", f"{cfg.MIN_AVG_VOLUME:,}")
    logger.info("Output CSV  : %s", cfg.OUTPUT_CSV)

    from screener.screener import run_screener
    from screener.notifier import send_notifications

    table, signals = run_screener(cfg)

    # ── Print summary table ────────────────────────────────────────────────────
    print("\n" + "═" * 90)
    print("  EMA Weekly Screener Results")
    print("═" * 90)

    if table.empty:
        print("  No results — check your symbol list and internet connection.")
    else:
        # Show top 20 by volume
        display_cols = [c for c in ["Symbol", "Close", f"EMA{cfg.EMA_FAST}", f"EMA{cfg.EMA_SLOW}",
                                     "Avg_Volume_10W", "Cross_Up", "Cross_Down", "Week"]
                        if c in table.columns]
        print(table[display_cols].head(20).to_string(index=False))
        print(f"\n  Total stocks screened: {len(table)}")
        print(f"  Full results saved  : {cfg.OUTPUT_CSV}")

    # ── Print crossover signals ────────────────────────────────────────────────
    if signals:
        print("\n" + "═" * 90)
        print(f"  🚨 {len(signals)} CROSSOVER SIGNAL(S) DETECTED")
        print("═" * 90)
        for sig in signals:
            from screener.notifier import build_alert_message
            print("\n" + build_alert_message(sig))
    else:
        print("\n  ✅ No EMA crossovers detected this week.")

    # ── Send notifications ─────────────────────────────────────────────────────
    if not args.no_notify:
        send_notifications(signals, cfg)
    else:
        logger.info("Notifications skipped (--no-notify flag).")

    return 0


if __name__ == "__main__":
    sys.exit(main())

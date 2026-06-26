"""Watchdog wrapper for manim-bot with exponential backoff.

Starts bot.py as a subprocess and auto-restarts on crash.
Backoff: 3s → 6s → 12s → 24s → 48s → 60s (cap).
Resets to 3s after a healthy run (>120s uptime).
Logs to logs/watchdog.log.
Sends Telegram notification on restart (if bot token configured).
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Resolve paths relative to this script's directory
SCRIPT_DIR = Path(__file__).resolve().parent
BOT_SCRIPT = SCRIPT_DIR / "bot.py"
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "watchdog.log"

RESTART_DELAY_BASE = 3
RESTART_DELAY_CAP = 60
HEALTHY_UPTIME = 120  # seconds — reset backoff if alive this long

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("watchdog")


def _notify_telegram(message: str) -> None:
    """Send a Telegram notification about watchdog restart (best-effort)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(SCRIPT_DIR / ".env")
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("WATCHDOG_NOTIFY_CHAT", "")
        if not token or not chat_id:
            return

        import httpx
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        httpx.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
    except Exception:
        pass  # Notifications are best-effort, don't crash watchdog


def main() -> None:
    delay = RESTART_DELAY_BASE
    restart_count = 0

    while True:
        logger.info(f"Starting bot: {BOT_SCRIPT}")
        started = time.monotonic()

        try:
            proc = subprocess.run(
                [sys.executable, str(BOT_SCRIPT)],
                cwd=str(SCRIPT_DIR),
            )
            exit_code = proc.returncode
        except KeyboardInterrupt:
            logger.info("Watchdog interrupted — exiting")
            break
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            exit_code = -1

        uptime = time.monotonic() - started
        restart_count += 1
        logger.info(f"Bot exited with code {exit_code} (uptime {uptime:.0f}s, restart #{restart_count})")

        # Notify owner on restart (but not on first start)
        if restart_count > 1:
            _notify_telegram(
                f"🔄 *Manim Bot restarted* (#{restart_count})\n"
                f"Exit code: `{exit_code}`\n"
                f"Uptime: `{uptime:.0f}s`\n"
                f"Next restart in `{delay}s`"
            )

        # Healthy run — reset backoff
        if uptime >= HEALTHY_UPTIME:
            delay = RESTART_DELAY_BASE
            restart_count = 0  # reset counter on healthy run

        logger.info(f"Restarting in {delay}s…")
        time.sleep(delay)
        delay = min(delay * 2, RESTART_DELAY_CAP)


if __name__ == "__main__":
    main()

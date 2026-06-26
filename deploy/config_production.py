"""Production configuration for Manim Bot deployed on Oracle Cloud / Linux server.

Environment variables override defaults.
Copy this to .env on the server and fill in secrets.
"""

import os
from pathlib import Path

_env_path = Path(__file__).parent / ".env"

# Manual .env loading (no dotenv dependency until pip install)
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _getint(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _getbool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("true", "1", "yes")


# ── Telegram ────────────────────────────────────────────────────────────────
BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
# Chat ID for watchdog notifications
WATCHDOG_NOTIFY_CHAT = _get("WATCHDOG_NOTIFY_CHAT", "")

# ── LLM: DashScope (Qwen 3.6 Plus for chat + vision) ──────────────────────
DASHSCOPE_API_KEY = _get("OPENAI_API_KEY")
CHAT_MODEL = _get("CHAT_MODEL", "qwen3.6-plus")
LLM_BASE_URL = _get("LLM_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")

# ── LLM: GPT-5.5 (self-hosted proxy for Manim code generation) ─────────────
GPT_BASE_URL = _get("GPT_PROXY_BASE_URL", "http://64.118.150.213:8080/v1")
GPT_API_KEY = _get("GPT_PROXY_API_KEY", DASHSCOPE_API_KEY)
GPT_MODEL = _get("MANIM_MODEL", "gpt-5.5")
GPT_REASONING_EFFORT = _get("GPT_REASONING_EFFORT", "xhigh")
GPT_MAX_RETRIES = _getint("GPT_MAX_RETRIES", 3)

# ── Manim rendering (server-optimized) ─────────────────────────────────────
MANIM_QUALITY = _get("MANIM_QUALITY", "-qm")     # 720p on server
MANIM_TIMEOUT = _getint("MANIM_TIMEOUT", 300)     # 5 min (faster server CPU)
MANIM_MAX_RETRIES = _getint("MANIM_MAX_RETRIES", 1)

# ── Queue / Concurrency ────────────────────────────────────────────────────
# Server has 12 GB RAM — can handle 2 concurrent renders
MAX_CONCURRENT_RENDERS = _getint("MAX_CONCURRENT_RENDERS", 2)

# ── Memory guard ────────────────────────────────────────────────────────────
MEMORY_THRESHOLD_PCT = _get("MEMORY_THRESHOLD_PCT", "85")

# ── Render directory ───────────────────────────────────────────────────────
RENDER_DIR = _get("RENDER_DIR", "/tmp/manim_render")

# ── Cloudflare D1 Cache (disabled by default) ──────────────────────────────
CF_API_TOKEN = _get("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT_ID = _get("CF_ACCOUNT_ID")
CF_DATABASE_ID = _get("CF_DATABASE_ID")
D1_ENABLED = bool(CF_API_TOKEN and CF_ACCOUNT_ID and CF_DATABASE_ID
                  and not CF_API_TOKEN.startswith("placeholder"))

# ── TTS / Voiceover ────────────────────────────────────────────────────────
VOICEOVER_ENABLED = _getbool("TTS_ENABLED", True)
TTS_ENABLED = VOICEOVER_ENABLED
TTS_VOICE = _get("TTS_VOICE", "en-US-AndrewMultilingualNeural")
TTS_RATE = _get("TTS_RATE", "+10%")
TTS_VOLUME = _get("TTS_VOLUME", "+0%")

# ── Media ───────────────────────────────────────────────────────────────────
FFMPEG_PATH = _get("FFMPEG_PATH", "ffmpeg")

# ── WebApp ──────────────────────────────────────────────────────────────────
WEBAPP_URL = _get("WEBAPP_URL", "")

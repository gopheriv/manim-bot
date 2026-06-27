"""Bot configuration loaded from .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the same directory as this script
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


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

# ── LLM: DashScope (Qwen 3.6 Plus for chat + vision) ──────────────────────
DASHSCOPE_API_KEY = _get("OPENAI_API_KEY")
CHAT_MODEL = _get("CHAT_MODEL", "qwen3.6-plus")
LLM_BASE_URL = _get("LLM_BASE_URL", "")

# ── LLM: Qwen 3.7 Max (for Manim code generation) ─────────────────────
GPT_BASE_URL = _get("GPT_BASE_URL", "")
GPT_API_KEY = _get("GPT_API_KEY", "")
GPT_MODEL = _get("MANIM_MODEL", "qwen3.7-max")
IMAGE_MODEL = _get("IMAGE_MODEL", "")
GPT_REASONING_EFFORT = _get("GPT_REASONING_EFFORT", "")
GPT_MAX_RETRIES = _getint("GPT_MAX_RETRIES", 2)

# ── LLM: Claude Opus 4.8 (Anthropic, for chat + vision) ────────────────────
CLAUDE_BASE_URL = _get("CLAUDE_BASE_URL", "")
CLAUDE_API_KEY = _get("CLAUDE_API_KEY")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-opus-4-8")

# ── LLM Provider switch: qwen or claude ─────────────────────────────────────
LLM_PROVIDER = _get("LLM_PROVIDER", "qwen").lower()

# ── Manim rendering ─────────────────────────────────────────────────────────
MANIM_QUALITY = _get("MANIM_QUALITY", "-qm")
MANIM_TIMEOUT = _getint("MANIM_TIMEOUT", 600)  # 10 minutes
MANIM_MAX_RETRIES = _getint("MANIM_MAX_RETRIES", 1)  # self-heal attempts

# ── Queue / Concurrency ─────────────────────────────────────────────────────
MAX_CONCURRENT_RENDERS = _getint("MAX_CONCURRENT_RENDERS", 1)  # 1 on i5/8GB RAM

# ── Cloudflare D1 Cache ─────────────────────────────────────────────────────
CF_API_TOKEN = _get("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT_ID = _get("CF_ACCOUNT_ID")
CF_DATABASE_ID = _get("CF_DATABASE_ID")
D1_ENABLED = bool(CF_API_TOKEN and CF_ACCOUNT_ID and CF_DATABASE_ID
                  and not CF_API_TOKEN.startswith("placeholder"))

# ── TTS / Voiceover ────────────────────────────────────────────────────────
VOICEOVER_ENABLED = _getbool("TTS_ENABLED", True)  # backward compat alias
TTS_ENABLED = VOICEOVER_ENABLED
TTS_VOICE = _get("TTS_VOICE", "en-US-AndrewMultilingualNeural")
TTS_RATE = _get("TTS_RATE", "+10%")
TTS_VOLUME = _get("TTS_VOLUME", "+0%")

# ── Media ───────────────────────────────────────────────────────────────────
FFMPEG_PATH = _get("FFMPEG_PATH", "ffmpeg")

# ── WebApp ──────────────────────────────────────────────────────────────────
WEBAPP_URL = _get("WEBAPP_URL", "")

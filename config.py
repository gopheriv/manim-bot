"""Bot configuration loaded from .env file."""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from the same directory as this script. load_dotenv() returns False
# when the file is absent — surface that instead of silently starting with no
# env vars (the bot would otherwise fail later with confusing runtime errors).
_env_path = Path(__file__).parent / ".env"
_DOTENV_LOADED = load_dotenv(_env_path)
if not _DOTENV_LOADED:
    logger.warning(
        ".env not found at %s — relying on process environment only. "
        "Required keys (TELEGRAM_BOT_TOKEN, GPT_API_KEY, …) may be missing.",
        _env_path,
    )


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _getint(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _getfloat(key: str, default: float = 0.0) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Truthy env values. Includes "on"/"y" — common forms that the old check missed.
_TRUE_VALUES = frozenset({"true", "1", "yes", "on", "y", "t"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off", "n", "f", ""})


def _getbool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in _TRUE_VALUES:
        return True
    if val in _FALSE_VALUES:
        return False
    return default


# ── Telegram ────────────────────────────────────────────────────────────────
BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")

# ── LLM: DashScope (Qwen 3.6 Plus for chat + vision) ──────────────────────
# DashScope is OpenAI-compatible, so the key historically lived under the
# OPENAI_API_KEY env name. Prefer an explicit DASHSCOPE_API_KEY when present,
# fall back to OPENAI_API_KEY for backward compatibility.
DASHSCOPE_API_KEY = _get("DASHSCOPE_API_KEY") or _get("OPENAI_API_KEY")
QWEN_API_KEY = DASHSCOPE_API_KEY  # same DashScope key, for judge fallback
CHAT_MODEL = _get("CHAT_MODEL", "qwen3.6-plus")
# DashScope's OpenAI-compatible base URL — shared by chat and the judge fallback
# (JUDGE_BASE_URL below intentionally points at the same endpoint).
LLM_BASE_URL = _get("LLM_BASE_URL", "")

# ── LLM: Qwen 3.7 Max (for Manim code generation) ─────────────────────
GPT_BASE_URL = _get("GPT_BASE_URL", "")
GPT_API_KEY = _get("GPT_API_KEY", "")
# Env key is MANIM_MODEL (the model used for Manim code-gen); the variable keeps
# the historical GPT_MODEL name. Accept GPT_MODEL too for forward consistency.
GPT_MODEL = _get("MANIM_MODEL") or _get("GPT_MODEL", "qwen3.7-max")
IMAGE_MODEL = _get("IMAGE_MODEL", "")
GPT_REASONING_EFFORT = _get("GPT_REASONING_EFFORT", "")
GPT_MAX_RETRIES = _getint("GPT_MAX_RETRIES", 2)

# ── LLM: Claude Opus 4.8 (Anthropic, for chat + vision) ────────────────────
CLAUDE_BASE_URL = _get("CLAUDE_BASE_URL", "")
CLAUDE_API_KEY = _get("CLAUDE_API_KEY")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-opus-4-8")

# ── LLM: GLM-5.2 (Baishan EdgeFN, Anthropic Messages format) ─────────────
GLM_BASE_URL = _get("GLM_BASE_URL", "")
GLM_API_KEY = _get("GLM_API_KEY", "")
GLM_MODEL = _get("GLM_MODEL", "GLM-5.2")

# ── LLM Provider switch: qwen or claude ─────────────────────────────────────
LLM_PROVIDER = _get("LLM_PROVIDER", "qwen").lower()

# ── Judge of AI Court (separate, STRONG model — correctness review only) ──────
# JUDGE_PROVIDER: "auto" prefers Claude (strongest) when CLAUDE_API_KEY is set,
# else falls back to the JUDGE_* OpenAI-compatible endpoint. Force with
# "claude" or "openai".
JUDGE_PROVIDER = _get("JUDGE_PROVIDER", "auto").lower()
# Same DashScope endpoint as LLM_BASE_URL — the judge fallback reuses it.
JUDGE_BASE_URL = _get("JUDGE_BASE_URL", "")
JUDGE_API_KEY = _get("JUDGE_API_KEY", "")
JUDGE_MODEL = _get("JUDGE_MODEL", "MiniMax-M3")
JUDGE_TIMEOUT = _getint("JUDGE_TIMEOUT", 60)
JUDGE_MAX_ITERATIONS = _getint("JUDGE_MAX_ITERATIONS", 2)

# ── Manim rendering ─────────────────────────────────────────────────────────
MANIM_QUALITY = _get("MANIM_QUALITY", "-qm")  # fallback only; render tier default wins
MANIM_TIMEOUT = _getint("MANIM_TIMEOUT", 600)  # 10 minutes
MANIM_MAX_RETRIES = _getint("MANIM_MAX_RETRIES", 1)  # self-heal attempts (code bugs only); matches .env

# ── Render tier (quality scales with available hardware) ─────────────────────
# auto = detect from RAM/CPU; or force cinematic | standard | constrained
RENDER_TIER = _get("RENDER_TIER", "auto").lower()
MANIM_FPS = _getint("MANIM_FPS", 0)  # 0 = use the tier's fps; >0 forces a value

# ── Code generation quality knobs ────────────────────────────────────────────
# Larger output ceiling so ambitious multi-scene code is not truncated. Raised
# to 24576: storyboard-driven generation (multiple beats) plus reasoning tokens
# were exceeding 16384 and getting cut off — truncation was the single largest
# cause of Judge rejections.
MANIM_MAX_OUTPUT_TOKENS = _getint("MANIM_MAX_OUTPUT_TOKENS", 32768)
# Enable Qwen "thinking" for the creative code-gen task. Safeguarded in llm.py:
# if a thinking response returns no content, it retries with thinking disabled.
MANIM_ENABLE_THINKING = _getbool("MANIM_ENABLE_THINKING", True)
# Reviewer-driven pre-render repair (education accuracy + low critic score).
REVIEW_REPAIR_ENABLED = _getbool("REVIEW_REPAIR_ENABLED", True)
CRITIC_REPAIR_THRESHOLD = _getfloat("CRITIC_REPAIR_THRESHOLD", 6.0)

# Storyboard / cinematography IR: generate a validatable beat/shot/timing/camera/
# narration plan BEFORE code, then implement it beat-by-beat. Graceful — failure
# falls back to the lighter scene-layout plan and today's behavior.
STORYBOARD_ENABLED = _getbool("STORYBOARD_ENABLED", True)

# Visual Metaphor Library: a curated registry of teaching metaphors (function as a
# machine, derivative as a sliding tangent, matrix as a warping grid…). When a
# prompt matches, the director gets a menu to choose a spine metaphor and the code
# generator gets a concrete, implementable Manim recipe for it. Graceful — no match
# (or disabled) simply adds nothing and the pipeline behaves as before.
VISUAL_METAPHORS_ENABLED = _getbool("VISUAL_METAPHORS_ENABLED", True)

# Best-of-N tournament: generate N candidates, render drafts in parallel on the
# cloud farm, vision-rank the ACTUAL frames, and keep the best. 1 = disabled
# (single candidate, today's behavior). Only activates when the cloud farm is
# available (rendering N locally on an 8 GB box is unsafe). Set BEST_OF_N=3 to
# enable. Fully graceful: any failure falls back to single-candidate generation.
BEST_OF_N = _getint("BEST_OF_N", 1)
BEST_OF_N_DRAFT_QUALITY = _get("BEST_OF_N_DRAFT_QUALITY", "-ql")  # drafts judged for composition

# ── Visual feedback loop (render → vision critique → regenerate) ─────────────
VISUAL_CRITIC_ENABLED = _getbool("VISUAL_CRITIC_ENABLED", True)
VISUAL_CRITIC_MAX_PASSES = _getint("VISUAL_CRITIC_MAX_PASSES", 1)
VISUAL_CRITIC_KEYFRAMES = _getint("VISUAL_CRITIC_KEYFRAMES", 4)
# Which provider scores rendered frames: "qwen" (default) or "claude".
VISION_PROVIDER = _get("VISION_PROVIDER", "qwen").lower()

# ── Cloud render farm (free GitHub Actions worker) ───────────────────────────
# Heavy/HD/best-of-N renders are dispatched to a GitHub Actions workflow on a
# (ideally public, for 16 GB/unlimited runners) worker repo, keeping the bot's
# own source private. Disabled until a worker repo + workflow are set up.
CLOUD_RENDER_ENABLED = _getbool("CLOUD_RENDER_ENABLED", False)
CLOUD_RENDER_REPO = _get("CLOUD_RENDER_REPO", "")          # e.g. "gopheriv/manim-render-worker"
CLOUD_RENDER_WORKFLOW = _get("CLOUD_RENDER_WORKFLOW", "render.yml")
CLOUD_RENDER_BRANCH = _get("CLOUD_RENDER_BRANCH", "main")
CLOUD_RENDER_TIMEOUT = _getint("CLOUD_RENDER_TIMEOUT", 3600)  # seconds to await a cloud job (60 min — long/deep renders)
CLOUD_RENDER_POLL = _getint("CLOUD_RENDER_POLL", 10)         # seconds between status polls

# ── Queue / Concurrency ─────────────────────────────────────────────────────
MAX_CONCURRENT_RENDERS = _getint("MAX_CONCURRENT_RENDERS", 1)  # 1 on i5/8GB RAM

# ── Cloudflare D1 Cache ─────────────────────────────────────────────────────
CF_API_TOKEN = _get("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT_ID = _get("CF_ACCOUNT_ID")
CF_DATABASE_ID = _get("CF_DATABASE_ID")


def _is_placeholder(val: str) -> bool:
    """True if a config value is empty or a leftover placeholder."""
    return not val or val.lower().startswith("placeholder")


# Every D1 credential must be real — a real token paired with placeholder
# account/database IDs would otherwise appear "enabled" and fail at query time.
D1_ENABLED = not any(
    _is_placeholder(v) for v in (CF_API_TOKEN, CF_ACCOUNT_ID, CF_DATABASE_ID)
)

# ── TTS / Voiceover ────────────────────────────────────────────────────────
# Two independently-controllable switches: VOICEOVER_ENABLED gates whether the
# bot narrates at all; TTS_ENABLED gates the text-to-speech synthesis. When only
# the legacy TTS_ENABLED key is set, it drives both (backward compat).
_TTS_LEGACY = _getbool("TTS_ENABLED", True)
VOICEOVER_ENABLED = _getbool("VOICEOVER_ENABLED", _TTS_LEGACY)
TTS_ENABLED = _getbool("TTS_ENABLED", True)
TTS_VOICE = _get("TTS_VOICE", "en-US-AndrewMultilingualNeural")
# TTS_RATE / TTS_VOLUME are edge-tts string deltas (e.g. "+10%"), not numbers.
TTS_RATE = _get("TTS_RATE", "+10%")
TTS_VOLUME = _get("TTS_VOLUME", "+0%")

# ── Media ───────────────────────────────────────────────────────────────────
FFMPEG_PATH = _get("FFMPEG_PATH", "ffmpeg")

# ── WebApp ──────────────────────────────────────────────────────────────────
# Optional Telegram WebApp URL. Empty by default — the inline "Open app" button
# is only shown when this is set to a deployed mini-app URL.
WEBAPP_URL = _get("WEBAPP_URL", "")


# ── Startup validation ───────────────────────────────────────────────────────
# Keys the bot cannot run without, given the currently-selected providers. Call
# validate_config() once at startup so misconfiguration fails fast and loudly
# instead of surfacing as a confusing runtime error mid-request.
def validate_config() -> list[str]:
    """Return a list of human-readable configuration problems (empty == OK)."""
    problems: list[str] = []

    if not BOT_TOKEN:
        problems.append("TELEGRAM_BOT_TOKEN is not set — the bot cannot connect to Telegram.")

    # Code generation always runs through the GPT_* (Manim) endpoint.
    if not GPT_API_KEY:
        problems.append("GPT_API_KEY is not set — Manim code generation will fail.")

    # The active chat/vision provider needs its credentials.
    if LLM_PROVIDER == "claude" and not CLAUDE_API_KEY:
        problems.append("LLM_PROVIDER=claude but CLAUDE_API_KEY is not set.")
    elif LLM_PROVIDER == "glm" and not GLM_API_KEY:
        problems.append("LLM_PROVIDER=glm but GLM_API_KEY is not set.")
    elif LLM_PROVIDER == "qwen" and not DASHSCOPE_API_KEY:
        problems.append("LLM_PROVIDER=qwen but no DASHSCOPE_API_KEY/OPENAI_API_KEY is set.")

    if CLOUD_RENDER_ENABLED and not CLOUD_RENDER_REPO:
        problems.append("CLOUD_RENDER_ENABLED=true but CLOUD_RENDER_REPO is not set.")

    return problems


def assert_config_valid() -> None:
    """Log every configuration problem and raise if any are fatal."""
    problems = validate_config()
    for p in problems:
        logger.error("CONFIG: %s", p)
    if problems:
        raise RuntimeError(
            f"{len(problems)} configuration problem(s) found — see logs above."
        )

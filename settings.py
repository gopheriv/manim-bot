"""
Per-user settings storage — JSON file-backed configuration with file locking.

Each chat can override:
  - voiceover_enabled: bool
  - tts_voice: str (edge-tts voice name)
  - tts_rate: str ("-50%" to "+100%")
  - theme: str (theme name)
  - quality: str ("-ql", "-qm", "-qh")

Falls back to global config.py defaults if no per-user override exists.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

try:
    from filelock import FileLock
except ImportError:
    # Degraded: no file lock if filelock not installed
    FileLock = None  # type: ignore

from config import TTS_VOICE, TTS_RATE, VOICEOVER_ENABLED, MANIM_QUALITY, LLM_PROVIDER

logger = logging.getLogger("settings")

SETTINGS_FILE = Path(__file__).parent / "user_settings.json"
SETTINGS_LOCK = SETTINGS_FILE.with_suffix(".json.lock")


def _acquire_lock():
    """Acquire a file lock for settings access."""
    if FileLock:
        lock = FileLock(str(SETTINGS_LOCK), timeout=5)
        lock.acquire()
        return lock
    return None


def _release_lock(lock):
    """Release the file lock."""
    if lock:
        try:
            lock.release()
        except Exception:
            pass


def _load() -> dict:
    """Load the entire settings file (thread-safe with file lock)."""
    lock = _acquire_lock()
    try:
        if not SETTINGS_FILE.exists():
            return {}
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse %s — starting fresh", SETTINGS_FILE, exc_info=True)
        return {}
    finally:
        _release_lock(lock)


def _save(data: dict) -> None:
    """Write the entire settings file (thread-safe with file lock)."""
    lock = _acquire_lock()
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    finally:
        _release_lock(lock)


# ── Public API ───────────────────────────────────────────────────────────────

def get(chat_id: int, key: str) -> str | bool:
    """Get a setting for a chat, falling back to global defaults."""
    data = _load()
    user = data.get(str(chat_id), {})

    if key == "voiceover_enabled":
        return user.get("voiceover_enabled", VOICEOVER_ENABLED)
    elif key == "tts_voice":
        return user.get("tts_voice", TTS_VOICE)
    elif key == "tts_rate":
        return user.get("tts_rate", TTS_RATE)
    elif key == "theme":
        return user.get("theme", "visual_math")
    elif key == "quality":
        return user.get("quality", MANIM_QUALITY)
    elif key == "provider":
        return user.get("provider", LLM_PROVIDER)
    else:
        raise KeyError(f"Unknown setting: {key}")


def get_all(chat_id: int) -> dict:
    """Get all settings for a chat (with defaults filled in)."""
    return {
        "voiceover_enabled": get(chat_id, "voiceover_enabled"),
        "tts_voice": get(chat_id, "tts_voice"),
        "tts_rate": get(chat_id, "tts_rate"),
        "theme": get(chat_id, "theme"),
        "quality": get(chat_id, "quality"),
        "provider": get(chat_id, "provider"),
    }


def set(chat_id: int, key: str, value) -> None:
    """Set a single setting for a chat."""
    data = _load()
    cid = str(chat_id)
    if cid not in data:
        data[cid] = {}
    data[cid][key] = value
    _save(data)
    logger.info("Set %s=%s for chat_id=%d", key, value, chat_id)


def set_many(chat_id: int, updates: dict) -> None:
    """Set multiple settings for a chat at once."""
    data = _load()
    cid = str(chat_id)
    if cid not in data:
        data[cid] = {}
    data[cid].update(updates)
    _save(data)
    logger.info("Updated settings for chat_id=%d: %s", chat_id, updates)


def reset(chat_id: int) -> None:
    """Remove all per-user overrides for a chat (revert to global defaults)."""
    data = _load()
    data.pop(str(chat_id), None)
    _save(data)
    logger.info("Reset settings for chat_id=%d", chat_id)


# ── Available TTS voices (popular English ones) ─────────────────────────────

AVAILABLE_VOICES = [
    ("en-US-ChristopherNeural", "Christopher (US, Male)"),
    ("en-US-JennyNeural", "Jenny (US, Female)"),
    ("en-US-AriaNeural", "Aria (US, Female)"),
    ("en-US-GuyNeural", "Guy (US, Male)"),
    ("en-US-DavisNeural", "Davis (US, Male)"),
    ("en-US-TonyNeural", "Tony (US, Male)"),
    ("en-GB-RyanNeural", "Ryan (UK, Male)"),
    ("en-GB-SoniaNeural", "Sonia (UK, Female)"),
    ("en-AU-WilliamNeural", "William (AU, Male)"),
    ("en-AU-NatashaNeural", "Natasha (AU, Female)"),
]

AVAILABLE_THEMES = [
    ("visual_math", "📐 Visual Math", "Premium explainer style with semantic color"),
    ("default", "🎨 Default", "Standard Manim dark theme"),
    ("nord", "🧊 Nord", "Deep slate, pastel blues, minimal"),
    ("cyberpunk", "💜 Cyberpunk", "Black, neon pink/cyan, glowing"),
    ("chalkboard", "📝 Chalkboard", "Dark green, chalk white, rough"),
]

AVAILABLE_QUALITIES = [
    ("-l", "⚡ Preview", "480p @ 15fps", "~1-2 min (fastest)"),
    ("-ql", "🚀 Fast", "480p @ 15fps", "~2-4 min"),
    ("-qm", "✅ Standard", "720p @ 60fps", "~5-8 min"),
    ("-qh", "🎬 High", "1080p @ 60fps", "~10-15 min"),
]

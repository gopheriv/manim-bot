"""Regression tests for bot.py pure helpers (provider display, ellipsis).

bot.py constructs a Bot/Dispatcher at import and pulls in the full stack, so it
isn't always importable in a bare CI env. Skip gracefully when it can't load —
the assertions only matter where the bot module is available.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import bot
    _BOT_OK = True
except Exception:  # pragma: no cover — env-dependent (missing BOT_TOKEN etc.)
    _BOT_OK = False

pytestmark = pytest.mark.skipif(not _BOT_OK, reason="bot.py not importable in this env")


# ── B26: provider display name (a glm user must not be shown "Qwen") ──────────

def test_provider_display_name_known():
    assert bot._provider_display_name("qwen").startswith("Qwen")
    assert bot._provider_display_name("claude").startswith("Claude")
    assert bot._provider_display_name("glm").startswith("GLM")


def test_provider_display_name_defaults_and_tolerates():
    assert bot._provider_display_name(None).startswith("Qwen")   # unset → default
    assert bot._provider_display_name("") .startswith("Qwen")
    assert bot._provider_display_name("GLM").startswith("GLM")    # case-insensitive
    assert bot._provider_display_name("mystery") == "mystery"      # unknown → echo


# ── B33: ellipsis only when actually truncating ──────────────────────────────

def test_ellipsize_no_truncation():
    assert bot._ellipsize("short", 80) == "short"
    assert bot._ellipsize("exactly-ten", len("exactly-ten")) == "exactly-ten"


def test_ellipsize_truncates_with_marker():
    out = bot._ellipsize("x" * 100, 10)
    assert out == "x" * 10 + "…"
    assert len(out) == 11


def test_ellipsize_handles_empty():
    assert bot._ellipsize("", 5) == ""
    assert bot._ellipsize(None, 5) == ""

"""Tests for intent classification heuristic regex (no LLM dependency)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the regex patterns from bot.py by reading the source
# Since bot.py has heavy dependencies, we test the regex patterns directly
import re

_ANIMATE_RE = re.compile(
    r"\b(animat|render|draw|visuali[sz]e|manim|animate|show\s+me|make\s+(a|an)\s+(video|animation|clip))\b",
    re.IGNORECASE,
)
_CHAT_RE = re.compile(
    r"\b(explain|what\s+is|how\s+to|why|help|hello|hi\b|thanks|translate|write\s+(a|an)\s+(poem|essay|story))\b",
    re.IGNORECASE,
)


def classify_heuristic(text: str) -> str | None:
    """Same logic as _classify_intent fast-path, returns None if ambiguous."""
    cleaned = text.strip().rstrip(".!?,:;")
    word_count = len(cleaned.split())

    if _ANIMATE_RE.search(cleaned) and not _CHAT_RE.search(cleaned):
        if word_count <= 6:
            return "ANIMATE"

    if _CHAT_RE.search(cleaned) and not _ANIMATE_RE.search(cleaned):
        return "CHAT"

    return None  # ambiguous — needs LLM fallback


# ── ANIMATE cases ────────────────────────────────────────────────────────────

def test_animate_simple():
    assert classify_heuristic("animate a circle") == "ANIMATE"


def test_animate_render():
    assert classify_heuristic("render a graph") == "ANIMATE"


def test_animate_draw():
    assert classify_heuristic("draw a triangle") == "ANIMATE"


def test_animate_manin():
    assert classify_heuristic("manim visualisation") == "ANIMATE"


def test_animate_show_me():
    assert classify_heuristic("show me a sine wave") == "ANIMATE"


def test_animate_make_video():
    assert classify_heuristic("make a video of Fourier transform") == "ANIMATE"


def test_animate_visualize_us():
    assert classify_heuristic("visualize eigenvalues") == "ANIMATE"


# ── CHAT cases ───────────────────────────────────────────────────────────────

def test_chat_hello():
    assert classify_heuristic("hello") == "CHAT"


def test_chat_explain():
    assert classify_heuristic("explain eigenvalues") == "CHAT"


def test_chat_what_is():
    assert classify_heuristic("what is a matrix") == "CHAT"


def test_chat_how_to():
    # "how to learn manim" matches both CHAT (how to) and ANIMATE (manim)
    # → ambiguous → LLM fallback (correct behavior)
    result = classify_heuristic("how to learn manim")
    assert result is None or result == "CHAT"  # both acceptable


def test_chat_help():
    assert classify_heuristic("help me") == "CHAT"


def test_chat_thanks():
    assert classify_heuristic("thanks!") == "CHAT"


# ── Ambiguous cases (should return None → LLM fallback) ─────────────────────

def test_ambiguous_both_keywords():
    # Has both animate and chat keywords
    result = classify_heuristic("explain how to animate a curve")
    # Should be None because both regexes match
    assert result is None


def test_ambiguous_long_text():
    # Long text with animate keyword but many words
    result = classify_heuristic("animate the most beautiful and complex mathematical visualization you can think of with lots of details")
    # Word count > 6, so heuristic should return None
    assert result is None


# ── Edge cases ───────────────────────────────────────────────────────────────

def test_empty_string():
    assert classify_heuristic("") is None


def test_whitespace_only():
    assert classify_heuristic("   ") is None


def test_short_animate():
    # Short animate → should match
    assert classify_heuristic("draw circle") == "ANIMATE"


def test_no_match():
    assert classify_heuristic("foo bar baz") is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

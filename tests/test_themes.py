"""3Blue1Brown theme (WP3): registered everywhere, looked up, and cycles cleanly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import settings as user_settings
from themes import ALL_THEMES, THEME_ORDER, get_theme, next_theme, build_theme_prompt


def test_threeblue1brown_registered():
    assert "threeblue1brown" in ALL_THEMES
    assert "threeblue1brown" in THEME_ORDER


def test_threeblue1brown_lookup_and_palette():
    t = get_theme("threeblue1brown")
    assert t.name == "3Blue1Brown"
    assert t.bg_color == "#000000"
    # Structured palette: (primary, accent/insight, transform, contrast, text).
    assert len(t.colors) == 5
    prompt = build_theme_prompt(t)
    assert "#000000" in prompt
    assert "3Blue1Brown" in prompt


def test_theme_cycle_reaches_new_theme_and_wraps():
    seen, cur = set(), THEME_ORDER[0]
    for _ in range(len(THEME_ORDER)):
        seen.add(cur)
        cur = next_theme(cur)
    assert "threeblue1brown" in seen
    assert cur == THEME_ORDER[0]  # full loop wraps back to the start


def test_webapp_settings_accepts_new_theme():
    # CRITICAL: the Mini App validates the theme key against AVAILABLE_THEMES — the
    # theme is silently rejected from settings if it's missing from this list.
    keys = {key for key, _label, _desc in user_settings.AVAILABLE_THEMES}
    assert "threeblue1brown" in keys

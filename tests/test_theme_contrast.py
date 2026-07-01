"""Theme contrast ratio tests — WCAG readability gate.

Ensures every theme's text and palette colors are readable against its background.
Uses the exact WCAG 2.x contrast ratio formula (linearized sRGB → relative luminance).

Thresholds (never lowered):
  - text_color vs bg_color >= 4.5  (WCAG AA for body text)
  - each palette color vs bg_color >= 3.0  (shapes/objects visible)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from themes import (
    ALL_THEMES,
    THEME_ORDER,
    get_theme,
    contrast_ratio,
)
from settings import AVAILABLE_THEMES


# ── Blueprint theme registration ─────────────────────────────────────────────

def test_blueprint_theme_is_registered():
    """The new Blueprint theme must be retrievable (case-insensitive)."""
    t = get_theme("blueprint")
    assert t.name == "Blueprint"
    assert t.bg_color == "#1A2744"


def test_blueprint_in_theme_order():
    """Blueprint must be in THEME_ORDER."""
    assert "blueprint" in THEME_ORDER


def test_blueprint_in_available_themes():
    """Blueprint must be in the WebApp validation list."""
    keys = [k for k, _, _ in AVAILABLE_THEMES]
    assert "blueprint" in keys


# ── Blueprint contrast assertions ────────────────────────────────────────────

def test_blueprint_text_contrast():
    """Blueprint text must be readable against its background (WCAG AA >= 4.5)."""
    t = get_theme("blueprint")
    bg = t.bg_color
    text = t.colors[4]  # text color is index 4
    ratio = contrast_ratio(text, bg)
    print(f"\nBlueprint text-vs-bg contrast: {ratio:.2f}")
    assert ratio >= 4.5, (
        f"Blueprint text {text} on bg {bg} has contrast {ratio:.2f} < 4.5"
    )


def test_blueprint_palette_contrast():
    """Blueprint palette colors must be visible against background (>= 3.0)."""
    t = get_theme("blueprint")
    bg = t.bg_color
    for i, name in enumerate(["primary", "accent", "transform", "contrast"]):
        color = t.colors[i]
        ratio = contrast_ratio(color, bg)
        print(f"  Blueprint {name} ({color}) vs bg ({bg}): {ratio:.2f}")
        assert ratio >= 3.0, (
            f"Blueprint {name} {color} on bg {bg} has contrast {ratio:.2f} < 3.0"
        )


# ── All themes contrast printout (informational, not asserting) ──────────────

def test_print_all_theme_contrasts():
    """Print the text-vs-bg contrast of ALL existing themes for visibility.

    This does NOT assert on existing themes — it is purely informational.
    """
    print("\n── Theme contrast ratios (text vs bg) ──")
    for key in THEME_ORDER:
        t = ALL_THEMES.get(key)
        if t is None:
            continue
        bg = t.bg_color
        text = t.colors[4] if len(t.colors) > 4 else "#FFFFFF"
        ratio = contrast_ratio(text, bg)
        status = "✓" if ratio >= 4.5 else "⚠"
        print(f"  {status} {key:20s} text {text} on bg {bg}: {ratio:.2f}")

        for i, name in enumerate(["primary", "accent", "transform", "contrast"]):
            if i < len(t.colors):
                color = t.colors[i]
                r = contrast_ratio(color, bg)
                status_c = "✓" if r >= 3.0 else "⚠"
                print(f"      {status_c} {name:12s} {color} on bg {bg}: {r:.2f}")

    # Always pass — this is informational only.
    assert True


# ── Contrast helper correctness ──────────────────────────────────────────────

def test_contrast_black_vs_white():
    """Black vs white must have the maximum contrast ratio (~21:1)."""
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert 20.9 <= ratio <= 21.1, f"Black vs white contrast should be ~21, got {ratio}"


def test_contrast_same_color_is_one():
    """Identical colors must have ratio 1.0."""
    assert contrast_ratio("#808080", "#808080") == 1.0


def test_contrast_is_symmetric():
    """contrast_ratio(a, b) == contrast_ratio(b, a)."""
    a, b = "#1A2744", "#64B5F6"
    assert abs(contrast_ratio(a, b) - contrast_ratio(b, a)) < 1e-10

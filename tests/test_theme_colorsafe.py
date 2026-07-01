"""Color-blind-safe theme tests — deuteranopia simulation gate.

Ensures the 'colorsafe' theme's palette colors stay distinguishable under
red-green color blindness (deuteranopia). Uses computed helpers only — no
typed-by-hand numbers.

Thresholds (never lowered):
  - contrast_ratio(text, bg) >= 4.5       (WCAG AA body text)
  - contrast_ratio(each palette color, bg) >= 3.0  (shapes visible)
  - color_distance(a, b) >= 60            (distinct normally)
  - color_distance(simulate_deuteranopia(a), simulate_deuteranopia(b)) >= 40
    (STILL distinct for a red-green color-blind viewer)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from itertools import combinations

from themes import (
    THEME_ORDER,
    get_theme,
    contrast_ratio,
    simulate_deuteranopia,
    color_distance,
)
from settings import AVAILABLE_THEMES


# ── Registration ─────────────────────────────────────────────────────────────

def test_colorsafe_theme_is_registered():
    t = get_theme("colorsafe")
    assert t.name == "ColorSafe"
    assert t.bg_color == "#101418"


def test_colorsafe_in_theme_order():
    assert "colorsafe" in THEME_ORDER


def test_colorsafe_in_available_themes():
    keys = [k for k, _, _ in AVAILABLE_THEMES]
    assert "colorsafe" in keys


# ── Helper sanity checks ─────────────────────────────────────────────────────

def test_simulate_deuteranopia_black_stays_black():
    assert simulate_deuteranopia("#000000") == "#000000"


def test_color_distance_of_self_is_zero():
    assert color_distance("#56B4E9", "#56B4E9") == 0.0


def test_color_distance_black_white():
    # sqrt(255² + 255² + 255²) ≈ 441.67
    d = color_distance("#000000", "#FFFFFF")
    assert 441.0 <= d <= 442.0, f"Black-white distance should be ~441.67, got {d}"


# ── ColorSafe contrast (readability) ─────────────────────────────────────────

def test_colorsafe_text_contrast():
    t = get_theme("colorsafe")
    bg = t.bg_color
    text = t.colors[4]
    ratio = contrast_ratio(text, bg)
    print(f"\nColorSafe text-vs-bg contrast: {ratio:.2f}")
    assert ratio >= 4.5, (
        f"ColorSafe text {text} on bg {bg} has contrast {ratio:.2f} < 4.5"
    )


def test_colorsafe_palette_contrast():
    t = get_theme("colorsafe")
    bg = t.bg_color
    for i, name in enumerate(["primary", "accent", "transform", "contrast"]):
        color = t.colors[i]
        ratio = contrast_ratio(color, bg)
        print(f"  ColorSafe {name} ({color}) vs bg ({bg}): {ratio:.2f}")
        assert ratio >= 3.0, (
            f"ColorSafe {name} {color} on bg {bg} has contrast {ratio:.2f} < 3.0"
        )


# ── ColorSafe pairwise distinctness (normal + deuteranopia) ──────────────────

_PALETTE_NAMES = ["primary", "accent", "transform", "contrast"]


def test_colorsafe_pairwise_distances():
    """Every pair must be distinct normally (>= 60) and under deuteranopia (>= 40)."""
    t = get_theme("colorsafe")
    colors = [t.colors[i] for i in range(4)]  # primary, accent, transform, contrast

    print("\n── ColorSafe pairwise distances ──")
    for (i, ni), (j, nj) in combinations(enumerate(_PALETTE_NAMES), 2):
        a, b = colors[i], colors[j]

        # Normal distance
        normal_dist = color_distance(a, b)
        print(f"  {ni} ({a}) vs {nj} ({b}):")
        print(f"    normal distance: {normal_dist:.1f}  ", end="")

        # Deuteranopia-simulated distance
        a_sim = simulate_deuteranopia(a)
        b_sim = simulate_deuteranopia(b)
        sim_dist = color_distance(a_sim, b_sim)
        print(f"simulated: {a_sim} vs {b_sim} = {sim_dist:.1f}")

        assert normal_dist >= 60, (
            f"ColorSafe {ni}/{nj} normal distance {normal_dist:.1f} < 60"
        )
        assert sim_dist >= 40, (
            f"ColorSafe {ni}/{nj} deuteranopia-simulated distance {sim_dist:.1f} < 40 "
            f"(colors {a}->{a_sim} and {b}->{b_sim} become too similar)"
        )

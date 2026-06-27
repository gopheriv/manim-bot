"""Tier-aware prompt assembly: ambition on capable HW, strict on the laptop."""

from render_tier import CINEMATIC, CONSTRAINED
from prompt_builder import build_manim_system_prompt, budget_block


def test_constrained_prompt_is_strict():
    s = build_manim_system_prompt(prompt="animate a fourier series", tier=CONSTRAINED)
    assert "exactly 3 layers" in s          # strict style
    assert "FORBIDDEN" in s                  # surface ban
    assert "HARDWARE BUDGET" in s


def test_cinematic_prompt_is_ambitious():
    s = build_manim_system_prompt(prompt="animate a fourier series", tier=CINEMATIC)
    assert "cinematic" in s.lower()
    assert "MovingCameraScene" in s          # camera allowed
    assert "exactly 3 layers" not in s
    assert "PERFORMANCE ENVELOPE" in s


def test_budget_block_respects_tier():
    assert "FORBIDDEN" in budget_block(CONSTRAINED)
    assert "FORBIDDEN" not in budget_block(CINEMATIC)

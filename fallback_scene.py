"""Deterministic fallback Manim scene generator.

Used when LLM-generated code fails to compile/render. The goal is to always
return a valid, lightweight animation instead of failing the user request.
"""

from __future__ import annotations

import re


def _safe_title(prompt: str, max_len: int = 54) -> str:
    title = re.sub(r"\s+", " ", prompt.strip()) or "Mathematical idea"
    title = title[:max_len].rstrip()
    title = title.replace("\\", "\\\\").replace('"', '\\"')
    return title


def build_fallback_scene(prompt: str, bg_color: str = "#0B1026") -> str:
    """Return ultra-conservative Manim CE code that renders quickly on low-RAM machines."""
    title = _safe_title(prompt)
    bg = bg_color.replace('"', "") or "#0B1026"

    return f'''from manim import *

class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        white = "#F8FAFC"
        blue = "#58C4DD"

        t = Text("{title}", font_size=32, color=white)
        self.play(FadeIn(t, shift=DOWN * 0.2), run_time=1.2)
        self.wait(0.8)
        self.play(FadeOut(t, shift=UP * 0.2), run_time=1.0)
        self.wait(0.5)
'''

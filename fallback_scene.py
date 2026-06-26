"""Deterministic fallback Manim scene generator.

Used when LLM-generated code fails to compile/render. The goal is to always
return a valid, lightweight animation instead of failing the user request.
"""

from __future__ import annotations

import re
from textwrap import indent


def _safe_title(prompt: str, max_len: int = 54) -> str:
    title = re.sub(r"\s+", " ", prompt.strip()) or "Mathematical idea"
    title = title[:max_len].rstrip()
    title = title.replace("\\", "\\\\").replace('"', '\\"')
    return title


def build_fallback_scene(prompt: str, bg_color: str = "#0B1026") -> str:
    """Return conservative Manim CE code that renders quickly."""
    title = _safe_title(prompt)
    bg = bg_color.replace('"', "") or "#0B1026"

    return f'''from manim import *
import numpy as np

class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        white = "#F8FAFC"
        blue = "#58C4DD"
        yellow = "#F5D547"
        teal = "#2DD4BF"
        coral = "#FF6B6B"

        title = Text("{title}", font_size=34, color=white)
        title.to_edge(UP, buff=0.35)
        title_bg = BackgroundRectangle(title, color="{bg}", fill_opacity=0.88, buff=0.18)
        title_group = VGroup(title_bg, title).set_z_index(10)

        plane = NumberPlane(
            x_range=[-5, 5, 1],
            y_range=[-3, 3, 1],
            x_length=9.5,
            y_length=4.8,
            background_line_style={{"stroke_color": "#334155", "stroke_width": 1, "stroke_opacity": 0.45}},
        ).shift(DOWN * 0.25)
        axes = Axes(
            x_range=[-5, 5, 1],
            y_range=[-2.5, 2.5, 1],
            x_length=9.5,
            y_length=4.3,
            tips=False,
            axis_config={{"color": white, "stroke_width": 2}},
        ).move_to(plane)

        curve = axes.plot(lambda x: 0.55 * np.sin(1.4 * x) + 0.18 * x, x_range=[-4.6, 4.6], color=blue, stroke_width=4)
        glow = curve.copy().set_stroke(blue, width=12, opacity=0.18)
        moving_x = ValueTracker(-4.4)
        dot = always_redraw(lambda: Dot(
            axes.c2p(moving_x.get_value(), 0.55 * np.sin(1.4 * moving_x.get_value()) + 0.18 * moving_x.get_value()),
            radius=0.08,
            color=yellow,
        ).set_z_index(8))

        idea = Text("A question becomes motion, structure, then insight", font_size=28, color=white)
        idea.to_edge(DOWN, buff=0.45)
        idea_bg = BackgroundRectangle(idea, color="{bg}", fill_opacity=0.85, buff=0.16)
        idea_group = VGroup(idea_bg, idea).set_z_index(10)

        nodes = VGroup()
        for i, x in enumerate([-3.2, -1.6, 0, 1.6, 3.2]):
            color = [coral, yellow, teal, blue, white][i]
            node = Circle(radius=0.18, color=color, stroke_width=3).move_to(axes.c2p(x, 0.55 * np.sin(1.4 * x) + 0.18 * x))
            nodes.add(node)

        self.play(FadeIn(title_group, shift=DOWN * 0.15), FadeIn(plane), FadeIn(axes), run_time=1.4)
        self.play(Create(glow), Create(curve), run_time=2.4, rate_func=smooth)
        self.add(dot)
        self.play(moving_x.animate.set_value(4.4), LaggedStart(*[FadeIn(n, scale=0.6) for n in nodes], lag_ratio=0.12), run_time=4.2, rate_func=smooth)
        self.play(FadeIn(idea_group, shift=UP * 0.15), run_time=1.2)

        pulse_t = ValueTracker(0)
        def breathe(mob, dt):
            pulse_t.increment_value(dt)
            mob.set_stroke(opacity=0.72 + 0.25 * np.sin(pulse_t.get_value() * 2.2))
        nodes.add_updater(breathe)
        self.wait(1.5)
'''

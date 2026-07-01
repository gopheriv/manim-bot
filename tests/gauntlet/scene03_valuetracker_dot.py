"""Gauntlet #3: ValueTracker + always_redraw dot on a curve (then clear_updaters)."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(x_range=[-3, 3], y_range=[-1, 9], x_length=10, y_length=6)
        graph = axes.plot(lambda x: x**2, color=BLUE)
        self.play(Create(axes), Create(graph), run_time=1.5)

        t = ValueTracker(-3)
        dot = always_redraw(lambda: Dot(
            axes.c2p(t.get_value(), t.get_value()**2),
            color=YELLOW, radius=0.08
        ))
        trail = TracedPath(dot.get_center, stroke_color=YELLOW, stroke_width=2)

        self.add(dot, trail)
        self.play(t.animate.set_value(3), run_time=4, rate_func=smooth)
        dot.clear_updaters()
        self.wait(0.5)

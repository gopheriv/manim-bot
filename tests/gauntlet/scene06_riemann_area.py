"""Gauntlet #6: Riemann rectangles → area (get_riemann_rectangles, get_area)."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(x_range=[0, 4], y_range=[0, 5], x_length=8, y_length=5)
        graph = axes.plot(lambda x: 0.25 * x**2 + 1, color=BLUE)

        # Riemann rectangles (animate dx shrinking)
        rects_thick = axes.get_riemann_rectangles(graph, x_range=[0.5, 3.5], dx=0.5, color=GREEN, fill_opacity=0.4)
        rects_thin = axes.get_riemann_rectangles(graph, x_range=[0.5, 3.5], dx=0.1, color=GREEN, fill_opacity=0.4)

        # Filled area
        area = axes.get_area(graph, x_range=[0.5, 3.5], color=YELLOW, fill_opacity=0.3)

        self.play(Create(axes), Create(graph), run_time=1.5)
        self.play(FadeIn(rects_thick), run_time=1)
        self.play(Transform(rects_thick, rects_thin), run_time=2)
        self.play(FadeOut(rects_thick), FadeIn(area), run_time=1.5)
        self.wait(0.5)

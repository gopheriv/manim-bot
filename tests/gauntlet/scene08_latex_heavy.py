"""Gauntlet #8: LaTeX-heavy derivation — substrings_to_isolate + set_color_by_tex."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        # Color-map specific substrings
        eq = MathTex(
            r"f(x) = x^2 + 3x + 2",
            substrings_to_isolate=["x^2", "3x", "2"],
            font_size=40,
        )
        eq.set_color_by_tex("x^2", BLUE)
        eq.set_color_by_tex("3x", YELLOW)
        eq.set_color_by_tex("2", GREEN)
        eq.move_to(UP * 2)

        # Match colors on axes
        axes = Axes(x_range=[-3, 1], y_range=[-1, 7], x_length=8, y_length=5).shift(DOWN)
        graph = axes.plot(lambda x: x**2 + 3*x + 2, color=WHITE, x_range=[-3, 1])

        self.play(Write(eq), run_time=1.5)
        self.play(Create(axes), Create(graph), run_time=2)
        self.wait(0.5)

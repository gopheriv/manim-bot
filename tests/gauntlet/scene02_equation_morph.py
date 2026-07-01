"""Gauntlet #2: Equation morph (TransformMatchingTex)."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        eq1 = MathTex(r"(a+b)^2", font_size=48)
        eq2 = MathTex(r"a^2 + 2ab + b^2", font_size=48)

        self.play(Write(eq1), run_time=1)
        self.wait(0.5)
        self.play(TransformMatchingTex(eq1, eq2), run_time=2)
        self.wait(0.5)

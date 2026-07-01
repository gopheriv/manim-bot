"""GROUND-TRUTH TRUE POSITIVE — two text labels overlapping at the same point.

Both equations are drawn at ORIGIN, so the second lands on top of the first and the
result is an illegible tangle that PERSISTS in the settled frame.
Label: defect:overlap:center.
"""
from manim import *


class GenScene(Scene):
    def construct(self):
        a = MathTex(r"E = mc^2", font_size=60).move_to(ORIGIN)
        b = MathTex(r"p = mv", font_size=60).move_to(ORIGIN)  # same spot → overlaps a
        self.play(Write(a))
        self.play(Write(b))
        self.wait(1.0)

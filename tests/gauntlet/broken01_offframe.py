"""GROUND-TRUTH TRUE POSITIVE — object off the frame edge (top-right corner).

The circle + its label sit half outside the visible frame; the defect PERSISTS in
the settled frame. Label: defect:offframe:top_right.
"""
from manim import *


class GenScene(Scene):
    def construct(self):
        # Frame is ~14.22 x 8.0 units; right edge x≈7.11, top edge y≈4.0.
        # Center the circle at (7.5, 3.0) so its right half + top spill off-frame.
        circle = Circle(radius=1.5, color=YELLOW, fill_opacity=0.4).move_to(RIGHT * 7.5 + UP * 3.0)
        label = Text("result", font_size=40).move_to(RIGHT * 7.2 + UP * 1.0)  # right edge clips it
        self.play(Create(circle), Write(label))
        self.wait(1.0)

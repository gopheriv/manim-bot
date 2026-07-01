"""GROUND-TRUTH TRUE POSITIVE — three objects stacked at ORIGIN (cluttered mush).

A circle, a square and a text label are all placed at ORIGIN with no separation, so
they pile on top of each other into an unreadable clump that PERSISTS in the settled
frame. Label: defect:origin_stack:center.
"""
from manim import *


class GenScene(Scene):
    def construct(self):
        circle = Circle(radius=1.4, color=BLUE, fill_opacity=0.5).move_to(ORIGIN)
        square = Square(side_length=2.4, color=RED, fill_opacity=0.5).move_to(ORIGIN)
        label = Text("STACKED", font_size=48, color=WHITE).move_to(ORIGIN)
        self.play(Create(circle), Create(square), Write(label))
        self.wait(1.0)

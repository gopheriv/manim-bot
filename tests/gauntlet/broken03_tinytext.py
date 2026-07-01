"""GROUND-TRUTH TRUE POSITIVE — body text far too small to read (sub-10pt).

A readable title plus a paragraph at font_size=8 (well under any readable floor at
480p). The unreadable text PERSISTS in the settled frame.
Label: defect:tiny_text:center.
"""
from manim import *


class GenScene(Scene):
    def construct(self):
        title = Text("Theorem", font_size=48).to_edge(UP, buff=1.0)
        body = Text(
            "This crucial explanation is the whole point of the slide but it is "
            "rendered so small that no viewer could ever read a single word of it.",
            font_size=8,
        ).move_to(ORIGIN)
        self.play(Write(title))
        self.play(Write(body))
        self.wait(1.0)

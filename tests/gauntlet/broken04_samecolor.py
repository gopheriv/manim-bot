"""GROUND-TRUTH TRUE POSITIVE — text at near-zero contrast against the background.

A readable white title, plus body text whose colour (#161A22) is almost identical to
the background (#10131A) — present but unreadable. PERSISTS in the settled frame.
Label: defect:low_contrast:center.
"""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#10131A"
        title = Text("Key Result", font_size=46, color=WHITE).to_edge(UP, buff=1.2)
        body = Text(
            "the contrast of this line is far too low for anyone to read it",
            font_size=30, color="#161A22",  # ~background → invisible
        ).move_to(ORIGIN)
        self.play(Write(title))
        self.play(Write(body))
        self.wait(1.0)

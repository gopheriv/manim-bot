"""Gauntlet #10: Vectors on a plane — Arrow(buff=0) + GrowArrow + labels."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        plane = NumberPlane(
            x_range=[-5, 5], y_range=[-3, 3],
            background_line_style={"stroke_opacity": 0.2},
        )
        self.play(Create(plane), run_time=1)

        v1 = Arrow(start=ORIGIN, end=[3, 1, 0], color=BLUE, buff=0, stroke_width=4)
        v2 = Arrow(start=ORIGIN, end=[1, 2, 0], color=RED, buff=0, stroke_width=4)
        lbl1 = MathTex(r"\vec{v}_1", font_size=30, color=BLUE).next_to(v1.get_end(), UR, buff=0.1)
        lbl2 = MathTex(r"\vec{v}_2", font_size=30, color=RED).next_to(v2.get_end(), UL, buff=0.1)

        self.play(GrowArrow(v1), Write(lbl1), run_time=1)
        self.play(GrowArrow(v2), Write(lbl2), run_time=1)
        self.wait(0.5)

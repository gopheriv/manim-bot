"""Gauntlet #9: Staggered reveal — LaggedStart over a VGroup."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        dots = VGroup(*[
            Dot(RIGHT * i * 0.8 + LEFT * 2, color=BLUE)
            for i in range(6)
        ])
        labels = VGroup(*[
            MathTex(str(i), font_size=24).next_to(d, DOWN, buff=0.2)
            for i, d in enumerate(dots)
        ])

        self.play(
            LaggedStart(*[FadeIn(d, shift=UP * 0.3) for d in dots], lag_ratio=0.15),
            run_time=2,
        )
        self.play(
            LaggedStart(*[Write(l) for l in labels], lag_ratio=0.1),
            run_time=1.5,
        )
        self.wait(0.5)

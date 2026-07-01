"""Gauntlet #4: Camera push-in — MUST use MovingCameraScene + self.camera.frame."""
from manim import *


class GenScene(MovingCameraScene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(x_range=[-3, 3], y_range=[-1, 9], x_length=10, y_length=6)
        graph = axes.plot(lambda x: x**2, color=BLUE)
        dot = Dot(axes.c2p(1, 1), color=YELLOW, radius=0.08)
        label = MathTex(r"(1, 1)", font_size=24, color=YELLOW).next_to(dot, UR, buff=0.1)

        self.play(Create(axes), Create(graph), FadeIn(dot), Write(label), run_time=1.5)

        # Push in on the dot
        self.camera.frame.save_state()
        self.play(
            self.camera.frame.animate.scale(0.3).move_to(dot.get_center()),
            run_time=2,
        )
        self.wait(0.5)

        # Pull back out
        self.play(Restore(self.camera.frame), run_time=1.5)
        self.wait(0.5)

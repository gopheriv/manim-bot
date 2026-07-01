"""Gauntlet #1: Function plot + labels (Axes.plot, get_axis_labels)."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-1, 9, 2],
            x_length=10,
            y_length=6,
            axis_config={"include_numbers": True, "font_size": 20},
            tips=True,
        )
        labels = axes.get_axis_labels(x_label="x", y_label="f(x)")
        graph = axes.plot(lambda x: x**2, color=BLUE, x_range=[-3, 3])
        graph_label = MathTex(r"f(x) = x^2", font_size=36, color=BLUE).next_to(graph, UR, buff=0.2)

        self.play(Create(axes), Write(labels), run_time=1.5)
        self.play(Create(graph), Write(graph_label), run_time=2)
        self.wait(0.5)

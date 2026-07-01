"""Gauntlet #7: Grid transform — NumberPlane + ApplyMatrix with ghost copy."""
from manim import *


class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        plane = NumberPlane(
            x_range=[-5, 5], y_range=[-3, 3],
            background_line_style={"stroke_opacity": 0.4},
        )
        # Ghost copy of original grid
        ghost = plane.copy().set_stroke(opacity=0.15)
        self.add(ghost)

        matrix = [[1, 1], [0, 1]]  # shear
        self.play(Create(plane), run_time=1)
        self.play(ApplyMatrix(matrix, plane), run_time=3)
        self.wait(0.5)

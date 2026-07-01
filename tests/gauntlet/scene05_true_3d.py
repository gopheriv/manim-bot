"""Gauntlet #5: TRUE 3D — ThreeDScene + set_camera_orientation + Surface."""
from manim import *
import numpy as np


class GenScene(ThreeDScene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        # Set up 3D camera orientation
        self.set_camera_orientation(phi=70 * DEGREES, theta=-30 * DEGREES)

        # Create a surface (paraboloid)
        surface = Surface(
            lambda u, v: np.array([u, v, 0.2 * (u**2 + v**2)]),
            u_range=[-2, 2],
            v_range=[-2, 2],
            checkerboard_colors=[BLUE_D, BLUE_E],
            resolution=(16, 16),
            fill_opacity=0.6,
        )

        # Add axes
        axes = ThreeDAxes(x_range=[-2, 2], y_range=[-2, 2], z_range=[-1, 3])

        self.play(Create(axes), FadeIn(surface), run_time=2)
        # Slow rotation to show 3D
        self.begin_ambient_camera_rotation(rate=0.1)
        self.wait(2)
        self.stop_ambient_camera_rotation()

"""Complex analysis templates: Mandelbrot, contour integrals."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class MandelbrotTemplate(SceneTemplate):
    """Mandelbrot set zoom revealing self-similarity."""
    name = "mandelbrot"
    keywords = ["mandelbrot", "fractal", "complex", "zoom", "self-similar", "iteration", "julia", "set"]
    category = "complex_analysis"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Mandelbrot Set", font_size=36, color="{color}")
title.to_edge(UP)
eq = MathTex(r"z_{{n+1}} = z_n^2 + c", font_size=36, color=WHITE)
eq.to_edge(UP, buff=1.2)
self.play(Write(title, run_time=1.5), Write(eq, run_time=1.5))

# Mandelbrot set as parametric surface
# For simplicity, show the boundary curve using angle parameterization
def mandelbrot_escape(c, max_iter=50):
    z = 0
    for n in range(max_iter):
        z = z**2 + c
        if abs(z) > 2:
            return n / max_iter
    return 0

# Show the set outline
outline = ParametricFunction(
    lambda t: 2 * np.array([math.cos(t), math.sin(t), 0]),
    t_range=[0, TAU],
    color="{color}",
)
outline.set_stroke(width=2)

# Draw approximate Mandelbrot boundary using key points
boundary_points = [
    np.array([-2, 0, 0]),
    np.array([-0.75, 0.5, 0]),
    np.array([0.25, 0.5, 0]),
    np.array([0.5, 0, 0]),
    np.array([0.25, -0.5, 0]),
    np.array([-0.75, -0.5, 0]),
    np.array([-2, 0, 0]),
]

boundary = VGroup()
for i in range(1, len(boundary_points)):
    boundary.add(Line(boundary_points[i-1], boundary_points[i], color="{color}", stroke_width=2))
self.play(Create(boundary), run_time=1.5)

# Label main cardioid
cardioid = MathTex(r"\\text{{Main Cardioid}}", font_size=24, color="#F59E0B")
cardioid.move_to(np.array([-0.5, 0, 0]))
self.play(Write(cardioid), run_time=1)

# Zoom animation (simulated)
zoom_text = Text("Zooming into self-similar region...", font_size=24, color=WHITE)
zoom_text.to_edge(DOWN)
self.play(Write(zoom_text), run_time=1)

# Mini mandelbrot (smaller copy)
mini_points = [p * 0.2 + np.array([0.3, 0, 0]) for p in boundary_points]
mini_boundary = VGroup()
for i in range(1, len(mini_points)):
    mini_boundary.add(Line(mini_points[i-1], mini_points[i], color="#10B981", stroke_width=2))
self.play(Create(mini_boundary), run_time=1)

self.wait(2)
""")


class ContourIntegralTemplate(SceneTemplate):
    """Contour integration in the complex plane."""
    name = "contour_integral"
    keywords = ["contour", "integral", "residue", "pole", "complex plane", "cauchy", "path"]
    category = "complex_analysis"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Contour Integration", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

# Complex plane
axes = Axes(
    x_range=[-3, 3, 1], y_range=[-2.5, 2.5, 1],
    x_length=8, y_length=6,
)
axes.to_edge(DOWN)
re_label = Text("Re", font_size=16)
re_label.next_to(axes.x_axis, RIGHT)
im_label = Text("Im", font_size=16)
im_label.next_to(axes.y_axis, UP)
self.play(Create(axes), Write(re_label), Write(im_label), run_time=1)

# Contour (unit circle)
contour = Circle(radius=1.5, color="{color}", stroke_width=2)
contour.move_to(axes.c2p(0, 0))
contour_glow = contour.copy().set_stroke(width=8, opacity=0.15).set_fill(opacity=0)
self.add(contour_glow)
self.play(Create(contour, run_time=2))

# Poles inside contour
pole = Dot(axes.c2p(0.5, 0.3), color="#F59E0B", radius=0.1)
pole_label = MathTex("z_0", font_size=20, color="#F59E0B")
pole_label.next_to(pole, UR)
self.play(FadeIn(pole), Write(pole_label), run_time=1)

# Cauchy's integral formula
cauchy = MathTex(r"\\oint_C f(z)\\,dz = 2\\pi i \\sum \\text{{Res}}(f, z_k)", font_size=28)
cauchy.to_edge(UP, buff=1)
self.play(Write(cauchy, run_time=2))

# Arrow showing direction of integration
arrow_tip = Triangle(color=WHITE).scale(0.1)
arrow_tip.move_to(contour.get_top())
arrow_tip.rotate(PI/2)
self.play(FadeIn(arrow_tip), run_time=0.5)

self.wait(2)
""")

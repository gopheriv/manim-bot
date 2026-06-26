"""Calculus templates: Riemann sum, gradient descent, integration."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class RiemannSumTemplate(SceneTemplate):
    """Riemann sum approximation of an integral with converging rectangles."""
    name = "riemann_sum"
    keywords = ["riemann", "integral", "area", "rectangle", "sum", "approximate", "under curve", "definite"]
    category = "calculus"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Riemann Sum Approximation", font_size=36, color="{color}")
title.to_edge(UP)
axes = Axes(x_range=[0, 4, 1], y_range=[0, 3, 0.5], x_length=10, y_length=5)
axes.to_edge(DOWN)
self.play(Write(title, run_time=1.5), Create(axes, run_time=1))

# Function: f(x) = x^2 / 4 + 0.5
def f(x):
    return x**2 / 4 + 0.5

curve = ParametricFunction(
    lambda t: axes.c2p(t, f(t)),
    t_range=[0, 4],
    color="{color}",
)
curve.set_stroke(width=3)
curve_glow = curve.copy().set_stroke(width=12, opacity=0.15).set_fill(opacity=0)
self.add(curve_glow)
self.play(Create(curve, run_time=2))

# Label
eq_label = MathTex(r"f(x) = \frac{{x^2}}{{4}} + 0.5", font_size=28, color="{color}")
eq_label.to_corner(UR)
self.play(Write(eq_label, run_time=1))

# Show Riemann sums with increasing n
for n in [4, 8, 16, 32]:
    rects = VGroup()
    dx = 4.0 / n
    for i in range(n):
        x_i = i * dx
        h = f(x_i)
        rect = Rectangle(
            width=axes.x_axis.unit_size * dx,
            height=axes.y_axis.unit_size * h,
            fill_color="{color}",
            fill_opacity=0.3,
            stroke_color=WHITE,
            stroke_width=0.5,
        )
        rect.move_to(axes.c2p(x_i + dx/2, h/2), aligned_edge=ORIGIN)
        rects.add(rect)

    self.play(FadeIn(rects, run_time=1))

    area_label = MathTex(f"n = {n},\\; S = {{sum(f(i*dx)*dx for i in range(n)):.2f}}", font_size=24)
    area_label.to_corner(DL)
    self.play(FadeIn(area_label), run_time=0.5)
    self.wait(0.5)
    self.remove(area_label)

# True area
true_area = 4**3/12 + 0.5*4  # integral of x^2/4 + 0.5 from 0 to 4
final_label = MathTex(f"\\int_0^4 f(x)\\,dx = {true_area:.2f}", font_size=28, color="#10B981")
final_label.to_corner(DL)
self.play(Write(final_label, run_time=1))

self.wait(2)
""")


class GradientDescentTemplate(SceneTemplate):
    """Gradient descent finding minimum of a loss function."""
    name = "gradient_descent"
    keywords = ["gradient", "descent", "loss", "minimum", "optimize", "learn", "train", "cost"]
    category = "calculus"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Gradient Descent", font_size=36, color="{color}")
title.to_edge(UP)
# Loss function: L(w) = (w-2)^2 + 0.5
axes = Axes(x_range=[-1, 5, 1], y_range=[0, 10, 2], x_length=10, y_length=5)
axes.to_edge(DOWN)
self.play(Write(title, run_time=1.5), Create(axes, run_time=1))

loss_curve = ParametricFunction(
    lambda t: axes.c2p(t, (t - 2)**2 + 0.5),
    t_range=[-0.5, 4.5],
    color="{color}",
)
loss_curve.set_stroke(width=3)
eq = MathTex(r"L(w) = (w - 2)^2 + 0.5", font_size=28, color=WHITE)
eq.to_corner(UR)
self.play(Create(loss_curve, run_time=2), Write(eq, run_time=1))

# Gradient descent steps
lr = {config.extra_params.get('learning_rate', 0.3)}
w = 0.0
min_x = axes.c2p(2, 0.5)[0]
min_y = axes.c2p(2, 0.5)[1]

dot = Dot(color="#F59E0B", radius=0.12)
dot.move_to(axes.c2p(w, (w - 2)**2 + 0.5))
trail = VGroup(dot.copy().set_opacity(0.3))
self.add(trail, dot)

for step in range(5):
    grad = 2 * (w - 2)
    w_new = w - lr * grad

    old_point = axes.c2p(w, (w - 2)**2 + 0.5)
    new_point = axes.c2p(w_new, (w_new - 2)**2 + 0.5)

    line = Line(old_point, new_point, color="#10B981", stroke_width=2)
    trail.add(dot.copy().set_opacity(0.3))
    self.play(Create(line), dot.animate.move_to(new_point), run_time=0.5)
    w = w_new

# Label minimum
min_dot = Dot(axes.c2p(2, 0.5), color="#10B981", radius=0.1)
min_label = MathTex(r"w^* = 2", font_size=24, color="#10B981")
min_label.next_to(min_dot, DOWN)
self.play(FadeIn(min_dot), Write(min_label), run_time=1)
self.wait(0.5)

self.wait(2)
""")

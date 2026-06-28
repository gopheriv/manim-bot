"""Fourier series and transform templates."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class FourierSeriesTemplate(SceneTemplate):
    """Fourier series decomposition showing harmonics building up."""
    name = "fourier_series"
    keywords = ["fourier", "series", "harmonics", "decompose", "sine wave", "frequency", "sum", "wave", "spectrum"]
    category = "series_transforms"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        title = config.title or "Fourier Series Decomposition"
        n_terms = config.extra_params.get("n_terms", 5)

        return _common_manim_header() + _indent(f"""
title = Text("{title}", font_size=36, color="{color}")
title.to_edge(UP)
axes = Axes(x_range=[-4, 4, 1], y_range=[-1.5, 1.5, 0.5], x_length=10, y_length=4)
axes.to_edge(DOWN)
self.play(Write(title, run_time=1.5), Create(axes, run_time=1))

# Target: square wave approximation with Fourier series
# f(x) = 4/pi * sum(sin((2k-1)x) / (2k-1), k=1..n)
n_terms = {n_terms}
colors = {repr(config.colors[:5])}

# Build up term by term
partial_sum = lambda x: 0
current_curve = None

for k in range(1, n_terms + 1):
    n = 2 * k - 1
    term = lambda x, old=partial_sum: old(x) + (4 / math.pi) * math.sin(n * x) / n
    partial_sum = term

    # Recompute curve with more terms
    new_curve = ParametricFunction(
        lambda t, ps=partial_sum: axes.c2p(t, ps(t)),
        t_range=[-math.pi, math.pi],
        color=colors[(k-1) % len(colors)],
    )
    new_curve.set_stroke(width=2 + k * 0.3)

    # Label showing number of terms
    label = MathTex(f"n = {{k}}", font_size=24, color=colors[(k-1) % len(colors)])
    label.to_corner(UR)

    if current_curve:
        self.play(Transform(current_curve, new_curve), FadeIn(label), run_time=1.5)
    else:
        current_curve = new_curve
        self.play(Create(current_curve), FadeIn(label), run_time=1.5)

    self.wait(0.5)

self.wait(2)
""")


class LaplaceTransformTemplate(SceneTemplate):
    """Laplace transform visualization."""
    name = "laplace_transform"
    keywords = ["laplace", "transform", "s-domain", "integral transform", "poles", "zeros"]
    category = "series_transforms"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        a_val = config.extra_params.get('damping', 0.5)
        w_val = config.frequency
        return _common_manim_header() + _indent(f"""
title = Text("Laplace Transform", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

# Time domain function: e^(-at) * sin(wt)
a = {a_val}
w = {w_val}

eq_time = MathTex(r"f(t) = e^{{-{a_val}t}} \\sin({w_val}t)", font_size=32)
eq_time.to_edge(UP, buff=1)
self.play(Write(eq_time, run_time=1.5))

time_axes = Axes(x_range=[0, 10, 1], y_range=[-1, 1, 0.5], x_length=5, y_length=3)
time_axes.to_edge(LEFT, buff=1)
time_label = Text("Time Domain", font_size=20)
time_label.next_to(time_axes, UP)
self.play(Create(time_axes), Write(time_label))

time_curve = ParametricFunction(
    lambda t: time_axes.c2p(t, math.exp(-a * t) * math.sin(w * t)),
    t_range=[0, 10],
    color="{color}",
)
time_curve.set_stroke(width=2)
self.play(Create(time_curve, run_time=2))

# Frequency domain (magnitude plot)
eq_freq = MathTex(r"F(s) = \\frac{{w}}{{(s + a)^2 + w^2}}", font_size=28)
eq_freq.to_edge(RIGHT, buff=2)
self.play(Write(eq_freq, run_time=1.5))

freq_axes = Axes(x_range=[-2, 5, 1], y_range=[0, 1.5, 0.5], x_length=5, y_length=3)
freq_axes.to_edge(RIGHT, buff=1)
freq_label = Text("Frequency Domain", font_size=20)
freq_label.next_to(freq_axes, UP)
self.play(Create(freq_axes), Write(freq_label))

# Magnitude: |F(s)| at s = iw
mag_curve = ParametricFunction(
    lambda s: freq_axes.c2p(s, w / math.sqrt((s + a)**2 + w**2) if s > -2 else 0),
    t_range=[-1, 5],
    color="#10B981",
)
mag_curve.set_stroke(width=2)
self.play(Create(mag_curve, run_time=2))

self.wait(2)
""")

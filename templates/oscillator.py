"""Oscillator templates: damped, driven, coupled, pendulum."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class DampedOscillatorTemplate(SceneTemplate):
    """Damped harmonic oscillator with phase space diagram."""
    name = "damped_oscillato"
    keywords = ["damp", "oscillat", "harmonic", "spring", "pendulum", "bounce", "vibrat", "wave", "frequency"]
    category = "oscillato"

    def generate_code(self, config: TemplateConfig) -> str:
        damping = config.damping
        freq = config.frequency
        color = config.colors[0]
        title = config.title or "Damped Harmonic Oscillato"
        equation = config.equation or r"x'' + 2\zeta\omega x' + \omega^2 x = 0"
        dur = min(config.duration, 15)  # cap at 15s for safety

        return _common_manim_header() + _indent(f"""
# Title
title = Text("{title}", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

# Equation
eq = MathTex(r"{equation}", font_size=32, color=WHITE)
eq.next_to(title, DOWN, buff=0.3)
self.play(FadeIn(eq, run_time=1))

# Axes
axes = Axes(
    x_range=[0, {dur}, 1],
    y_range=[-1.5, 1.5, 0.5],
    x_length=10,
    y_length=5,
    axis_config={{"color": WHITE}},
)
axes.to_edge(DOWN, buff=0.5)
self.play(Create(axes, run_time=1.5))

# Damped oscillation curve
damping = {damping}
freq = {freq}

def x_func(t):
    return math.exp(-damping * t) * math.sin(2 * math.pi * freq * t)

curve = axes.plot(x_func, x_range=[0, {dur - 0.1}], color="{color}", stroke_width=3)
curve_glow = curve.copy().set_stroke(width=12, opacity=0.15)
self.add(curve_glow)
self.play(Create(curve, run_time=3))

# Moving dot tracing the curve
dot = Dot(axes.c2p(0, x_func(0)), radius=0.1, color="{color}")
self.add(dot)

t_tracker = ValueTracker(0)
dot.add_updater(lambda m: m.move_to(axes.c2p(t_tracker.get_value(), x_func(t_tracker.get_value()))))
self.play(t_tracker.animate.set_value({dur - 0.1}), run_time=4, rate_func=linear)

# Phase space (compact, right side)
phase_axes = Axes(
    x_range=[-1.5, 1.5, 0.5],
    y_range=[-1.5, 1.5, 0.5],
    x_length=3.5,
    y_length=3.5,
)
phase_axes.to_edge(RIGHT, buff=0.3).shift(DOWN * 0.3)
phase_label = Text("Phase Space", font_size=18, color=WHITE)
phase_label.next_to(phase_axes, UP, buff=0.1)
self.play(FadeIn(phase_axes), Write(phase_label), run_time=1)

def phase_func(t):
    x = math.exp(-damping * t) * math.sin(2 * math.pi * freq * t)
    v = math.exp(-damping * t) * (
        2 * math.pi * freq * math.cos(2 * math.pi * freq * t)
        - damping * math.sin(2 * math.pi * freq * t)
    )
    return phase_axes.c2p(x * 0.8, v * 0.5)

phase_curve = ParametricFunction(phase_func, t_range=[0, {dur - 0.1}], color="#10B981", stroke_width=2)
self.play(Create(phase_curve, run_time=2.5))

self.wait(1.5)
""")


class DrivenOscillatorTemplate(SceneTemplate):
    """Driven oscillator with resonance."""
    name = "driven_oscillato"
    keywords = ["driven", "resonance", "force", "push", "external", "steady"]
    category = "oscillato"

    def generate_code(self, config: TemplateConfig) -> str:
        freq = config.frequency
        color = config.colors[0]
        dur = min(config.duration, 15)

        return _common_manim_header() + _indent(f"""
title = Text("Driven Oscillator & Resonance", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

axes = Axes(x_range=[0, {dur}, 1], y_range=[-2, 2, 0.5], x_length=11, y_length=4, axis_config={{"color": WHITE}})
axes.to_edge(DOWN)
self.play(Create(axes, run_time=1))

# Driving force
force_curve = axes.plot(lambda t: math.sin(2 * math.pi * {freq} * t), x_range=[0, {dur - 0.1}], color="#F59E0B", stroke_width=2, opacity=0.6)
self.play(Create(force_curve, run_time=2))

force_label = MathTex(r"F(t) = F_0 \\sin(\\omega t)", font_size=28, color="#F59E0B")
force_label.next_to(axes, UP, buff=0.3)
self.play(Write(force_label))

# Response
damping = 0.1
def response(t):
    ratio = {freq} / 1.0
    amp = 1.0 / math.sqrt((1 - ratio**2)**2 + (2 * damping * ratio)**2)
    return min(amp, 3) * math.exp(-damping * t) * math.sin(2 * math.pi * {freq} * t)

resp_curve = axes.plot(response, x_range=[0, {dur - 0.1}], color="{color}", stroke_width=3)
resp_glow = resp_curve.copy().set_stroke(width=12, opacity=0.15)
self.add(resp_glow)
self.play(Create(resp_curve, run_time=3))

self.wait(1.5)
""")

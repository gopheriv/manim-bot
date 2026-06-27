"""Physics templates: Maxwell, Schrödinger, thermodynamics, optics."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class SchrodingerTemplate(SceneTemplate):
    """Schrödinger equation with wavefunction evolution."""
    name = "schrodinger"
    keywords = ["schrodinger", "quantum", "wavefunction", "particle", "probability", "potential", "well", "barrier", "schroedinger"]
    category = "physics"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Schrödinger Equation", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

eq = MathTex(r"i\\hbar\\frac{{\\partial \\psi}}{{\\partial t}} = -\\frac{{\\hbar^2}}{{2m}}\\frac{{\\partial^2 \\psi}}{{\\partial x^2}} + V(x)\\psi", font_size=28, color=WHITE)
eq.to_edge(UP, buff=1.2)
self.play(Write(eq, run_time=2))

axes = Axes(x_range=[-5, 5, 1], y_range=[-1.5, 1.5, 0.5], x_length=10, y_length=4)
axes.to_edge(DOWN)
self.play(Create(axes, run_time=1))

# Wave packet
def wave_packet(x, t):
    sigma = 1.0
    k0 = 2.0
    return math.exp(-(x - 0.5*t)**2 / (2*sigma**2)) * math.cos(k0 * x - t)

wave = ParametricFunction(
    lambda t: axes.c2p(t, wave_packet(t, 0)),
    t_range=[-5, 5],
    color="{color}",
)
wave.set_stroke(width=3)
self.play(Create(wave, run_time=2))

# Potential well
well_depth = {config.extra_params.get('well_depth', 0.8)}
well = Polygon(
    axes.c2p(-2, 0), axes.c2p(-2, -well_depth),
    axes.c2p(2, -well_depth), axes.c2p(2, 0),
    fill_color="#F59E0B", fill_opacity=0.3, stroke_color=WHITE,
)
self.play(FadeIn(well), run_time=1)

# Animate wave packet moving
self.play(wave.animate.shift(RIGHT * 3), run_time=3)

self.wait(2)
""")


class ThermodynamicsTemplate(SceneTemplate):
    """Thermodynamics: entropy, heat engines, PV diagrams."""
    name = "thermodynamics"
    keywords = ["thermo", "entropy", "heat", "carnot", "engine", "pv", "pressure", "volume", "temperature", "gas"]
    category = "physics"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Carnot Heat Engine", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

# PV diagram
axes = Axes(x_range=[1, 5, 1], y_range=[0.5, 4, 0.5], x_length=8, y_length=5)
axes.to_edge(DOWN)
x_label = axes.get_x_axis_label("V")
y_label = axes.get_y_axis_label("P")
self.play(Create(axes), Write(x_label), Write(y_label), run_time=1)

# Isotherms: PV = nRT
T_hot = {config.extra_params.get('T_hot', 3)}
T_cold = {config.extra_params.get('T_cold', 1.5)}

isotherm_hot = ParametricFunction(
    lambda v: axes.c2p(v, T_hot / v),
    t_range=[1.2, 4.5],
    color="#F59E0B",
)
isotherm_hot.set_stroke(width=2)
isotherm_cold = ParametricFunction(
    lambda v: axes.c2p(v, T_cold / v),
    t_range=[1.2, 4.5],
    color="{color}",
)
isotherm_cold.set_stroke(width=2)

self.play(Create(isotherm_hot), run_time=1.5)
self.play(Create(isotherm_cold), run_time=1.5)

hot_label = MathTex("T_H", color="#F59E0B")
hot_label.move_to(axes.c2p(4, T_hot/4 + 0.3))
cold_label = MathTex("T_C", color="{color}")
cold_label.move_to(axes.c2p(4, T_cold/4 + 0.3))
self.play(Write(hot_label), Write(cold_label))

# Carnot cycle path
v1, v2, v3, v4 = 1.5, 3.0, 3.5, 1.8
cycle_points = [
    axes.c2p(v1, T_hot/v1),
    axes.c2p(v2, T_hot/v2),
    axes.c2p(v2, T_cold/v2),
    axes.c2p(v3, T_cold/v3),
    axes.c2p(v3, T_hot/v3),
    axes.c2p(v4, T_hot/v4),
    axes.c2p(v4, T_cold/v4),
    axes.c2p(v1, T_cold/v1),
    axes.c2p(v1, T_hot/v1),
]

cycle = Polygon(*cycle_points[:4], fill_color="{color}", fill_opacity=0.2, stroke_color=WHITE, stroke_width=2)

# Efficiency
eff = 1 - T_cold / T_hot
eff_label = Text(f"\\u03b7 = 1 - T_C/T_H = {{eff:.2f}}", font_size=28, color="#10B981")
eff_label.to_corner(UR)
self.play(Create(cycle, run_time=2), Write(eff_label, run_time=1.5))

self.wait(2)
""")

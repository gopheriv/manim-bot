"""Probability templates: CLT, distributions, Bayesian."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class CLTTemplate(SceneTemplate):
    """Central Limit Theorem with converging distributions."""
    name = "central_limit_theorem"
    keywords = ["central limit", "clt", "bell curve", "normal", "gaussian", "distribution", "converge", "sample", "mean", "central", "limit", "theorem"]
    category = "probability"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Central Limit Theorem", font_size=36, color="{color}")
title.to_edge(UP)
axes = Axes(x_range=[-4, 4, 1], y_range=[0, 1, 0.2], x_length=10, y_length=5)
axes.to_edge(DOWN)
self.play(Write(title, run_time=1.5), Create(axes, run_time=1))

# Bell curve
def normal(x, mu=0, sigma=1):
    return math.exp(-(x-mu)**2 / (2*sigma**2)) / (sigma * math.sqrt(2*math.pi))

bell = ParametricFunction(
    lambda t: axes.c2p(t, normal(t)),
    t_range=[-4, 4],
    color="{color}",
)
bell.set_stroke(width=3)
bell_glow = bell.copy().set_stroke(width=12, opacity=0.15).set_fill(opacity=0)
self.add(bell_glow)

# Show distributions converging
samples = [1, 3, 5, 10, 30]
colors = {repr(config.colors[:5])}

for i, n in enumerate(samples):
    sigma = 1.0 / math.sqrt(n)
    dist = ParametricFunction(
        lambda t: axes.c2p(t, normal(t, sigma=sigma) * math.sqrt(n)),
        t_range=[-4, 4],
        color=colors[i % len(colors)],
        stroke_opacity=0.6,
    )
    dist.set_stroke(width=2)
    self.play(Create(dist, run_time=1))

    n_label = MathTex(f"n = {{n}}", font_size=24, color=colors[i % len(colors)])
    n_label.to_corner(UR)
    self.play(FadeIn(n_label), run_time=0.3)
    self.wait(0.3)
    self.play(FadeOut(n_label), run_time=0.2)

# Final bell curve
eq = MathTex(r"\\bar{{{{X}}}}_n \\xrightarrow{{d}} \\mathcal{{N}}(\\mu, \\sigma^2/n)", font_size=28)
eq.to_edge(UP, buff=1)
self.play(Create(bell, run_time=2), Write(eq, run_time=1.5))

self.wait(2)
""")


class BayesTheoremTemplate(SceneTemplate):
    """Bayes' theorem visualization."""
    name = "bayes_theorem"
    keywords = ["bayes", "bayesian", "posterior", "prior", "likelihood", "probability", "conditional"]
    category = "probability"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Bayes' Theorem", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

eq = MathTex(r"P(A|B) = \\frac{{P(B|A) \\cdot P(A)}}{{P(B)}}", font_size=40, color=WHITE)
eq.to_edge(UP, buff=1.2)
self.play(Write(eq, run_time=2))

# Venn diagram
circle_a = Circle(radius=1.5, color="{color}", fill_opacity=0.3)
circle_a.to_edge(LEFT, buff=2)
circle_b = Circle(radius=1.5, color="#10B981", fill_opacity=0.3)
circle_b.to_edge(RIGHT, buff=2)

self.play(Create(circle_a), run_time=1)
self.play(Create(circle_b), run_time=1)

label_a = Text("A", font_size=24, color="{color}")
label_a.move_to(circle_a.get_center() + LEFT * 0.5)
label_b = Text("B", font_size=24, color="#10B981")
label_b.move_to(circle_b.get_center() + RIGHT * 0.5)
self.play(Write(label_a), Write(label_b))

# Highlight intersection
intersection = circle_a.copy().set_fill(opacity=0.5).set_color("#F59E0B")
self.play(FadeIn(intersection), run_time=1)

self.wait(2)
""")

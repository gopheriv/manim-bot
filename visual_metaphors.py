"""Visual Metaphor Library — a curated vocabulary of teaching metaphors.

The bot's prompts have always *exhorted* the model to "turn abstractions into
visual metaphors" (prompt_builder.BASE_MANIM_RULES), but provided no concrete,
reusable vocabulary — so the quality of the metaphor varied wildly per
generation. This module turns that prose into an actual capability:

  * a registry of named metaphors (function-as-machine, derivative-as-sliding-
    tangent, matrix-as-warping-grid…), each with the abstract concept it serves,
    the pedagogical *why*, and a concrete, implementable Manim CE recipe;
  * ``recommend_metaphors(prompt)`` picks the metaphor(s) a prompt invites;
  * ``format_metaphors_for_director`` gives the storyboard director a menu to
    choose a spine metaphor from;
  * ``format_metaphors_for_codegen`` gives the code generator the concrete
    recipe so the chosen metaphor is implemented idiomatically, not improvised.

Graceful by design: no match (or the feature disabled) simply contributes
nothing and the pipeline behaves exactly as before.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Metaphor:
    """One teaching metaphor: the idea it serves, when it fits, and how to build it."""

    name: str            # stable id, e.g. "function_machine"
    concept: str         # the abstract idea it makes felt
    triggers: tuple[str, ...]  # word PREFIXES in the prompt that invite it
    visual: str          # one-line description of the visual idea
    why: str             # the pedagogical payoff — why it teaches
    recipe: str          # a concrete Manim CE sketch the generator adapts


# ── The library ───────────────────────────────────────────────────────────────
# Recipes are deliberately concrete (real Manim CE classes/animations) but are
# sketches: the generator adapts names, values and the specific function/topic.

_REGISTRY: tuple[Metaphor, ...] = (
    Metaphor(
        name="function_machine",
        concept="a function as an input → output machine",
        triggers=("function", "map", "mapping", "transform", "compose", "inverse"),
        visual="a labelled box that swallows an input value and emits f(input)",
        why="makes 'f(x)' a process you can watch, not a static symbol — inputs flow in, "
            "outputs drop out, and composition becomes machines wired in series.",
        recipe=(
            "machine = RoundedRectangle(width=3, height=2, corner_radius=0.2)\n"
            "label = MathTex('f').scale(1.5).move_to(machine)\n"
            "x_val = MathTex('x').next_to(machine, LEFT, buff=1)\n"
            "in_arrow = Arrow(x_val.get_right(), machine.get_left(), buff=0.2)\n"
            "self.play(Create(machine), Write(label))\n"
            "self.play(Write(x_val), GrowArrow(in_arrow))\n"
            "# Feed the input THROUGH the machine to become the output:\n"
            "y_val = MathTex('f(x)').next_to(machine, RIGHT, buff=1)\n"
            "out_arrow = Arrow(machine.get_right(), y_val.get_left(), buff=0.2)\n"
            "self.play(x_val.animate.move_to(machine.get_center()).set_opacity(0))\n"
            "self.play(GrowArrow(out_arrow), Write(y_val))"
        ),
    ),
    Metaphor(
        name="derivative_tangent",
        concept="the derivative as the slope of a tangent line sliding along a curve",
        triggers=("derivative", "differentiat", "slope", "tangent", "rate", "gradient"),
        visual="a tangent line that glides along a curve, its tilt reporting f'(x)",
        why="the derivative stops being a rule and becomes a MOTION — the viewer sees "
            "steepness change in real time and feels where it is zero, positive, negative.",
        recipe=(
            "ax = Axes(x_range=[-3, 3], y_range=[-2, 8])\n"
            "graph = ax.plot(lambda x: x**2, color=BLUE)\n"
            "a = ValueTracker(0.05)  # alpha in (0, 1): position ALONG the plotted curve\n"
            "tangent = always_redraw(lambda: TangentLine(graph, alpha=a.get_value(), length=5, color=YELLOW))\n"
            "dot = always_redraw(lambda: Dot(graph.point_from_proportion(a.get_value()), color=YELLOW))\n"
            "self.play(Create(ax), Create(graph))\n"
            "self.add(tangent, dot)\n"
            "self.play(a.animate.set_value(0.95), run_time=4)  # tilt = f'(x) in motion"
        ),
    ),
    Metaphor(
        name="integral_area",
        concept="the integral as accumulating area under a curve",
        triggers=("integral", "integrat", "area", "accumulat", "antiderivative", "riemann"),
        visual="Riemann rectangles fill the region under a curve, then refine into smooth area",
        why="the ∫ symbol becomes a SUM you watch grow — coarse bars shrink to a continuum, "
            "so 'area under the curve' is something accumulated, not asserted.",
        recipe=(
            "ax = Axes(x_range=[0, 4], y_range=[0, 16])\n"
            "graph = ax.plot(lambda x: x**2, color=BLUE)\n"
            "rects_coarse = ax.get_riemann_rectangles(graph, x_range=[0, 4], dx=1.0, color=[BLUE, GREEN])\n"
            "rects_fine = ax.get_riemann_rectangles(graph, x_range=[0, 4], dx=0.2, color=[BLUE, GREEN])\n"
            "self.play(Create(ax), Create(graph))\n"
            "self.play(Create(rects_coarse))\n"
            "# Refine the partition — the sum converges to the true area:\n"
            "self.play(Transform(rects_coarse, rects_fine), run_time=2)"
        ),
    ),
    Metaphor(
        name="limit_zoom",
        concept="a limit as zooming in until the complicated looks simple",
        triggers=("limit", "continu", "approach", "infinitesimal", "tangent", "smooth"),
        visual="the camera pushes in on a point until a curve becomes indistinguishable from a line",
        why="'approaching a value' becomes a literal zoom — local linearity, continuity and "
            "L'Hôpital all become things you SEE by getting closer.",
        recipe=(
            "ax = Axes(x_range=[-3, 3], y_range=[-1, 5])\n"
            "graph = ax.plot(lambda x: x**2, color=BLUE)\n"
            "focus = ax.input_to_graph_point(1, graph)\n"
            "dot = Dot(focus, color=YELLOW)\n"
            "self.play(Create(ax), Create(graph), FadeIn(dot))\n"
            "# Use a MovingCameraScene: zoom the frame onto the point until the\n"
            "# curve looks straight (local linearity = the limit made visible).\n"
            "self.play(self.camera.frame.animate.scale(0.15).move_to(focus), run_time=3)"
        ),
    ),
    Metaphor(
        name="matrix_transform",
        concept="a matrix as a transformation that warps space",
        triggers=("matrix", "matrices", "linear", "transform", "rotation", "shear", "determinant", "basis"),
        visual="a grid of space bends/rotates/stretches under the matrix; basis vectors lead the move",
        why="a matrix stops being a number table — it becomes an ACTION on the whole plane, and the "
            "determinant becomes the area scaling you can literally watch.",
        recipe=(
            "plane = NumberPlane(x_range=[-5, 5], y_range=[-5, 5])\n"
            "i_hat = Arrow(ORIGIN, [1, 0, 0], buff=0, color=GREEN)\n"
            "j_hat = Arrow(ORIGIN, [0, 1, 0], buff=0, color=RED)\n"
            "self.play(Create(plane), GrowArrow(i_hat), GrowArrow(j_hat))\n"
            "M = [[2, 1], [0, 1]]  # the transformation to apply\n"
            "self.play(ApplyMatrix(M, plane),\n"
            "          ApplyMatrix(M, i_hat), ApplyMatrix(M, j_hat), run_time=3)\n"
            "# (Prefer LinearTransformationScene for a self-labelling version.)"
        ),
    ),
    Metaphor(
        name="complex_rotation",
        concept="multiplying by a complex number as a rotation + scaling of the plane",
        triggers=("complex", "imaginary", "argand", "phase", "euler", "rotation", "phasor"),
        visual="multiplying by i rotates a vector 90°; by re^{iθ} rotates by θ and scales by r",
        why="'imaginary' becomes geometric — multiplication is rotation, so i²=−1 (two 90° turns) "
            "and Euler's formula are seen, not memorised.",
        recipe=(
            "plane = ComplexPlane().add_coordinates()\n"
            "v = Arrow(plane.n2p(0), plane.n2p(complex(2, 1)), buff=0, color=YELLOW)\n"
            "self.play(Create(plane), GrowArrow(v))\n"
            "# Multiply by i  →  a 90° rotation about the origin:\n"
            "self.play(Rotate(v, angle=PI/2, about_point=plane.n2p(0)), run_time=2)\n"
            "# Or animate the whole plane under z -> z * e^{i*theta}:\n"
            "self.play(plane.animate.apply_complex_function(lambda z: z * np.exp(1j*PI/3)))"
        ),
    ),
    Metaphor(
        name="vector_field_flow",
        concept="a vector field as a flow that carries test particles",
        triggers=("field", "vector", "flow", "divergence", "curl", "fluid", "gradient", "stream"),
        visual="arrows fill the plane; dropped particles stream along them, tracing the dynamics",
        why="a field of arrows is static and hard to read; releasing particles turns it into MOTION, "
            "so divergence (spreading) and curl (swirling) become visible behaviours.",
        recipe=(
            "func = lambda p: np.array([-p[1], p[0], 0]) / 3  # a rotational field\n"
            "field = ArrowVectorField(func)\n"
            "self.play(Create(field))\n"
            "stream = StreamLines(func, stroke_width=2, max_anchors_per_line=30)\n"
            "self.add(stream)\n"
            "stream.start_animation(warm_up=True, flow_speed=1.5)\n"
            "self.wait(stream.virtual_time / stream.flow_speed)"
        ),
    ),
    Metaphor(
        name="eigen_directions",
        concept="eigenvectors as the special directions a transform only stretches",
        triggers=("eigen", "eigenvalue", "eigenvector", "diagonal", "principal", "spectral"),
        visual="most vectors rotate off their line under a matrix; eigenvectors stay on theirs, only scaling",
        why="'eigen' becomes concrete — among all directions, a few are SPECIAL: the transform leaves "
            "them pointing the same way and the eigenvalue is just how much they stretch.",
        recipe=(
            "plane = NumberPlane()\n"
            "M = [[2, 1], [1, 2]]  # eigenvectors [1,1] (λ=3) and [1,-1] (λ=1)\n"
            "generic = Arrow(ORIGIN, [1, 0, 0], buff=0, color=GREY)\n"
            "eigen = Arrow(ORIGIN, [1, 1, 0], buff=0, color=YELLOW)  # stays on its line\n"
            "self.play(Create(plane), GrowArrow(generic), GrowArrow(eigen))\n"
            "self.play(ApplyMatrix(M, plane), ApplyMatrix(M, generic),\n"
            "          ApplyMatrix(M, eigen), run_time=3)\n"
            "# generic swings off its line; eigen only lengthens (×3) — that is λ."
        ),
    ),
    Metaphor(
        name="series_convergence",
        concept="an infinite series as partial sums marching toward a limit",
        triggers=("series", "sum", "converg", "diverg", "geometric", "taylor", "sequence", "partial"),
        visual="terms stack up one by one while a running total creeps toward a target line",
        why="'infinite sum' becomes a JOURNEY — each term is a step, and convergence is the steps "
            "getting so small the total settles, so the limit is earned rather than declared.",
        recipe=(
            "ax = Axes(x_range=[0, 10], y_range=[0, 2])\n"
            "target = DashedLine(ax.c2p(0, 2), ax.c2p(10, 2), color=GREEN)  # the limit\n"
            "self.play(Create(ax), Create(target))\n"
            "partial, dots = 0, VGroup()\n"
            "for n in range(1, 8):  # geometric: sum 1/2^k -> 1, scaled to target\n"
            "    partial += 1 / 2**n\n"
            "    d = Dot(ax.c2p(n, 2 * partial / (1 - 0.5**8) * (1 - 0.5)), color=YELLOW)\n"
            "    dots.add(d)\n"
            "    self.play(FadeIn(d, shift=UP*0.2), run_time=0.4)  # creeping toward the line"
        ),
    ),
    Metaphor(
        name="probability_particles",
        concept="probability as a crowd of outcomes / flowing mass",
        triggers=("probab", "random", "distribution", "expectation", "stochast", "bayes", "sampl", "monte"),
        visual="hundreds of dots scatter by chance and pile into bars — the histogram IS the distribution",
        why="probability stops being a fraction on paper — you watch frequency BECOME shape as samples "
            "accumulate, so a distribution is an emergent crowd, and expectation is its balance point.",
        recipe=(
            "ax = Axes(x_range=[-4, 4], y_range=[0, 0.5])\n"
            "samples = np.random.default_rng(0).normal(0, 1, 400)  # fixed seed = deterministic\n"
            "dots = VGroup(*[Dot(ax.c2p(x, 0.45), radius=0.03, color=BLUE) for x in samples])\n"
            "self.play(LaggedStartMap(FadeIn, dots, lag_ratio=0.002))\n"
            "# Let them fall to the axis — their density traces the distribution:\n"
            "curve = ax.plot(lambda x: np.exp(-x**2 / 2) / np.sqrt(2 * np.pi), color=YELLOW)\n"
            "self.play(*[d.animate.move_to(ax.c2p(x, 0)) for d, x in zip(dots, samples)],\n"
            "          Create(curve), run_time=3)  # frequency becomes the bell curve"
        ),
    ),
    Metaphor(
        name="graph_search",
        concept="a graph/tree search as a wave of exploration lighting nodes in visit order",
        triggers=("graph", "tree", "bfs", "dfs", "traversal", "search", "shortest", "dijkstra", "node", "edge"),
        visual="nodes light up in the order they're visited; the frontier spreads outward edge by edge",
        why="an algorithm becomes a VISIBLE process — BFS ripples in rings, DFS plunges deep then "
            "backtracks, so the difference between strategies is seen, not described.",
        recipe=(
            "from manim import Graph\n"
            "verts = [1, 2, 3, 4, 5, 6]\n"
            "edges = [(1, 2), (1, 3), (2, 4), (3, 5), (3, 6)]\n"
            "g = Graph(verts, edges, layout='tree', root_vertex=1, labels=True)\n"
            "self.play(Create(g))\n"
            "visit_order = [1, 2, 3, 4, 5, 6]  # BFS order from the algorithm\n"
            "for v in visit_order:  # light each node as the frontier reaches it\n"
            "    self.play(g[v].animate.set_color(YELLOW), run_time=0.4)"
        ),
    ),
    Metaphor(
        name="recursion_nesting",
        concept="recursion as self-similar structure unfolding (and folding back)",
        triggers=("recursion", "recursive", "fractal", "self-similar", "divide", "factorial", "fibonacci"),
        visual="a shape contains a smaller copy of itself, nested down to a base case, then resolves back up",
        why="recursion becomes spatial — each call is a smaller nested frame, the base case is the "
            "innermost box, and the return values bubble back outward, making the call stack tangible.",
        recipe=(
            "def nest(level, square):\n"
            "    if level == 0:  # base case — innermost box\n"
            "        return\n"
            "    inner = square.copy().scale(0.6).set_color(interpolate_color(BLUE, YELLOW, 1-level/4))\n"
            "    self.play(TransformFromCopy(square, inner), run_time=0.6)  # the recursive call\n"
            "    nest(level - 1, inner)\n"
            "    # (returning up the stack — animate a brief highlight on the way back)\n"
            "outer = Square(side_length=5, color=BLUE)\n"
            "self.play(Create(outer))\n"
            "nest(4, outer)"
        ),
    ),
)


# ── Matching ──────────────────────────────────────────────────────────────────

def _tokens(prompt: str) -> list[str]:
    """Lowercase alphabetic word tokens (matches the _assess_complexity approach)."""
    return re.findall(r"[a-z]+", prompt.lower())


def _score(metaphor: Metaphor, tokens: list[str]) -> int:
    """How many DISTINCT triggers the prompt hits (word-prefix match, not substring).

    Prefix matching catches inflections ("differentiation"←differentiat,
    "integrate"←integrat) while a token like "paragraph" no longer matches a
    "graph" trigger the way a bare substring scan would.
    """
    hit = set()
    for trig in metaphor.triggers:
        if any(tok.startswith(trig) for tok in tokens):
            hit.add(trig)
    return len(hit)


def recommend_metaphors(prompt: str, max_n: int = 2) -> list[Metaphor]:
    """Return up to ``max_n`` metaphors a prompt invites, best match first.

    Empty when nothing matches — the caller then adds no metaphor guidance and
    the pipeline behaves exactly as before. Ties break by registry order so the
    selection is deterministic (no per-run randomness).
    """
    if not prompt or max_n <= 0:
        return []
    tokens = _tokens(prompt)
    scored = [(m, _score(m, tokens)) for m in _REGISTRY]
    ranked = sorted(
        (ms for ms in scored if ms[1] > 0),
        key=lambda ms: ms[1],
        reverse=True,
    )
    return [m for m, _ in ranked[:max_n]]


# ── Formatting for the two planning stages ────────────────────────────────────

def format_metaphors_for_director(metaphors: list[Metaphor]) -> str:
    """A menu for the storyboard director: choose ONE spine metaphor.

    Returns "" for an empty list so callers can unconditionally append it.
    """
    if not metaphors:
        return ""
    lines = [
        "## VISUAL METAPHOR PALETTE — choose ONE as the spine of this explainer",
        "Pick the single metaphor that best makes the core idea *felt*, then design the "
        "beats to build it up progressively. Don't blend several — commit to one and name "
        "it in the concept and opening beats.",
    ]
    for m in metaphors:
        lines.append(f"- **{m.name}** — {m.concept}. {m.visual}. WHY: {m.why}")
    return "\n".join(lines)


def format_metaphors_for_codegen(metaphors: list[Metaphor]) -> str:
    """Concrete Manim CE recipes for the chosen metaphor(s), for the generator.

    Returns "" for an empty list so callers can unconditionally append it.
    """
    if not metaphors:
        return ""
    lines = [
        "## METAPHOR RECIPES — concrete Manim CE patterns to realize the storyboard's metaphor",
        "If the storyboard commits to one of these metaphors, implement it with the idiom below "
        "(adapt the function, values, and labels to THIS topic — the recipe is a skeleton, not a "
        "fixed scene). Keep everything deterministic (fixed seeds).",
    ]
    for m in metaphors:
        lines.append(f"\n### {m.name} — {m.concept}\n```python\n{m.recipe}\n```")
    return "\n".join(lines)

"""Domain-specific generation guidance.

prompt_builder gives the code generator tier-aware *style* but no *field-specific*
rules. A linear-algebra animation has different conventions (show i_hat/j_hat first,
fade the grid) than a probability one (accumulate samples into a histogram). This
module supplies a concise rule block per domain, auto-selected from the prompt and
injected into the code-gen system prompt — the same wiring as ``visual_metaphors``.

Graceful by design: no domain match (or nothing recognisable) → empty string → the
pipeline behaves exactly as before.

    domain = recommend_domain(prompt)            # "linear_algebra" | ... | None
    guidance = format_domain_guidance(domain)    # "" when None/unknown
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    """One subject area: when it applies, and the rules to inject for it."""

    name: str                  # stable id, e.g. "linear_algebra"
    triggers: tuple[str, ...]  # word PREFIXES in the prompt that select it
    guidance: str              # the rule block injected into the code-gen prompt


_REGISTRY: tuple[Domain, ...] = (
    Domain(
        name="linear_algebra",
        triggers=(
            "matrix", "matrices", "eigen", "determinant", "basis", "linear",
            "vector", "span", "orthogonal", "subspace", "transformation", "dot product",
        ),
        guidance=(
            "## DOMAIN — Linear algebra\n"
            "- Show the basis vectors i_hat=(1,0) and j_hat=(0,1) as colored Arrows FIRST, "
            "on a FAINT NumberPlane (`background_line_style={\"stroke_opacity\": 0.2}`).\n"
            "- Show the unit square the basis vectors span BEFORE any transformation.\n"
            "- Apply a matrix by transforming the grid, i_hat, j_hat (and the square) TOGETHER "
            "with `ApplyMatrix` — or use `LinearTransformationScene` for a self-labelling version.\n"
            "- Determinant = area scaling: animate the unit square morph into the parallelogram "
            "and compare areas (1 → |det|).\n"
            "- Keep the viewer's eye on the vectors/shapes, not the grid lines."
        ),
    ),
    Domain(
        name="calculus",
        triggers=(
            "derivative", "differentiat", "integral", "integrat", "limit", "tangent",
            "slope", "riemann", "series", "taylor", "converg", "antiderivative",
        ),
        guidance=(
            "## DOMAIN — Calculus\n"
            "- Plot with `axes.plot(f, x_range=[a, b])` (NOT the deprecated `get_graph`); "
            "label curves with `axes.get_graph_label(...)` or a `MathTex` next to the curve.\n"
            "- Derivative: animate a `TangentLine` sliding along the curve via a `ValueTracker`; "
            "its tilt IS f'(x) — show the slope value updating.\n"
            "- Integral: `axes.get_riemann_rectangles(graph, dx=...)` with dx shrinking "
            "(`Transform` coarse → fine) so the sum visibly converges to the area.\n"
            "- Limit: push the camera/frame in on the point so 'approaching' is a literal zoom.\n"
            "- Series/convergence: overlay successive partial sums in distinct colors marching to the limit."
        ),
    ),
    Domain(
        name="physics",
        triggers=(
            "force", "velocity", "acceleration", "energy", "momentum", "wave",
            "oscillat", "pendulum", "gravity", "charge", "current", "projectile",
            "kinematic", "friction", "orbit", "spring",
        ),
        guidance=(
            "## DOMAIN — Physics\n"
            "- Represent vector quantities (force, velocity) as `Arrow`s with `GrowArrow`; "
            "scale length to magnitude and keep direction physically correct.\n"
            "- Drive motion with a single time `ValueTracker` + updaters so position/velocity stay in sync.\n"
            "- Keep the governing equation on screen and update its symbols as the motion plays "
            "(color a symbol the same as the object it measures).\n"
            "- Waves: a parametric curve redrawn from a phase tracker; label time and position axes.\n"
            "- Use deterministic values (fixed constants) — no per-run randomness."
        ),
    ),
    Domain(
        name="probability",
        triggers=(
            "probab", "random", "distribution", "expectation", "variance", "bayes",
            "sampl", "stochast", "binomial", "poisson", "gaussian", "monte",
        ),
        guidance=(
            "## DOMAIN — Probability & statistics\n"
            "- Show outcomes as many small dots/particles; let them ACCUMULATE into a histogram "
            "(`BarChart` or stacked `Rectangle`s) so frequency visibly becomes the distribution.\n"
            "- Mark the expectation as a balance point / vertical line; shade ±1σ for spread.\n"
            "- Overlay the theoretical curve (e.g. the normal PDF) on top of the empirical bars.\n"
            "- ALWAYS seed randomness deterministically: `rng = np.random.default_rng(0)`."
        ),
    ),
    Domain(
        name="computer_science",
        triggers=(
            "algorithm", "sort", "recursion", "recursive", "complexity", "bfs", "dfs",
            "dijkstra", "binary", "stack", "queue", "hash", "linked", "traversal",
            "adjacency", "pointer",
        ),
        guidance=(
            "## DOMAIN — Computer science / algorithms\n"
            "- Graphs/trees: use the `Graph` mobject; light nodes in visit order with `set_color` "
            "and show the expanding frontier (BFS ripples outward; DFS plunges then backtracks).\n"
            "- Sorting: color-code the elements being compared/swapped and animate the moves.\n"
            "- Recursion: show nested, self-similar frames; let return values bubble back outward.\n"
            "- Keep a live label of the current step / loop variable / call depth.\n"
            "- Make the data structure the hero; annotations support it."
        ),
    ),
    Domain(
        name="chemistry",
        triggers=(
            "molecule", "atom", "bond", "electron", "orbital", "periodic", "reaction",
            "ion", "acid", "base", "valence", "compound", "stoichiometr",
        ),
        guidance=(
            "## DOMAIN — Chemistry\n"
            "- Atoms = labeled `Circle`/`Dot`s with element symbols; bonds = `Line`s "
            "(double/triple bonds = parallel lines); arrange molecules with `VGroup(...).arrange(...)`.\n"
            "- Animate a reaction by `ReplacementTransform`-ing the reactant group into the product group.\n"
            "- Show electron movement as small dots traveling along bond paths.\n"
            "- Keep a balanced chemical equation on screen and highlight what changes."
        ),
    ),
    Domain(
        name="geometry",
        triggers=(
            "triangle", "pythago", "hypotenuse", "right angle", "perpendicular",
            "polygon", "quadrilateral", "parallelogram", "rhombus", "trapezoid",
            "circle theorem", "inscribed", "circumference", "arc length",
            "congruen", "similar triangle", "isometric", "symmetry",
            "angle bisect", "altitude", "median",
            "perimeter", "area of", "heron",
        ),
        guidance=(
            "## DOMAIN — Geometry\n"
            "- Construct figures with `Polygon` (vertices as a sequence of [x,y,0] points) "
            "and `Circle(radius=...)` or `Arc` for angles. Mark right angles with `RightAngle(line1, line2)` "
            "and other angles with `Angle(line1, line2, radius=...)` — both are importable from `manim`.\n"
            "- Label vertices with `Dot` + `MathTex` placed OUTSIDE the shape (use `.next_to(..., buff=0.3)`). "
            "Label side lengths with `MathTex` near the midpoint of each edge.\n"
            "- For a theorem proof (e.g. Pythagoras), build the figure FIRST (triangle + squares on each side), "
            "then animate the proof step: color one square, show it equals the sum of the other two via "
            "`ReplacementTransform` or area comparison.\n"
            "- Keep the figure centered and uncluttered — use `self.camera.background_color` for contrast "
            "and `stroke_width=2` for readability. Use `VGroup(...).move_to(ORIGIN)` to center."
        ),
    ),
    Domain(
        name="number_theory",
        triggers=(
            "prime", "primes", "composit", "factor", "divisib",
            "modul", "modulo", "remainder", "congruen",
            "gcd", "euclid", "lcm",
            "fibonacci", "golden ratio",
            "totient", "euler phi",
            "sieve", "eratosth",
            "perfect number",
        ),
        guidance=(
            "## DOMAIN — Number theory\n"
            "- Show integers as rows of `Dot`s or small `Square`s arranged with `VGroup.arrange()` "
            "(e.g. 12 = 3×4 grid of dots) so divisibility is visible as regrouping.\n"
            "- Show a prime as a number that can ONLY form a 1×n row (no internal rectangle possible). "
            "Animate failed attempts to arrange into 2+ equal rows.\n"
            "- Modular arithmetic: use a `NumberLine` with ticks 0..n-1, or place `Dot`s in a `Circle` "
            "layout and animate an `Arrow` hopping +k mod n (use `Rotate` around the circle center).\n"
            "- Fibonacci: animate growing `Square`s whose side lengths follow F_n, arranged in the golden spiral.\n"
            "- Keep a running `MathTex` of the current relation (e.g. '12 = 3 × 4', 'gcd(48,18) = 6') "
            "visible on screen and update it as the visual changes."
        ),
    ),
)


def _tokens(prompt: str) -> list[str]:
    """Lowercase alphabetic word tokens (same approach as visual_metaphors)."""
    return re.findall(r"[a-z]+", prompt.lower())


def _score(domain: Domain, tokens: list[str]) -> int:
    """Distinct triggers the prompt hits (word-prefix match, not substring)."""
    hit = set()
    for trig in domain.triggers:
        # Multi-word triggers (e.g. "dot product") are matched as substrings of the
        # joined prompt; single-word triggers match a token PREFIX (inflection-friendly).
        if " " in trig:
            if trig in " ".join(tokens):
                hit.add(trig)
        elif any(tok.startswith(trig) for tok in tokens):
            hit.add(trig)
    return len(hit)


def recommend_domain(prompt: str) -> str | None:
    """Return the single best-matching domain name, or None when nothing matches.

    Deterministic: ties break by registry order. A scene is almost always one field,
    so we pick one domain rather than blending several.
    """
    if not prompt:
        return None
    tokens = _tokens(prompt)
    best: tuple[int, int] | None = None  # (score, -index) for stable max
    best_name: str | None = None
    for i, dom in enumerate(_REGISTRY):
        score = _score(dom, tokens)
        if score > 0 and (best is None or (score, -i) > best):
            best = (score, -i)
            best_name = dom.name
    return best_name


def format_domain_guidance(domain: str | None) -> str:
    """Return the guidance block for a domain id, or "" for None/unknown."""
    if not domain:
        return ""
    for dom in _REGISTRY:
        if dom.name == domain:
            return dom.guidance
    return ""

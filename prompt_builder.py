"""Prompt builder — tier-aware prompts for the Manim code generator.

Philosophy: quality-first, scaled to the hardware. On capable hardware
(cinematic/standard tiers) the model is directed to compose ambitious,
professionally directed animations. On the constrained tier (8 GB laptop) it
falls back to the strict "elegant minimalism" budget that keeps renders alive.
The budget is a *tier*, not a global law.
"""

from __future__ import annotations

import re

from render_tier import Tier, get_tier


# Detect the installed Manim version once so prompts can pin the API surface the
# model must target (prevents fixes from reintroducing removed/renamed APIs).
# Fallback is "0.19+" (a real, comparable floor) only when the import fails —
# the live version is preferred whenever Manim is importable.
_MANIM_VERSION_FALLBACK = "0.19+"
try:
    import manim as _manim
    MANIM_VERSION = getattr(_manim, "__version__", _MANIM_VERSION_FALLBACK)
except Exception:
    MANIM_VERSION = _MANIM_VERSION_FALLBACK


# ── Core rules ────────────────────────────────────────────────────────────────

BASE_MANIM_RULES = f"""You write Manim Community Edition animation code.
Output ONLY Python code. No explanation, no markdown fences.

## Structure
- `from manim import *` and `import numpy as np`
- The scene class MUST be named `GenScene`. Use `class GenScene(Scene):` — or
  `class GenScene(MovingCameraScene):` when you want camera moves, or
  `class GenScene(ThreeDScene):` for true 3D — with `def construct(self):`
- Set `self.camera.background_color = "HEX"` in construct()
- Use ONLY Manim CE built-ins — no external libs, no network
- Set properties via methods: `.set_stroke()`, `.set_fill()`, `.set_opacity()` — avoid kwargs like `stroke_color=` in constructors when possible
- Duration and complexity are governed by the performance/budget section below

## MANIM VERSION & API SAFETY (CRITICAL)
- Target Manim Community Edition v{MANIM_VERSION}. Use ONLY methods, classes and
  keyword arguments that exist in this version — verify each one, do not invent.
- These were REMOVED or RENAMED — NEVER use them (use the replacement):
  `ShowCreation` → `Create`; `TextMobject`/`TexMobject` → `Text`/`Tex`/`MathTex`;
  `get_graph` → `axes.plot`; `ApplyMethod(m.x())` → `m.animate.x()`;
  `CONFIG = {{...}}` class dicts (pass args to `__init__` instead);
  `ShowCreationThenFadeOut`/`ShowCreationThenDestruction` → `ShowPassingFlash`.

## NUMPY 2.x COMPATIBILITY (CRITICAL)
- NEVER use `np.math.*` — use `math.*` (import math)
- NEVER use `np.float`, `np.int`, `np.bool`, `np.complex`, `np.object`, `np.str`
- Use Python builtins: `float`, `int`, `bool`, `str`
- Use `np.float64`, `np.int64` for typed numpy scalars

## MANIM COLOR API (CRITICAL — causes runtime AttributeError)
- `interpolate_color()`, `color_gradient()`, `average_color()`, and similar color
  functions require **ManimColor objects**, NOT bare hex strings.
- WRONG: `COOL = "#3498db"` then `interpolate_color(COOL, WARM, alpha)` → crashes with
  `'str' object has no attribute 'interpolate'`.
- CORRECT: `COOL = ManimColor("#3498db")` (or use built-ins: `BLUE`, `RED`, `TEAL`, etc.)
- When building color stops / gradient palettes as lists, wrap every entry:
  `color_stops = [ManimColor(c) for c in ["#hex1", "#hex2", "#hex3"]]`.
- `set_color("#hex")` and `fill_color="#hex"` accept strings — ONLY `interpolate_color`
  and friends need ManimColor. When in doubt, wrap with `ManimColor()`.

## VISUAL POLISH — avoid these specific defects (they look like bugs)
- **Boxes must not clip their contents**: any `SurroundingRectangle`/`BackgroundRectangle`
  needs `buff>=0.15`; the box edge must never touch or cross the text/glyphs inside it.
- **Create each shape ONCE — no ghost/double outlines**: do not animate a duplicate
  `.copy()` together with the original (it renders as a doubled, offset outline). A glow
  copy is `add()`-ed separately AFTER creation at low opacity, never `Create`-d alongside.
  For a cube/box wireframe use a SINGLE `Cube`/`Prism` or one `VGroup` of edges.
- **Fills stay clean, not muddy**: keep `fill_opacity<=0.25`, and an object's fill and
  stroke share ONE color. Never layer a warm fill (yellow/orange) over a cool object
  (blue/teal) — translucent overlap muddies to brown.
- **One color per structure**: grid/subdivision lines on a figure use a SINGLE consistent
  color, not a cyan+yellow mix. Reserve a second accent only for a deliberate highlight.
- **Panels never overlap the hero**: place explanatory text/equation panels in EMPTY
  screen space with `buff>=0.4` from the main figure; if a panel would overlap it, shift
  the figure aside first. Never draw a label box on top of the main object.
- **No stray markers**: a moving dot / `TracedPath` must leave a VISIBLE trail and end at
  a meaningful point. Never leave a lone dot wandering with no trace, and never let it end
  on top of text.
- **Use the whole frame**: don't leave half the frame empty for more than ~2s — bring in
  the label/equation on the empty side early, or center the hero object.
- **Iterative geometry: manage visual density**: when repeating an algorithm (chords,
  polygons, subdivisions), NEVER keep all iterations visible at full opacity. After N≥4
  iterations, fade older ones to opacity≤0.15 or remove them entirely. Alternatively,
  zoom/scale the scene so the latest iteration occupies most of the frame. Distinct
  high-contrast colors per iteration (not pastels that blend to grey).
- **Text-before-geometry sync**: when a formula box or calculation panel appears, its
  values must be highlighted/computed IN SYNC with the geometry action on screen. Never
  show a fully populated formula box while the geometric element hasn't appeared yet.
  Sequence: geometry draws → corresponding value appears in box → highlight both together.
- **Algebra↔geometry connector**: every time you highlight a term in an equation that
  corresponds to a geometric element, draw an animated connector (arrow, dashed line,
  or moving dot) between them. Simultaneous appearance alone is not enough — the viewer
  must SEE the link.
- **Screen-budget rule**: the frame has ~4 zones (top, left, right, bottom). Never
  activate a new zone while existing content hasn't been faded/moved away. When adding
  bottom summary text, first fade the top hero element to make room. Never let text
  overlap fading content — leave `buff>=0.3` between old and new.
"""

# ── Style directives (concise) ────────────────────────────────────────────────

STYLE_DIRECTIVES = """## Visual Style (3 layers, not 5)
Every scene has exactly 3 layers:
1. **Background**: NumberPlane, grid, or 10-20 small dots (NOT 30+ particles)
2. **Primary**: the main mathematical object (curve, shape, equation)
3. **Annotation**: labels, arrows, highlights

## Animation Flow (3 beats)
- Beat 1: background + title appear (1-2s)
- Beat 2: main object constructs/draws (3-5s)
- Beat 3: insight — transform, highlight, or reveal (2-4s)
- End with 1-2s of ambient motion (pulsing glow, gentle drift)

Use `LaggedStart` for staggered reveals. Use `Create`/`Write` over `FadeIn` for primary objects.

## Quality Markers
- `set_color_by_gradient()` on curves
- One glow layer (thick stroke copy, opacity 0.15) on the main object
- `TracedPath` on ONE moving element (not multiple)
- `ValueTracker` + `always_redraw` for animated parameters
- `BackgroundRectangle` behind text for readability

## Direction within the budget
Even at these strict limits, still DIRECT it: use color semantically (one concept = one
color, consistently); morph equations with `TransformMatchingTex`/`ReplacementTransform`
instead of fade-and-replace; reveal information step by step to build intuition rather than
dumping the answer; and vary transitions (`GrowFromCenter`, `Indicate`, `Circumscribe`),
not just `FadeIn`. Beauty within the 3-layer budget — not minimalism for its own sake.
"""

# ── HARDWARE BUDGET (the critical addition) ───────────────────────────────────

# NOTE: This budget applies ONLY to the *constrained* tier (the 8 GB laptop).
# Capable tiers use _cinematic_budget() instead, which deliberately RELAXES these
# limits (e.g. Surfaces become allowed). The two are never combined, so the
# "ParametricSurface forbidden here / allowed there" difference is by tier, not a
# contradiction.
HARDWARE_BUDGET = """## HARDWARE BUDGET (i5-1155G7, 8GB RAM — STRICT LIMITS)

Your code runs on a laptop with 8GB RAM. Exceeding these limits crashes the render.

### POINT BUDGET: max 40 points total
| Operation | Points | Limit |
|-----------|--------|-------|
| `self.play()` call | 2 each | max 10 |
| `always_redraw` / `add_updater` | 8 each | **max 2 total** |
| `Surface` / `ParametricSurface` | 25 each | **FORBIDDEN** |
| `ThreeDScene` | 12 | allowed only if requested |
| `TracedPath` | 6 each | max 1 |
| `LaggedStart` with >10 items | 4 each | max 2 |
| `Sphere`, `Cube`, 3D objects | 8 each | max 3 |
| Long scenes | small cost/frame | keep tight; trim dead time |
| `.copy()` for glow | 1 each | max 2 |
| `Transform` between complex shapes | 3 each | max 3 |

### FORBIDDEN (will crash)
- `always_redraw` inside `always_redraw` (nested updaters)
- `Surface` with resolution > (16, 32)
- More than 2 updater-driven elements
- `ParametricSurface` of any kind
- `TracedPath` inside `ThreeDScene`
- Background particle fields > 25 dots
- Multiple simultaneous `self.wait()` with updaters running
- `Scene` subclass of `ThreeDScene` unless 3D is explicitly requested

### When in doubt: simpler wins
A clean, readable animation that renders successfully is ALWAYS better than an ambitious one that crashes. When you're unsure if something will fit in the budget, leave it out.
"""

# ── Scene awareness (simplified) ──────────────────────────────────────────────

SCENE_AWARENESS = """## Layout Rules
- Max 2 objects at ORIGIN simultaneously
- When introducing a new main object, fade out the old one
- Use `next_to(buff=0.3+)` for spacing
- `Text` and `MathTex` must have explicit `font_size`
- Use `VGroup().arrange()` for 3+ related elements
- Phase transitions: old objects FadeOut before new ones FadeIn
"""

# ── Anti-lazy (condensed) ────────────────────────────────────────────────────

ANTI_LAZY = """## Quality Floor
- At least 3 animated objects (not just title + equation)
- Use `Create`/`Write`/`DrawBorderThenFill` — not just `FadeIn`
- Scene must have continuous motion — no dead frames > 0.5s
- Final 2s: ambient motion (pulse, glow, drift) — NOT a freeze frame
- Use the full screen — spread objects, don't cluster in center
"""

# ── 3D limits ────────────────────────────────────────────────────────────────

HARDWARE_3D_LIMITS = """## 3D Scene Limits (only when 3D is requested)
- Surface resolution MAX (16, 32)
- MAX 1 updater in 3D
- Arrow3D: MAX 10. Sphere/Cube: MAX 5
- MAX 2 camera moves
- Duration ≤ 18 seconds
- Prefer 2D with depth cues over heavy 3D
"""

# ── Ambition-first house style (capable tiers) ───────────────────────────────

CINEMATIC_STYLE = """## DIRECTION — compose like an award-winning motion designer
You are DIRECTING a professionally produced educational animation, not emitting code.
Before writing code, design the shot: visual storytelling, pacing, rhythm, surprise,
visual hierarchy, camera language, color harmony, composition, and educational clarity.
Every frame should read like a deliberately designed illustration; every second should
carry meaningful motion. If a professional motion designer would not find a beat visually
interesting, redesign it. Do NOT produce a template animation — invent a unique visual idea.

## MOTION DESIGN — no static scenes
Objects enter elegantly, transform naturally, move with purpose, and react to their
neighbours. Avoid abrupt jumps — interpolate. In preference to plain Fade/Write, reach for:
`TransformMatchingTex`, `TransformMatchingShapes`, `ReplacementTransform`, `FadeTransform`,
`FadeTransformPieces`, `MoveToTarget`, `LaggedStart` (tune `lag_ratio`), `AnimationGroup`,
`Succession`, `UpdateFromFunc`, `always_redraw` + `ValueTracker`. Vary entrances and
emphasis: `GrowFromCenter`, `GrowArrow`, `Circumscribe`, `Flash`, `Indicate`, `FocusOn`.
Never repeat the same reveal twice in a row.

## RHYTHM — let important ideas breathe
Alternate fast / slow / pause / emphasis. Vary `run_time` and `rate_func` (`smooth`,
`there_and_back`, `ease_in_out`). Hold on the key insight; move briskly through routine
steps. Avoid constant-speed motion.

## COMPOSITION — frame every shot
Balanced layouts, intentional whitespace, clear focal points, depth and layering
(foreground/background separation), symmetry where it helps and deliberate asymmetry where
it adds energy. Never dump everything on screen — reveal gradually via progressive
disclosure. Use the WHOLE frame; don't cluster at the origin or leave half the frame dead
for more than ~2s.

## CAMERA — part of the storytelling
Prefer `class GenScene(MovingCameraScene):` and direct the camera with intent —
`self.camera.frame.animate.scale(...)` / `.move_to(...)` to push in on the decisive moment,
follow motion, frame a detail, or pull back to reveal scale. Every camera move must have a
reason; no aimless drift. (Use `ThreeDScene` instead only when the concept is genuinely 3D.)

## EDUCATIONAL STORYTELLING — build intuition, don't dump the answer
Reveal step by step and create anticipation: each beat answers the viewer's current
question while opening the next. Turn abstractions into VISUAL METAPHORS so the viewer
FEELS the math — a function as a machine, a limit as a zoom, a derivative as tangent
motion, an integral as accumulating area, a vector as a force, a matrix transforming space,
a complex number rotating the plane, probability as flowing particles.

## EQUATIONS ARE ALIVE
Symbols move, merge, split, rearrange and morph rather than vanishing and reappearing. Use
`TransformMatchingTex` extensively so a term visibly travels from one line to the next.
Reuse and MOVE/reshape objects instead of deleting and recreating them.

## RICH, PROGRESSIVE DIAGRAMS — never minimal
Build axes, grids, labels, callouts, highlight regions, dynamic arrows, measurements,
animated braces, and legends — assembled progressively, not all at once. Keep live-updating
values (`DecimalNumber` + `always_redraw`) where they aid clarity.

## LAYERED ANIMATION — multiple things at once
Each scene runs several simultaneous layers: the hero animation, supporting annotations, a
subtle background motion, a camera move, and highlighting — not a single object moving in
isolation.

## POLISH (only when it improves clarity)
Tasteful glow (a low-opacity stroke copy added BEHIND the hero — added, never `Create`-d
alongside it), highlights, a single motion trail (`TracedPath` on ONE element, with a
visible trail that ends meaningfully), temporary guides, attention cues, animated
measurements and legends. Close on intentional ambient motion, never a hard freeze frame.

## CODE CRAFT
Structure the scene logically with small, well-named helper functions; avoid duplication;
name mobjects for what they represent. Keep everything deterministic (fixed seeds; no
wall-clock or per-run randomness) so the same code always renders the same film.

Aim for 5-8 well-composed visual beats with clean, varied transitions between them.
"""

COLOR_LANGUAGE = """## COLOR LANGUAGE — meaning, not decoration
Choose ONE cohesive palette and use color SEMANTICALLY and consistently across the whole
scene — a concept keeps its color in equations, graphs, vectors and labels. Default roles:
- blue = known / given          - red = contradiction / warning
- yellow = current focus         - purple = auxiliary / construction
- green = result / conclusion    - orange = transformation in progress
Stay within this palette plus neutrals (white/grey for axes, labels, structure). Do not
introduce extra hues outside these roles — a limited, consistent palette reads as designed;
a rainbow reads as noise. Honor the active VISUAL THEME's palette when one is provided.
Never colour at random.
"""

ANTI_LAZY_CINEMATIC = """## QUALITY FLOOR (cinematic)
- A clear narrative arc: hook → build → insight → resolution.
- Every second has meaningful motion across MULTIPLE coordinated layers — never a static
  frame, never just a title and one equation.
- Prefer morph/transform over fade-and-replace; reuse and move objects rather than deleting
  and recreating them.
- Every object earns its place — remove clutter rather than adding filler.
- Surprise the viewer at least once; close on deliberate ambient motion, not a frozen frame.
"""


def _cinematic_budget(tier: Tier) -> str:
    surface = "allowed when they serve the concept (keep Surface resolution ≤ (32, 64))" if tier.allow_surface else "avoid Surface/ParametricSurface"
    threed = "allowed" if tier.allow_3d else "avoid"
    return f"""## PERFORMANCE ENVELOPE (tier: {tier.name} — capable hardware, be ambitious but clean)
You have generous resources. Prioritize a polished, correct, readable animation over raw object count.
- Updaters (`always_redraw`/`add_updater`): up to {tier.max_updaters}. Prefer `ValueTracker` + `always_redraw` for live parameters.
- 3D (`ThreeDScene`): {threed}. Surfaces: {surface}.
- Keep within roughly {tier.point_budget} "effort points" of complexity so the render stays stable — an elegant frame beats a crowded one.
- A crowded or overlapping frame is a defect. When unsure, compose more carefully rather than adding more objects.
"""


def _constrained_budget() -> str:
    """The strict 8 GB-laptop budget (today's behavior)."""
    return "\n\n".join([STYLE_DIRECTIVES, HARDWARE_BUDGET, ANTI_LAZY, HARDWARE_3D_LIMITS])


def _style_and_budget_sections(tier: Tier) -> list[str]:
    """Return the tier-appropriate style + performance sections."""
    if tier.name == "constrained":
        return [_constrained_budget()]
    return [CINEMATIC_STYLE, COLOR_LANGUAGE, _cinematic_budget(tier), ANTI_LAZY_CINEMATIC]


def budget_block(tier: Tier | None = None) -> str:
    """Return just the tier's performance envelope (no full style block).

    Used by formats with their own style rules (e.g. TikTok) that still need to
    respect the hardware budget — previously these dropped the budget entirely.
    """
    tier = tier or get_tier()
    if tier.name == "constrained":
        return HARDWARE_BUDGET + "\n\n" + HARDWARE_3D_LIMITS
    return _cinematic_budget(tier)


# ── Fix/repair prompts ───────────────────────────────────────────────────────

FIX_INTRO = """Previous Manim script failed with this error:
```
{error}
```
Fix the bug. Keep the SAME visual concept and change as little as possible —
repair the defect, don't redesign. {budget_note}
"""

# Tier-specific tail for FIX_INTRO. On the constrained tier, trimming complexity
# is a valid repair; on capable tiers it would wrongly contradict the cinematic
# "several simultaneous layers" direction, so we tell it to PRESERVE the layers.
_FIX_BUDGET_NOTE_CONSTRAINED = (
    "Do not add objects/layers/effects beyond the original; simplify if needed to "
    "stay within the hardware budget."
)
_FIX_BUDGET_NOTE_CAPABLE = (
    "Preserve the original's layers and ambition — only fix what is broken."
)

LAYOUT_REPAIR_INTRO = """Layout validator found overlap/crowding:
{issues}
Fix ONLY positions, spacing, and timing. Preserve the concept and colors.
"""

# ── Complexity assessment ────────────────────────────────────────────────────

_COMPLEX_KEYWORDS = frozenset({
    "compare", "relationship", "transform", "series", "matrix",
    "surface", "fourier", "eigen", "convergence", "integral",
    "derivative", "graph", "tangent", "slope", "gradient",
})


def _assess_complexity(prompt: str) -> str:
    # Match keywords as a word PREFIX, not a free substring: this catches
    # inflections ("transformation"←transform, "derivatives"←derivative,
    # "eigenvalues"←eigen) while rejecting the false positives a bare substring
    # check produced ("paragraph"/"telegraph" no longer match "graph").
    tokens = re.findall(r"[a-z]+", prompt.lower())
    word_count = len(prompt.split())
    has_complex = any(
        tok.startswith(kw) for tok in tokens for kw in _COMPLEX_KEYWORDS
    )

    if word_count > 12 or (word_count > 6 and has_complex):
        return "COMPLEX"
    elif word_count <= 4 and not has_complex:
        return "SIMPLE"
    return "MEDIUM"


def build_complexity_modifier(prompt: str, tier: Tier | None = None) -> str:
    tier = tier or get_tier()
    level = _assess_complexity(prompt)
    if tier.name == "constrained":
        if level == "SIMPLE":
            return "## Simple concept\n2-3 layers, 12-18 seconds. Quality over quantity."
        elif level == "COMPLEX":
            return "## Multi-concept scene\nUp to 3 layers, 20-25 seconds. Still respect ALL hardware limits."
        return ""
    # Capable tiers — scale ambition with complexity.
    if level == "SIMPLE":
        return "## Simple concept\nKeep it focused (15-22s), but still beautifully composed and polished."
    elif level == "COMPLEX":
        return "## Multi-concept scene\nDevelop it fully: multiple coordinated beats, 25-40s, deliberate composition and camera work where it helps."
    return ""


# ── Scene plan prompt ────────────────────────────────────────────────────────

SCENE_PLAN_SYSTEM_PROMPT = """Plan a Manim animation scene layout as JSON. Output ONLY valid JSON.

Every object MUST include all of these fields: id, type, role, position, priority, visible_from, visible_to.

{
  "objects": [
    {"id": "name", "type": "Text|MathTex|Circle|...", "role": "background|primary|annotation", "position": "top|center|bottom|left|right", "priority": 1, "visible_from": 0, "visible_to": 15}
  ],
  "phases": [
    {"name": "intro", "time": [0, 3], "visible": ["title", "bg"], "action": "FadeIn"}
  ]
}

Rules:
- role: "background" = grid/atmosphere, "primary" = the main mathematical object, "annotation" = labels/arrows/highlights
- priority: 1=essential, 2=important, 3=decoration
- Each phase transitions cleanly (old out, new in)

Valid field values (use ONLY these):
- type: a real Manim CE class — Text, MathTex, Tex, Circle, Square, Line, Arrow, Dot,
  Axes, NumberPlane, VGroup, Polygon, Rectangle (no invented class names).
- position: one of top, center, bottom, left, right, top_left, top_right,
  bottom_left, bottom_right.
- priority: integer 1, 2, or 3.
- visible_from / visible_to: numbers in seconds, with visible_from < visible_to, and
  every object's window inside the overall timeline (phase times below).
- phases[].time: a [start, end] pair in seconds, contiguous and non-overlapping.
"""

# ── Assembly functions ────────────────────────────────────────────────────────

def build_manim_system_prompt(
    theme_instructions: str = "",
    prompt: str = "",
    scene_plan: str = "",
    tier: Tier | None = None,
    storyboard: str = "",
) -> str:
    """Build the tier-aware system prompt for code generation.

    When a ``storyboard`` (cinematography IR) is supplied it is the AUTHORITATIVE
    plan the generator must implement beat-by-beat; the lighter ``scene_plan``
    layout is only used as a fallback when there is no storyboard.
    """
    tier = tier or get_tier()
    sections = [BASE_MANIM_RULES]
    sections.extend(_style_and_budget_sections(tier))
    sections.append(SCENE_AWARENESS)
    complexity = build_complexity_modifier(prompt, tier) if prompt else ""
    if complexity:
        sections.append(complexity)
    if storyboard:
        # The director's plan wins — it already encodes composition/timing/camera.
        sections.append(storyboard)
    elif scene_plan:
        sections.append(f"## Scene Layout\n{scene_plan}")
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_scene_plan_prompt() -> str:
    return SCENE_PLAN_SYSTEM_PROMPT


def build_layout_repair_prompt(issues: str, theme_instructions: str = "", prompt: str = "", tier: Tier | None = None) -> str:
    tier = tier or get_tier()
    safe_issues = issues.replace("{", "{{").replace("}", "}}")
    # Layout repair only nudges positions/spacing/timing — it does NOT regenerate
    # the scene. So we keep the lightweight layout rules (SCENE_AWARENESS) and the
    # API-safety floor (BASE_MANIM_RULES) but DROP the heavy style/budget blocks
    # that would otherwise balloon a focused repair with irrelevant direction.
    sections = [LAYOUT_REPAIR_INTRO.format(issues=safe_issues), BASE_MANIM_RULES, SCENE_AWARENESS]
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_manim_fix_prompt(error: str, theme_instructions: str = "", prompt: str = "", tier: Tier | None = None) -> str:
    tier = tier or get_tier()
    safe_error = error.replace("{", "{{").replace("}", "}}")
    budget_note = _FIX_BUDGET_NOTE_CONSTRAINED if tier.name == "constrained" else _FIX_BUDGET_NOTE_CAPABLE
    sections = [FIX_INTRO.format(error=safe_error, budget_note=budget_note), BASE_MANIM_RULES]
    sections.extend(_style_and_budget_sections(tier))
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)

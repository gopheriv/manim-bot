"""Prompt builder — tier-aware prompts for the Manim code generator.

Philosophy: quality-first, scaled to the hardware. On capable hardware
(cinematic/standard tiers) the model is directed to compose ambitious,
professionally directed animations. On the constrained tier (8 GB laptop) it
falls back to the strict "elegant minimalism" budget that keeps renders alive.
The budget is a *tier*, not a global law.
"""

from __future__ import annotations

from render_tier import Tier, get_tier


# Detect the installed Manim version once so prompts can pin the API surface the
# model must target (prevents fixes from reintroducing removed/renamed APIs).
try:
    import manim as _manim
    MANIM_VERSION = getattr(_manim, "__version__", "0.20.x")
except Exception:
    MANIM_VERSION = "0.20.x"


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
"""

# ── HARDWARE BUDGET (the critical addition) ───────────────────────────────────

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
| Scene > 200 frames | +1/frame | stay under 200 |
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

CINEMATIC_STYLE = """## Visual Direction (cinematic — aim for a professionally directed explainer)
Make it clear AND beautiful. Compose every frame on purpose.

- **Composition**: think in layers — a subtle background/atmosphere, the supporting
  structure (axes, grids, vectors), and the hero mathematical object in front. Use the
  WHOLE frame; balance negative space; don't cluster everything at the origin.
- **Semantic, consistent color**: each concept keeps its color across equations, graphs,
  vectors and labels. Pick a small, cohesive palette and stick to it.
- **Strong motion design**: `Create`/`Write`/`DrawBorderThenFill` for hero objects,
  `LaggedStart` for staggered reveals, `ReplacementTransform` to morph between related
  forms. Ease with `rate_func` (smooth, there_and_back). No dead frames > 0.4s.
- **Camera as a tool**: with `MovingCameraScene`, push in on the key moment, frame a
  detail, or pull back to reveal scale — only when it serves the idea.
- **Polish**: a soft glow on the hero object, a faint guiding grid, a gentle ambient
  drift to close (never a hard freeze frame).
- **Pacing by cognitive load**: simple beats ~2s, rich transforms 4-6s. Total duration
  20-40s is welcome when the content earns it.

Aim for 4-7 well-composed visual beats with clean transitions between them.
"""

ANTI_LAZY_CINEMATIC = """## Quality Floor (cinematic)
- A clear narrative arc: hook → build → insight → resolution.
- Multiple coordinated elements working together — not just a title and one equation.
- Every object earns its place; remove clutter rather than adding filler.
- Close on intentional ambient motion, not a frozen frame.
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
    return [CINEMATIC_STYLE, _cinematic_budget(tier), ANTI_LAZY_CINEMATIC]


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
Fix the bug. Keep the SAME visual concept.
Do NOT add more objects, layers, or effects than the original.
Simplify if needed to stay within hardware budget.
"""

LAYOUT_REPAIR_INTRO = """Layout validator found overlap/crowding:
{issues}
Fix ONLY positions, spacing, and timing. Preserve the concept and colors.
"""

# ── Complexity assessment ────────────────────────────────────────────────────

def _assess_complexity(prompt: str) -> str:
    words = prompt.lower().split()
    word_count = len(words)
    complex_keywords = [
        "compare", "relationship", "transform", "series", "matrix",
        "surface", "fourier", "eigen", "convergence", "integral",
        "derivative", "graph", "tangent", "slope", "gradient",
    ]
    has_complex = any(kw in prompt.lower() for kw in complex_keywords)

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
"""

# ── Assembly functions ────────────────────────────────────────────────────────

def build_manim_system_prompt(
    theme_instructions: str = "",
    prompt: str = "",
    scene_plan: str = "",
    tier: Tier | None = None,
) -> str:
    """Build the tier-aware system prompt for code generation."""
    tier = tier or get_tier()
    sections = [BASE_MANIM_RULES]
    sections.extend(_style_and_budget_sections(tier))
    sections.append(SCENE_AWARENESS)
    complexity = build_complexity_modifier(prompt, tier) if prompt else ""
    if complexity:
        sections.append(complexity)
    if scene_plan:
        sections.append(f"## Scene Layout\n{scene_plan}")
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_scene_plan_prompt() -> str:
    return SCENE_PLAN_SYSTEM_PROMPT


def build_layout_repair_prompt(issues: str, theme_instructions: str = "", prompt: str = "", tier: Tier | None = None) -> str:
    tier = tier or get_tier()
    safe_issues = issues.replace("{", "{{").replace("}", "}}")
    sections = [LAYOUT_REPAIR_INTRO.format(issues=safe_issues), BASE_MANIM_RULES]
    sections.extend(_style_and_budget_sections(tier))
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_manim_fix_prompt(error: str, theme_instructions: str = "", prompt: str = "", tier: Tier | None = None) -> str:
    tier = tier or get_tier()
    safe_error = error.replace("{", "{{").replace("}", "}}")
    sections = [FIX_INTRO.format(error=safe_error), BASE_MANIM_RULES]
    sections.extend(_style_and_budget_sections(tier))
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)

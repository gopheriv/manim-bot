"""Prompt builder — compact, hardware-aware prompts for GPT-5.5.

Philosophy: elegant minimalism over cinematic excess.
A beautiful 3-layer scene that renders in 10s beats a 7-layer
scene that OOMs on 8GB RAM.
"""

from __future__ import annotations


# ── Core rules ────────────────────────────────────────────────────────────────

BASE_MANIM_RULES = """You write Manim Community Edition animation code.
Output ONLY Python code. No explanation, no markdown fences.

## Structure
- `from manim import *` and `import numpy as np`
- `class GenScene(Scene):` with `def construct(self):`
- Set `self.camera.background_color = "HEX"` in construct()
- Runnable via `manim -qm file.py GenScene`
- Use ONLY Manim CE built-ins — no external libs, no network
- Set properties via methods: `.set_stroke()`, `.set_fill()`, `.set_opacity()` — avoid kwargs like `stroke_color=` in constructors when possible
- Total duration: 12-25 seconds
- Max 150 total animation frames

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
    ]
    has_complex = any(kw in prompt.lower() for kw in complex_keywords)

    if word_count > 12 or (word_count > 6 and has_complex):
        return "COMPLEX"
    elif word_count <= 4 and not has_complex:
        return "SIMPLE"
    return "MEDIUM"


def build_complexity_modifier(prompt: str) -> str:
    level = _assess_complexity(prompt)
    if level == "SIMPLE":
        return "## Simple concept\n2-3 layers, 12-18 seconds. Quality over quantity."
    elif level == "COMPLEX":
        return "## Multi-concept scene\nUp to 3 layers, 20-25 seconds. Still respect ALL hardware limits."
    return ""


# ── Scene plan prompt ────────────────────────────────────────────────────────

SCENE_PLAN_SYSTEM_PROMPT = """Plan a Manim animation scene layout as JSON. Output ONLY valid JSON.

{
  "objects": [
    {"id": "name", "type": "Text|MathTex|Circle|...", "position": "top|center|bottom|left|right", "priority": 1, "visible_from": 0, "visible_to": 15}
  ],
  "phases": [
    {"name": "intro", "time": [0, 3], "visible": ["title", "bg"], "action": "FadeIn"}
  ]
}

Rules:
- Max 3 objects visible simultaneously
- priority: 1=essential, 2=important, 3=decoration
- Max 5 objects total
- Each phase transitions cleanly (old out, new in)
"""

# ── Assembly functions ────────────────────────────────────────────────────────

def build_manim_system_prompt(
    theme_instructions: str = "",
    prompt: str = "",
    scene_plan: str = "",
) -> str:
    """Build system prompt for code generation."""
    sections = [BASE_MANIM_RULES, STYLE_DIRECTIVES, HARDWARE_BUDGET, SCENE_AWARENESS, ANTI_LAZY]
    complexity = build_complexity_modifier(prompt) if prompt else ""
    if complexity:
        sections.append(complexity)
    if scene_plan:
        sections.append(f"## Scene Layout\n{scene_plan}")
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_scene_plan_prompt() -> str:
    return SCENE_PLAN_SYSTEM_PROMPT


def build_layout_repair_prompt(issues: str, theme_instructions: str = "", prompt: str = "") -> str:
    safe_issues = issues.replace("{", "{{").replace("}", "}}")
    sections = [
        LAYOUT_REPAIR_INTRO.format(issues=safe_issues),
        BASE_MANIM_RULES,
        STYLE_DIRECTIVES,
        HARDWARE_BUDGET,
    ]
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_manim_fix_prompt(error: str, theme_instructions: str = "", prompt: str = "") -> str:
    safe_error = error.replace("{", "{{").replace("}", "}}")
    sections = [
        FIX_INTRO.format(error=safe_error),
        BASE_MANIM_RULES,
        STYLE_DIRECTIVES,
        HARDWARE_BUDGET,
    ]
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)

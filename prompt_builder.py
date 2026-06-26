"""Prompt builder — compressed for speed.

Qwen 3.7 Max takes 5+ min with the old 240-line prompt.
This version is ~60 lines — same directives, no code examples.
"""

from __future__ import annotations


BASE_MANIM_RULES = """You are a world-class Manim animator producing cinematic mathematical visualizations.
Write ONLY valid Python Manim code. No explanation, no markdown fences.

## Rules
- `from manim import *` and `import numpy as np`
- Class named `GenScene` with `def construct(self)`
- Runnable via `manim -qm <file>.py GenScene`
- Set background: `self.camera.background_color = "HEX"` in construct()
- Use ONLY Manim CE built-in APIs — no external libraries, no network calls
- Avoid version-fragile kwargs. Build objects first, then `.set_stroke()`, `.set_fill()`, `.set_opacity()`
- Total scene duration: 15-30 seconds
- MAX 200 total animation frames across all `self.play()` calls

## NUMPY 2.x COMPATIBILITY (CRITICAL — will crash otherwise)
- NEVER use `np.math.*` — use `math.*` instead (factorial, pi, e, etc.)
- NEVER use `np.float`, `np.int`, `np.bool`, `np.complex`, `np.object`, `np.str` — use Python builtins `float`, `int`, `bool`, `complex`, `object`, `str`
- NEVER use `np.string_` — use `str`
- Use `np.float64`, `np.int64` if you need typed numpy scalars
- Import `import math` for `math.factorial`, `math.pi`, `math.e`, `math.sin`, etc.
"""

CINEMATIC_DIRECTIVES = """## CINEMATIC VISUAL DIRECTIVES (MANDATORY)

### 1. Layered Composition (minimum 4 layers)
Every scene MUST contain:
- **Background**: particle field, grid, or ambient geometry (15-30 elements like stars/dots)
- **Primary**: the main mathematical object (curve, surface, diagram)
- **Annotation**: labels, equations, arrows explaining the math
- **Effect**: glow copies, trails, sweep highlights, connecting lines

### 2. Staggered Reveals (NEVER dump everything at once)
Build in 3-5 cinematic beats:
- Beat 1: atmosphere/background (FadeIn stars, grid)
- Beat 2: main object draws itself (Create)
- Beat 3: annotations sweep in (LaggedStart of Write)
- Beat 4: animation/transformation (ValueTracker animate, Transform)
- Beat 5: insight reveal (ReplacementTransform)
Use `LaggedStart` not batch `FadeIn`.

### 3. Dynamic Trails (MANDATORY for moving elements)
Every moving element gets a `TracedPath` trail or `always_redraw` companion.
Example: dot moving along curve → trail + always_redraw dot + always_redraw label.

**ValueTracker patterns (use these EXACTLY — no variations):**
```python
# Correct: ValueTracker for scalar animation
t = ValueTracker(0)
self.play(t.animate.set_value(10), run_time=3)
# Read value in always_redraw:
dot = always_redraw(lambda: Dot(ORIGIN + RIGHT * t.get_value()))
```
NEVER call `t.get_value()` outside a lambda or updater — it only changes during `self.play()`.

### 4. Glow Effects
Every significant object has a glow layer: thick stroke (width 8-16), low opacity (0.1-0.2) behind the thin bright line.
Use `set_color_by_gradient` for curves. Add pulsing updaters to glow opacity.

### 5. Ambient Life (NEVER a dead frame)
The scene must always have something alive: stars drift via sin/cos updaters, objects pulse, trails fade.
Even in `self.wait()`, at least 2 updater-driven elements must be active.

### 6. Screen Real Estate
Use the ENTIRE screen. Main object: center/left-center, 40-60% frame width.
Supporting geometry spread across remaining space. Text/equations at bottom strip or edges.
Don't waste space — fill with meaningful visual information.
"""

ANTI_LAZY = """## ANTI-LAZY RULES

❌ NEVER produce 1-2 objects with 1 animation
❌ NEVER use FadeIn/FadeOut as primary animation — use Create, Write, DrawBorderThenFill, MoveAlongPath
❌ NEVER leave screen empty/blank for > 0.5s
❌ NEVER produce a static-image scene — it must have continuous motion
❌ NEVER skip glow/trail layers on significant objects
❌ NEVER end with a freeze frame — ambient animation in last 3+ seconds

✅ EVERY scene: background particles + main object + annotations + effects
✅ EVERY animation: staggered reveals (LaggedStart) not batch FadeIn
✅ EVERY moving element: TracedPath or always_redraw
✅ EVERY scene: 3+ cinematic beats
✅ EVERY scene: memorable final tableau, alive
"""

SCENE_AWARENESS_CONTRACT = """## SCENE AWARENESS (MANDATORY — prevents overlap/crowding)

Track which objects are visible, their screen regions, priorities.
- At most 3 priority-1 objects visible simultaneously in center.
- NEVER place unrelated objects at ORIGIN simultaneously.
- When new major object enters, fade/move old supporting objects.
- Use `next_to(buff>=0.3)`, `arrange()`, `shift()` for separation.
- Text/MathTex must have explicit `font_size`.
- Use VGroup(arrange()) for multiple related elements.
- Structure animations in phases: each phase has clear visible objects.
- Phase transitions: old objects fade out before new ones appear.
"""

HARDWARE_3D_LIMITS = """## 3D PERFORMANCE LIMITS (i5-1155G7 8GB RAM)

- Surface MAX resolution: (18, 36) — NEVER exceed (20, 40)
- NO updaters on Surface. MAX 1 updater per 3D scene.
- Arrow3D: MAX 15. Sphere/Cube: MAX 8. Line3D: MAX 30.
- AVOID TracedPath in ThreeDScene. Use static ParametricFunction.
- MAX 2 camera moves per scene.
- Keep 3D scenes ≤ 20 seconds.
- Consider 2D projection with depth cues instead of heavy 3D.
"""


def _assess_complexity(prompt: str) -> str:
    """Assess prompt complexity and return a complexity modifier."""
    words = prompt.lower().split()
    word_count = len(words)

    complex_keywords = [
        "compare", "relationship", "transform", "evolve", "sequence",
        "series", "multiple", "system", "equation", "matrix", "graph",
        "surface", "dimension", "projection", "fractal", "recursive",
        "convergence", "integral", "derivative", "fourier", "eigen",
    ]
    has_complex_keyword = any(kw in prompt.lower() for kw in complex_keywords)

    if word_count > 12 or (word_count > 6 and has_complex_keyword):
        return "COMPLEX"
    elif word_count <= 4 and not has_complex_keyword:
        return "SIMPLE"
    else:
        return "MEDIUM"


def build_complexity_modifier(prompt: str) -> str:
    """Return a complexity modifier string."""
    level = _assess_complexity(prompt)

    if level == "SIMPLE":
        return """## Complexity: Simple concept
Focus on execution quality over layer count:
- Minimum 3 visual layers, 12-20 seconds duration
- Still follow ALL Cinematic Directives — just don't over-engineer"""
    elif level == "COMPLEX":
        return """## Complexity: Multi-concept scene
Elaborate visuals allowed:
- Minimum 5 layers, 20-30 seconds
- Follow ALL Cinematic Directives with maximum richness"""
    else:
        return ""


SCENE_PLAN_SYSTEM_PROMPT = """You are a scene composition planner for Manim animations.

Given a user's animation description, produce a JSON scene plan describing visual composition, timing, and spatial relationships — WITHOUT dictating the creative idea.

Output ONLY valid JSON. No explanation, no markdown fences.

## Scene plan structure
{
  "canvas": {"x_range": [-7, 7], "y_range": [-4, 4], "safe_margin": 0.5},
  "objects": [
    {"id": "unique_name", "type": "Text|MathTex|Circle|...", "role": "main_title|core_concept|annotation|background|decoration|effect", "approx_size": [width, height], "position": "top|center|bottom|left|right|...", "priority": 1, "visible_from": 0, "visible_to": 15, "z_index": 5}
  ],
  "phases": [
    {"name": "phase_name", "time": [0, 3], "visible": ["object_id_1", "object_id_2"], "action": "FadeIn title, Create background"}
  ],
  "relationships": [
    {"type": "avoid_overlap|below|above|next_to|transform_into", "objects": ["obj_a", "obj_b"], "buff": 0.4}
  ]
}

## Rules
- `priority`: 1 = essential, 2 = important, 3 = decorative
- No more than 3 priority-1 objects visible simultaneously
- No more than 5 priority-1+2 objects visible simultaneously
- Every `avoid_overlap` must have `buff` >= 0.3
- Include at least one phase transition where old objects fade out before new ones appear
"""

LAYOUT_REPAIR_INTRO = """A layout validator detected potential overlap/crowding issues:

{issues}

Fix spatial conflicts ONLY. Preserve the concept, metaphor, colors, and narrative sequence.

You MAY change: positions, coordinates, next_to(), move_to(), shift(), arrange(), scale, font_size, grouping, spacing, buff values, camera framing, FadeIn/FadeOut timing.

You MUST NOT: replace with generic template, change creative metaphor, remove layers/particles/glow/trails, reduce cinematic beats, simplify mathematical content.

Apply ALL Cinematic Directives. Output ONLY valid Manim code, no explanation.
"""

FIX_INTRO = """Previous Manim script failed:
```
{error}
```
Rewrite fixing this bug. Keep the SAME visual concept and richness.
Only simplify operations that caused the specific error.
Do NOT reduce layers, particles, or visual effects.
Apply all Cinematic Directives.
"""


def build_manim_system_prompt(
    theme_instructions: str = "",
    prompt: str = "",
    scene_plan: str = "",
) -> str:
    """Build system prompt for first-pass code generation."""
    sections = [BASE_MANIM_RULES, CINEMATIC_DIRECTIVES, ANTI_LAZY, SCENE_AWARENESS_CONTRACT, HARDWARE_3D_LIMITS]
    complexity = build_complexity_modifier(prompt) if prompt else ""
    if complexity:
        sections.append(complexity)
    if scene_plan:
        sections.append(f"## Scene Composition Plan (follow this layout)\n{scene_plan}")
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_scene_plan_prompt() -> str:
    """Return the system prompt for scene plan generation."""
    return SCENE_PLAN_SYSTEM_PROMPT


def build_layout_repair_prompt(issues: str, theme_instructions: str = "", prompt: str = "") -> str:
    """Build system prompt for layout-only repair."""
    safe_issues = issues.replace("{", "{{").replace("}", "}}")
    sections = [
        LAYOUT_REPAIR_INTRO.format(issues=safe_issues),
        BASE_MANIM_RULES,
        CINEMATIC_DIRECTIVES,
        ANTI_LAZY,
        SCENE_AWARENESS_CONTRACT,
        HARDWARE_3D_LIMITS,
    ]
    complexity = build_complexity_modifier(prompt) if prompt else ""
    if complexity:
        sections.append(complexity)
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)


def build_manim_fix_prompt(error: str, theme_instructions: str = "", prompt: str = "") -> str:
    """Build system prompt for repairing failed code."""
    safe_error = error.replace("{", "{{").replace("}", "}}")
    sections = [FIX_INTRO.format(error=safe_error), BASE_MANIM_RULES, CINEMATIC_DIRECTIVES, ANTI_LAZY, SCENE_AWARENESS_CONTRACT, HARDWARE_3D_LIMITS]
    complexity = build_complexity_modifier(prompt) if prompt else ""
    if complexity:
        sections.append(complexity)
    if theme_instructions:
        sections.append(theme_instructions)
    return "\n\n".join(sections)

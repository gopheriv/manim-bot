# Manim Research — Sourced Reference for Bug Prevention

> Every claim has a source URL. ManimCE = Community Edition (what THIS project uses).
> ManimGL = 3b1b's personal engine (design ideas only — NEVER copy GL code).

---

## A. ManimCE Engine Reference

### A.1 Minimal Scene Anatomy

```python
from manim import *

class GenScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
```

- `Scene` is the base class. `construct()` is the main method — Manim calls it automatically.
  (https://docs.manim.community/en/stable/tutorials/quickstart.html)
- `self.play(Animation)` renders an animation. Multiple animations in one call run simultaneously.
- `self.wait(duration)` holds the frame for `duration` seconds (default 1).
- `self.add(mobject)` adds a mobject to the scene instantly (no animation).
- `self.remove(mobject)` removes a mobject instantly.

### A.2 Core Mobjects — Constructor Signatures

| Mobject | Key Parameters | Source |
|---------|---------------|--------|
| `Text(text, font_size=48, color=WHITE, font="", slant=NORMAL, weight=NORMAL)` | Pango-based, no LaTeX needed | https://docs.manim.community/en/stable/reference/manim.mobject.text.text_mobject.Text.html |
| `MathTex(tex_string, substrings_to_isolate=None, tex_to_color_map=None, font_size=48)` | Auto-wraps in math mode `$...$`. Requires LaTeX installed. | https://docs.manim.community/en/stable/reference/manim.mobject.text.tex_mobject.MathTex.html |
| `Tex(tex_string, font_size=48)` | LaTeX text mode (not auto-wrapped in `$...$`). | https://docs.manim.community/en/stable/reference/manim.mobject.text.tex_mobject.Tex.html |
| `Circle(radius=1, color=WHITE, **kwargs)` | | https://docs.manim.community/en/stable/reference/manim.mobject.geometry.arc.Circle.html |
| `Square(side_length=2, color=WHITE, **kwargs)` | | https://docs.manim.community/en/stable/reference/manim.mobject.geometry.polygram.Square.html |
| `Line(start, end, color=WHITE, buff=0, **kwargs)` | `buff` shortens the line at each end | https://docs.manim.community/en/stable/reference/manim.mobject.geometry.line.Line.html |
| `Arrow(start, end, buff=0.2, color=WHITE, max_tip_length_to_length_ratio=0.25, **kwargs)` | | https://docs.manim.community/en/stable/reference/manim.mobject.geometry.line.Arrow.html |
| `Dot(point=ORIGIN, radius=0.08, color=WHITE, **kwargs)` | | https://docs.manim.community/en/stable/reference/manim.mobject.geometry.arc.Dot.html |
| `Axes(x_range=None, y_range=None, x_length=None, y_length=None, axis_config=None, tips=True)` | Default x: (-7.11, 7.11), y: (-4, 4) | https://docs.manim.community/en/stable/reference/manim.mobject.graphing.coordinate_systems.Axes.html |
| `NumberPlane(x_range=(-7.11, 7.11), y_range=(-4, 4), **kwargs)` | Background grid | https://docs.manim.community/en/stable/reference/manim.mobject.graphing.number_line.NumberPlane.html |
| `VGroup(*mobjects, **kwargs)` | Groups mobjects. Supports `.arrange(direction, buff=0.25)` | https://docs.manim.community/en/stable/reference/manim.mobject.types.vectorized_mobject.VGroup.html |

### A.3 Core Animations

| Animation | Purpose | Source |
|-----------|---------|--------|
| `Create(mobject, **kwargs)` | Draw a VMobject stroke-by-stroke | https://docs.manim.community/en/stable/reference/manim.animation.creation.Create.html |
| `Write(mobject, **kwargs)` | Write text/formula (uses AddTextLetterByLetter internally) | https://docs.manim.community/en/stable/reference/manim.animation.creation.Write.html |
| `FadeIn(mobject, shift=None, scale=1, **kwargs)` | Fade in with optional motion | https://docs.manim.community/en/stable/reference/manim.animation.fading.FadeIn.html |
| `FadeOut(mobject, shift=None, scale=1, **kwargs)` | Fade out with optional motion | https://docs.manim.community/en/stable/reference/manim.animation.fading.FadeOut.html |
| `Transform(mobject, target_mobject, **kwargs)` | Morph one mobject into another | https://docs.manim.community/en/stable/reference/manim.animation.transform.Transform.html |
| `ReplacementTransform(mobject, target_mobject, **kwargs)` | Like Transform but replaces source in scene | https://docs.manim.community/en/stable/reference/manim.animation.transform.ReplacementTransform.html |
| `TransformMatchingTex(source, target)` | Morph LaTeX keeping shared terms | https://docs.manim.community/en/stable/reference/manim.animation.transform.TransformMatchingTex.html |
| `MoveAlongPath(mobject, path, **kwargs)` | Move mobject along a VMobject path | https://docs.manim.community/en/stable/reference/manim.animation.creation.MoveAlongPath.html |
| `GrowFromCenter(mobject, **kwargs)` | Scale from 0 at center to full size | https://docs.manim.community/en/stable/reference/manim.animation.growing.GrowFromCenter.html |
| `GrowArrow(arrow, **kwargs)` | Grow an arrow from its start point | https://docs.manim.community/en/stable/reference/manim.animation.growing.GrowArrow.html |
| `Circumscribe(mobject, **kwargs)` | Draw a rectangle around, then fade | https://docs.manim.community/en/stable/reference/manim.animation.indication.Circumscribe.html |
| `Indicate(mobject, **kwargs)` | Flash/scale emphasis | https://docs.manim.community/en/stable/reference/manim.animation.indication.Indicate.html |
| `Flash(mobject_or_point, **kwargs)` | Radial flash lines | https://docs.manim.community/en/stable/reference/manim.animation.indication.Flash.html |
| `LaggedStart(*animations, lag_ratio=0.05)` | Stagger animations with delay | https://docs.manim.community/en/stable/reference/manim.animation.composition.LaggedStart.html |
| `AnimationGroup(*animations)` | Run animations simultaneously | https://docs.manim.community/en/stable/reference/manim.animation.composition.AnimationGroup.html |
| `Succession(*animations)` | Run animations one after another | https://docs.manim.community/en/stable/reference/manim.animation.composition.Succession.html |
| `ShowPassingFlash(mobject, **kwargs)` | Brief flash traveling along path | https://docs.manim.community/en/stable/reference/manim.animation.creation.ShowPassingFlash.html |

**`.animate` syntax** — chains method calls into animations:
```python
self.play(circle.animate.shift(RIGHT).set_color(RED), run_time=2)
```
(https://docs.manim.community/en/stable/reference/manim.mobject.mobject.Mobject.html#manim.mobject.mobject.Mobject.animate)

### A.4 Graphs / Plots / ValueTracker

| Feature | ManimCE API | Notes | Source |
|---------|-------------|-------|--------|
| Plot a function | `axes.plot(func, x_range=None, **kwargs)` | `get_graph` was DEPRECATED in v0.14.0 and renamed to `plot()`; it still exists as a shim in 0.20.1 and emits a DeprecationWarning — prefer `axes.plot()` | https://docs.manim.community/en/stable/changelog/0.14.0-changelog.html |
| Parametric curve | `axes.plot_parametric_curve(func, **kwargs)` | | https://docs.manim.community/en/stable/reference/manim.mobject.graphing.coordinate_systems.ParametricFunction.html |
| Implicit curve | `axes.plot_implicit_curve(func, **kwargs)` | | Axes reference |
| Derivative graph | `axes.plot_derivative_graph(graph, **kwargs)` | | Axes reference |
| Area under curve | `axes.get_area(graph, x_range, color=None)` | | CoordinateSystem reference |
| Riemann rectangles | `axes.get_riemann_rectangles(graph, x_range=None, dx=0.1, input_sample_type="left", **kwargs)` | | CoordinateSystem reference |
| ValueTracker | `ValueTracker(initial_value=0)` | `.get_value()`, `.set_value()`, `.increment_value()` | https://docs.manim.community/en/stable/reference/manim.mobject.value_tracker.ValueTracker.html |
| Updater | `mobject.add_updater(func)` | `func` receives `(mobject, dt)` or `(mobject)`. Call `mobject.clear_updaters()` to remove. | Mobject reference |
| always_redraw | `always_redraw(func)` | `func` returns a new mobject each frame. EXPENSIVE. | https://docs.manim.community/en/stable/reference/manim.mobject.mobject.Mobject.html |
| DecimalNumber | `DecimalNumber(num_decimal_places=2, **kwargs)` | Often paired with `add_updater(lambda d: d.set_value(tracker.get_value()))` | Reference |
| Coords to point | `axes.c2p(x, y)` or `axes @ (x, y)` (v0.19+) | Converts graph coords to scene coords | Axes reference |
| Point to coords | `axes.p2c(point)` or `axes @ point` (v0.19+) | Inverse of c2p | Axes reference |

### A.5 Positioning

| Method | Purpose | Source |
|--------|---------|--------|
| `.move_to(point)` | Move center to absolute point | Mobject reference |
| `.shift(vector)` | Move relative to current position | Mobject reference |
| `.next_to(mobject, direction=RIGHT, buff=0.25)` | Place adjacent to another mobject | Mobject reference |
| `.to_edge(direction)` | Move to edge of frame (e.g. `UP`, `LEFT`) | Mobject reference |
| `.to_corner(direction)` | Move to corner (e.g. `UL`, `DR`) | Mobject reference |
| `.arrange(direction, buff=0.25)` | Arrange VGroup children in a direction | VGroup reference |
| `.align_to(mobject, direction)` | Align edge with another mobject | Mobject reference |

**Frame dimensions**: Default visible frame is **14.22 units wide × 8.0 units tall** (16:9 aspect).
Coordinates: x ∈ [-7.11, 7.11], y ∈ [-4.0, 4.0]. Objects outside these bounds are invisible.
(https://docs.manim.community/en/stable/reference/manim.constants.html — `FRAME_WIDTH = 14.22`, `FRAME_HEIGHT = 8.0`)

**Direction constants**: `UP = [0, 1, 0]`, `DOWN = [0, -1, 0]`, `LEFT = [-1, 0, 0]`, `RIGHT = [1, 0, 0]`,
`UR = UP + RIGHT`, `UL = UP + LEFT`, `DR = DOWN + RIGHT`, `DL = DOWN + LEFT`,
`ORIGIN = [0, 0, 0]`.
(https://docs.manim.community/en/stable/reference/manim.constants.html)

### A.6 LaTeX Requirements

- `MathTex` and `Tex` require a LaTeX distribution (TeX Live on Linux/macOS, MiKTeX on Windows).
  (https://docs.manim.community/en/stable/installation/windows.html)
- `Text` does NOT require LaTeX — it uses Pango/Cairo for font rendering.
- Common LaTeX errors:
  - Missing packages → `LaTeX Error: File '*.sty' not found` → install via `tlmgr install <package>` or MiKTeX auto-install
  - Unescaped special characters: `#`, `$`, `%`, `&`, `_`, `{`, `}` must be escaped in LaTeX strings
  - Use raw strings `r"..."` to avoid Python escape conflicts with LaTeX backslashes
  - Custom preambles via `TexTemplate` + `template.add_to_preamble(r"\usepackage{amsmath}")`
  - `MathTex` double-brace splitting bug was fixed in v0.20.1
  (https://docs.manim.community/en/stable/changelog/0.20.0-changelog.html)

### A.7 Color API

- Built-in colors: `RED`, `BLUE`, `GREEN`, `YELLOW`, `ORANGE`, `PURPLE`, `TEAL`, `PINK`, `GOLD`,
  `MAROON`, `GREY`, `WHITE`, `BLACK` and graded variants (`BLUE_A` through `BLUE_E`).
  (https://docs.manim.community/en/stable/reference/manim.utils.color.html)
- `ManimColor("#hex")` wraps a hex string for color operations.
- `interpolate_color(c1, c2, alpha)` requires **ManimColor objects**, NOT bare strings.
  WRONG: `interpolate_color("#3498db", RED, 0.5)` → crashes.
  CORRECT: `interpolate_color(ManimColor("#3498db"), RED, 0.5)`.
- `set_color("#hex")` and constructor `color="#hex"` DO accept bare strings.
- `color_gradient([c1, c2], num)` requires ManimColor objects in the list.
- `set_color_by_gradient(c1, c2)` on a VMobject is safe.
- v0.18.0: `colour` library dependency removed, replaced with built-in `ManimColor`.
  (https://docs.manim.community/en/stable/changelog/0.18.0-changelog.html)

---

## B. 3Blue1Brown Design Principles (ideas only — NOT code to copy)

### B.1 The 5-Stage Pedagogical Arc

Every 3b1b video follows guided discovery, not "definition → theorem → proof":

1. **Concrete Hook** — Start with a tangible question the viewer already has intuition about.
   - Calculus: "Can you rediscover the area of a circle?" (https://www.3blue1brown.com/lessons/essence-of-calculus)
   - Linear Algebra: "What does a vector actually look like?" (https://www.3blue1brown.com/lessons/vectors)
   - Neural Networks: "What does a 2 look like to a computer?" (https://www.3blue1brown.com/lessons/neural-networks)

2. **Build Intuition Through Manipulation** — Let the viewer "feel" the concept.
   - Unwrap circle rings into rectangles (calculus)
   - Tip-to-tail vector addition (vectors)
   - Watch grid lines morph under a matrix (linear transformations)

3. **Formalize** — Only after intuition is built, introduce notation. The viewer already knows what it *means*.
   - dx is a concrete small number like 0.1 that shrinks toward zero
   - A matrix IS just "where do the basis vectors go"

4. **Generalize** — Show the specific case was an instance of a broader principle.

5. **Payoff / Surprise** — End with an "aha" moment or unexpected connection.

### B.2 Semantic Color System

| Concept Role | Color | Evidence |
|-------------|-------|----------|
| Primary variable / x-axis | BLUE | `t2c={"x": BLUE}` in project CLAUDE.md |
| Secondary variable / y-axis | RED or YELLOW | `t2c={"y": RED}` in CLAUDE.md |
| Highlighted / important term | YELLOW or GOLD | Used for emphasis throughout |
| Positive values | BLUE | Neural network lesson |
| Negative values | RED | Neural network lesson |
| Axes, structure | GREY | `DEFAULT_LIGHT_COLOR = GREY_B` |

**Rule**: One concept = one color, bound CONSISTENTLY across the whole scene.
(https://github.com/3b1b/videos — CLAUDE.md project style guide)

### B.3 Pacing

- One scene = one visual beat. Videos are composed of many short scenes.
- `self.wait()` after every significant reveal — gives the viewer time to absorb.
- Objects appear via `FadeIn` with `lag_ratio=0.1`, not instant pop-in.
- A `self.wait()` before the "aha" moment — breath before insight.
- Never show the formula before the intuition — formal expression appears after the visual.
- Complex diagrams are assembled piece by piece (staggered `FadeIn`), not shown all at once.
- Ghost copy of "before" state stays visible during transformations.
  (https://www.3blue1brown.com/lessons/linear-transformations)

### B.4 Recurring Visual Devices + ManimCE Equivalents

| Device | When Used | ManimCE Equivalent |
|--------|-----------|-------------------|
| Number line / axis | 1D concepts, scalars | `NumberLine()`, `Axes()` |
| Vector arrow | Linear algebra, forces | `Arrow(start, end, buff=0)` |
| Grid / coordinate space | Transformations | `NumberPlane()` + `ApplyMatrix(matrix)` |
| Grid morph with ghost | Linear maps | `plane.copy().set_opacity(0.3)` as ghost + `Transform(plane, target)` |
| Dot tracing a path | Parametric curves | `Dot()` + `TracedPath(dot.get_center)` |
| Axes + plotted curve | Calculus, functions | `Axes()` + `axes.plot(func)` |
| Area under curve | Integrals | `axes.get_area(graph, x_range)` |
| Riemann rectangles | Integration convergence | `axes.get_riemann_rectangles(graph, dx=0.1)` |
| Tangent line | Derivatives | `always_redraw` + custom tangent construction |
| Secant approaching | Limit definition | `ValueTracker` + `always_redraw` with `Line` |
| Camera zoom-in | Limits, "locally linear" | `MovingCameraScene` + `self.camera.frame.animate.scale(0.1).move_to(point)` |
| Cascading reveal | Sets, layers, sequences | `LaggedStart(*anims, lag_ratio=0.1)` or `FadeIn(group, lag_ratio=0.1)` |
| ValueTracker knob | Dynamic parameter | `ValueTracker` + `always_redraw` |
| Colored equation terms | Algebra↔geometry link | `MathTex(..., substrings_to_isolate=[...])` + `.set_color_by_tex()` |
| Unwrap/unroll metaphor | Circle area, Fourier | `Transform(arc, rectangle)` |

---

## C. Common ManimCE Failure Modes

### C.1 ManimGL Names Used on ManimCE (THE #1 bug)

| ManimGL (WRONG) | ManimCE (CORRECT) | Source |
|-----------------|-------------------|--------|
| `ShowCreation` | `Create` | https://docs.manim.community/en/stable/faq/general.html |
| `TexMobject` | `MathTex` | Same |
| `TextMobject` | `Tex` or `Text` | Same |
| `axes.get_graph(f)` | `axes.plot(f)` | Deprecated v0.14.0 (shim still exists in 0.20.1) |
| `CONFIG = {...}` | Class attrs or `__init__` | Removed v0.2.0 |
| `ApplyMethod(m.x())` | `m.animate.x()` | Preferred syntax |
| `ShowCreationThenFadeOut` | `ShowPassingFlash` | Deprecated v0.15.0 |
| `Scene.rotate_in_place()` | `.rotate()` | Removed v0.13 |
| `Scene.scale_in_place()` | `.scale()` | Removed v0.13 |

### C.2 Version-Specific Deprecations (0.18–0.20)

- v0.18.0: `colour` library removed → use `ManimColor`
- v0.18.1: `Mobject.wag()` removed; `manim new` → `manim init`
- v0.19.0: `ManimColor.from_hex(hex=)` → `hex_str=`; `Scene.next_section(type=)` → `section_type=`;
  `Sector(inner_radius, outer_radius)` → `radius`; `SurroundingRectangle` signature changed
- v0.20.0: `YELLOW_C` color value corrected; `MathTex` splitting algorithm rewritten
  (https://docs.manim.community/en/stable/changelog/)

### C.3 NumPy 2.x Compatibility

- `np.float`, `np.int`, `np.bool`, `np.complex`, `np.object`, `np.str` REMOVED in NumPy 2.0
- `np.math.*` REMOVED → use `math.*` (import math)
- Fix: use Python builtins (`float`, `int`, `bool`) or typed numpy (`np.float64`, `np.int64`)
  (NumPy 2.0 migration guide)

### C.4 Updater Issues

- Python closure bug in loops: `lambda m: m.next_to(obj, RIGHT)` captures last `obj`.
  Fix: `lambda m, o=obj: m.next_to(o, RIGHT)` (default arg captures value).
- Nested updaters (`always_redraw` inside `always_redraw`) cause infinite recursion.
- `always_redraw` is expensive — max 2 on constrained hardware.
- `wait()` can break `DecimalNumber` position inside updater (known bug, GitHub #3963).
- Updaters never removed → render hangs or extremely slow. Call `.clear_updaters()`.

### C.5 self.play() with Non-Animations

- `self.play(mobject)` → `TypeError: object is not callable`
- Fix: `self.play(Create(mobject))` or `self.play(FadeIn(mobject))`
- Empty VGroup in `self.play(FadeOut(VGroup()))` → silent no-op

### C.6 Color API Crashes

- `interpolate_color("#hex", RED, 0.5)` → `AttributeError: 'str' object has no attribute 'interpolate'`
- Fix: wrap with `ManimColor("#hex")` first
- `color_gradient(["#hex1", "#hex2"], 5)` → same error; wrap each entry

### C.7 Objects Going Off-Screen

- Frame is 14.22 × 8.0 units. Objects beyond ±7.11 (x) or ±4.0 (y) are invisible.
- Using raw scene coords `[x, y, 0]` instead of `axes.c2p(x, y)` places objects wrong.
- `is_off_screen()` method had bugs (GitHub #1158).

### C.8 LaTeX Failures

- Missing LaTeX distribution → `FileNotFoundError: latex`
- Unescaped special characters in strings
- Non-Latin scripts in `Tex` → missing glyphs (use `Text` instead, GitHub #2848)
- Long text in `Tex` auto-wraps unexpectedly (GitHub #3143)

### C.9 Class Structure Requirements

- This project requires `class GenScene(Scene):` with `def construct(self):`.
- The CI worker (`deploy/ci_render.py`) checks for `"class GenScene"` and `"def construct"`.
- Wrong class name or missing method → render blocked.

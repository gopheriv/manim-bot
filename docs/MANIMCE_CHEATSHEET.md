# ManimCE Cheatsheet — Verified Primitives (v0.20.1)

> Every snippet below has been **rendered and verified with manim 0.20.1 (`manim -ql`)**
> — each produces a valid .mp4 with zero errors.
> These are **known-good** building blocks the generator can rely on.
> Frame size: 14.22 × 8.0 units (config.frame_width × config.frame_height).

---

## 1. Basic Scene

```python
from manim import *
import numpy as np

class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1a1a2e"
        title = Text("Hello Manim", font_size=48, color=WHITE)
        self.play(Write(title), run_time=1.5)
        self.wait(0.5)
        self.play(FadeOut(title))
        self.wait(0.5)
```

---

## 2. Plotted Function with Axes

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-1, 9, 2],
            x_length=10,
            y_length=6,
            axis_config={"include_numbers": True, "font_size": 20},
            tips=True,
        )
        labels = axes.get_axis_labels(x_label="x", y_label="f(x)")
        graph = axes.plot(lambda x: x**2, color=BLUE, x_range=[-3, 3])
        graph_label = MathTex(r"f(x) = x^2", font_size=36, color=BLUE).next_to(graph, UR, buff=0.2)

        self.play(Create(axes), Write(labels), run_time=1.5)
        self.play(Create(graph), Write(graph_label), run_time=2)
        self.wait(1)
```

---

## 3. Transform / Morph Between Equations

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        eq1 = MathTex(r"(a+b)^2", font_size=48)
        eq2 = MathTex(r"a^2 + 2ab + b^2", font_size=48)

        self.play(Write(eq1), run_time=1)
        self.wait(0.5)
        self.play(TransformMatchingTex(eq1, eq2), run_time=2)
        self.wait(1)
```

---

## 4. Moving Dot Along a Path

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(x_range=[-3, 3], y_range=[-1, 9], x_length=10, y_length=6)
        graph = axes.plot(lambda x: x**2, color=BLUE)
        self.play(Create(axes), Create(graph), run_time=1.5)

        t = ValueTracker(-3)
        dot = always_redraw(lambda: Dot(
            axes.c2p(t.get_value(), t.get_value()**2),
            color=YELLOW, radius=0.08
        ))
        trail = TracedPath(dot.get_center, stroke_color=YELLOW, stroke_width=2)

        self.add(dot, trail)
        self.play(t.animate.set_value(3), run_time=4, rate_func=smooth)
        dot.clear_updaters()
        self.wait(0.5)
```

---

## 5. ValueTracker with Live-Updating Label

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        tracker = ValueTracker(0)
        number = DecimalNumber(0, num_decimal_places=2, font_size=48, color=YELLOW)
        number.add_updater(lambda d: d.set_value(tracker.get_value()))
        number.move_to(UP * 2)

        label = MathTex(r"x = ", font_size=48).next_to(number, LEFT, buff=0.2)
        self.add(label, number)

        self.play(tracker.animate.set_value(5), run_time=3)
        self.wait(0.5)
        self.play(tracker.animate.set_value(0), run_time=2)
        number.clear_updaters()
        self.wait(0.5)
```

---

## 6. Labeled Vectors on a NumberPlane

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        plane = NumberPlane(
            x_range=[-5, 5], y_range=[-3, 3],
            background_line_style={"stroke_opacity": 0.2},
        )
        self.play(Create(plane), run_time=1)

        v1 = Arrow(start=ORIGIN, end=[3, 1, 0], color=BLUE, buff=0, stroke_width=4)
        v2 = Arrow(start=ORIGIN, end=[1, 2, 0], color=RED, buff=0, stroke_width=4)
        lbl1 = MathTex(r"\vec{v}_1", font_size=30, color=BLUE).next_to(v1.get_end(), UR, buff=0.1)
        lbl2 = MathTex(r"\vec{v}_2", font_size=30, color=RED).next_to(v2.get_end(), UL, buff=0.1)

        self.play(GrowArrow(v1), Write(lbl1), run_time=1)
        self.play(GrowArrow(v2), Write(lbl2), run_time=1)
        self.wait(1)
```

---

## 7. Area Under a Curve (Integral Visualization)

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(x_range=[0, 4], y_range=[0, 5], x_length=8, y_length=5)
        graph = axes.plot(lambda x: 0.25 * x**2 + 1, color=BLUE)

        # Riemann rectangles (animate dx shrinking)
        rects_thick = axes.get_riemann_rectangles(graph, x_range=[0.5, 3.5], dx=0.5, color=GREEN, fill_opacity=0.4)
        rects_thin = axes.get_riemann_rectangles(graph, x_range=[0.5, 3.5], dx=0.1, color=GREEN, fill_opacity=0.4)

        # Filled area
        area = axes.get_area(graph, x_range=[0.5, 3.5], color=YELLOW, fill_opacity=0.3)

        self.play(Create(axes), Create(graph), run_time=1.5)
        self.play(FadeIn(rects_thick), run_time=1)
        self.play(Transform(rects_thick, rects_thin), run_time=2)
        self.play(FadeOut(rects_thick), FadeIn(area), run_time=1.5)
        self.wait(1)
```

---

## 8. Camera Push-In and Release (MovingCameraScene)

```python
class GenScene(MovingCameraScene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        axes = Axes(x_range=[-3, 3], y_range=[-1, 9], x_length=10, y_length=6)
        graph = axes.plot(lambda x: x**2, color=BLUE)
        dot = Dot(axes.c2p(1, 1), color=YELLOW, radius=0.08)
        label = MathTex(r"(1, 1)", font_size=24, color=YELLOW).next_to(dot, UR, buff=0.1)

        self.play(Create(axes), Create(graph), FadeIn(dot), Write(label), run_time=1.5)

        # Push in on the dot
        self.camera.frame.save_state()
        self.play(
            self.camera.frame.animate.scale(0.3).move_to(dot.get_center()),
            run_time=2,
        )
        self.wait(1)

        # Pull back out
        self.play(Restore(self.camera.frame), run_time=1.5)
        self.wait(0.5)
```

---

## 9. Staggered Reveal with LaggedStart

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        dots = VGroup(*[
            Dot(RIGHT * i * 0.8 + LEFT * 2, color=BLUE)
            for i in range(6)
        ])
        labels = VGroup(*[
            MathTex(str(i), font_size=24).next_to(d, DOWN, buff=0.2)
            for i, d in enumerate(dots)
        ])

        self.play(
            LaggedStart(*[FadeIn(d, shift=UP * 0.3) for d in dots], lag_ratio=0.15),
            run_time=2,
        )
        self.play(
            LaggedStart(*[Write(l) for l in labels], lag_ratio=0.1),
            run_time=1.5,
        )
        self.wait(1)
```

---

## 10. Colored Equation Terms (Algebra ↔ Geometry Link)

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        # Color-map specific substrings
        eq = MathTex(
            r"f(x) = x^2 + 3x + 2",
            substrings_to_isolate=["x^2", "3x", "2"],
            font_size=40,
        )
        eq.set_color_by_tex("x^2", BLUE)
        eq.set_color_by_tex("3x", YELLOW)
        eq.set_color_by_tex("2", GREEN)
        eq.move_to(UP * 2)

        # Match colors on axes
        axes = Axes(x_range=[-3, 1], y_range=[-1, 7], x_length=8, y_length=5).shift(DOWN)
        graph = axes.plot(lambda x: x**2 + 3*x + 2, color=WHITE, x_range=[-3, 1])

        self.play(Write(eq), run_time=1.5)
        self.play(Create(axes), Create(graph), run_time=2)
        self.wait(1)
```

---

## 11. Grid Transformation (Linear Algebra)

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        plane = NumberPlane(
            x_range=[-5, 5], y_range=[-3, 3],
            background_line_style={"stroke_opacity": 0.4},
        )
        # Ghost copy of original grid
        ghost = plane.copy().set_stroke(opacity=0.15)
        self.add(ghost)

        matrix = [[1, 1], [0, 1]]  # shear
        self.play(Create(plane), run_time=1)
        self.play(ApplyMatrix(matrix, plane), run_time=3)
        self.wait(1)
```

---

## 12. Ambient Motion Ending (Not a Freeze Frame)

```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = "#1e1e2e"
        circle = Circle(radius=2, color=TEAL, stroke_width=3)
        glow = circle.copy().set_stroke(width=12, opacity=0.15)
        self.add(glow, circle)
        self.play(Create(circle), run_time=1.5)

        # Ambient: gentle pulsing glow
        glow.add_updater(lambda m, dt: m.set_stroke(
            opacity=0.1 + 0.05 * np.sin(self.renderer.time * 2)
        ))
        self.wait(2)
        glow.clear_updaters()
```

---

## Quick Reference: Key Patterns

| Pattern | Code |
|---------|------|
| Background color | `self.camera.background_color = "#hex"` |
| Position at edge | `obj.to_edge(UP)`, `obj.to_corner(UL)` |
| Space from another | `obj.next_to(other, DOWN, buff=0.3)` |
| Group + arrange | `VGroup(a, b, c).arrange(RIGHT, buff=0.3)` |
| Staggered fade | `FadeIn(group, lag_ratio=0.1)` |
| Glow copy | `glow = obj.copy().set_stroke(width=12, opacity=0.15)` |
| Background behind text | `BackgroundRectangle(text, buff=0.15, fill_opacity=0.7)` |
| Surrounding box | `SurroundingRectangle(obj, buff=0.15, color=YELLOW)` |
| Dashed line | `DashedVMobject(Line(start, end), num_dashes=20)` |
| Dashed circle | `DashedVMobject(Circle(radius=2), num_dashes=30)` |
| Parametric curve | `ParametricFunction(lambda t: [np.cos(t), np.sin(t), 0], t_range=[0, TAU])` |

# Manim Bug Catalog — Common Failures in Generated Code

> Each bug: Symptom → Cause → WRONG snippet → RIGHT snippet (ManimCE 0.20.1, verified).
> Source URLs inline. This catalog feeds into `prompt_builder.py` and `scene_validator.py`.

---

## 1. Using ManimGL Names on ManimCE

**Symptom:** `AttributeError: module 'manim' has no attribute 'ShowCreation'`

**Cause:** The LLM copies code patterns from 3b1b's ManimGL tutorials. These class/function names don't exist in ManimCE.
(https://docs.manim.community/en/stable/faq/general.html)

**WRONG:**
```python
self.play(ShowCreation(circle))
text = TexMobject(r"x^2")
label = TextMobject("Hello")
```

**RIGHT (ManimCE):**
```python
self.play(Create(circle))
text = MathTex(r"x^2")
label = Tex("Hello")       # or Text("Hello") for non-LaTeX
```

---

## 2. Calling Removed/Deprecated Methods (v0.18–0.20)

**Symptom:** `AttributeError` or `TypeError` on methods that were renamed or had parameters changed.

**Cause:** APIs evolve between ManimCE versions. LLMs trained on older docs produce stale calls.
(https://docs.manim.community/en/stable/changelog/)

**WRONG:**
```python
# Removed in v0.13:
circle.rotate_in_place(PI)
circle.scale_in_place(2)

# Renamed parameter in v0.19:
color = ManimColor.from_hex(hex="#3498db")  # hex= renamed to hex_str=

# Removed in v0.18.1:
mobject.wag(0.5)

# Changed in v0.19:
self.next_section("Title", type=SectionType.NORMAL)  # type= → section_type=
```

**RIGHT (ManimCE 0.20.1):**
```python
circle.rotate(PI)
circle.scale(2)

color = ManimColor.from_hex(hex_str="#3498db")

# No .wag() equivalent — use .shift() with wobble or custom updater

self.next_section("Title", section_type=SectionType.NORMAL)
```

---

## 3. Objects Overlapping or Going Off-Frame

**Symptom:** Objects are invisible or stacked on top of each other.

**Cause:** Default frame is 14.22 × 8.0 units. Objects beyond ±7.11 (x) or ±4.0 (y) are invisible.
Multiple objects at ORIGIN overlap. Using raw scene coordinates instead of `axes.c2p()`.
(config.frame_width / config.frame_height verified at runtime)

**WRONG:**
```python
# Both at ORIGIN — overlap
title = Text("Title")
equation = MathTex(r"x^2 + y^2 = r^2")
self.add(title, equation)

# Off-frame
label = Text("Far away").shift(RIGHT * 10)  # x=10 > 7.11 = invisible

# Wrong coordinate system
dot = Dot([3.0, 2.0, 0])  # scene coords, not axes coords
```

**RIGHT:**
```python
title = Text("Title", font_size=36).to_edge(UP)
equation = MathTex(r"x^2 + y^2 = r^2", font_size=36).next_to(title, DOWN, buff=0.5)
self.add(title, equation)

label = Text("Right side", font_size=28).to_edge(RIGHT, buff=0.5)

dot = Dot(axes.c2p(3.0, 2.0))  # axes coords → scene coords
```

---

## 4. LaTeX Not Installed or Bad LaTeX String → MathTex Crash

**Symptom:** `FileNotFoundError: latex` or `LaTeX Error` during render.

**Cause:** `MathTex`/`Tex` require a LaTeX distribution. Bad strings (unescaped special chars) also crash.
(https://docs.manim.community/en/stable/installation/windows.html)

**WRONG:**
```python
# Unescaped special characters
MathTex(r"100% of cases")  # % is a LaTeX comment character
MathTex("a & b")           # & must be escaped

# Non-ASCII in Tex
Tex("Привет мир")          # Cyrillic may fail without proper font setup
```

**RIGHT:**
```python
MathTex(r"100\% \text{ of cases}")  # escape %
MathTex(r"a \& b")                   # escape &
MathTex(r"f(x) = x_1")              # ok in math mode (subscript)

Text("Привет мир")                    # Text uses Pango, no LaTeX needed
```

---

## 5. Updaters Never Removed → Render Hangs or Slow

**Symptom:** Render takes forever or never completes.

**Cause:** `add_updater` / `always_redraw` run every frame. If not cleared, they accumulate.
Nested updaters cause infinite recursion.

**WRONG:**
```python
dot.add_updater(lambda m: m.move_to(tracker.get_value() * RIGHT))
# ... many animations later ...
# updater still running, computing every frame even though dot is off-screen

# Nested updater — infinite recursion
inner = always_redraw(lambda: Circle(radius=tracker.get_value()))
outer = always_redraw(lambda: VGroup(inner, Square()))
```

**RIGHT:**
```python
dot.add_updater(lambda m: m.move_to(tracker.get_value() * RIGHT))
self.play(tracker.animate.set_value(5), run_time=3)
dot.clear_updaters()  # remove when done

# Max 2 always_redraw on constrained hardware. Never nest them.
```

---

## 6. self.play() Given a Non-Animation or Empty VGroup

**Symptom:** `TypeError: object is not callable` or silent no-op.

**Cause:** `self.play()` expects Animation objects, not Mobjects. An empty VGroup in FadeOut is a silent no-op.
(https://stackoverflow.com/questions/tagged/manim)

**WRONG:**
```python
self.play(circle)                    # TypeError — circle is a Mobject
self.play(FadeOut(VGroup()))         # silent no-op — nothing to fade
self.play(circle, square)            # TypeError — both are Mobjects
```

**RIGHT:**
```python
self.play(Create(circle))
self.play(FadeIn(circle), FadeIn(square))
# Check VGroup is non-empty before FadeOut:
group = VGroup(*[m for m in objects if m is not None])
if len(group) > 0:
    self.play(FadeOut(group))
```

---

## 7. Color API — Hex Strings vs ManimColor

**Symptom:** `AttributeError: 'str' object has no attribute 'interpolate'`

**Cause:** `interpolate_color()`, `color_gradient()`, `average_color()` require ManimColor objects, not strings.
`set_color("#hex")` accepts strings — only color utility functions need wrapping.

**WRONG:**
```python
COOL = "#3498db"
WARM = "#e74c3c"
mid = interpolate_color(COOL, WARM, 0.5)  # crash — strings
gradient = color_gradient([COOL, WARM], 5)  # crash — strings
```

**RIGHT:**
```python
COOL = ManimColor("#3498db")
WARM = ManimColor("#e74c3c")
mid = interpolate_color(COOL, WARM, 0.5)  # OK
gradient = color_gradient([COOL, WARM], 5)  # OK

# set_color and constructor args accept strings directly:
circle = Circle(color="#3498db")  # OK
circle.set_color("#3498db")       # OK
```

---

## 8. Class Not Named GenScene or Missing construct

**Symptom:** CI worker: `"scene must define class GenScene with a construct method"`

**Cause:** This project's render harness (`deploy/ci_render.py`) checks for `"class GenScene"` and `"def construct"` literally.
Any other class name or method name fails.

**WRONG:**
```python
class MyScene(Scene):        # wrong name
    def construct(self):
        pass

class GenScene:              # not inheriting Scene
    def construct(self):
        pass

class GenScene(Scene):       # correct name but wrong method
    def setup(self):
        pass
```

**RIGHT:**
```python
class GenScene(Scene):
    def construct(self):
        # ... animation code
        pass

# Or for camera moves:
class GenScene(MovingCameraScene):
    def construct(self):
        pass

# Or for 3D:
class GenScene(ThreeDScene):
    def construct(self):
        pass
```

---

## 9. NumPy 2.x Incompatibilities

**Symptom:** `AttributeError: module 'numpy' has no attribute 'float'` (or `int`, `bool`, etc.)

**Cause:** NumPy 2.0 removed deprecated type aliases. `np.math.*` also removed.

**WRONG:**
```python
x = np.float(3.14)
y = np.int(42)
z = np.math.factorial(5)
arr = np.array([1, 2, 3], dtype=np.bool)
```

**RIGHT:**
```python
import math
x = float(3.14)
y = int(42)
z = math.factorial(5)
arr = np.array([1, 2, 3], dtype=bool)  # Python builtin bool, or np.bool_
```

---

## 10. Python Closure Bug in Updater Loops

**Symptom:** Only the last object in a loop responds to its updater.

**Cause:** Python lambda captures the loop variable by reference, not by value. All lambdas see the final value.

**WRONG:**
```python
dots = [Dot() for _ in range(5)]
for i, dot in enumerate(dots):
    dot.add_updater(lambda m: m.move_to(RIGHT * i))  # all see i=4
```

**RIGHT:**
```python
dots = [Dot() for _ in range(5)]
for i, dot in enumerate(dots):
    dot.add_updater(lambda m, idx=i: m.move_to(RIGHT * idx))  # captures value
```

---

## 11. CONFIG Dict (ManimGL Pattern)

**Symptom:** `AttributeError: 'GenScene' object has no attribute 'my_var'`

**Cause:** The `CONFIG` dict was removed in ManimCE v0.2.0. Class attributes set via CONFIG are not inherited.

**WRONG:**
```python
class GenScene(Scene):
    CONFIG = {
        "background_color": BLUE,
        "my_radius": 2.0,
    }
    def construct(self):
        c = Circle(radius=self.my_radius)  # AttributeError
```

**RIGHT:**
```python
class GenScene(Scene):
    def construct(self):
        self.camera.background_color = BLUE
        my_radius = 2.0
        c = Circle(radius=my_radius)
```

---

## 12. ApplyMethod — Deprecated in ManimCE (not removed)

**Symptom:** DeprecationWarning in logs; may be removed in a future ManimCE version.

**Cause:** `ApplyMethod` is present in ManimCE 0.20.1 (verified: `hasattr(manim, 'ApplyMethod')` is `True`) but is deprecated. The preferred idiom is the `.animate` syntax. Using `ApplyMethod` still works today but is discouraged and will break when removed.

**DEPRECATED (still works but will be removed):**
```python
self.play(ApplyMethod(circle.shift, RIGHT))
self.play(ApplyMethod(text.set_color, RED))
```

**PREFERRED (ManimCE idiomatic):**
```python
self.play(circle.animate.shift(RIGHT))
self.play(text.animate.set_color(RED))
```

---

## 13. ShowCreationThenFadeOut (Removed)

**Symptom:** `NameError: name 'ShowCreationThenFadeOut' is not defined`

**Cause:** Deprecated v0.15.0, removed subsequently. Use `ShowPassingFlash` or manual Create+FadeOut.

**WRONG:**
```python
self.play(ShowCreationThenFadeOut(line))
```

**RIGHT:**
```python
self.play(ShowPassingFlash(line, time_width=0.5))
# or:
self.play(Create(line))
self.wait(0.5)
self.play(FadeOut(line))
```

---

## 14. set_euler_angles on MovingCameraScene's camera.frame

**ENFORCED** by `scene_validator._check_camera_scene_mismatch` — caught statically before render.

**Symptom:** `TypeError: Mobject.__getattr__.<locals>.setter() got an unexpected keyword argument 'phi'`

**Cause:** `set_euler_angles()` is a **ThreeDCamera** method — it does NOT exist on `MovingCameraScene`'s `camera.frame` (which is a plain `ScreenRectangle`). Generated code sometimes confuses 2D camera scenes with 3D camera scenes.

**WRONG:**
```python
class GenScene(MovingCameraScene):  # 2D camera!
    def construct(self):
        self.camera.frame.set_euler_angles(phi=70*DEGREES, theta=-30*DEGREES)  # TypeError!
```

**RIGHT:**
```python
# Option 1: Use ThreeDScene for 3D camera angles
class GenScene(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=70*DEGREES, theta=-30*DEGREES)

# Option 2: For 2D camera, use .animate to scale/move (not rotate in 3D)
class GenScene(MovingCameraScene):
    def construct(self):
        self.camera.frame.save_state()
        self.play(self.camera.frame.animate.scale(0.5).move_to(target))
        self.play(Restore(self.camera.frame))
```

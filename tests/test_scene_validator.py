"""scene_validator — the WP3 static hygiene checks (stale copy, section cleanup, long construct)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scene_validator import (
    validate_layout,
    _check_stale_copy,
    _check_section_cleanup,
    _check_long_construct,
    _check_manim_gl_names,
    _check_non_animation_in_play,
    _check_updater_closure_in_loop,
    _check_camera_scene_mismatch,
)


# ── stale .copy() ─────────────────────────────────────────────────────────────

def test_flags_abandoned_copies():
    code = (
        "a = circle.copy()\n"
        "b = square.copy()\n"
        "self.play(Create(a), Create(b))\n"  # never faded/transformed
    )
    assert _check_stale_copy(code)


def test_copy_used_in_transform_is_clean():
    code = (
        "a = circle.copy()\n"
        "b = square.copy()\n"
        "self.play(Transform(a, target), FadeOut(b))\n"
    )
    assert _check_stale_copy(code) == []


def test_single_copy_not_flagged():
    # One tracked copy is normal; don't be noisy.
    assert _check_stale_copy("a = circle.copy()\nself.add(a)\n") == []


# ── section cleanup ───────────────────────────────────────────────────────────

def test_flags_section_without_cleanup():
    code = (
        "# === SCENE 1: intro ===\n"
        "self.play(Write(title))\n"
        "# === SCENE 2: body ===\n"          # no FadeOut between → flagged
        "self.play(Write(body))\n"
    )
    assert _check_section_cleanup(code)


def test_sections_with_cleanup_are_clean():
    code = (
        "# === SCENE 1 ===\n"
        "self.play(Write(title))\n"
        "self.play(FadeOut(title))\n"
        "# === SCENE 2 ===\n"
        "self.play(Write(body))\n"
    )
    assert _check_section_cleanup(code) == []


def test_no_sections_no_warning():
    assert _check_section_cleanup("self.play(Write(x))\n") == []


# ── long construct ────────────────────────────────────────────────────────────

def test_flags_long_construct_without_teardown():
    code = "\n".join("self.play(Create(Dot()))" for _ in range(30))
    assert _check_long_construct(code)


def test_long_construct_with_fadeout_is_clean():
    code = "\n".join("self.play(Create(Dot()))" for _ in range(30)) + "\nself.play(FadeOut(*self.mobjects))\n"
    assert _check_long_construct(code) == []


def test_short_scene_not_flagged():
    assert _check_long_construct("self.play(Create(Dot()))\n") == []


# ── integration: clean scene passes the whole validator ───────────────────────

def test_clean_scene_has_no_new_false_positives():
    code = (
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        t = Text('Hi', font_size=36)\n"
        "        self.play(Write(t), run_time=1.0)\n"
        "        self.play(FadeOut(t))\n"
    )
    issues = validate_layout(code)
    # The three new checks must not fire on this clean scene.
    joined = " ".join(issues).lower()
    assert "copy()" not in joined
    assert "section" not in joined
    assert "self.play() calls with no" not in joined


# ── ManimGL-only names ───────────────────────────────────────────────────────

def test_flags_show_creation():
    code = "self.play(ShowCreation(circle))\n"
    assert _check_manim_gl_names(code)


def test_flags_texmobject():
    code = "text = TexMobject(r'x^2')\n"
    assert _check_manim_gl_names(code)


def test_flags_textmobject():
    code = "label = TextMobject('hello')\n"
    assert _check_manim_gl_names(code)


def test_flags_apply_method():
    code = "self.play(ApplyMethod(circle.shift, RIGHT))\n"
    assert _check_manim_gl_names(code)


def test_flags_config_class_dict():
    code = "class GenScene(Scene):\n    CONFIG = {\n        'bg': BLUE\n    }\n"
    assert _check_manim_gl_names(code)


def test_config_bare_word_not_flagged():
    # "config" in comments/variables should NOT trigger
    code = "from config import settings\n# load config\n"
    assert _check_manim_gl_names(code) == []


def test_clean_manim_ce_code_no_gl_flags():
    code = (
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        c = Circle()\n"
        "        self.play(Create(c))\n"
        "        self.play(c.animate.shift(RIGHT))\n"
    )
    assert _check_manim_gl_names(code) == []


def test_flags_show_creation_then_fadeout():
    code = "self.play(ShowCreationThenFadeOut(line))\n"
    assert _check_manim_gl_names(code)


# ── non-animation in self.play() ─────────────────────────────────────────────

def test_flags_bare_mobject_in_play():
    # Conservative: only flag when we can see the mobject constructor assignment
    code = "circle = Circle()\nself.play(circle)\n"
    assert _check_non_animation_in_play(code)


def test_unknown_bare_name_not_flagged():
    # Without visible assignment, we stay silent (conservative)
    code = "self.play(circle)\n"
    assert _check_non_animation_in_play(code) == []


def test_animation_in_play_is_clean():
    code = "self.play(Create(circle))\n"
    assert _check_non_animation_in_play(code) == []


def test_multiple_animations_in_play_is_clean():
    code = "self.play(FadeIn(a), FadeOut(b))\n"
    assert _check_non_animation_in_play(code) == []


def test_animate_syntax_is_clean():
    # .animate is not a bare arg — it's obj.animate.method()
    code = "self.play(circle.animate.shift(RIGHT))\n"
    assert _check_non_animation_in_play(code) == []


def test_lagged_start_is_clean():
    code = "self.play(LaggedStart(*anims, lag_ratio=0.1))\n"
    assert _check_non_animation_in_play(code) == []


# ── updater closure in loop ──────────────────────────────────────────────────

def test_flags_updater_closure_bug():
    code = (
        "dots = [Dot() for _ in range(5)]\n"
        "for i, dot in enumerate(dots):\n"
        "    dot.add_updater(lambda m: m.move_to(RIGHT * i))\n"
    )
    assert _check_updater_closure_in_loop(code)


def test_updater_with_default_arg_is_clean():
    code = (
        "dots = [Dot() for _ in range(5)]\n"
        "for i, dot in enumerate(dots):\n"
        "    dot.add_updater(lambda m, i=i: m.move_to(RIGHT * i))\n"
    )
    assert _check_updater_closure_in_loop(code) == []


def test_updater_outside_loop_is_clean():
    code = (
        "dot = Dot()\n"
        "dot.add_updater(lambda m: m.shift(UP * 0.01))\n"
    )
    assert _check_updater_closure_in_loop(code) == []


def test_no_updater_in_loop_is_clean():
    code = (
        "for dot in dots:\n"
        "    self.play(FadeIn(dot))\n"
    )
    assert _check_updater_closure_in_loop(code) == []


# ── integration: new checks don't false-positive on clean scenes ─────────────

def test_new_checks_clean_on_real_scene():
    code = (
        "from manim import *\n"
        "import numpy as np\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        ax = Axes(x_range=[-3, 3], y_range=[-2, 8])\n"
        "        graph = ax.plot(lambda x: x**2, color=BLUE)\n"
        "        t = ValueTracker(0.0)\n"
        "        dot = always_redraw(lambda: Dot(ax.c2p(t.get_value(), t.get_value()**2)))\n"
        "        self.add(ax, graph, dot)\n"
        "        self.play(Create(ax), Create(graph), run_time=1.5)\n"
        "        self.play(t.animate.set_value(2.0), run_time=3)\n"
        "        dot.clear_updaters()\n"
        "        self.play(FadeOut(dot))\n"
    )
    issues = validate_layout(code)
    joined = " ".join(issues).lower()
    assert "manimgl" not in joined
    assert "bare name" not in joined
    assert "closure" not in joined


# ── Task 1: deprecated axes methods ──────────────────────────────────────────

def test_flags_get_graph():
    code = "graph = axes.get_graph(lambda x: x**2)\n"
    issues = _check_manim_gl_names(code)
    assert issues
    assert any("get_graph" in i and "deprecated" in i.lower() for i in issues)


def test_flags_get_derivative_graph():
    code = "deriv = axes.get_derivative_graph(graph)\n"
    issues = _check_manim_gl_names(code)
    assert issues
    assert any("get_derivative_graph" in i for i in issues)


def test_flags_get_implicit_curve():
    code = "curve = axes.get_implicit_curve(lambda x, y: x**2 + y**2 - 1)\n"
    issues = _check_manim_gl_names(code)
    assert issues
    assert any("get_implicit_curve" in i for i in issues)


def test_axes_plot_is_clean():
    code = "graph = axes.plot(lambda x: x**2, color=BLUE)\n"
    assert _check_manim_gl_names(code) == []


def test_deprecated_apply_method_is_flagged():
    code = "self.play(ApplyMethod(circle.shift, RIGHT))\n"
    issues = _check_manim_gl_names(code)
    assert issues
    # Should be in the "deprecated" tier, not the "absent" tier
    assert any("deprecated" in i.lower() and "ApplyMethod" in i for i in issues)
    assert not any("NameError" in i for i in issues)


# ── Task 2: prebuilt animation in self.play() is NOT a false positive ────────

def test_prebuilt_animation_group_not_flagged():
    code = (
        "intro = AnimationGroup(FadeIn(a), FadeIn(b))\n"
        "self.play(intro)\n"
    )
    assert _check_non_animation_in_play(code) == []


def test_prebuilt_lagged_start_not_flagged():
    code = (
        "reveal = LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.1)\n"
        "self.play(reveal)\n"
    )
    assert _check_non_animation_in_play(code) == []


def test_unknown_variable_not_flagged():
    # We can't know what some_var is — conservative: don't flag
    code = "self.play(some_var)\n"
    assert _check_non_animation_in_play(code) == []


def test_mobject_from_constructor_is_flagged():
    code = "c = Circle()\nself.play(c)\n"
    assert _check_non_animation_in_play(code)


def test_text_mobject_is_flagged():
    code = "title = Text('Hello', font_size=36)\nself.play(title)\n"
    assert _check_non_animation_in_play(code)


# ── Task 6: nested loop false positive ───────────────────────────────────────

def test_nested_loop_no_false_positive():
    # Outer loop has no updater; inner loop has updater with correct default arg.
    # The regex must not misfire by merging bodies across loops.
    code = (
        "for group in groups:\n"
        "    for i, dot in enumerate(group):\n"
        "        dot.add_updater(lambda m, i=i: m.move_to(RIGHT * i))\n"
        "    self.play(FadeIn(group))\n"
    )
    assert _check_updater_closure_in_loop(code) == []


# ── Camera/Scene-class mismatch ──────────────────────────────────────────────

# Rule A: self.camera.frame on wrong base class

def test_flags_camera_frame_on_plain_scene():
    code = (
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.camera.frame.animate.scale(0.5)\n"
    )
    issues = _check_camera_scene_mismatch(code)
    assert issues
    assert any("camera.frame" in i and "MovingCameraScene" in i for i in issues)


def test_flags_camera_frame_on_threed_scene():
    code = (
        "class GenScene(ThreeDScene):\n"
        "    def construct(self):\n"
        "        self.camera.frame.animate.scale(0.5)\n"
    )
    issues = _check_camera_scene_mismatch(code)
    assert issues
    assert any("camera.frame" in i and "MovingCameraScene" in i for i in issues)


# Rule B: ThreeDScene-only methods on wrong base class

def test_flags_set_camera_orientation_on_plain_scene():
    code = (
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.set_camera_orientation(phi=70*DEGREES, theta=-30*DEGREES)\n"
    )
    issues = _check_camera_scene_mismatch(code)
    assert issues
    assert any("set_camera_orientation" in i and "ThreeDScene" in i for i in issues)


def test_flags_move_camera_on_moving_camera_scene():
    code = (
        "class GenScene(MovingCameraScene):\n"
        "    def construct(self):\n"
        "        self.move_camera(phi=70*DEGREES)\n"
    )
    issues = _check_camera_scene_mismatch(code)
    assert issues
    assert any("move_camera" in i and "ThreeDScene" in i for i in issues)


# Rule C: set_euler_angles (always crashes)

def test_flags_set_euler_angles_on_camera_frame():
    code = (
        "class GenScene(MovingCameraScene):\n"
        "    def construct(self):\n"
        "        self.camera.frame.set_euler_angles(phi=70*DEGREES, theta=-30*DEGREES)\n"
    )
    issues = _check_camera_scene_mismatch(code)
    assert issues
    assert any("set_euler_angles" in i and "phantom" in i.lower() for i in issues)


def test_flags_set_euler_angles_on_any_scene():
    code = (
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.camera.frame.set_euler_angles(phi=70*DEGREES)\n"
    )
    issues = _check_camera_scene_mismatch(code)
    assert issues
    # Should flag BOTH Rule A (camera.frame on Scene) and Rule C (set_euler_angles)
    assert len(issues) >= 2


# Negative tests (must NOT flag)

def test_cheatsheet_snippet_8_no_false_positive():
    """The EXACT cheatsheet #8 — correct MovingCameraScene with camera.frame."""
    code = """from manim import *
import numpy as np

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
"""
    assert _check_camera_scene_mismatch(code) == []


def test_correct_threed_scene_no_false_positive():
    code = (
        "class GenScene(ThreeDScene):\n"
        "    def construct(self):\n"
        "        self.set_camera_orientation(phi=70*DEGREES, theta=-30*DEGREES)\n"
        "        self.begin_ambient_camera_rotation(rate=0.1)\n"
        "        self.wait(3)\n"
        "        self.stop_ambient_camera_rotation()\n"
    )
    assert _check_camera_scene_mismatch(code) == []


def test_plain_scene_no_camera_no_false_positive():
    code = (
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        circle = Circle()\n"
        "        self.play(Create(circle))\n"
    )
    assert _check_camera_scene_mismatch(code) == []


def test_no_genscene_class_stays_silent():
    """No GenScene class found — stay silent (not our code)."""
    code = (
        "class MyScene(Scene):\n"
        "    def construct(self):\n"
        "        self.camera.frame.animate.scale(0.5)\n"
    )
    assert _check_camera_scene_mismatch(code) == []


def test_unknown_base_class_stays_silent():
    """Custom base class — stay silent (we don't know its camera APIs)."""
    code = (
        "class GenScene(LinearTransformationScene):\n"
        "    def construct(self):\n"
        "        self.camera.frame.animate.scale(0.5)\n"
    )
    assert _check_camera_scene_mismatch(code) == []

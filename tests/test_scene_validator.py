"""scene_validator — the WP3 static hygiene checks (stale copy, section cleanup, long construct)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scene_validator import (
    validate_layout,
    _check_stale_copy,
    _check_section_cleanup,
    _check_long_construct,
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

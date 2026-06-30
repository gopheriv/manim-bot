"""AST safety validation — reject code-execution/file/network/escape vectors,
and (critically) DON'T false-positive on legitimate generated scenes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from code_safety import validate_code_safety, safety_report


def _ok(code: str) -> bool:
    return validate_code_safety(code)[0]


# ── must REJECT (fail closed) ─────────────────────────────────────────────────

def test_rejects_os_import():
    assert not _ok("import os\nos.system('id')\n")


def test_rejects_from_os_import():
    assert not _ok("from os import system\nsystem('id')\n")


def test_rejects_subprocess():
    assert not _ok("import subprocess\nsubprocess.run(['ls'])\n")


def test_rejects_exec_eval_compile():
    assert not _ok("exec('print(1)')")
    assert not _ok("eval('1+1')")
    assert not _ok("compile('1', '<s>', 'eval')")


def test_rejects_dunder_import_and_open_input():
    assert not _ok("__import__('os')")
    assert not _ok("open('/etc/passwd').read()")
    assert not _ok("x = input()")


def test_rejects_sandbox_escape_dunders():
    # The classic ``().__class__.__bases__[0].__subclasses__()`` escape.
    assert not _ok("y = ().__class__.__bases__[0].__subclasses__()")
    assert not _ok("g = (lambda: 0).__globals__")


def test_rejects_relative_and_unknown_imports():
    assert not _ok("from . import secrets\n")
    assert not _ok("import requests\n")
    assert not _ok("import pathlib\n")


def test_report_is_human_readable():
    msg = safety_report("import os\n")
    assert "Unsafe" in msg and "os" in msg


# ── must ALLOW (no false positives on real scenes) ────────────────────────────

_REAL_SCENE = """from manim import *
import numpy as np
import math

class GenScene(MovingCameraScene):
    def construct(self):
        ax = Axes(x_range=[-3, 3], y_range=[-2, 8])
        graph = ax.plot(lambda x: x**2, color=BLUE)
        t = ValueTracker(0.0)
        dot = always_redraw(lambda: Dot(ax.i2gp(t.get_value(), graph)))
        self.add(ax, graph, dot)
        self.play(self.camera.frame.animate.scale(0.5))
        self.play(t.animate.set_value(2.0), run_time=3)
        rng = np.random.default_rng(0)
        pts = [Dot([rng.uniform(-1, 1), math.sin(i), 0]) for i in range(5)]
        self.play(*[FadeIn(p) for p in pts])
"""

_THREE_D = """from manim import *
import numpy as np

class GenScene(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=30 * DEGREES)
        surf = Surface(lambda u, v: np.array([u, v, np.sin(u)]))
        self.add(surf)
        self.move_camera(phi=40 * DEGREES, run_time=2)
"""


def test_allows_real_scene():
    assert _ok(_REAL_SCENE)


def test_allows_3d_scene():
    assert _ok(_THREE_D)


def test_allows_safe_stdlib_extras():
    assert _ok("import random\nimport itertools\nfrom functools import reduce\n")


def test_empty_or_syntax_error_is_not_unsafe():
    # Safety module defers syntax to the truncation/compile path.
    assert _ok("")
    assert _ok("def construct(self):\n    x = (")  # truncated → not our concern


# ── corpus regression: every shipped recipe / fallback must pass ──────────────

def test_fallback_scene_is_safe():
    from fallback_scene import build_fallback_scene
    assert _ok(build_fallback_scene("explain eigenvalues with a rubber sheet"))


def test_all_metaphor_recipes_are_safe():
    from visual_metaphors import _REGISTRY
    for m in _REGISTRY:
        ok, issues = validate_code_safety(m.recipe)
        assert ok, f"metaphor {m.name} recipe flagged unsafe: {issues}"


def test_character_helper_source_is_safe_if_available():
    # pi_creature imports manim at module load; skip cleanly where manim isn't installed.
    import importlib.util
    if importlib.util.find_spec("manim") is None:
        return
    import re
    from pi_creature import format_character_helper
    block = format_character_helper()
    m = re.search(r"```python\n(.*?)\n```", block, re.DOTALL)
    assert m, "expected a fenced python block"
    ok, issues = validate_code_safety(m.group(1))
    assert ok, f"PiCreature helper flagged unsafe: {issues}"

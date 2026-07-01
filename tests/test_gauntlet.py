"""Fast guard: every gauntlet scene must pass safety + validate_layout + py_compile.

This is the permanent guard that the validator never starts fighting good hard scenes.
Rendering is tested separately in scripts/render_gauntlet.py (manual, not in pytest).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import py_compile

from code_safety import validate_code_safety
from scene_validator import validate_layout

GAUNTLET_DIR = Path(__file__).parent / "gauntlet"
SCENE_FILES = sorted(GAUNTLET_DIR.glob("scene*.py"))


def _read_scene(name: str) -> str:
    filepath = GAUNTLET_DIR / f"{name}.py"
    return filepath.read_text(encoding="utf-8")


# ── Safety + Layout + py_compile for each scene ──────────────────────────────

def test_gauntlet_01_safety():
    code = _read_scene("scene01_function_plot")
    safe, _ = validate_code_safety(code)
    assert safe, "Scene 1 failed safety check"


def test_gauntlet_01_layout():
    code = _read_scene("scene01_function_plot")
    issues = validate_layout(code)
    assert issues == [], f"Scene 1 layout issues: {issues}"


def test_gauntlet_01_compile():
    filepath = GAUNTLET_DIR / "scene01_function_plot.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_02_safety():
    code = _read_scene("scene02_equation_morph")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_02_layout():
    code = _read_scene("scene02_equation_morph")
    issues = validate_layout(code)
    assert issues == [], f"Scene 2 layout issues: {issues}"


def test_gauntlet_02_compile():
    filepath = GAUNTLET_DIR / "scene02_equation_morph.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_03_safety():
    code = _read_scene("scene03_valuetracker_dot")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_03_layout():
    code = _read_scene("scene03_valuetracker_dot")
    issues = validate_layout(code)
    assert issues == [], f"Scene 3 layout issues: {issues}"


def test_gauntlet_03_compile():
    filepath = GAUNTLET_DIR / "scene03_valuetracker_dot.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_04_safety():
    code = _read_scene("scene04_camera_pushin")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_04_layout():
    code = _read_scene("scene04_camera_pushin")
    issues = validate_layout(code)
    assert issues == [], f"Scene 4 layout issues: {issues}"


def test_gauntlet_04_compile():
    filepath = GAUNTLET_DIR / "scene04_camera_pushin.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_05_safety():
    code = _read_scene("scene05_true_3d")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_05_layout():
    code = _read_scene("scene05_true_3d")
    issues = validate_layout(code)
    assert issues == [], f"Scene 5 layout issues: {issues}"


def test_gauntlet_05_compile():
    filepath = GAUNTLET_DIR / "scene05_true_3d.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_06_safety():
    code = _read_scene("scene06_riemann_area")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_06_layout():
    code = _read_scene("scene06_riemann_area")
    issues = validate_layout(code)
    assert issues == [], f"Scene 6 layout issues: {issues}"


def test_gauntlet_06_compile():
    filepath = GAUNTLET_DIR / "scene06_riemann_area.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_07_safety():
    code = _read_scene("scene07_grid_transform")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_07_layout():
    code = _read_scene("scene07_grid_transform")
    issues = validate_layout(code)
    assert issues == [], f"Scene 7 layout issues: {issues}"


def test_gauntlet_07_compile():
    filepath = GAUNTLET_DIR / "scene07_grid_transform.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_08_safety():
    code = _read_scene("scene08_latex_heavy")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_08_layout():
    code = _read_scene("scene08_latex_heavy")
    issues = validate_layout(code)
    assert issues == [], f"Scene 8 layout issues: {issues}"


def test_gauntlet_08_compile():
    filepath = GAUNTLET_DIR / "scene08_latex_heavy.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_09_safety():
    code = _read_scene("scene09_staggered_reveal")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_09_layout():
    code = _read_scene("scene09_staggered_reveal")
    issues = validate_layout(code)
    assert issues == [], f"Scene 9 layout issues: {issues}"


def test_gauntlet_09_compile():
    filepath = GAUNTLET_DIR / "scene09_staggered_reveal.py"
    py_compile.compile(str(filepath), doraise=True)


def test_gauntlet_10_safety():
    code = _read_scene("scene10_vectors")
    safe, _ = validate_code_safety(code)
    assert safe


def test_gauntlet_10_layout():
    code = _read_scene("scene10_vectors")
    issues = validate_layout(code)
    assert issues == [], f"Scene 10 layout issues: {issues}"


def test_gauntlet_10_compile():
    filepath = GAUNTLET_DIR / "scene10_vectors.py"
    py_compile.compile(str(filepath), doraise=True)

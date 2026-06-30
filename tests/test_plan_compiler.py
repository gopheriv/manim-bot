"""Plan schema + deterministic compiler (WP4): validation, safe-by-construction output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from plan_schema import validate_plan, validate_expr
from plan_compiler import compile_plan
from code_safety import validate_code_safety


def _good_plan() -> dict:
    return {
        "title": "Derivative as a slope",
        "objects": [
            {"id": "ttl", "kind": "Text", "zone": "top", "text": "Derivatives", "color": "#F5D547"},
            {"id": "ax", "kind": "Axes", "zone": "center", "x_range": [-3, 3], "y_range": [-2, 8]},
            {"id": "g", "kind": "Plot", "on": "ax", "expr": "x**2", "color": "#58C4DD"},
            {"id": "eq", "kind": "MathTex", "zone": "bottom", "tex": r"f(x)=x^2"},
        ],
        "beats": [
            {"actions": [
                {"op": "write", "target": "ttl", "run_time": 1.0},
                {"op": "create", "target": "ax", "run_time": 1.5},
                {"op": "create", "target": "g", "run_time": 1.5},
                {"op": "wait", "seconds": 0.5},
                {"op": "write", "target": "eq"},
                {"op": "indicate", "target": "g"},
            ]}
        ],
    }


# ── expr safety ───────────────────────────────────────────────────────────────

def test_expr_allows_safe_math():
    assert validate_expr("x**2")
    assert validate_expr("np.sin(x) + np.cos(2*x)")
    assert validate_expr("np.exp(-x**2 / 2)")
    assert validate_expr("abs(x) * np.sqrt(x)")


def test_expr_rejects_unsafe():
    assert not validate_expr("__import__('os').system('id')")
    assert not validate_expr("open('f')")
    assert not validate_expr("y + 1")            # unknown name
    assert not validate_expr("x.__class__")      # attribute escape
    assert not validate_expr("eval('1')")


# ── plan validation ────────────────────────────────────────────────────────────

def test_good_plan_validates():
    ok, issues = validate_plan(_good_plan())
    assert ok, issues


def test_rejects_unknown_kind():
    p = _good_plan()
    p["objects"].append({"id": "bad", "kind": "SVGMobject", "zone": "center"})
    ok, _ = validate_plan(p)
    assert not ok


def test_rejects_unsafe_plot_expr():
    p = _good_plan()
    p["objects"][2]["expr"] = "__import__('os')"
    ok, _ = validate_plan(p)
    assert not ok


def test_rejects_dangling_target():
    p = _good_plan()
    p["beats"][0]["actions"].append({"op": "create", "target": "ghost"})
    ok, _ = validate_plan(p)
    assert not ok


def test_rejects_plot_with_unknown_axes():
    p = _good_plan()
    p["objects"][2]["on"] = "nope"
    ok, _ = validate_plan(p)
    assert not ok


# ── compilation ─────────────────────────────────────────────────────────────────

def test_compiles_to_valid_safe_python():
    code = compile_plan(_good_plan())
    assert code is not None
    # syntactically valid
    compile(code, "<plan>", "exec")
    # structurally a renderable scene
    assert "class GenScene(Scene):" in code and "def construct(self):" in code
    # safe by construction → passes the WP1 gate
    ok, issues = validate_code_safety(code)
    assert ok, issues
    # axes emitted before its plot
    assert code.index("ax = Axes") < code.index("g = ax.plot")
    # plot defaulted/explicit colour is a real expression, not the string "BLUE"
    assert 'color="#58C4DD"' in code


def test_compile_is_deterministic():
    assert compile_plan(_good_plan()) == compile_plan(_good_plan())


def test_invalid_plan_compiles_to_none():
    assert compile_plan({"objects": [], "beats": []}) is None


def test_latex_is_safely_escaped():
    p = _good_plan()
    p["objects"][3]["tex"] = r"\frac{d}{dx}\left(x^2\right)"
    code = compile_plan(p)
    compile(code, "<plan>", "exec")  # backslashes must not break the literal

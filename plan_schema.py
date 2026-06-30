"""Plan schema (WP4 Phase A) — a *compilable* subset of the storyboard IR.

The storyboard IR is rich and freeform (the LLM still writes the final code). This
schema is the opposite: a small, strict, machine-checkable plan that a deterministic
compiler (``plan_compiler.compile_plan``) can turn into guaranteed-safe Manim code with
NO LLM at render time. The LLM only fills this JSON; everything dangerous is impossible
to express, and a plan that doesn't fully validate is rejected so the pipeline falls
back to normal LLM code-gen.

Shape::

    {
      "title": "Derivative as a slope",
      "objects": [
        {"id": "ttl", "kind": "Text",   "zone": "top",    "text": "Derivatives", "color": "#F5D547"},
        {"id": "ax",  "kind": "Axes",   "zone": "center", "x_range": [-3, 3], "y_range": [-2, 8]},
        {"id": "g",   "kind": "Plot",   "on": "ax", "expr": "x**2", "color": "#58C4DD"},
        {"id": "eq",  "kind": "MathTex", "zone": "bottom", "tex": "f(x)=x^2"}
      ],
      "beats": [
        {"actions": [{"op": "write", "target": "ttl", "run_time": 1.0},
                     {"op": "create", "target": "ax"}, {"op": "create", "target": "g"},
                     {"op": "wait", "seconds": 0.5}, {"op": "write", "target": "eq"}]}
      ]
    }
"""
from __future__ import annotations

import ast

# Whitelisted object kinds (every one maps to a real, safe Manim CE constructor).
ALLOWED_KINDS = frozenset({
    "Text", "MathTex", "Tex", "Axes", "NumberPlane", "Dot", "Line", "Arrow",
    "Circle", "Square", "Rectangle", "VGroup", "Plot",
})
ALLOWED_ZONES = frozenset({"top", "bottom", "center", "left", "right",
                           "top_left", "top_right", "bottom_left", "bottom_right"})
ALLOWED_OPS = frozenset({"create", "write", "fadein", "fadeout", "transform", "indicate", "wait"})

# Functions permitted inside a Plot ``expr`` (called as ``np.<fn>``), plus bare ``abs``.
_ALLOWED_EXPR_FUNCS = frozenset({
    "sin", "cos", "tan", "exp", "log", "log2", "log10", "sqrt", "abs",
    "sinh", "cosh", "tanh", "arctan", "arcsin", "arccos", "sign", "floor", "ceil",
})
_ALLOWED_EXPR_NAMES = frozenset({"x", "np", "abs"})  # 'abs' is the one allowed bare-name call


def validate_expr(expr: str) -> bool:
    """True if ``expr`` is a safe arithmetic expression of x (functions via ``np.``).

    Compiled into ``lambda x: <expr>`` by the compiler, so it must contain ONLY the
    variable x, numeric constants, arithmetic operators, ``np.<fn>(...)`` calls and
    ``np.pi``/``np.e`` attributes. Anything else (other names, attribute escapes,
    arbitrary calls) is rejected.
    """
    if not isinstance(expr, str) or not expr.strip():
        return False
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                if not (isinstance(f.value, ast.Name) and f.value.id == "np"
                        and f.attr in _ALLOWED_EXPR_FUNCS):
                    return False
            elif isinstance(f, ast.Name):
                if f.id != "abs":
                    return False
            else:
                return False
        elif isinstance(node, ast.Attribute):
            # only np.<attr> (e.g. np.pi) — and the attr must be safe-ish
            if not (isinstance(node.value, ast.Name) and node.value.id == "np"):
                return False
            if node.attr.startswith("__"):
                return False
        elif isinstance(node, ast.Name):
            if node.id not in _ALLOWED_EXPR_NAMES:
                return False
        elif isinstance(node, (ast.Expression, ast.Load, ast.Constant,
                               ast.BinOp, ast.UnaryOp,
                               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
                               ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd)):
            pass
        else:
            return False
    return True


_PLAN_PROMPT = """You are a layout planner for short Manim CE animations. Output ONLY a
JSON object (no markdown fences) describing the scene as data — NOT code.

Shape:
{
  "title": "short title",
  "objects": [
    {"id": "ttl", "kind": "Text", "zone": "top", "text": "...", "color": "#hex"},
    {"id": "ax", "kind": "Axes", "zone": "center", "x_range": [-3,3], "y_range": [-2,8]},
    {"id": "g", "kind": "Plot", "on": "ax", "expr": "x**2", "color": "#hex"},
    {"id": "eq", "kind": "MathTex", "zone": "bottom", "tex": "f(x)=x^2"}
  ],
  "beats": [
    {"actions": [
      {"op": "write", "target": "ttl", "run_time": 1.0},
      {"op": "create", "target": "ax"}, {"op": "create", "target": "g"},
      {"op": "wait", "seconds": 0.5}, {"op": "indicate", "target": "g"}
    ]}
  ]
}

STRICT rules (a plan that breaks any of these is discarded):
- kind ∈ {Text, MathTex, Tex, Axes, NumberPlane, Dot, Line, Arrow, Circle, Square, Rectangle, VGroup, Plot}.
- zone ∈ {top, bottom, center, left, right, top_left, top_right, bottom_left, bottom_right}.
- op ∈ {create, write, fadein, fadeout, transform, indicate, wait}; transform needs "to".
- Plot needs "on" (an Axes id) and "expr": an arithmetic function of x using ONLY x, numbers,
  + - * / ** %, and np.<fn> (np.sin, np.cos, np.exp, np.sqrt, np.log, np.tan, abs). No other names/calls.
- Every action "target"/"to" must be a defined object id. Colors are #hex strings.
- Keep it focused: 3-7 objects, one beat list of well-paced actions."""


def build_plan_prompt(theme_instructions: str = "") -> str:
    """System prompt that asks the LLM for a STRICT, compilable plan JSON."""
    return _PLAN_PROMPT + (f"\n\n{theme_instructions}" if theme_instructions else "")


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_plan(plan: dict) -> tuple[bool, list[str]]:
    """Return ``(ok, issues)``. ok=False means: do NOT compile — fall back to LLM code-gen."""
    issues: list[str] = []
    if not isinstance(plan, dict):
        return False, ["plan is not an object"]

    objects = plan.get("objects")
    beats = plan.get("beats")
    if not isinstance(objects, list) or not objects:
        issues.append("plan needs a non-empty 'objects' list")
    if not isinstance(beats, list) or not beats:
        issues.append("plan needs a non-empty 'beats' list")
    if issues:
        return False, issues

    ids: set[str] = set()
    for i, obj in enumerate(objects):
        where = f"object {i}"
        if not isinstance(obj, dict):
            issues.append(f"{where}: not an object")
            continue
        oid = obj.get("id")
        kind = obj.get("kind")
        if not isinstance(oid, str) or not oid:
            issues.append(f"{where}: missing string 'id'")
        elif oid in ids:
            issues.append(f"{where}: duplicate id '{oid}'")
        else:
            ids.add(oid)
        if kind not in ALLOWED_KINDS:
            issues.append(f"{where} ('{oid}'): kind '{kind}' not in {sorted(ALLOWED_KINDS)}")
        # kind-specific requirements
        if kind in ("Text",) and not isinstance(obj.get("text"), str):
            issues.append(f"{where} ('{oid}'): Text needs 'text'")
        if kind in ("MathTex", "Tex") and not isinstance(obj.get("tex"), str):
            issues.append(f"{where} ('{oid}'): {kind} needs 'tex'")
        if kind == "Plot":
            if not validate_expr(obj.get("expr", "")):
                issues.append(f"{where} ('{oid}'): Plot 'expr' missing or unsafe (use x and np.<fn>)")
            if not isinstance(obj.get("on"), str):
                issues.append(f"{where} ('{oid}'): Plot needs 'on' (an Axes id)")
        zone = obj.get("zone")
        if kind != "Plot" and zone is not None and zone not in ALLOWED_ZONES:
            issues.append(f"{where} ('{oid}'): zone '{zone}' not in {sorted(ALLOWED_ZONES)}")
        col = obj.get("color")
        if col is not None and not (isinstance(col, str) and col.startswith("#")):
            issues.append(f"{where} ('{oid}'): color must be a #hex string")

    # Plot 'on' must reference an existing Axes/NumberPlane
    axes_ids = {o.get("id") for o in objects if isinstance(o, dict) and o.get("kind") in ("Axes", "NumberPlane")}
    for o in objects:
        if isinstance(o, dict) and o.get("kind") == "Plot" and o.get("on") not in axes_ids:
            issues.append(f"Plot '{o.get('id')}' references unknown axes '{o.get('on')}'")

    # Beats / actions
    for bi, beat in enumerate(beats):
        actions = beat.get("actions") if isinstance(beat, dict) else None
        if not isinstance(actions, list) or not actions:
            issues.append(f"beat {bi}: needs a non-empty 'actions' list")
            continue
        for ai, act in enumerate(actions):
            where = f"beat {bi} action {ai}"
            if not isinstance(act, dict):
                issues.append(f"{where}: not an object")
                continue
            op = act.get("op")
            if op not in ALLOWED_OPS:
                issues.append(f"{where}: op '{op}' not in {sorted(ALLOWED_OPS)}")
                continue
            if op == "wait":
                if not _is_number(act.get("seconds", 1)):
                    issues.append(f"{where}: wait 'seconds' must be a number")
                continue
            target = act.get("target")
            if target not in ids:
                issues.append(f"{where}: target '{target}' is not a defined object id")
            if op == "transform" and act.get("to") not in ids:
                issues.append(f"{where}: transform needs 'to' referencing a defined object id")
            rt = act.get("run_time", 1)
            if not _is_number(rt) or rt <= 0:
                issues.append(f"{where}: run_time must be a positive number")

    return (not issues), issues

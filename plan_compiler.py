"""Plan compiler (WP4 Phase B) — deterministic plan dict -> safe Manim CE code.

No LLM here: a validated plan (see ``plan_schema.validate_plan``) is turned into a
Manim scene by string templating over a whitelisted object/op vocabulary. The output
is safe BY CONSTRUCTION (only ``from manim import *`` + ``import numpy as np``, only
known constructors, expressions pre-validated) so it trivially passes ``code_safety``.

Reproducible: the same plan always yields byte-identical code.
"""
from __future__ import annotations

import json

from plan_schema import validate_plan

# zone -> a placement method call appended to the constructor.
_ZONE_PLACEMENT = {
    "top": ".to_edge(UP)",
    "bottom": ".to_edge(DOWN)",
    "left": ".to_edge(LEFT)",
    "right": ".to_edge(RIGHT)",
    "center": ".move_to(ORIGIN)",
    "top_left": ".to_corner(UL)",
    "top_right": ".to_corner(UR)",
    "bottom_left": ".to_corner(DL)",
    "bottom_right": ".to_corner(DR)",
}

_OP_ANIM = {
    "create": "Create",
    "write": "Write",
    "fadein": "FadeIn",
    "fadeout": "FadeOut",
    "indicate": "Indicate",
}


def _lit(s: str) -> str:
    """A safe Python string literal for arbitrary text/LaTeX (handles quotes/backslashes)."""
    return json.dumps(s)


def _color_suffix(obj: dict) -> str:
    """', color="#hex"' to append after existing args, or '' when no color set."""
    col = obj.get("color")
    return f', color="{col}"' if col else ""


def _color_only(obj: dict) -> str:
    """'color="#hex"' as a sole arg, or '' when no color set."""
    col = obj.get("color")
    return f'color="{col}"' if col else ""


def _construct(obj: dict) -> str:
    """Return the constructor expression for one object (no placement)."""
    kind = obj["kind"]
    if kind == "Text":
        fs = int(obj.get("font_size", 36))
        return f'Text({_lit(obj.get("text", ""))}, font_size={fs}{_color_suffix(obj)})'
    if kind in ("MathTex", "Tex"):
        fs = int(obj.get("font_size", 40))
        return f'{kind}({_lit(obj.get("tex", ""))}, font_size={fs}{_color_suffix(obj)})'
    if kind == "Axes":
        xr = obj.get("x_range", [-5, 5])
        yr = obj.get("y_range", [-3, 3])
        return f'Axes(x_range={list(xr)}, y_range={list(yr)})'
    if kind == "NumberPlane":
        return 'NumberPlane(background_line_style={"stroke_opacity": 0.25})'
    if kind == "Plot":
        # Default to the bare BLUE constant (NOT the string "BLUE", which Manim
        # won't resolve to the colour) when the plan doesn't specify a colour.
        col = obj.get("color")
        color_arg = f', color="{col}"' if col else ", color=BLUE"
        return f'{obj["on"]}.plot(lambda x: {obj["expr"]}{color_arg})'
    if kind in ("Dot", "Circle", "Square", "Rectangle"):
        return f'{kind}({_color_only(obj)})'
    if kind in ("Line", "Arrow"):
        return f'{kind}(LEFT, RIGHT{_color_suffix(obj)})'
    if kind == "VGroup":
        members = obj.get("members") or []
        inner = ", ".join(str(m) for m in members)
        return f'VGroup({inner}).arrange(DOWN, buff=0.4)' if inner else "VGroup()"
    # Should never reach here for a validated plan.
    return "VGroup()"


def _emit_object(obj: dict) -> str:
    expr = _construct(obj)
    if obj["kind"] != "Plot":  # plots are tied to their axes, not a zone
        expr += _ZONE_PLACEMENT.get(obj.get("zone") or "", "")
    return f'        {obj["id"]} = {expr}'


def _emit_action(act: dict) -> str:
    op = act["op"]
    if op == "wait":
        return f'        self.wait({float(act.get("seconds", 1))})'
    rt = float(act.get("run_time", 1))
    if op == "transform":
        return f'        self.play(Transform({act["target"]}, {act["to"]}), run_time={rt})'
    anim = _OP_ANIM[op]
    return f'        self.play({anim}({act["target"]}), run_time={rt})'


def compile_plan(plan: dict, bg_color: str = "#0B1026") -> str | None:
    """Compile a plan to Manim code. Returns None if the plan doesn't validate
    (caller falls back to LLM code-gen)."""
    ok, _issues = validate_plan(plan)
    if not ok:
        return None

    objects = plan["objects"]
    # Emit non-Plot objects first (so a Plot's Axes variable already exists), each
    # group in original order so VGroup members precede their group.
    ordered = [o for o in objects if o.get("kind") != "Plot"] + \
              [o for o in objects if o.get("kind") == "Plot"]

    lines = [
        "from manim import *",
        "import numpy as np",
        "",
        "",
        "class GenScene(Scene):",
        "    def construct(self):",
        f"        self.camera.background_color = {_lit(bg_color)}",
    ]
    for obj in ordered:
        lines.append(_emit_object(obj))
    for beat in plan["beats"]:
        for act in beat["actions"]:
            lines.append(_emit_action(act))
    lines.append("        self.wait(0.5)")
    return "\n".join(lines) + "\n"

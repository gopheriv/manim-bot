"""Scene validator — detects likely overlap/crowding issues in generated Manim code.

Runs lightweight text/AST analysis AFTER code generation, BEFORE rendering.
Returns a list of human-readable issues for the layout repair step.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def validate_layout(code: str) -> list[str]:
    """Analyze generated Manim code for likely overlap/crowding issues.

    Returns a list of issue descriptions. Empty list = no issues detected.
    """
    issues: list[str] = []

    issues.extend(_check_multiple_origin(code))
    issues.extend(_check_missing_fadeout(code))
    issues.extend(_check_no_buff(code))
    issues.extend(_check_text_without_font_size(code))
    issues.extend(_check_simultaneous_center(code))
    issues.extend(_check_missing_arrange(code))
    issues.extend(_check_zero_buff_next_to(code))
    issues.extend(_check_stale_copy(code))
    issues.extend(_check_section_cleanup(code))
    issues.extend(_check_long_construct(code))
    issues.extend(_check_manim_gl_names(code))
    issues.extend(_check_non_animation_in_play(code))
    issues.extend(_check_updater_closure_in_loop(code))
    issues.extend(_check_camera_scene_mismatch(code))

    return issues


def _check_multiple_origin(code: str) -> list[str]:
    """Detect multiple objects placed at ORIGIN without next_to/arrange separation."""
    # Find all .move_to(ORIGIN) calls
    origin_moves = re.findall(
        r"(\w+)\s*\.\s*move_to\s*\(\s*ORIGIN\s*\)", code
    )
    # Also count objects created without explicit positioning (default is ORIGIN)
    # This is harder to detect, so we focus on explicit move_to(ORIGIN)

    if len(origin_moves) > 2:
        unique = set(origin_moves)
        if len(unique) > 1:
            return [
                f"Multiple objects moved to ORIGIN: {', '.join(unique)}. "
                f"Use next_to(), arrange(), or explicit coordinates to separate them."
            ]
    return []


def _check_missing_fadeout(code: str) -> list[str]:
    """Detect scenes with many FadeIn/Create/Write but no FadeOut — likely overcrowding."""
    add_patterns = len(re.findall(
        r"\b(FadeIn|Create|Write|DrawBorderThenFill)\s*\(", code
    ))
    remove_patterns = len(re.findall(
        r"\b(FadeOut|Uncreate|Unwrite)\s*\(", code
    ))

    # Also count Transform as a form of removal
    transform_patterns = len(re.findall(
        r"\b(ReplacementTransform|Transform)\s*\(", code
    ))

    total_removes = remove_patterns + transform_patterns

    if add_patterns >= 5 and total_removes == 0:
        return [
            f"Scene has {add_patterns} object-creation animations but NO FadeOut/Transform removals. "
            f"Objects will accumulate and overlap. Add FadeOut or Transform to clear old objects "
            f"before introducing new ones."
        ]
    return []


def _check_no_buff(code: str) -> list[str]:
    """Detect next_to() calls without explicit buff parameter."""
    next_to_calls = re.findall(r"\.next_to\s*\([^)]*\)", code)
    no_buff = [c for c in next_to_calls if "buff" not in c]

    if len(no_buff) >= 3:
        return [
            f"{len(no_buff)} next_to() calls without explicit buff parameter. "
            f"Default buff is 0.25 which is often too small. Use buff >= 0.3 for visual separation."
        ]
    return []


def _check_zero_buff_next_to(code: str) -> list[str]:
    """Detect next_to() with buff=0 which causes objects to touch."""
    zero_buff = re.findall(r"\.next_to\s*\([^)]*buff\s*=\s*0\s*[,)]", code)
    if zero_buff:
        return [
            f"{len(zero_buff)} next_to() call(s) with buff=0. "
            f"Objects will touch or overlap. Use buff >= 0.3."
        ]
    return []


def _check_text_without_font_size(code: str) -> list[str]:
    """Detect Text/MathTex without explicit font_size — may be too large/small for layout."""
    # Match Text("...") or MathTex("...") without font_size
    text_calls = re.findall(r"\b(Text|MathTex|Tex)\s*\([^)]*\)", code)
    with_size = re.findall(r"\b(Text|MathTex|Tex)\s*\([^)]*font_size", code)

    without_size = len(text_calls) - len(with_size)
    if without_size >= 3:
        return [
            f"{without_size} Text/MathTex objects without explicit font_size. "
            f"Set font_size explicitly to control layout proportions."
        ]
    return []


def _check_simultaneous_center(code: str) -> list[str]:
    """Detect multiple .move_to(ORIGIN) or .to_edge() without temporal separation.

    This is a heuristic — we check if multiple objects are placed at center
    within the same self.play() block.
    """
    # Find self.play() blocks and check for multiple center placements
    play_blocks = re.findall(r"self\.play\s*\((.*?)\)", code, re.DOTALL)

    for block in play_blocks:
        origin_count = len(re.findall(r"move_to\s*\(\s*ORIGIN\s*\)", block))
        if origin_count >= 2:
            return [
                f"self.play() block contains {origin_count} objects moved to ORIGIN simultaneously. "
                f"Separate them spatially or temporally."
            ]
    return []


def _check_missing_arrange(code: str) -> list[str]:
    """Detect VGroup with multiple elements but no arrange() call."""
    # Find VGroup(...) with 3+ elements
    vgroup_pattern = re.compile(r"VGroup\s*\(([^)]+)\)", re.DOTALL)

    for match in vgroup_pattern.finditer(code):
        content = match.group(1)
        # Count comma-separated arguments (rough heuristic)
        elements = [c.strip() for c in content.split(",") if c.strip()]
        if len(elements) >= 3:
            # Check if .arrange() is called nearby
            start = match.end()
            after = code[start:start + 200]
            if ".arrange" not in after and ".arrange" not in content:
                return [
                    f"VGroup with {len(elements)} elements but no .arrange() call. "
                    f"Use .arrange() to distribute elements with proper spacing."
                ]
    return []


def _check_stale_copy(code: str) -> list[str]:
    """Detect `x = obj.copy()` results that are never FadeOut/Transform'd.

    A leftover `.copy()` sits on top of its original and reads as a doubled object.
    Only flags when 2+ copies are abandoned (a single tracked copy is usually fine).
    """
    copies = re.findall(r"(\w+)\s*=\s*\w+\s*\.\s*copy\s*\(\s*\)", code)
    stale = []
    for var in dict.fromkeys(copies):  # de-dupe, keep order
        removed = re.search(
            rf"\b(FadeOut|Uncreate|Transform|ReplacementTransform|FadeTransform)\s*\([^)]*\b{re.escape(var)}\b",
            code,
        )
        if not removed:
            stale.append(var)
    if len(stale) >= 2:
        return [
            f"{len(stale)} .copy() result(s) ({', '.join(stale)}) are never FadeOut/Transform'd — "
            f"leftover duplicates sit on their originals. Fade or transform them, or don't copy."
        ]
    return []


def _check_section_cleanup(code: str) -> list[str]:
    """Detect comment-delimited sections that don't clear before the next one."""
    lines = code.split("\n")
    section_idx = [
        i for i, ln in enumerate(lines)
        if re.match(r"\s*#.*(={3,}|\bSCENE\b|\bSection\b|\bPart\b)", ln, re.IGNORECASE)
    ]
    if len(section_idx) < 2:
        return []
    missing = 0
    for a, b in zip(section_idx, section_idx[1:]):
        between = "\n".join(lines[a:b])
        if not re.search(r"\b(FadeOut|Uncreate)\b|self\.clear\s*\(", between):
            missing += 1
    if missing:
        return [
            f"{missing} comment-delimited section(s) end without a FadeOut/clear — objects "
            f"carry into the next section and overlap. Clear each section before the next."
        ]
    return []


def _check_long_construct(code: str) -> list[str]:
    """Detect a long construct() with many plays but no teardown at all."""
    play_calls = len(re.findall(r"self\.play\s*\(", code))
    has_teardown = bool(re.search(r"\b(FadeOut|Uncreate)\b|self\.clear\s*\(", code))
    if play_calls > 25 and not has_teardown:
        return [
            f"{play_calls} self.play() calls with no FadeOut/clear anywhere — a long scene that "
            f"never tears down accumulates objects. Clear between sections to keep frames readable."
        ]
    return []


# ── ManimGL-only names (the #1 crash source) ─────────────────────────────────

# Names that exist in ManimGL but NOT in ManimCE (or were renamed/removed).
# Detecting these BEFORE render saves a full render cycle.
_MANIMGL_ONLY_NAMES = {
    "ShowCreation": "Create",
    "TexMobject": "MathTex",
    "TextMobject": "Tex or Text",
    "ShowCreationThenFadeOut": "ShowPassingFlash",
    "ShowCreationThenDestruction": "ShowPassingFlash",
    "ApplyMethod": ".animate syntax (e.g. obj.animate.shift(RIGHT))",
    "CONFIG": "constructor args or class attributes",
    "rotate_in_place": ".rotate()",
    "scale_in_place": ".scale()",
}

# Deprecated Axes methods — still exist as shims but issue DeprecationWarning
_DEPRECATED_AXES_METHODS = {
    "get_graph": "axes.plot()",
    "get_implicit_curve": "axes.plot_implicit_curve()",
    "get_derivative_graph": "axes.plot_derivative_graph()",
}


def _check_manim_gl_names(code: str) -> list[str]:
    """Detect ManimGL-only names and deprecated ManimCE APIs in generated code.

    Two severity tiers:
      - ``_MANIMGL_ONLY_NAMES`` (excluding ApplyMethod): truly absent in ManimCE →
        will raise NameError/AttributeError at render time.
      - ``ApplyMethod`` + ``_DEPRECATED_AXES_METHODS``: still present in ManimCE
        but deprecated — works today, may be removed tomorrow. Flagged as advisory.
    """
    absent: list[str] = []      # names that do NOT exist in ManimCE
    deprecated: list[str] = []  # names that exist but are deprecated

    for name, replacement in _MANIMGL_ONLY_NAMES.items():
        if name == "ApplyMethod":
            # ApplyMethod IS present in ManimCE (deprecated, not removed) —
            # handled separately below so the message is accurate.
            if re.search(r"\bApplyMethod\s*\(", code):
                deprecated.append(f"`ApplyMethod(...)` is deprecated → use `{replacement}`")
            continue
        if name == "CONFIG":
            # CONFIG is too common as a bare word — only flag the class-dict pattern
            if re.search(r"^\s*CONFIG\s*=\s*\{", code, re.MULTILINE):
                absent.append(f"`{name}` → use `{replacement}`")
        else:
            # Match as a whole word to avoid false positives (e.g. "MyShowCreation")
            if re.search(rf"\b{re.escape(name)}\b", code):
                absent.append(f"`{name}` → use `{replacement}`")

    # Deprecated Axes methods — still exist as __getattr__ shims but issue
    # DeprecationWarning. Match the method-call form to avoid false positives
    # on unrelated attributes or variable names (e.g. ``my_get_graph``).
    for method, replacement in _DEPRECATED_AXES_METHODS.items():
        if re.search(rf"\.{re.escape(method)}\s*\(", code):
            deprecated.append(f"`.{method}()` is deprecated → use `{replacement}`")

    issues: list[str] = []
    if absent:
        issues.append(
            f"ManimGL-only names detected ({len(absent)}): "
            + "; ".join(absent)
            + ". These do NOT exist in ManimCE and will cause NameError/AttributeError."
        )
    if deprecated:
        issues.append(
            f"Deprecated ManimCE APIs detected ({len(deprecated)}): "
            + "; ".join(deprecated)
            + ". These still work but are deprecated and may be removed in a future version."
        )
    return issues


def _check_non_animation_in_play(code: str) -> list[str]:
    """Detect likely non-animation objects passed directly to self.play().

    Conservative heuristic: only flag ``self.play(varname)`` when ``varname`` was
    assigned earlier from a known **Mobject constructor** (Circle, Text, MathTex,
    etc.). If the name was assigned from an animation constructor
    (AnimationGroup, LaggedStart, …), from an unrecognised call, or its
    assignment is not found, we stay silent — a missed catch is fine; a false
    alarm that triggers needless LLM repair is not.
    """
    # Match self.play(something) where something is a bare identifier.
    bare_args = re.findall(
        r"self\.play\s*\(\s*([a-zA-Z_]\w*)\s*\)", code
    )
    if not bare_args:
        return []

    # Filter out common animation names and 'self'
    animation_names = {
        "Create", "Write", "FadeIn", "FadeOut", "Transform",
        "ReplacementTransform", "GrowFromCenter", "GrowArrow",
        "ShowPassingFlash", "Indicate", "Circumscribe", "Flash",
        "MoveAlongPath", "Rotate", "Rotating", "Restore",
        "AnimationGroup", "LaggedStart", "Succession",
        "Uncreate", "Unwrite", "DrawBorderThenFill",
    }
    candidates = [a for a in bare_args if a not in animation_names and a != "self"]
    if not candidates:
        return []

    # Known MOBJECT constructors — assigning from one of these and then passing
    # the bare name to self.play() is almost certainly a bug.
    mobject_constructors = {
        "Circle", "Square", "Rectangle", "RoundedRectangle",
        "Text", "MathTex", "Tex", "DecimalNumber", "Integer",
        "Dot", "Line", "Arrow", "DoubleArrow", "DashedLine",
        "VGroup", "VMobject", "Group",
        "Axes", "NumberPlane", "NumberLine", "ComplexPlane",
        "Polygon", "Triangle", "RegularPolygon", "Star",
        "Ellipse", "Arc", "AnnularSector", "Sector",
        "Cube", "Sphere", "Cylinder", "Torus", "Cone",
        "ParametricFunction", "Surface",
        "ImageMobject", "SVGMobject",
        "Brace", "BraceBetweenPoints",
        "Table", "BarChart", "PieChart",
        "SurroundingRectangle", "BackgroundRectangle",
        "DashedVMobject",
    }

    # Build a set of names known to be assigned from mobject constructors
    # by scanning assignment patterns: `name = Constructor(...)`
    mobject_vars: set[str] = set()
    for var_name in candidates:
        # Look for `var_name = Constructor(...)` anywhere before the self.play call
        pattern = rf"\b{re.escape(var_name)}\s*=\s*(\w+)\s*\("
        for m in re.finditer(pattern, code):
            constructor = m.group(1)
            if constructor in mobject_constructors:
                mobject_vars.add(var_name)
                break

    suspicious = [v for v in candidates if v in mobject_vars]
    if suspicious:
        return [
            f"self.play() called with bare Mobject name(s) {', '.join(suspicious[:3])} — "
            f"self.play() expects Animation objects (e.g. Create(x), FadeIn(x)), "
            f"not Mobjects. This will cause TypeError at render time."
        ]
    return []


def _check_updater_closure_in_loop(code: str) -> list[str]:
    """Detect updater lambdas inside for-loops that capture the loop variable by reference.

    Pattern: `for ... in ...: ... add_updater(lambda m: ...)` where the lambda
    body references the loop variable without a default-arg capture.
    """
    # Find for-loops that contain add_updater or always_redraw with lambda
    for_blocks = re.finditer(
        r"for\s+(\w+)(?:\s*,\s*(\w+))?\s+in\s+.*?:\s*\n"
        r"((?:[ \t]+.*\n)*)",
        code,
    )
    for block in for_blocks:
        loop_vars = [v for v in [block.group(1), block.group(2)] if v]
        body = block.group(3)
        # Check if body contains updater with lambda
        if not re.search(r"(add_updater|always_redraw)\s*\(\s*lambda", body):
            continue
        # Check if lambda body references loop variable without default arg
        for var in loop_vars:
            # Match lambda ... : ... var ... where var is used in the body
            # but NOT captured as a default arg (lambda m, var=var: ...)
            lambdas = re.finditer(
                rf"lambda\s+\w+[^:]*:\s*[^#\n]*\b{re.escape(var)}\b", body
            )
            for lam in lambdas:
                lam_text = lam.group(0)
                # Check if var is captured as default arg
                if not re.search(rf",\s*{re.escape(var)}\s*=\s*{re.escape(var)}", lam_text):
                    return [
                        f"Updater lambda in for-loop captures `{var}` by reference — "
                        f"all updaters will see the LAST value of `{var}`. "
                        f"Fix: `lambda m, {var}={var}: ...` to capture by value."
                    ]
    return []


# ── Camera/Scene-class API mismatch (verified against manim 0.20.1) ─────────

# ThreeDScene-ONLY scene methods (Scene=False, MovingCamera=False, ThreeDScene=True).
# Verified via hasattr on real classes. Calling these as self.<method>(...) requires
# class GenScene(ThreeDScene).
_THREEDSCENE_ONLY_METHODS = frozenset({
    "set_camera_orientation",
    "move_camera",
    "begin_ambient_camera_rotation",
    "stop_ambient_camera_rotation",
    "add_fixed_in_frame_mobjects",
    "add_fixed_orientation_mobjects",
})

# Known scene base classes. If the base class is not one of these, stay silent
# (the code might use a custom scene class we don't know about — low FP priority).
_KNOWN_BASES = frozenset({"Scene", "MovingCameraScene", "ThreeDScene"})


def _check_camera_scene_mismatch(code: str) -> list[str]:
    """Detect camera API calls that don't match the scene's base class.

    Three rules (all empirically verified against manim 0.20.1):

    A) ``self.camera.frame`` used but base is Scene or ThreeDScene — camera.frame
       is a MovingCamera feature (a ScreenRectangle). Only MovingCameraScene provides it.

    B) A ThreeDScene-only method called as ``self.<method>(`` but base is not ThreeDScene.

    C) ``self.camera.frame.set_euler_angles(`` — set_euler_angles is a phantom attribute
       on Mobject (via __getattr__) that always crashes when called. It is never valid.

    When the base class can't be determined, stays silent (low false-positive priority).
    """
    # 1. Parse the base class
    m = re.search(r"class\s+GenScene\s*\(\s*(\w+)\s*\)", code)
    if not m:
        return []  # no GenScene class found — stay silent
    base = m.group(1)
    if base not in _KNOWN_BASES:
        return []  # unknown base class — stay silent

    issues: list[str] = []

    # Rule A: self.camera.frame used but base is not MovingCameraScene
    if base != "MovingCameraScene" and re.search(r"self\.camera\.frame\b", code):
        issues.append(
            f"uses self.camera.frame but GenScene is {base} — camera.frame is a "
            f"MovingCameraScene feature; use class GenScene(MovingCameraScene)."
        )

    # Rule B: ThreeDScene-only method called but base is not ThreeDScene
    if base != "ThreeDScene":
        for method in _THREEDSCENE_ONLY_METHODS:
            if re.search(rf"self\.{method}\s*\(", code):
                issues.append(
                    f"uses self.{method}() (ThreeDScene only) but GenScene is {base} — "
                    f"use class GenScene(ThreeDScene)."
                )

    # Rule C: set_euler_angles on camera.frame — always crashes (phantom attribute)
    if re.search(r"self\.camera\.frame\.set_euler_angles\s*\(", code):
        issues.append(
            "set_euler_angles is a phantom Mobject attribute that always crashes — "
            "for 3D rotation use class GenScene(ThreeDScene) with "
            "self.set_camera_orientation(phi=, theta=)."
        )

    return issues


def has_issues(issues: list[str]) -> bool:
    """Return True if there are any layout issues."""
    return len(issues) > 0

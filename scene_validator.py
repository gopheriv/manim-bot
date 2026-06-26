"""Scene validator — detects likely overlap/crowding issues in generated Manim code.

Runs lightweight text/AST analysis AFTER code generation, BEFORE rendering.
Returns a list of human-readable issues for the layout repair step.
"""

from __future__ import annotations

import ast
import logging
import re
from collections import Counter

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


def has_issues(issues: list[str]) -> bool:
    """Return True if there are any layout issues."""
    return len(issues) > 0

"""Scene planner — generates a JSON composition plan before Manim code generation.

The plan describes objects, their spatial regions, visibility timeline,
and overlap-avoidance relationships. This is NOT a template — it constrains
layout without dictating the creative metaphor.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Position → approximate Manim coordinate hints
POSITION_MAP: dict[str, str] = {
    "top": "UP * 3",
    "top-left": "UP * 3 + LEFT * 3",
    "top-right": "UP * 3 + RIGHT * 3",
    "center": "ORIGIN",
    "left": "LEFT * 4",
    "right": "RIGHT * 4",
    "bottom": "DOWN * 3",
    "bottom-left": "DOWN * 3 + LEFT * 3",
    "bottom-right": "DOWN * 3 + RIGHT * 3",
}


def parse_scene_plan(raw: str) -> dict[str, Any] | None:
    """Parse and validate a JSON scene plan from LLM output.

    Returns the parsed dict or None if invalid.
    """
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        plan = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Scene plan JSON parse failed: {e}")
        return None

    # Minimal structural validation
    if not isinstance(plan, dict):
        logger.warning("Scene plan is not a dict")
        return None

    if "objects" not in plan or not isinstance(plan["objects"], list):
        logger.warning("Scene plan missing 'objects' list")
        return None

    if not plan["objects"]:
        logger.warning("Scene plan has empty objects list")
        return None

    # Validate each object has required fields
    required_fields = {"id", "type", "role", "position", "priority", "visible_from", "visible_to"}
    for obj in plan["objects"]:
        missing = required_fields - set(obj.keys())
        if missing:
            logger.warning(f"Scene plan object missing fields: {missing}")
            return None

    # Check crowding limits
    issues = check_crowding(plan)
    if issues:
        logger.info(f"Scene plan crowding warnings: {issues}")
        # Don't reject — just log. The code generator will see these in the plan.

    return plan


def check_crowding(plan: dict[str, Any]) -> list[str]:
    """Check if any time window has too many high-priority objects visible."""
    issues: list[str] = []
    objects = plan.get("objects", [])
    phases = plan.get("phases", [])

    # Check per-phase crowding
    for phase in phases:
        visible_ids = set(phase.get("visible", []))
        visible_objs = [o for o in objects if o["id"] in visible_ids]
        p1_count = sum(1 for o in visible_objs if o.get("priority", 3) == 1)
        p12_count = sum(1 for o in visible_objs if o.get("priority", 3) <= 2)

        phase_name = phase.get("name", f"t={phase.get('time', '?')}")
        if p1_count > 3:
            issues.append(f"Phase '{phase_name}': {p1_count} priority-1 objects (max 3)")
        if p12_count > 5:
            issues.append(f"Phase '{phase_name}': {p12_count} priority-1+2 objects (max 5)")

    # Check spatial overlap — multiple objects at same position
    position_groups: dict[str, list[str]] = {}
    for obj in objects:
        pos = obj.get("position", "center")
        position_groups.setdefault(pos, []).append(obj["id"])

    for pos, ids in position_groups.items():
        if len(ids) > 2:
            issues.append(f"Position '{pos}' has {len(ids)} objects: {ids}")

    return issues


def format_plan_for_prompt(plan: dict[str, Any]) -> str:
    """Format a validated scene plan as a compact JSON string for the code gen prompt."""
    return json.dumps(plan, indent=2, ensure_ascii=False)

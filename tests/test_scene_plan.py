"""Scene-plan parsing — guards the schema/validator contract.

Regression: the validator required a `role` field the prompt never asked for,
so every plan was silently rejected and "scene awareness" was effectively off.
"""

import json

from scene_planner import parse_scene_plan
from prompt_builder import SCENE_PLAN_SYSTEM_PROMPT


def _valid_plan() -> str:
    return json.dumps({
        "objects": [
            {"id": "title", "type": "Text", "role": "annotation", "position": "top",
             "priority": 1, "visible_from": 0, "visible_to": 15},
            {"id": "curve", "type": "ParametricFunction", "role": "primary", "position": "center",
             "priority": 1, "visible_from": 2, "visible_to": 15},
        ],
        "phases": [
            {"name": "intro", "time": [0, 3], "visible": ["title"], "action": "Write"},
        ],
    })


def test_valid_plan_with_role_parses():
    plan = parse_scene_plan(_valid_plan())
    assert plan is not None
    assert len(plan["objects"]) == 2


def test_plan_missing_role_is_rejected():
    bad = json.dumps({
        "objects": [
            {"id": "title", "type": "Text", "position": "top",
             "priority": 1, "visible_from": 0, "visible_to": 15},
        ],
        "phases": [],
    })
    assert parse_scene_plan(bad) is None


def test_prompt_schema_advertises_role():
    # The generation prompt must ask for every field the validator requires,
    # otherwise plans get silently dropped again.
    assert "role" in SCENE_PLAN_SYSTEM_PROMPT


def test_strips_markdown_fences():
    fenced = "```json\n" + _valid_plan() + "\n```"
    plan = parse_scene_plan(fenced)
    assert plan is not None

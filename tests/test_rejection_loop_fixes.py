"""Tests for the rejection-loop fixes: truncation detection, lesson injection,
and recurring-constraint promotion."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import common
import error_learner
import storyboard


# ── looks_truncated (#1) ─────────────────────────────────────────────────────

def test_truncated_open_call():
    code = "from manim import *\nclass GenScene(Scene):\n    def construct(self):\n        self.play(Create("
    assert common.looks_truncated(code)


def test_truncated_open_paren():
    code = "from manim import *\nclass GenScene(Scene):\n    def construct(self):\n        c = Circle("
    assert common.looks_truncated(code)


def test_truncated_dangling_block():
    code = "from manim import *\nclass GenScene(Scene):\n    def construct(self):"
    assert common.looks_truncated(code)


def test_complete_code_not_truncated():
    code = (
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.play(Create(Circle()))\n"
    )
    assert not common.looks_truncated(code)


def test_buggy_but_complete_not_truncated():
    # A logic/API bug is NOT truncation — it compiles, so completion is wrong.
    code = (
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.play(Nonexistent())\n"
    )
    assert not common.looks_truncated(code)


def test_empty_code_not_truncated():
    assert not common.looks_truncated("")
    assert not common.looks_truncated("   \n  ")


# ── Lesson retrieval (#4, #5) ────────────────────────────────────────────────

def _seed_rejections(tmp_path, monkeypatch, records):
    f = tmp_path / "judge_rejections.json"
    f.write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(error_learner, "JUDGE_REJECTION_FILE", f)


def _rec(sig, lesson, count, days_ago=0):
    from datetime import datetime, timedelta
    ts = (datetime.now() - timedelta(days=days_ago)).isoformat()
    return {
        "signature": sig, "lesson": lesson, "count": count,
        "first_seen": ts, "last_seen": ts,
    }


def test_top_lessons_ranked_by_count(tmp_path, monkeypatch):
    _seed_rejections(tmp_path, monkeypatch, [
        _rec("a", "lesson A", count=1),
        _rec("b", "lesson B", count=5),
        _rec("c", "lesson C", count=3),
    ])
    top = error_learner.get_top_judge_lessons(limit=2)
    assert top == ["lesson B", "lesson C"]  # highest counts first


def test_recurring_constraints_threshold(tmp_path, monkeypatch):
    _seed_rejections(tmp_path, monkeypatch, [
        _rec("a", "seen twice", count=2),
        _rec("b", "seen thrice", count=3),
        _rec("c", "seen five", count=5),
    ])
    constraints = error_learner.get_recurring_lesson_constraints(min_count=3)
    assert "seen thrice" in constraints
    assert "seen five" in constraints
    assert "seen twice" not in constraints  # below threshold


def test_recurring_constraints_empty_when_none_recur(tmp_path, monkeypatch):
    _seed_rejections(tmp_path, monkeypatch, [_rec("a", "one off", count=1)])
    assert error_learner.get_recurring_lesson_constraints(min_count=3) == []


# ── Storyboard prompt injection (#4, #5) ─────────────────────────────────────

def test_storyboard_prompt_plain():
    p = storyboard.build_storyboard_prompt()
    assert "HARD CONSTRAINTS" not in p
    assert "LESSONS FROM PRIOR" not in p


def test_storyboard_prompt_injects_lessons():
    p = storyboard.build_storyboard_prompt(lessons=["keep text readable"])
    assert "LESSONS FROM PRIOR" in p
    assert "keep text readable" in p


def test_storyboard_prompt_injects_hard_constraints():
    p = storyboard.build_storyboard_prompt(hard_constraints=["never overlap panels"])
    assert "HARD CONSTRAINTS" in p
    assert "never overlap panels" in p

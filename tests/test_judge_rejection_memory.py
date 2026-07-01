"""Judge rejection memory — record rejected defects (reason + code) so the
generator is warned and never repeats the same mistake."""

import pytest

import error_learner as el


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    # Point the rejection store at a throwaway file so tests don't touch real data.
    monkeypatch.setattr(el, "JUDGE_REJECTION_FILE", tmp_path / "judge_rejections.json")
    yield


def test_logs_and_surfaces_a_lesson():
    n = el.log_judge_rejection(
        ["Line 12: ShowCreation does not exist in manim CE, use Create instead"],
        code="ShowCreation(circle)",
        verdict="REPAIR",
    )
    assert n == 1
    block = el.get_judge_avoidance_modifiers()
    assert "DO NOT REPEAT" in block
    assert "ShowCreation" in block and "use Create" in block


def test_same_mistake_dedupes_across_line_numbers():
    el.log_judge_rejection(["Line 12: ShowCreation removed, use Create"], verdict="REPAIR")
    el.log_judge_rejection(["Line 47: ShowCreation removed, use Create"], verdict="REPAIR")
    stats = el.get_judge_rejection_stats()
    assert stats["distinct_lessons"] == 1          # one lesson, not two
    assert stats["total_rejections"] == 2          # but counted twice
    assert stats["top"][0][0] == 2                 # count == 2


def test_distinct_reasons_are_separate_lessons():
    el.log_judge_rejection([
        "Line 1: ShowCreation removed, use Create",
        "Line 5: np.float removed in numpy 2.x, use float",
    ], verdict="REJECT")
    assert el.get_judge_rejection_stats()["distinct_lessons"] == 2


def test_learned_after_first_occurrence():
    # The whole point: surfaced immediately so it never happens a 2nd time.
    assert el.get_judge_avoidance_modifiers() == ""   # empty before any rejection
    el.log_judge_rejection(["Line 3: animating a mobject never added to the scene"])
    assert "never added" in el.get_judge_avoidance_modifiers()


def test_empty_and_noise_reasons_ignored():
    assert el.log_judge_rejection([]) == 0
    assert el.log_judge_rejection(["", "  ", "ok"]) == 0   # too short / blank
    assert el.get_judge_rejection_stats()["distinct_lessons"] == 0


def test_avoidance_block_is_bounded():
    for i in range(25):
        el.log_judge_rejection([f"Line {i}: distinct defect number {i} in the code"])
    block = el.get_judge_avoidance_modifiers(limit=10)
    assert block.count("\n- ") <= 10


def test_ranked_by_frequency():
    el.log_judge_rejection(["rare defect happened once"])
    for _ in range(3):
        el.log_judge_rejection(["frequent defect happened thrice"])
    block = el.get_judge_avoidance_modifiers()
    # the more-frequent lesson should appear before the rarer one
    assert block.index("frequent defect") < block.index("rare defect")

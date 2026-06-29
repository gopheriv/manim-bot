"""Storyboard / cinematography IR — parse, validate-as-composition, compile."""
import json

from storyboard import (
    parse_storyboard,
    validate_storyboard,
    format_storyboard_for_codegen,
    storyboard_narration,
)
from prompt_builder import build_manim_system_prompt
from render_tier import CLOUD_CINEMATIC


def _beat(i, s, e, **kw):
    b = {
        "id": f"b{i}", "name": "build", "purpose": f"purpose {i}",
        "start_s": s, "end_s": e, "objects": ["axes"], "action": "draw axes",
        "camera": "hold", "transition_in": "Create", "emphasis": "axes",
        "narration": f"line {i}",
    }
    b.update(kw)
    return b


def _good_sb():
    return {
        "title": "T", "concept": "the one idea", "duration_target_s": 24,
        "key_points": ["definition", "intuition", "worked example", "recap"],
        "palette": {"known": "#58C4DD", "focus": "#F5D547", "result": "#2DD4BF"},
        "beats": [_beat(1, 0, 6), _beat(2, 6, 12), _beat(3, 12, 18), _beat(4, 18, 24)],
    }


# ── parsing ───────────────────────────────────────────────────────────────────

def test_parse_plain_and_fenced():
    sb = _good_sb()
    assert parse_storyboard(json.dumps(sb)) is not None
    assert parse_storyboard("```json\n" + json.dumps(sb) + "\n```") is not None


def test_parse_salvages_surrounding_prose():
    sb = _good_sb()
    raw = "Here is the storyboard:\n" + json.dumps(sb) + "\nHope it helps!"
    assert parse_storyboard(raw) is not None


def test_parse_rejects_garbage_and_empty():
    assert parse_storyboard("not json at all") is None
    assert parse_storyboard("") is None
    assert parse_storyboard(json.dumps({"beats": []})) is None  # no beats


def test_parse_requires_load_bearing_beat_fields():
    bad = _good_sb()
    del bad["beats"][1]["narration"]   # a beat missing narration
    assert parse_storyboard(json.dumps(bad)) is None


def test_parse_coerces_quoted_duration_to_number():
    # The LLM sometimes quotes the duration ("30"). Left as a string it would
    # skip validation's isinstance check and crash the narration length budget
    # (str > int). parse_storyboard must coerce it back to a number.
    sb = _good_sb()
    sb["duration_target_s"] = "24"
    parsed = parse_storyboard(json.dumps(sb))
    assert isinstance(parsed["duration_target_s"], (int, float))
    assert parsed["duration_target_s"] == 24
    # A non-numeric string is dropped rather than left to explode downstream.
    sb["duration_target_s"] = "about half a minute"
    parsed = parse_storyboard(json.dumps(sb))
    assert "duration_target_s" not in parsed


# ── validation as composition (non-fatal) ─────────────────────────────────────

def test_clean_storyboard_has_no_issues():
    assert validate_storyboard(_good_sb()) == []


def test_codegen_spec_forwards_per_beat_covers():
    sb = _good_sb()
    sb["beats"][0]["covers"] = ["definition", "intuition"]
    spec = format_storyboard_for_codegen(sb)
    assert "covers: definition, intuition" in spec


def test_flags_too_few_beats():
    sb = _good_sb()
    sb["beats"] = sb["beats"][:2]
    issues = validate_storyboard(sb)
    assert any("beats" in i.lower() for i in issues)


def test_flags_non_contiguous_timeline():
    sb = _good_sb()
    sb["beats"][2]["start_s"] = 99   # gap
    issues = validate_storyboard(sb)
    assert any("contiguous" in i.lower() or "previous ended" in i.lower() for i in issues)


def test_flags_camera_move_without_reason():
    sb = _good_sb()
    sb["beats"][1]["camera"] = "zoom"   # single word, no target/reason
    issues = validate_storyboard(sb)
    assert any("camera" in i.lower() for i in issues)


def test_flags_missing_palette():
    sb = _good_sb()
    sb["palette"] = {"only": "#fff"}
    issues = validate_storyboard(sb)
    assert any("palette" in i.lower() for i in issues)


def test_flags_crowded_beat():
    sb = _good_sb()
    sb["beats"][0]["objects"] = [f"o{i}" for i in range(8)]
    issues = validate_storyboard(sb)
    assert any("objects" in i.lower() for i in issues)


# ── compile to spec + narration ───────────────────────────────────────────────

def test_format_produces_beat_spec():
    spec = format_storyboard_for_codegen(_good_sb())
    assert "STORYBOARD" in spec and spec.count("BEAT ") >= 4
    assert "Semantic palette" in spec


def test_narration_concatenates_in_order():
    assert storyboard_narration(_good_sb()) == "line 1 line 2 line 3 line 4"


# ── prompt injection: storyboard is authoritative over scene_plan ─────────────

def test_storyboard_wins_over_scene_plan_in_prompt():
    spec = format_storyboard_for_codegen(_good_sb())
    p = build_manim_system_prompt(prompt="x", scene_plan="LAYOUT FALLBACK",
                                  storyboard=spec, tier=CLOUD_CINEMATIC)
    assert "implement EXACTLY" in p
    assert "LAYOUT FALLBACK" not in p   # scene_plan suppressed when storyboard present


def test_scene_plan_used_when_no_storyboard():
    p = build_manim_system_prompt(prompt="x", scene_plan="LAYOUT FALLBACK",
                                  storyboard="", tier=CLOUD_CINEMATIC)
    assert "LAYOUT FALLBACK" in p


# ── depth profiles: length + coverage scale with the chosen depth ─────────────

from storyboard import build_storyboard_prompt, _DEPTH_PROFILES


def test_depth_bands_injected_into_storyboard_prompt():
    for depth in ("compact", "standard", "deep"):
        p = build_storyboard_prompt(depth=depth)
        prof = _DEPTH_PROFILES[depth]
        assert "DEPTH & COVERAGE" in p
        assert prof["beats"] in p          # e.g. "8-12"
        assert prof["duration"] in p       # e.g. "60-90"
        assert prof["key_points"] in p     # e.g. "6-9"


def test_depth_bands_differ_by_depth():
    compact = build_storyboard_prompt(depth="compact")
    deep = build_storyboard_prompt(depth="deep")
    assert "4-6" in compact and "8-12" not in compact
    assert "8-12" in deep and "4-6" not in deep


def test_unknown_depth_falls_back_to_standard():
    p = build_storyboard_prompt(depth="bogus")
    assert _DEPTH_PROFILES["standard"]["beats"] in p


def test_key_points_surface_as_coverage_checklist():
    sb = _good_sb()
    sb["key_points"] = ["definition", "intuition", "worked example", "recap"]
    spec = format_storyboard_for_codegen(sb)
    assert "COVER EVERY POINT" in spec
    for kp in sb["key_points"]:
        assert f"- {kp}" in spec


def test_validate_flags_sparse_key_points():
    sb = _good_sb()
    sb["key_points"] = ["only one"]
    assert any("key_points" in i for i in validate_storyboard(sb))


def test_validate_allows_many_beats_for_deep_topics():
    sb = _good_sb()
    sb["beats"] = [_beat(i, i * 6, (i + 1) * 6) for i in range(12)]  # 12 beats
    sb["key_points"] = ["a", "b", "c", "d", "e", "f"]
    issues = validate_storyboard(sb)
    assert not any("is a lot" in i for i in issues)  # 12 beats no longer flagged

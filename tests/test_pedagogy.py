"""pedagogy.py — PEDAGOGY_DIRECTIVE and validate_pedagogical_storyboard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pedagogy import (
    PEDAGOGY_DIRECTIVE,
    STAGES,
    validate_pedagogical_storyboard,
)


# ── PEDAGOGY_DIRECTIVE content ───────────────────────────────────────────────

def test_directive_exists_and_is_non_empty():
    assert isinstance(PEDAGOGY_DIRECTIVE, str)
    assert len(PEDAGOGY_DIRECTIVE) > 100


def test_directive_mentions_all_five_stages():
    for stage in STAGES:
        assert stage in PEDAGOGY_DIRECTIVE, f"PEDAGOGY_DIRECTIVE missing stage: {stage}"


def test_directive_mentions_misconception():
    assert "misconception" in PEDAGOGY_DIRECTIVE.lower()


def test_directive_mentions_spine_metaphor():
    assert "spine_metaphor" in PEDAGOGY_DIRECTIVE.lower() or "spine metaphor" in PEDAGOGY_DIRECTIVE.lower()


def test_directive_mentions_pacing():
    assert "pause_after" in PEDAGOGY_DIRECTIVE


def test_directive_mentions_color_consistency():
    assert "color" in PEDAGOGY_DIRECTIVE.lower()
    assert "consistent" in PEDAGOGY_DIRECTIVE.lower() or "CONSISTENT" in PEDAGOGY_DIRECTIVE


# ── validate_pedagogical_storyboard ──────────────────────────────────────────

def _good_pedagogical_sb():
    return {
        "title": "Fourier Transform",
        "concept": "decomposing signals into frequencies",
        "misconception": "People think Fourier is about 'adding waves' — it's about projection.",
        "spine_metaphor": "A prism splitting white light into colors = Fourier splitting a signal into frequencies",
        "duration_target_s": 60,
        "key_points": ["what is a signal", "projection intuition", "the formula", "why it works", "payoff"],
        "palette": {"signal": "#58C4DD", "frequency": "#F5D547", "result": "#2DD4BF"},
        "beats": [
            {"id": "b1", "name": "hook", "purpose": "curiosity", "stage": "hook",
             "start_s": 0, "end_s": 6, "action": "show a complex waveform",
             "camera": "hold", "transition_in": "Create",
             "emphasis": "the waveform", "narration": "What is this signal made of?",
             "objects": ["wave"], "pause_after": 0.5},
            {"id": "b2", "name": "intuition", "purpose": "feel projection", "stage": "intuition",
             "start_s": 6, "end_s": 18, "action": "animate winding machine",
             "camera": "hold", "transition_in": "Transform",
             "emphasis": "center of mass", "narration": "Wind the signal around a circle...",
             "objects": ["winding"], "pause_after": 1.0},
            {"id": "b3", "name": "formalize", "purpose": "name the idea", "stage": "formalize",
             "start_s": 18, "end_s": 30, "action": "write the integral formula",
             "camera": "hold", "transition_in": "Write",
             "emphasis": "formula", "narration": "This is the Fourier transform.",
             "objects": ["formula"], "pause_after": 0.5},
            {"id": "b4", "name": "generalize", "purpose": "broader principle", "stage": "generalize",
             "start_s": 30, "end_s": 45, "action": "show it works for any signal",
             "camera": "hold", "transition_in": "FadeIn",
             "emphasis": "universality", "narration": "This works for ANY periodic signal.",
             "objects": ["examples"]},
            {"id": "b5", "name": "payoff", "purpose": "aha moment", "stage": "payoff",
             "start_s": 45, "end_s": 60, "action": "reveal connection to sound",
             "camera": "hold", "transition_in": "Transform",
             "emphasis": "the ear IS a Fourier transform", "narration": "Your ear does this!",
             "objects": ["ear"]},
        ],
    }


def test_good_pedagogical_storyboard_passes():
    issues = validate_pedagogical_storyboard(_good_pedagogical_sb())
    assert issues == []


def test_missing_misconception_is_flagged():
    sb = _good_pedagogical_sb()
    del sb["misconception"]
    issues = validate_pedagogical_storyboard(sb)
    assert any("misconception" in i.lower() for i in issues)


def test_empty_misconception_is_flagged():
    sb = _good_pedagogical_sb()
    sb["misconception"] = "   "
    issues = validate_pedagogical_storyboard(sb)
    assert any("misconception" in i.lower() for i in issues)


def test_missing_spine_metaphor_is_flagged():
    sb = _good_pedagogical_sb()
    del sb["spine_metaphor"]
    issues = validate_pedagogical_storyboard(sb)
    assert any("spine_metaphor" in i.lower() or "spine metaphor" in i.lower() for i in issues)


def test_missing_required_stages_is_flagged():
    sb = _good_pedagogical_sb()
    # Remove the hook beat — missing a required stage
    sb["beats"] = sb["beats"][1:]  # keep intuition, formalize, generalize, payoff
    issues = validate_pedagogical_storyboard(sb)
    assert any("hook" in i.lower() for i in issues)


def test_formalize_before_intuition_is_flagged():
    sb = _good_pedagogical_sb()
    # Swap: put formalize before intuition
    sb["beats"][1]["stage"] = "formalize"  # was intuition
    sb["beats"][2]["stage"] = "intuition"  # was formalize
    issues = validate_pedagogical_storyboard(sb)
    assert any("formalize" in i.lower() and "intuition" in i.lower() for i in issues)


def test_old_style_storyboard_passes_validation():
    """An old-style storyboard (no pedagogy fields) should NOT be rejected —
    it just won't have the pedagogical hallmarks. The check is advisory."""
    old_sb = {
        "title": "T", "concept": "idea",
        "duration_target_s": 24,
        "key_points": ["definition", "intuition", "recap"],
        "palette": {"known": "#58C4DD", "focus": "#F5D547", "result": "#2DD4BF"},
        "beats": [
            {"id": f"b{i}", "name": "build", "purpose": f"p{i}",
             "start_s": i*6, "end_s": (i+1)*6, "objects": ["axes"],
             "action": "draw", "camera": "hold", "transition_in": "Create",
             "emphasis": "axes", "narration": f"line {i}"}
            for i in range(4)
        ],
    }
    issues = validate_pedagogical_storyboard(old_sb)
    # It will flag missing fields — that's correct behavior for the check
    assert len(issues) > 0
    # But it should not crash
    assert isinstance(issues, list)

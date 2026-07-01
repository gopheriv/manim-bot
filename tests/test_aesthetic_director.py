"""Deterministic tests for the Aesthetic Director — fusion, parsing, gate, panel
orchestration with MOCKED vision (no API). These must pass in CI without any endpoint."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aesthetic_director import (
    Finding, AestheticVerdict, fuse, _parse_findings, _norm_location, run_panel,
    refine_visual, verdict_to_score,
)


def _verdict(n_high: int, n_med: int = 0) -> AestheticVerdict:
    fs = [Finding("framing", "high", "top", "off", "fix")] * n_high
    fs += [Finding("readability", "medium", "center", "nit", "tweak")] * n_med
    return AestheticVerdict(findings=fs)


def _mk_panel(verdict_seq):
    seq = list(verdict_seq)

    async def panel_fn(frames, hint=""):
        return seq.pop(0) if seq else _verdict(0)
    return panel_fn


async def _render_ok(code):
    return (f"video::{code[-12:]}", [b"frame"])


async def _repair_changes(code, plan):
    return code + "\n# fix"


def F(cat, sev, loc, issue="x", rem="y"):
    return Finding(cat, sev, loc, issue, rem)


# ── parsing ────────────────────────────────────────────────────────────────────

def test_parse_valid_finding():
    raw = '{"findings":[{"severity":"high","location":"top right","issue":"curve cut off","remedy":"rescale"}]}'
    fs = _parse_findings(raw, "framing")
    assert len(fs) == 1
    assert fs[0].severity == "high" and fs[0].location == "top_right" and fs[0].category == "framing"


def test_parse_drops_invalid_severity_and_empty_issue():
    raw = ('{"findings":[{"severity":"catastrophic","location":"center","issue":"x"},'
           '{"severity":"high","location":"center","issue":""}]}')
    assert _parse_findings(raw, "framing") == []


def test_parse_clean_and_junk():
    assert _parse_findings('{"findings":[]}', "framing") == []
    assert _parse_findings('not json at all', "framing") == []
    assert _parse_findings('', "framing") == []


def test_norm_location_aliases():
    assert _norm_location("upper right") == "top_right"
    assert _norm_location("MIDDLE") == "center"
    assert _norm_location("nonsense") == "center"
    assert _norm_location("top-left") == "top_left"


# ── fusion (the Director) ───────────────────────────────────────────────────────

def test_fuse_dedup_keeps_higher_severity():
    out = fuse([[F("framing", "low", "top", "minor")], [F("framing", "high", "top", "cut off")]])
    assert len(out) == 1 and out[0].severity == "high" and out[0].issue == "cut off"


def test_fuse_unions_distinct_categories_and_locations():
    out = fuse([[F("framing", "high", "top")], [F("readability", "high", "center")]])
    assert len(out) == 2


def test_fuse_ranks_high_first_then_framing_priority():
    out = fuse([[F("contrast", "medium", "center")],
                [F("readability", "high", "center")],
                [F("framing", "high", "top")]])
    assert out[0].severity == "high" and out[0].category == "framing"   # framing wins the tie
    assert out[-1].severity == "medium"                                  # medium sinks to the bottom


def test_fuse_caps_results():
    many = [[F("framing", "low", loc)] for loc in
            ["top", "bottom", "left", "right", "center", "top_left", "top_right"]]
    assert len(fuse(many, max_findings=3)) == 3


def test_empty_critic_does_not_cancel_a_finding():
    # absence of evidence from one critic must not cancel another's finding
    out = fuse([[], [F("framing", "high", "top")]])
    assert len(out) == 1 and out[0].severity == "high"


# ── verdict / gate ──────────────────────────────────────────────────────────────

def test_high_severity_gate():
    v = AestheticVerdict(findings=[F("readability", "medium", "center")])
    assert v.passed() and not v.has_high_severity() and v.high_count() == 0
    v2 = AestheticVerdict(findings=[F("framing", "high", "top")])
    assert (not v2.passed()) and v2.has_high_severity() and v2.high_count() == 1


def test_fix_plan_lists_findings_and_remedies():
    v = AestheticVerdict(findings=[F("framing", "high", "top", "curve cut off", "shrink y-range")])
    plan = v.fix_plan()
    assert "curve cut off" in plan and "shrink y-range" in plan
    assert AestheticVerdict(findings=[]).fix_plan() == ""


def test_verdict_to_score_mapping():
    # clean = 10; penalties: high -3, medium -1, low -0.5; floored at 0
    assert verdict_to_score(AestheticVerdict(findings=[])) == 10.0
    assert verdict_to_score(AestheticVerdict(findings=[F("framing", "high", "top")])) == 7.0
    assert verdict_to_score(AestheticVerdict(findings=[F("readability", "medium", "center")])) == 9.0
    assert verdict_to_score(AestheticVerdict(findings=[F("framing", "high", "top")] * 4)) == 0.0  # floored


# ── orchestration with mocked vision ────────────────────────────────────────────

def _vision_mock(framing="", readability="", contrast=""):
    async def fake(frames, caption):
        if "FRAMING & COMPOSITION" in caption:
            return framing or '{"findings":[]}'
        if "TEXT READABILITY" in caption:
            return readability or '{"findings":[]}'
        return contrast or '{"findings":[]}'
    return fake


def test_run_panel_flags_high_from_one_critic():
    fake = _vision_mock(framing='{"findings":[{"severity":"high","location":"top","issue":"curve off-frame","remedy":"rescale"}]}')
    v = asyncio.run(run_panel([b"x"], vision_fn=fake))
    assert v is not None and v.has_high_severity() and v.high_count() == 1
    assert v.findings[0].category == "framing"


def test_run_panel_clean_passes():
    v = asyncio.run(run_panel([b"x"], vision_fn=_vision_mock()))
    assert v is not None and v.passed() and v.critics_ok == 3 and v.findings == []


def test_run_panel_resilient_when_one_critic_errors():
    async def fake(frames, caption):
        if "TEXT READABILITY" in caption:
            raise RuntimeError("vision flaked")
        if "FRAMING & COMPOSITION" in caption:
            return '{"findings":[{"severity":"high","location":"top","issue":"off","remedy":"fix"}]}'
        return '{"findings":[]}'
    v = asyncio.run(run_panel([b"x"], vision_fn=fake))
    assert v is not None and v.critics_ok == 2 and v.has_high_severity()


def test_run_panel_none_when_all_critics_fail():
    async def fake(frames, caption):
        raise RuntimeError("endpoint down")
    assert asyncio.run(run_panel([b"x"], vision_fn=fake)) is None


def test_run_panel_empty_reply_is_failure_not_clean():
    # A blank vision reply (chat_with_images returns "" on error) must NOT count as a
    # clean vote — that would let a silent failure excuse a real defect (recall hazard).
    async def fake(frames, caption):
        if "TEXT READABILITY" in caption:
            return ""   # simulated endpoint failure
        if "FRAMING & COMPOSITION" in caption:
            return '{"findings":[{"severity":"high","location":"top","issue":"off","remedy":"fix"}]}'
        return '{"findings":[]}'
    v = asyncio.run(run_panel([b"x"], vision_fn=fake))
    assert v is not None and v.critics_ok == 2   # readability failed → not counted
    assert v.has_high_severity()


def test_run_panel_all_blank_replies_is_none():
    async def fake(frames, caption):
        return "   "  # all critics blank → unmeasured, not falsely clean
    assert asyncio.run(run_panel([b"x"], vision_fn=fake)) is None


def test_run_panel_none_on_no_frames():
    async def fake(frames, caption):
        return '{"findings":[]}'
    assert asyncio.run(run_panel([], vision_fn=fake)) is None


# ── refinement loop (Phase 4) ───────────────────────────────────────────────────

def test_loop_converges_and_keeps_clean():
    # pass0: 2 high → repair → pass1: clean
    res = asyncio.run(refine_visual("CODE", _render_ok, _mk_panel([_verdict(2), _verdict(0)]),
                                    _repair_changes, max_passes=3))
    assert res.converged is True
    assert res.best_verdict.high_count() == 0
    assert [p.high for p in res.passes] == [2, 0]


def test_loop_hits_cap_without_convergence():
    # always 2 high → never converges → stops after max_passes+1 renders
    res = asyncio.run(refine_visual("CODE", _render_ok, _mk_panel([_verdict(2)] * 5),
                                    _repair_changes, max_passes=3))
    assert res.converged is False
    assert len(res.passes) == 4              # passes 0,1,2,3
    assert res.best_verdict.high_count() == 2


def test_loop_keeps_best_when_a_later_pass_is_worse():
    # high: 2 → 1 → 3 → 1 ; best kept must be the minimum (1), not the last
    res = asyncio.run(refine_visual("CODE", _render_ok,
                                    _mk_panel([_verdict(2), _verdict(1), _verdict(3), _verdict(1)]),
                                    _repair_changes, max_passes=3))
    assert res.best_verdict.high_count() == 1
    assert [p.high for p in res.passes] == [2, 1, 3, 1]


def test_loop_stops_when_panel_unjudgeable():
    res = asyncio.run(refine_visual("CODE", _render_ok, _mk_panel([None]),
                                    _repair_changes, max_passes=3))
    assert res.best_verdict is None and res.best_code == "CODE"
    assert len(res.passes) == 1 and res.passes[0].high == -1


def test_loop_stops_on_repair_noop():
    async def repair_noop(code, plan):
        return code  # no change → loop must terminate
    res = asyncio.run(refine_visual("CODE", _render_ok, _mk_panel([_verdict(2)]),
                                    repair_noop, max_passes=3))
    assert len(res.passes) == 1 and res.converged is False
    assert res.best_verdict.high_count() == 2


def test_loop_render_failure_is_graceful():
    async def render_fail(code):
        return (None, [])
    res = asyncio.run(refine_visual("CODE", render_fail, _mk_panel([_verdict(0)]),
                                    _repair_changes, max_passes=2))
    # never produced a judgeable render → not converged, best_verdict None, no crash
    assert res.converged is False and res.best_verdict is None

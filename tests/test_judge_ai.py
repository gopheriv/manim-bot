"""Tests for the narrowed, fail-closed, tier-aware Judge."""
import asyncio
import json

import pytest

import judge_ai
from judge_ai import JudgeVerdict, JudgeReview, judge_code, _parse_review, _resolve_provider


# ── _parse_review ────────────────────────────────────────────────────────────

def test_parse_accept():
    r = _parse_review(json.dumps({"verdict": "ACCEPT", "score": 8.5}))
    assert r.verdict == JudgeVerdict.ACCEPT and r.score == 8.5
    assert r.is_acceptable and r.was_reviewed


def test_parse_repair_with_instructions():
    r = _parse_review(json.dumps({
        "verdict": "REPAIR", "score": 5.0,
        "critical_issues": ["Line 7: Circle(radius=...) ok"],
        "repair_instructions": ["Line 12: use rotate() not rotate_about()"],
    }))
    assert r.verdict == JudgeVerdict.REPAIR
    assert not r.is_acceptable
    assert r.repair_instructions


def test_parse_strips_fences():
    r = _parse_review("```json\n" + json.dumps({"verdict": "REJECT", "score": 2}) + "\n```")
    assert r.verdict == JudgeVerdict.REJECT


def test_unknown_verdict_becomes_repair_not_accept():
    # A gate that can't read the verdict must NOT wave code through.
    r = _parse_review(json.dumps({"verdict": "LGTM", "score": 9}))
    assert r.verdict == JudgeVerdict.REPAIR
    assert not r.is_acceptable


def test_model_cannot_force_unreviewed():
    r = _parse_review(json.dumps({"verdict": "UNREVIEWED", "score": 5}))
    assert r.verdict == JudgeVerdict.REPAIR  # demoted to conservative REPAIR


# ── fail-closed behavior ─────────────────────────────────────────────────────

def test_judge_fails_closed_to_unreviewed(monkeypatch):
    calls = {"n": 0}

    async def boom(system, user):
        calls["n"] += 1
        raise RuntimeError("endpoint down")

    monkeypatch.setattr(judge_ai, "_judge_complete", boom)
    r = asyncio.run(judge_code("class GenScene(Scene):\n  def construct(self): pass", "draw a circle"))
    assert r.verdict == JudgeVerdict.UNREVIEWED
    assert not r.is_acceptable          # UNREVIEWED is NOT a pass
    assert not r.was_reviewed
    assert calls["n"] == 2              # retried once before giving up


def test_judge_success_path(monkeypatch):
    async def ok(system, user):
        # tier-awareness: heaviness must be declared out of scope in the prompt
        assert "render tier" in system.lower()
        assert "false positive" in system.lower()
        return json.dumps({"verdict": "ACCEPT", "score": 9.0})

    monkeypatch.setattr(judge_ai, "_judge_complete", ok)
    r = asyncio.run(judge_code("code", "prompt", tier=None))
    assert r.verdict == JudgeVerdict.ACCEPT and r.is_acceptable


# ── provider resolution ──────────────────────────────────────────────────────

def test_resolve_provider_auto_prefers_claude(monkeypatch):
    monkeypatch.setattr(judge_ai, "JUDGE_PROVIDER", "auto")
    monkeypatch.setattr(judge_ai, "CLAUDE_API_KEY", "sk-test")
    assert _resolve_provider() == "claude"


def test_resolve_provider_auto_falls_back_to_openai(monkeypatch):
    monkeypatch.setattr(judge_ai, "JUDGE_PROVIDER", "auto")
    monkeypatch.setattr(judge_ai, "CLAUDE_API_KEY", "")
    monkeypatch.setattr(judge_ai, "JUDGE_BASE_URL", "https://x")
    monkeypatch.setattr(judge_ai, "JUDGE_API_KEY", "k")
    assert _resolve_provider() == "openai"


def test_resolve_provider_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(judge_ai, "JUDGE_PROVIDER", "auto")
    monkeypatch.setattr(judge_ai, "CLAUDE_API_KEY", "")
    monkeypatch.setattr(judge_ai, "JUDGE_BASE_URL", "")
    monkeypatch.setattr(judge_ai, "JUDGE_API_KEY", "")
    assert _resolve_provider() is None


def test_forced_claude_without_key_is_none(monkeypatch):
    monkeypatch.setattr(judge_ai, "JUDGE_PROVIDER", "claude")
    monkeypatch.setattr(judge_ai, "CLAUDE_API_KEY", "")
    assert _resolve_provider() is None

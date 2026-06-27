"""Render tier selection + invariants."""

import render_tier
from render_tier import CINEMATIC, STANDARD, CONSTRAINED, detect_tier


def _force(monkeypatch, name):
    monkeypatch.setattr(render_tier, "RENDER_TIER", name)
    monkeypatch.setattr(render_tier, "_active_tier", None)


def test_forced_tier_overrides(monkeypatch):
    _force(monkeypatch, "cinematic")
    assert detect_tier().name == "cinematic"
    _force(monkeypatch, "constrained")
    assert detect_tier().name == "constrained"


def test_constrained_keeps_protective_behavior():
    # The 8 GB-laptop tier must still downgrade hard and forbid surfaces.
    assert CONSTRAINED.default_quality == "-qm"
    assert CONSTRAINED.downgrade_quality == "-ql"
    assert CONSTRAINED.downgrade_fps == 15
    assert CONSTRAINED.allow_surface is False
    assert CONSTRAINED.max_updaters <= 2


def test_capable_tiers_unlock_quality():
    for t in (STANDARD, CINEMATIC):
        assert t.default_quality == "-qh"   # 1080p
        assert t.allow_surface is True
        assert t.weight_threshold > CONSTRAINED.weight_threshold
    # Cinematic never drops resolution for heavy scenes.
    assert CINEMATIC.downgrade_quality == "-qh"


def test_auto_detect_returns_a_known_tier(monkeypatch):
    _force(monkeypatch, "auto")
    assert detect_tier().name in {"cinematic", "standard", "constrained"}

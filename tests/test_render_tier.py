"""Render tier selection + invariants."""

import render_tier
from render_tier import CINEMATIC, STANDARD, CONSTRAINED, CLOUD_CINEMATIC, detect_tier


def _force(monkeypatch, name, cloud=False):
    monkeypatch.setattr(render_tier, "RENDER_TIER", name)
    monkeypatch.setattr(render_tier, "_active_tier", None)
    # Isolate local hardware detection from cloud-farm routing unless asked.
    monkeypatch.setattr(render_tier, "cloud_available", lambda: cloud)


def test_forced_tier_overrides(monkeypatch):
    # An explicit RENDER_TIER wins even when the cloud farm is active.
    _force(monkeypatch, "cinematic", cloud=True)
    assert detect_tier().name == "cinematic"
    _force(monkeypatch, "constrained", cloud=True)
    assert detect_tier().name == "constrained"


def test_constrained_keeps_protective_behavior():
    # The 8 GB-laptop tier must still downgrade hard and forbid surfaces.
    assert CONSTRAINED.default_quality == "-qm"
    assert CONSTRAINED.downgrade_quality == "-ql"
    assert CONSTRAINED.downgrade_fps == 15
    assert CONSTRAINED.allow_surface is False
    assert CONSTRAINED.max_updaters <= 2


def test_capable_tiers_unlock_quality():
    for t in (STANDARD, CINEMATIC, CLOUD_CINEMATIC):
        assert t.default_quality == "-qh"   # 1080p
        assert t.allow_surface is True
        assert t.weight_threshold > CONSTRAINED.weight_threshold
    # Cinematic tiers never drop resolution for heavy scenes.
    assert CINEMATIC.downgrade_quality == "-qh"
    assert CLOUD_CINEMATIC.downgrade_quality == "-qh"


def test_auto_detect_returns_a_known_local_tier(monkeypatch):
    # With the cloud farm OFF, auto-detect picks a local hardware tier.
    _force(monkeypatch, "auto", cloud=False)
    assert detect_tier().name in {"cinematic", "standard", "constrained"}


def test_cloud_farm_routes_generation_to_cinematic(monkeypatch):
    # With the cloud farm ON, generation + quality target the cloud cinematic tier
    # (the render runs on the 16 GB worker), regardless of local RAM.
    _force(monkeypatch, "auto", cloud=True)
    assert detect_tier().name == "cloud_cinematic"

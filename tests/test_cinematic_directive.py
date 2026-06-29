"""The motion-design house style must be baked into the cinematic generation
prompt, while the constrained laptop tier keeps its hardware budget plus a
budget-safe creative subset."""
from prompt_builder import build_manim_system_prompt, build_manim_fix_prompt
from render_tier import CINEMATIC, CLOUD_CINEMATIC, CONSTRAINED


def test_cinematic_prompt_embodies_directive():
    # Normalize whitespace so source line-wraps don't break phrase matching.
    p = " ".join(build_manim_system_prompt(prompt="explain the chain rule", tier=CINEMATIC).split())
    for needle in [
        "award-winning motion designer",
        "TransformMatchingTex",
        "MovingCameraScene",
        "progressive disclosure",
        "VISUAL METAPHORS",
        "COLOR LANGUAGE",
        "deterministic",
    ]:
        assert needle in p, f"cinematic prompt missing: {needle!r}"


def test_cloud_cinematic_gets_full_direction():
    p = build_manim_system_prompt(prompt="fourier series", tier=CLOUD_CINEMATIC)
    assert "award-winning motion designer" in p
    assert "COLOR LANGUAGE" in p
    # Cloud tier should advertise its generous envelope, not the 8 GB budget.
    assert "8GB" not in p and "8 GB" not in p


def test_constrained_keeps_budget_and_creative_subset():
    p = build_manim_system_prompt(prompt="rotating cube", tier=CONSTRAINED)
    # Hard limits remain.
    assert "HARDWARE BUDGET" in p
    assert "max 40 points total" in p
    # …but it still gets budget-safe direction.
    assert "Direction within the budget" in p
    assert "TransformMatchingTex" in p
    # The constrained tier must NOT pull in the heavy cinematic directive block.
    assert "award-winning motion designer" not in p


def test_fix_prompt_inherits_color_and_polish_rules():
    # The shared visual-polish rules ride along on the repair path too.
    fp = build_manim_fix_prompt("AttributeError: x", tier=CINEMATIC)
    assert "VISUAL POLISH" in fp

"""Tests for prompt complexity assessment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_builder import _assess_complexity, build_complexity_modifier, recommend_depth
from render_tier import CONSTRAINED, CINEMATIC, CLOUD_CINEMATIC


# ── SIMPLE prompts ───────────────────────────────────────────────────────────

def test_simple_single_word():
    assert _assess_complexity("circle") == "SIMPLE"


def test_simple_two_words():
    assert _assess_complexity("draw circle") == "SIMPLE"


def test_simple_three_words():
    assert _assess_complexity("animate a sine wave") == "SIMPLE"


def test_simple_four_words():
    # "show me a graph" has 4 words but "graph" is a complex keyword → MEDIUM
    assert _assess_complexity("show me a graph") == "MEDIUM"
    # Pure simple: no complex keywords
    assert _assess_complexity("draw a circle") == "SIMPLE"


# ── MEDIUM prompts ───────────────────────────────────────────────────────────

def test_medium_six_words():
    assert _assess_complexity("animate the probability distribution of a coin flip") == "MEDIUM"


def test_medium_with_complex_keyword():
    # Short but has a complex keyword
    assert _assess_complexity("show matrix multiplication") == "MEDIUM"


def test_medium_derivative():
    assert _assess_complexity("show derivative visually") == "MEDIUM"


# ── COMPLEX prompts ──────────────────────────────────────────────────────────

def test_complex_long():
    assert _assess_complexity(
        "compare the convergence behavior of gradient descent and Newton's method "
        "across different loss landscapes with 3D surface plots"
    ) == "COMPLEX"


def test_complex_multiple_concepts():
    assert _assess_complexity(
        "visualize the relationship between eigenvalues and eigenvectors as a transformation "
        "of space with multiple vector fields"
    ) == "COMPLEX"


# ── Complexity modifier ─────────────────────────────────────────────────────

def test_modifier_simple_constrained():
    result = build_complexity_modifier("draw circle", CONSTRAINED)
    assert "Simple concept" in result


def test_modifier_complex_constrained():
    result = build_complexity_modifier(
        "compare the convergence of gradient descent across multiple loss landscapes",
        CONSTRAINED,
    )
    assert "Multi-concept" in result


def test_modifier_complex_cinematic_is_ambitious():
    # Capable tier should not tell the model to "respect ALL hardware limits".
    result = build_complexity_modifier(
        "compare the convergence of gradient descent across multiple loss landscapes",
        CINEMATIC,
    )
    assert "Multi-concept" in result
    assert "hardware limits" not in result


def test_modifier_medium_empty():
    result = build_complexity_modifier("probability of coin flip animation", CONSTRAINED)
    assert result == ""


# ── recommend_depth (length/coverage policy) ─────────────────────────────────

def test_depth_constrained_always_compact():
    # The 8 GB laptop tier must stay short/safe regardless of complexity.
    assert recommend_depth("draw a circle", CONSTRAINED) == "compact"
    assert recommend_depth(
        "derive and prove the fourier series with a full worked example", CONSTRAINED
    ) == "compact"


def test_depth_capable_simple_is_standard():
    assert recommend_depth("animate a sine wave", CLOUD_CINEMATIC) == "standard"
    assert recommend_depth("show me a graph", CINEMATIC) == "standard"


def test_depth_capable_complex_is_deep():
    assert recommend_depth(
        "derive and prove the Fourier series with a worked example and geometric intuition",
        CLOUD_CINEMATIC,
    ) == "deep"


def test_capable_complexity_modifier_scales_length():
    # Capable-tier durations grew: simple ~30-45s, medium ~45-60s, complex ~60-90s.
    assert "30-45" in build_complexity_modifier("draw a circle", CLOUD_CINEMATIC)
    assert "45-60" in build_complexity_modifier(
        "animate the probability distribution of a coin flip", CLOUD_CINEMATIC
    )
    assert "60-90" in build_complexity_modifier(
        "derive and prove the fourier series step by step with a worked example", CLOUD_CINEMATIC
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

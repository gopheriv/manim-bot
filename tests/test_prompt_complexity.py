"""Tests for prompt complexity assessment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_builder import _assess_complexity, build_complexity_modifier


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

def test_modifier_simple_contains_adjustment():
    result = build_complexity_modifier("draw circle")
    assert "Complexity Adjustment" in result
    assert "3 visual layers" in result


def test_modifier_complex_contains_note():
    result = build_complexity_modifier(
        "compare the convergence of gradient descent across multiple loss landscapes"
    )
    assert "Complexity Note" in result
    assert "5 visual layers" in result


def test_modifier_medium_empty():
    result = build_complexity_modifier("probability of coin flip animation")
    assert result == ""


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

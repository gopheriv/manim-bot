"""Domain guidance — match precision, formatting, registry integrity, graceful no-op."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain_guidance import (
    _REGISTRY,
    recommend_domain,
    format_domain_guidance,
)


# ── matching ──────────────────────────────────────────────────────────────────

def test_linear_algebra_match():
    assert recommend_domain("visualize eigenvectors of a 2x2 matrix") == "linear_algebra"


def test_calculus_match():
    assert recommend_domain("show the derivative as a tangent line") == "calculus"


def test_physics_match():
    assert recommend_domain("animate a pendulum and its restoring force") == "physics"


def test_probability_match():
    assert recommend_domain("sample a gaussian distribution and build a histogram") == "probability"


def test_cs_match():
    assert recommend_domain("animate dijkstra shortest path traversal") == "computer_science"


def test_chemistry_match():
    assert recommend_domain("show a reaction between two molecules forming bonds") == "chemistry"


def test_geometry_match():
    assert recommend_domain("prove the pythagorean theorem with squares on a right triangle") == "geometry"


def test_number_theory_match():
    assert recommend_domain("visualize prime numbers and divisibility") == "number_theory"


def test_inflections_match_by_prefix():
    assert recommend_domain("explain differentiation rules") == "calculus"
    assert recommend_domain("a linear transformation of the plane") == "linear_algebra"


def test_unrelated_returns_none():
    assert recommend_domain("paint a calm sunset landscape") is None
    assert recommend_domain("") is None


def test_function_plot_does_not_misfire_to_cs():
    # "graph"/"tree" are deliberately NOT cs triggers (they collide with function
    # graphs / tree diagrams), so a bare plot shouldn't be tagged computer_science.
    assert recommend_domain("plot the graph of a function") != "computer_science"


def test_stronger_match_wins():
    # Two linalg triggers ("matrix", "determinant") beat an incidental one.
    assert recommend_domain("compute the determinant of the matrix") == "linear_algebra"


# ── formatting ────────────────────────────────────────────────────────────────

def test_format_returns_block_for_known_domain():
    g = format_domain_guidance("linear_algebra")
    assert "DOMAIN" in g and "basis" in g.lower()


def test_format_empty_for_none_or_unknown():
    assert format_domain_guidance(None) == ""
    assert format_domain_guidance("astrology") == ""


def test_recommend_then_format_roundtrip():
    g = format_domain_guidance(recommend_domain("integrate x^2 with riemann rectangles"))
    assert "Calculus" in g


# ── registry integrity ───────────────────────────────────────────────────────

def test_registry_well_formed():
    names = set()
    for d in _REGISTRY:
        assert d.name and d.name.islower() and " " not in d.name
        assert d.name not in names, f"duplicate domain {d.name}"
        names.add(d.name)
        assert d.triggers and d.guidance
        assert all(t == t.lower() for t in d.triggers)
        assert d.guidance.startswith("## DOMAIN")


def test_no_duplicate_trigger_within_domain():
    """Every domain must have unique triggers — no copy-paste duplicates."""
    for d in _REGISTRY:
        assert len(d.triggers) == len(set(d.triggers)), (
            f"domain {d.name} has duplicate triggers: "
            f"{[t for t in d.triggers if d.triggers.count(t) > 1]}"
        )

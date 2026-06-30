"""Visual Metaphor Library — matching precision, formatting, registry integrity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from visual_metaphors import (
    _REGISTRY,
    recommend_metaphors,
    format_metaphors_for_director,
    format_metaphors_for_codegen,
)


# ── matching ──────────────────────────────────────────────────────────────────

def test_clear_topic_matches_expected_metaphor():
    names = [m.name for m in recommend_metaphors("show the derivative as the slope of a curve")]
    assert "derivative_tangent" in names


def test_integral_prompt_matches_area_metaphor():
    names = [m.name for m in recommend_metaphors("animate the integral as accumulating area")]
    assert "integral_area" in names


def test_cs_prompt_matches_graph_search():
    names = [m.name for m in recommend_metaphors("animate breadth-first search on a tree")]
    assert "graph_search" in names


def test_inflections_match_by_prefix():
    # "differentiation" → differentiat, "transformation" → transform
    assert any(m.name == "derivative_tangent" for m in recommend_metaphors("explain differentiation"))
    assert any(m.name == "matrix_transform" for m in recommend_metaphors("a linear transformation of the grid"))


# ── new metaphors (WP2: 3b1b-distilled) ────────────────────────────────────────

def test_secant_metaphor_matches():
    names = [m.name for m in recommend_metaphors(
        "show the secant line difference quotient as dx approaches zero")]
    assert "secant_to_tangent" in names


def test_embedding_metaphor_matches():
    names = [m.name for m in recommend_metaphors(
        "what is a word embedding in a latent semantic space")]
    assert "embedding_vector" in names


def test_number_line_walk_matches_modular():
    names = [m.name for m in recommend_metaphors(
        "explain modular arithmetic and the remainder on a clock")]
    assert "number_line_walk" in names


def test_unrelated_prompt_returns_empty():
    assert recommend_metaphors("paint a calm sunset landscape with warm colors") == []


def test_no_false_positive_on_substring():
    # "paragraph" must NOT trigger the "graph" metaphor (prefix match, not substring).
    assert recommend_metaphors("write a paragraph about history") == []


def test_respects_max_n():
    # A prompt that invites several metaphors is still capped.
    busy = "compare the matrix transformation, the derivative slope, and the integral area"
    assert len(recommend_metaphors(busy, max_n=2)) <= 2
    assert len(recommend_metaphors(busy, max_n=1)) == 1


def test_ranks_stronger_match_first():
    # "matrix" + "transform" both hit matrix_transform (2 triggers) but only
    # "transform" hits function_machine (1) — the stronger match leads.
    ranked = recommend_metaphors("a matrix transformation of space", max_n=3)
    assert ranked[0].name == "matrix_transform"


def test_empty_and_degenerate_inputs():
    assert recommend_metaphors("") == []
    assert recommend_metaphors("derivative", max_n=0) == []


# ── formatting ────────────────────────────────────────────────────────────────

def test_director_menu_includes_name_and_why():
    ms = recommend_metaphors("show the derivative as a tangent slope")
    menu = format_metaphors_for_director(ms)
    assert "VISUAL METAPHOR PALETTE" in menu
    assert "derivative_tangent" in menu
    assert "WHY:" in menu


def test_codegen_recipes_include_code_block():
    ms = recommend_metaphors("integral as area under the curve")
    recipes = format_metaphors_for_codegen(ms)
    assert "METAPHOR RECIPES" in recipes
    assert "```python" in recipes
    assert "get_riemann_rectangles" in recipes  # the actual recipe body


def test_formatters_empty_list_is_blank():
    assert format_metaphors_for_director([]) == ""
    assert format_metaphors_for_codegen([]) == ""


# ── registry integrity ───────────────────────────────────────────────────────

def test_registry_entries_well_formed():
    names = set()
    for m in _REGISTRY:
        assert m.name and m.name.islower() and " " not in m.name
        assert m.name not in names, f"duplicate metaphor name {m.name}"
        names.add(m.name)
        assert m.concept and m.visual and m.why and m.recipe
        assert m.triggers and all(t == t.lower() for t in m.triggers)


def test_recipes_have_no_placeholder_ellipsis():
    # Guard against a stray "…" sneaking into a recipe — it would be copied
    # verbatim by the generator and break the Python.
    for m in _REGISTRY:
        assert "…" not in m.recipe, f"{m.name} recipe contains an ellipsis placeholder"

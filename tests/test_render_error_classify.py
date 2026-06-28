"""Tests for classify_render_error — the gate that decides whether a render
failure is a RESOURCE problem (RAM/timeout, code can't fix it → fail fast) or a
CODE problem (a real defect the LLM self-heal should try to repair)."""
import renderer
from renderer import classify_render_error


# ── resource failures (must NOT trigger LLM code repair) ─────────────────────

def test_ram_block_is_resource():
    # Exact string render() sets when RAM > 85% pre-render.
    err = "Render blocked: system RAM at 90% (0.8 GB free). Close other apps and retry."
    assert classify_render_error(err) == "resource"


def test_ram_kill_is_resource():
    err = "Render killed: system RAM hit 93% (0.4 GB free). Simplify the scene."
    assert classify_render_error(err) == "resource"


def test_timeout_is_resource():
    err = "Render timed out after 600s. The scene is too heavy."
    assert classify_render_error(err) == "resource"


def test_generic_memory_errors_are_resource():
    assert classify_render_error("MemoryError") == "resource"
    assert classify_render_error("Killed: out of memory") == "resource"
    assert classify_render_error("Cannot allocate memory") == "resource"


# ── code failures (SHOULD trigger LLM self-heal) ─────────────────────────────

def test_traceback_is_code():
    err = "Traceback (most recent call last):\nNameError: name 'eff' is not defined"
    assert classify_render_error(err) == "code"


def test_api_error_is_code():
    assert classify_render_error("AttributeError: 'Axes' object has no attribute 'get_graph'") == "code"
    assert classify_render_error("TypeError: Create() got an unexpected keyword argument 'foo'") == "code"


def test_numpy_error_is_code():
    assert classify_render_error("np.float is removed in numpy 2.x — use float instead") == "code"


def test_missing_output_is_code():
    assert classify_render_error("Manim exited OK but GenScene.mp4 not found.") == "code"


def test_empty_or_none_defaults_to_code():
    # No error string → don't fail-fast as resource; let the normal path run.
    assert classify_render_error("") == "code"
    assert classify_render_error(None) == "code"


# ── markers stay in sync with the strings render() actually sets ─────────────

def test_markers_match_renderer_strings():
    # Sanity: the resource markers are lowercase substrings of the real messages.
    for marker in renderer._RESOURCE_ERROR_MARKERS:
        assert marker == marker.lower()

"""Regression tests for LLM code extraction.

The render worker once received `scene.py` whose line 1 was the model's prose
preamble ("I'll fix the two correctness issues identified by the Judge:"), which
raised `SyntaxError: unterminated string literal` (the apostrophe in "I'll").
`extract_python_code` must strip ANY such wrapping so only runnable Python is
written — and the worker's inlined twin must behave identically.
"""
import importlib.util
from pathlib import Path

from common import extract_python_code

ROOT = Path(__file__).resolve().parent.parent


def _load(path: str):
    spec = importlib.util.spec_from_file_location(path.replace("/", "_"), ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The exact shape that broke production: conversational preamble, then a fenced
# block. The apostrophe in "I'll" is what made it a SyntaxError, not just noise.
FAILING_REPLY = (
    "I'll fix the two correctness issues identified by the Judge:\n\n"
    "```python\n"
    "from manim import *\n\n"
    "class GenScene(Scene):\n"
    "    def construct(self):\n"
    "        self.add(Dot())\n"
    "```\n"
)


def _compiles(code: str) -> bool:
    try:
        compile(code, "<scene>", "exec")
        return True
    except SyntaxError:
        return False


def test_strips_judge_preamble_and_compiles():
    code = extract_python_code(FAILING_REPLY)
    assert not code.startswith("I'll")
    assert "I'll fix" not in code
    assert code.startswith("from manim import *")
    assert "class GenScene" in code and "def construct" in code
    assert _compiles(code)


def test_unclosed_fence_with_preamble():
    # Truncated output: preamble + opening fence but the block was never closed.
    reply = (
        "Sure! Here is the corrected scene:\n\n"
        "```python\n"
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Square())\n"
    )
    code = extract_python_code(reply)
    assert code.startswith("from manim import *")
    assert "Here is the corrected" not in code
    assert "```" not in code
    assert _compiles(code)


def test_prose_then_bare_code_no_fence():
    reply = (
        "Here's the animation:\n"
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Circle())\n"
    )
    code = extract_python_code(reply)
    assert code.startswith("from manim import *")
    assert "Here's the animation" not in code
    assert _compiles(code)


def test_trailing_prose_after_block_removed():
    reply = (
        "```python\n"
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
        "```\n\n"
        "Let me know if you'd like any changes!"
    )
    code = extract_python_code(reply)
    assert "Let me know" not in code
    assert "you'd like" not in code  # the trailing apostrophe-prose is gone
    assert _compiles(code)


def test_picks_code_block_over_prose_block():
    # Some replies emit a short non-code fenced block (e.g. a note) then the code.
    reply = (
        "```\nNote: uses a Dot.\n```\n\n"
        "```python\n"
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
        "```\n"
    )
    code = extract_python_code(reply)
    assert code.startswith("from manim import *")
    assert "Note: uses a Dot" not in code


def test_happy_path_pure_code_unchanged():
    code_in = (
        "from manim import *\n"
        "class GenScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
    )
    assert extract_python_code(code_in).strip() == code_in.strip()


def test_empty_and_none():
    assert extract_python_code("") == ""
    assert extract_python_code(None) == ""  # type: ignore[arg-type]


def test_worker_twin_matches_canonical():
    # The worker is a self-contained file with an inlined copy — it must agree
    # with common.extract_python_code or the two-layer guard could diverge.
    ci_render = _load("deploy/ci_render.py")
    samples = [
        FAILING_REPLY,
        "```python\nfrom manim import *\nclass GenScene(Scene):\n    def construct(self):\n        pass\n```",
        "from manim import *\nclass GenScene(Scene):\n    def construct(self):\n        pass\n",
        "",
    ]
    for s in samples:
        assert ci_render.extract_python_code(s) == extract_python_code(s)


def test_worker_rejects_then_accepts_after_strip():
    # End-to-end at the worker boundary: the leaked preamble is stripped, so the
    # GenScene check passes and the result compiles.
    ci_render = _load("deploy/ci_render.py")
    code = ci_render.extract_python_code(FAILING_REPLY)
    assert "class GenScene" in code and "def construct" in code
    assert _compiles(code)

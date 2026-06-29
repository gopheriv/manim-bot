"""Template confidence / matching behaviour.

Guards the strength-based match_score: a template should fire only on a
specific phrase or two keyword words — never on a single generic word, which
must fall through to the LLM path.
"""
import pytest

from templates.base import SceneTemplate, TemplateConfig
from templates.registry import get_registry, TemplateRegistry


class _Tmpl(SceneTemplate):
    name = "Cross Product"
    category = "linear_algebra"
    keywords = ["cross product", "vector product", "perpendicular vector"]

    def generate_code(self, config: TemplateConfig) -> str:
        return "from manim import *\nclass GenScene(Scene):\n    def construct(self): pass\n"


class _Osc(SceneTemplate):
    name = "Damped Oscillator"
    category = "physics"
    keywords = ["damped", "harmonic", "oscillator", "phase space", "damping"]

    def generate_code(self, config: TemplateConfig) -> str:
        return "from manim import *\nclass GenScene(Scene):\n    def construct(self): pass\n"


# ── match_score unit behaviour ───────────────────────────────────────────────

def test_specific_phrase_fires():
    t = _Tmpl()
    assert t.match_score("animate the cross product of two vectors") >= 0.5


def test_two_keyword_words_fire():
    t = _Osc()
    assert t.match_score("a damped harmonic oscillator") >= 0.5


def test_single_generic_word_does_not_fire():
    # "perpendicular" alone (a single keyword word) must stay below threshold.
    t = _Tmpl()
    assert t.match_score("draw a perpendicular line") < 0.5


def test_unrelated_prompt_scores_zero():
    assert _Osc().match_score("explain prime numbers and the riemann hypothesis") == 0.0


def test_score_is_bounded():
    t = _Osc()
    s = t.match_score("damped harmonic oscillator phase space damping motion")
    assert 0.0 <= s <= 1.0


def test_no_keywords_scores_zero():
    class _Empty(_Osc):
        keywords = []
    assert _Empty().match_score("anything at all") == 0.0


# ── registry threshold ───────────────────────────────────────────────────────

def test_registry_threshold_is_strict():
    reg = TemplateRegistry()
    reg.register(_Osc())
    # Genuine, specific request → matches.
    m = reg.match("simulate a damped harmonic oscillator with its phase space")
    assert m is not None and m.confidence >= 0.5
    # A single generic keyword ("oscillator") must NOT hijack the prompt.
    assert reg.match("a gentle oscillator hum") is None


def test_real_registry_does_not_match_generic_words():
    reg = get_registry()
    # These contain ONE generic word that used to be a template keyword.
    for generic in ("show the expansion of the universe",
                    "animate the rotation of a cube",
                    "split the cake into equal parts"):
        m = reg.match(generic)
        assert m is None or m.confidence >= 0.5, f"generic prompt hijacked: {generic!r} -> {m}"


def test_real_registry_still_matches_clear_topics():
    reg = get_registry()
    m = reg.match("animate a damped harmonic oscillator with phase space diagram")
    assert m is not None
    assert 0.0 <= m.confidence <= 1.0


def test_every_template_generates_compilable_code():
    """Every registered template must emit syntactically valid GenScene code
    from its default config — a template that matches but emits broken Python
    would fail the render. (Regression: color placeholders were substituted
    unquoted -> `color=#hex`, breaking 48 JSON templates; a class template
    emitted a broken runtime f-string.)"""
    import py_compile
    import tempfile
    import os

    reg = get_registry()
    broken = []
    for t in reg._templates:
        try:
            code = t.generate_code(t.default_config())
            fh = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
            fh.write(code)
            fh.close()
            try:
                py_compile.compile(fh.name, doraise=True)
            finally:
                os.unlink(fh.name)
            assert "class GenScene" in code and "def construct" in code, t.name
        except py_compile.PyCompileError as e:
            broken.append(f"{t.name}: {str(e).splitlines()[-1][:80]}")
    assert not broken, "templates emit broken code:\n" + "\n".join(broken)

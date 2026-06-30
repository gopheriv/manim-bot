"""Character narrator (WP4): the helper instantiates and the injected snippet is valid.

The narrator ships as an injectable code snippet, so two things must hold: the class
actually builds a valid Manim mobject (caught here by instantiation), and the source the
generator pastes into a scene is syntactically valid Python (caught by compile()).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pi_creature import PiCreature, wants_character, format_character_helper


def test_pi_creature_instantiates():
    pc = PiCreature()
    # A VGroup of real submobjects: body, eyes, pupils, mouth.
    assert len(pc.submobjects) >= 4
    assert pc.mode == "plain"


def test_api_is_chainable_and_typed():
    pc = PiCreature(mode="happy")
    assert pc.mode == "happy"
    assert pc.change_mode("thinking") is pc      # returns self for chaining
    assert pc.mode == "thinking"
    assert pc.look_at([1, 1, 0]) is pc           # returns self
    assert pc.blink() is not None                # an animation
    bubble = pc.says("hello there")
    assert len(bubble.submobjects) >= 2          # rounded box + tail + text


def test_change_mode_falls_back_for_unknown():
    pc = PiCreature()
    pc.change_mode("not-a-real-mode")
    assert pc.mode == "plain"


def test_wants_character_phrases():
    assert wants_character("explain derivatives with a guide character")
    assert wants_character("teach this like a teacher please")
    assert not wants_character("animate a fourier series")
    assert not wants_character("")


def test_format_character_helper_emits_compilable_snippet():
    helper = format_character_helper()
    assert "```python" in helper
    assert "class PiCreature" in helper
    # Extract the fenced code and confirm it parses — it must compile when the
    # generator pastes it into a `from manim import *` scene file.
    code = helper.split("```python", 1)[1].rsplit("```", 1)[0]
    compile(code, "<injected-pi-creature>", "exec")

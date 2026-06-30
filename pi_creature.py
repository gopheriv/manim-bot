"""Character narrator — a minimal, dependency-free teaching guide (experimental).

3Blue1Brown's Pi-creature is a ManimGL construct backed by SVG/mode assets that are
not committed to that repo and have no Manim CE equivalent, so it cannot be ported as
code. This module instead builds a *small* friendly character entirely from Manim CE
primitives (no external assets) and ships it the same way the visual-metaphor recipes
ship: as an injectable code snippet.

  * ``PiCreature(VGroup)`` — a blob body, two eyes with pupils, and an arc mouth, with a
    tiny API: ``look_at(point)``, ``change_mode(...)``, ``blink()`` and ``says(text)``.
  * ``format_character_helper()`` returns the class *source* as a fenced code block so the
    code generator embeds it VERBATIM into the rendered scene. The cloud worker therefore
    needs no extra dependency — the generated ``GenScene`` file is self-contained.
  * ``wants_character(prompt)`` detects the opt-in phrases that ask for a guide.

Opt-in and OFF by default (``config.CHARACTER_NARRATOR_ENABLED``): a hand-built character
can read as rough, and forcing it could *lower* quality, so it only activates when the
prompt explicitly asks for a guide/teacher/character and the flag is enabled. Graceful —
when off (or no trigger phrase) nothing is injected and the pipeline behaves as before.
"""
from __future__ import annotations

import inspect

# Explicit imports (not `from manim import *`) keep THIS module lint-clean. The class is
# still authored to run under a star import: ``format_character_helper`` injects only the
# class source (via ``inspect.getsource``) into a scene that already does
# ``from manim import *`` and ``import numpy as np`` — the import line below is never part
# of the emitted snippet.
from manim import (
    PI,
    UP,
    DOWN,
    LEFT,
    RIGHT,
    UR,
    DL,
    BLACK,
    WHITE,
    BLUE_E,
    GREY_D,
    AnimationGroup,
    Arc,
    Circle,
    Dot,
    Line,
    Polygon,
    RoundedRectangle,
    Text,
    VGroup,
    there_and_back,
)
import numpy as np


class PiCreature(VGroup):
    """A minimal friendly guide built only from Manim CE primitives (no assets).

    Construct one and place it in a corner; then have it ``look_at`` the active object,
    ``blink()`` occasionally, ``change_mode(...)`` to react, and pop a ``says(text)``
    bubble to narrate. Everything is deterministic — same code, same character.
    """

    MODES = ("plain", "thinking", "happy", "confused")

    def __init__(self, color=BLUE_E, height=2.0, mode="plain", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode if mode in self.MODES else "plain"

        # Body: a circle stretched slightly tall reads as a friendly blob.
        body = Circle(radius=0.5).set_stroke(width=0).set_fill(color, opacity=1.0)
        body.stretch(1.2, dim=1)

        # Eyes: white discs with dark pupils, sitting in the upper third.
        eye = Circle(radius=0.18).set_fill(WHITE, opacity=1.0).set_stroke(GREY_D, width=1)
        eye_l = eye.copy().move_to(body.get_center() + UP * 0.28 + LEFT * 0.17)
        eye_r = eye.copy().move_to(body.get_center() + UP * 0.28 + RIGHT * 0.17)
        eyes = VGroup(eye_l, eye_r)
        pupils = VGroup(
            Dot(radius=0.07, color=BLACK).move_to(eye_l.get_center()),
            Dot(radius=0.07, color=BLACK).move_to(eye_r.get_center()),
        )

        self.body, self.eyes, self.pupils = body, eyes, pupils
        self.mouth = self._make_mouth(self.mode)
        self.add(body, eyes, pupils, self.mouth)
        self._gaze_for_mode(self.mode)
        self.scale_to_fit_height(height)

    # ── construction helpers ──────────────────────────────────────────────────
    def _make_mouth(self, mode):
        """Build a mouth sized to the CURRENT body, so it stays right after scaling."""
        w = self.body.width
        if mode == "happy":
            mouth = Arc(radius=0.45 * w, start_angle=PI, angle=PI)          # broad smile
        elif mode == "confused":
            mouth = Arc(radius=0.30 * w, start_angle=0, angle=PI)           # slight frown
        elif mode == "thinking":
            mouth = Line(LEFT * 0.18 * w, RIGHT * 0.18 * w)                 # neutral
        else:  # plain
            mouth = Arc(radius=0.55 * w, start_angle=PI + PI / 6, angle=PI - PI / 3)
        mouth.set_stroke(WHITE, width=4)
        mouth.move_to(self.body.get_center() + DOWN * 0.18 * self.body.height)
        return mouth

    def _gaze_for_mode(self, mode):
        """Aim the pupils to match the mood (up for thinking, aside for confused)."""
        if mode == "thinking":
            self.look_at(self.body.get_top() + UP * 2)
        elif mode == "confused":
            self.look_at(self.body.get_right() + RIGHT * 2 + UP)
        else:
            for e, p in zip(self.eyes, self.pupils):
                p.move_to(e.get_center())
        return self

    # ── public API ────────────────────────────────────────────────────────────
    def look_at(self, point):
        """Shift each pupil toward ``point``, kept inside its eye. Returns self."""
        point = np.array(point, dtype=float)
        for e, p in zip(self.eyes, self.pupils):
            center = e.get_center()
            direction = point - center
            norm = float(np.linalg.norm(direction))
            if norm > 1e-6:
                direction = direction / norm
            p.move_to(center + direction * (e.width / 2) * 0.45)
        return self

    def change_mode(self, mode):
        """Swap the mouth (and gaze) to one of MODES. Returns self for chaining."""
        if mode not in self.MODES:
            mode = "plain"
        self.mouth.become(self._make_mouth(mode))
        self._gaze_for_mode(mode)
        self.mode = mode
        return self

    def blink(self, run_time=0.3):
        """Return an animation that squashes the eyes shut and back (a blink)."""
        parts = [*self.eyes, *self.pupils]
        return AnimationGroup(
            *[m.animate(rate_func=there_and_back).stretch(0.15, dim=1) for m in parts],
            run_time=run_time,
        )

    def says(self, text, font_size=28, direction=UR, buff=0.15):
        """Return a speech bubble (rounded box + tail + text) placed by the creature."""
        label = Text(str(text), font_size=font_size, color=BLACK)
        box = RoundedRectangle(
            corner_radius=0.2,
            width=label.width + 0.6,
            height=label.height + 0.5,
        ).set_fill(WHITE, opacity=1.0).set_stroke(GREY_D, width=2)
        label.move_to(box.get_center())
        anchor = box.get_corner(DL)
        tail = Polygon(
            anchor + RIGHT * 0.3,
            anchor + RIGHT * 0.7,
            anchor + DOWN * 0.4 + RIGHT * 0.25,
        ).set_fill(WHITE, opacity=1.0).set_stroke(GREY_D, width=2)
        bubble = VGroup(box, tail, label)
        bubble.next_to(self, direction, buff=buff)
        return bubble


# ── Prompt integration (mirrors visual_metaphors.format_* — an injectable snippet) ──

_CHARACTER_PHRASES = (
    "with a character",
    "with a guide",
    "guide character",
    "like a teacher",
    "as a teacher",
    "teacher explains",
    "explain like",
    "with a narrator",
    "narrator",
    "mascot",
    "pi creature",
    "picreature",
)


def wants_character(prompt: str) -> bool:
    """True when the prompt explicitly asks for a guide/teacher/character narrator."""
    if not prompt:
        return False
    p = prompt.lower()
    return any(phrase in p for phrase in _CHARACTER_PHRASES)


def format_character_helper() -> str:
    """Return the PiCreature class source as a fenced block for the code-gen prompt.

    The generator pastes this VERBATIM into the scene, so the rendered file stays
    self-contained (no import of this module on the cloud worker). The source is read
    from the live class via ``inspect`` so the prompt can never drift from the code.
    """
    src = inspect.getsource(PiCreature)
    return (
        "## CHARACTER NARRATOR (opt-in) — embed this helper VERBATIM, then use it\n"
        "Paste the following class into the generated script EXACTLY as written (it depends "
        "only on `from manim import *` and `import numpy as np`, which you already import). "
        "Use ONE PiCreature as a friendly guide: park it in a corner, `look_at` the active "
        "object, `blink()` now and then, `change_mode('thinking'|'happy'|'confused'|'plain')` "
        "to react, and reveal a `says(text)` bubble to narrate each key beat. The guide "
        "SUPPORTS the math — keep it small and in a corner, never covering the main figure.\n"
        f"```python\n{src}\n```"
    )


__all__ = ["PiCreature", "wants_character", "format_character_helper"]

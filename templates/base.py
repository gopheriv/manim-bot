"""Base template class for speculative scene generation.

Each template is a proven, pre-tested Manim scene that accepts a small
JSON config (equations, colors, labels) instead of generating 200+ lines
of code from scratch. This reduces LLM code gen time from 30-90s to 5-15s.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TemplateConfig:
    """Parameters filled by LLM to customize a template scene."""
    title: str = ""
    equation: str = ""
    description: str = ""
    damping: float = 0.15
    frequency: float = 1.0
    amplitude: float = 1.0
    colors: list[str] = field(default_factory=lambda: ["#06B6D4", "#10B981", "#8B5CF6"])
    duration: int = 15
    extra_params: dict[str, float] = field(default_factory=dict)


@dataclass
class TemplateMatch:
    """Result of matching a user prompt against a template."""
    template: "SceneTemplate"
    confidence: float  # 0.0-1.0
    config: TemplateConfig


class SceneTemplate(ABC):
    """Base class for all pre-built Manim scene templates."""

    # Must be set by subclasses
    name: str = ""
    keywords: list[str] = []  # keywords for fuzzy matching
    category: str = ""  # oscillator, fourier, calculus, etc.

    @abstractmethod
    def generate_code(self, config: TemplateConfig) -> str:
        """Generate complete Manim scene code from a filled config.

        This is deterministic — no LLM calls needed. Returns valid Python
        that can be written to a .py file and rendered immediately.
        """

    def match_score(self, prompt: str) -> float:
        """Score how well this template matches the user prompt (0.0-1.0).

        Strength-based (not fraction-based) so the score does not depend on how
        many keywords a template happens to list. A template only earns a
        confident score from a SPECIFIC, unambiguous signal:

          - a multi-token keyword phrase present verbatim (e.g. "cross product",
            "integration by parts") → strong, +0.6
          - a single keyword word matched on a word boundary → +0.3
          - a stem/inflection match (e.g. "vectors"~"vector") → +0.15

        With the registry threshold (0.5) this means a template fires only on a
        specific phrase OR two keyword words — never on one generic word like
        "parts", "rotation" or "expansion" (those route to the LLM path, which
        on the cinematic/cloud tier produces far better output than a static
        template). Subclasses may override for smarter matching.
        """
        if not self.keywords:
            return 0.0

        prompt_lower = prompt.lower()
        words = [w for w in re.findall(r"[a-z0-9]+", prompt_lower) if len(w) >= 3]
        wordset = set(words)

        score = 0.0
        for kw in self.keywords:
            k = (kw or "").lower().strip()
            if not k:
                continue
            if " " in k or "-" in k:
                # Specific multi-token phrase — verbatim presence is a strong signal.
                if k in prompt_lower:
                    score += 0.6
            elif k in wordset:
                # Single keyword word on a word boundary (no loose substrings).
                score += 0.3
            elif any(len(w) >= 4 and (w.startswith(k) or k.startswith(w)) for w in words):
                # Stem / inflection (plurals, verb forms).
                score += 0.15

        return min(score, 1.0)

    def default_config(self) -> TemplateConfig:
        """Return sensible defaults — LLM only needs to override what matters."""
        return TemplateConfig()


def _common_manim_header(class_name: str = "GenScene", bg_color: str = "#0A0A0F") -> str:
    """Return the standard Manim scene header used by all templates.

    bg_color defaults to the dark template background, but callers (and the bot's
    template branch) substitute the active theme's background for style unity.
    """
    return f"""from manim import *
import numpy as np
import math


class {class_name}(Scene):
    def construct(self):
        self.camera.background_color = "{bg_color}"
"""


def _indent(code: str, spaces: int = 8) -> str:
    """Indent all lines for nesting inside construct()."""
    prefix = " " * spaces
    return "\n".join(prefix + line if line.strip() else line for line in code.split("\n"))


def _star_field(count: int = 20, spread: float = 6.0) -> str:
    """Generate a background star/particle field — shared helper.

    Static and cheap: `Dot` takes `fill_opacity` (not `opacity`) and we do NOT
    attach a per-dot updater (that would be {count} updaters — far over budget
    and the `sin(dt*…)` form barely moved anyway).
    """
    return f"""
# Background particle field (static — cheap, no per-dot updaters)
stars = VGroup()
for i in range({count}):
    angle = (i / {count}) * TAU
    r = np.random.uniform(1, {spread})
    star = Dot(
        r * np.array([math.cos(angle), math.sin(angle), 0]),
        radius=0.03,
        color=WHITE,
        fill_opacity=0.3,
    )
    stars.add(star)
self.play(FadeIn(stars, run_time=2), rate_func=smooth)
"""


def _glow_layer(obj_name: str, color: str, width: int = 12, opacity: float = 0.15) -> str:
    """Add a glow copy behind a Manim object.

    Returns plain Python code (NOT inside an f-string), so obj_name is
    interpolated once here and appears as a literal identifier in the output.
    """
    glow_name = f"{obj_name}_glow"
    return (
        f"\n{glow_name} = {obj_name}.copy()"
        f".set_stroke(width={width}, opacity={opacity})"
        f".set_fill(opacity=0)\n"
        f"self.add({glow_name})\n"
    )

"""Pre-built Manim scene templates for speculative code generation.

Instead of generating 200+ lines of Manim code from scratch (30-90s),
the LLM fills a small JSON config into a proven template (5-15s).
"""

from templates.registry import get_registry, reset_registry
from templates.base import SceneTemplate, TemplateConfig, TemplateMatch

__all__ = [
    "get_registry",
    "reset_registry",
    "SceneTemplate",
    "TemplateConfig",
    "TemplateMatch",
]
